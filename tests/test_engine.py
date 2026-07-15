"""Tests unitaires du moteur de règles fiscales (Lot 2).

Lancer avec : python -m unittest tests.test_engine -v
depuis la racine du projet (le dossier contenant fiscal_engine/ et tests/).
"""

import unittest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import db, resolver, calculator, orchestrator, aggregator, formula, units, parameters
from fiscal_engine.exceptions import (
    AucuneRegleApplicable,
    ReglesChevauchantes,
    FormuleInvalide,
    DonneesBaremeManquantes,
    UniteIncompatible,
    AucuneValeurParametreApplicable,
)

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"


def _creer_bdd_test() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    with open(CHEMIN_SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


def _inserer_donnees_de_base(conn: sqlite3.Connection) -> dict:
    """Insère un jeu de données minimal représentatif pour les tests :
    - Pays FR
    - Typologies TVA et Impôt sur le revenu
    - Type de dépense Alimentation
    - Prélèvement "TVA taux normal" avec deux règles successives (changement de taux simulé)
    - Prélèvement "Impôt sur le revenu" avec un barème progressif à 2 tranches
    - Catégorie produit "Épicerie salée" liée à la TVA
    Retourne un dict d'identifiants utiles aux tests.
    """
    conn.execute("INSERT INTO pays (code, nom) VALUES ('FR', 'France')")

    conn.execute(
        "INSERT INTO typologie_prelevement (code, libelle_fr) VALUES ('TVA', 'Taxe sur la valeur ajoutée')"
    )
    id_typo_tva = conn.execute(
        "SELECT id FROM typologie_prelevement WHERE code = 'TVA'"
    ).fetchone()["id"]

    conn.execute(
        "INSERT INTO typologie_prelevement (code, libelle_fr) VALUES ('IMPOT_REVENU', 'Impôt sur le revenu')"
    )
    id_typo_ir = conn.execute(
        "SELECT id FROM typologie_prelevement WHERE code = 'IMPOT_REVENU'"
    ).fetchone()["id"]

    conn.execute(
        "INSERT INTO type_depense (code, libelle_fr) VALUES ('ALIMENTATION', 'Alimentation')"
    )
    id_type_dep_alim = conn.execute(
        "SELECT id FROM type_depense WHERE code = 'ALIMENTATION'"
    ).fetchone()["id"]

    conn.execute(
        """INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, reference_legale)
           VALUES ('FR', ?, 'TVA_NORMAL', 'TVA taux normal', 'Art. 278 CGI')""",
        (id_typo_tva,),
    )
    id_prelevement_tva = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'TVA_NORMAL'"
    ).fetchone()["id"]

    # Deux règles successives pour tester le versioning temporel :
    # 19.6% jusqu'à fin 2013 (fictif pour le test), 20% ensuite.
    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
           VALUES (?, '2000-01-01', '2013-12-31', 'taux_fixe', 0.196, 'ttc_inclus', 'Test - ancien taux')""",
        (id_prelevement_tva,),
    )
    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
           VALUES (?, '2014-01-01', NULL, 'taux_fixe', 0.20, 'ttc_inclus', 'Test - taux actuel')""",
        (id_prelevement_tva,),
    )

    conn.execute(
        """INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, reference_legale)
           VALUES ('FR', ?, 'IR_BAREME', 'Impôt sur le revenu (barème)', 'Art. 197 CGI')""",
        (id_typo_ir,),
    )
    id_prelevement_ir = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'IR_BAREME'"
    ).fetchone()["id"]

    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, source_reference)
           VALUES (?, '2026-01-01', NULL, 'bareme_progressif', 'Test - barème simplifié 2 tranches')""",
        (id_prelevement_ir,),
    )
    id_regle_ir = conn.execute(
        "SELECT id FROM regle_prelevement WHERE prelevement_id = ?", (id_prelevement_ir,)
    ).fetchone()["id"]
    # Tranche 1 : 0 à 10000 -> 0% ; Tranche 2 : au-delà de 10000 -> 11%
    conn.execute(
        "INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux) VALUES (?, 0, 10000, 0.0)",
        (id_regle_ir,),
    )
    conn.execute(
        "INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux) VALUES (?, 10000, NULL, 0.11)",
        (id_regle_ir,),
    )

    # Prélèvement de test en mode 'base_directe' (type cotisation sociale sur
    # salaire brut : le taux s'applique tel quel, pas d'extraction TTC).
    conn.execute(
        """INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, reference_legale)
           VALUES ('FR', ?, 'COTIS_TEST', 'Cotisation de test', 'Test - base directe')""",
        (id_typo_ir,),  # typologie réutilisée par simplicité, sans incidence sur le test
    )
    id_prelevement_cotis = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'COTIS_TEST'"
    ).fetchone()["id"]
    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
           VALUES (?, '2026-01-01', NULL, 'taux_fixe', 0.10, 'base_directe', 'Test - cotisation 10%')""",
        (id_prelevement_cotis,),
    )

    # Prélèvement de test en mode 'montant_par_unite' (type TICPE : montant
    # fixe par litre, pas un pourcentage d'un montant).
    conn.execute(
        """INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, reference_legale)
           VALUES ('FR', ?, 'TICPE_TEST', 'TICPE de test', 'Test - montant par unite')""",
        (id_typo_ir,),  # typologie réutilisée par simplicité, sans incidence sur le test
    )
    id_prelevement_ticpe = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'TICPE_TEST'"
    ).fetchone()["id"]
    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, montant_unitaire, unite, source_reference)
           VALUES (?, '2026-01-01', NULL, 'montant_par_unite', 0.6829, 'L', 'Test - 0.6829 EUR/L')""",
        (id_prelevement_ticpe,),
    )

    # Paramètre de référence versionné (type PMSS), utilisé pour tester le
    # plafonnement via formule.
    conn.execute(
        "INSERT INTO parametre_reference (pays_code, code, libelle_fr) VALUES ('FR', 'PMSS_TEST', 'PMSS de test')"
    )
    id_parametre_pmss = conn.execute(
        "SELECT id FROM parametre_reference WHERE code = 'PMSS_TEST'"
    ).fetchone()["id"]
    conn.execute(
        """INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
           VALUES (?, '2026-01-01', NULL, 4000.0, 'Test - PMSS fictif 4000')""",
        (id_parametre_pmss,),
    )

    # Prélèvement de test plafonné via formule : min(base, PMSS_TEST) * 0.069
    conn.execute(
        """INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, reference_legale)
           VALUES ('FR', ?, 'COTIS_PLAFONNEE_TEST', 'Cotisation plafonnee de test', 'Test - plafonnement')""",
        (id_typo_ir,),
    )
    id_prelevement_plafonnee = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'COTIS_PLAFONNEE_TEST'"
    ).fetchone()["id"]
    conn.execute(
        """INSERT INTO regle_prelevement
           (prelevement_id, date_debut, date_fin, type_regle, formule, source_reference)
           VALUES (?, '2026-01-01', NULL, 'formule', 'min(base, PMSS_TEST) * 0.069', 'Test - formule plafonnee')""",
        (id_prelevement_plafonnee,),
    )

    conn.execute(
        """INSERT INTO categorie_produit (code, libelle_fr, type_depense_id)
           VALUES ('EPICERIE_SALEE', 'Épicerie salée', ?)""",
        (id_type_dep_alim,),
    )
    id_categorie = conn.execute(
        "SELECT id FROM categorie_produit WHERE code = 'EPICERIE_SALEE'"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id) VALUES (?, ?)",
        (id_categorie, id_prelevement_tva),
    )

    conn.commit()
    return {
        "id_prelevement_tva": id_prelevement_tva,
        "id_prelevement_ir": id_prelevement_ir,
        "id_prelevement_cotis": id_prelevement_cotis,
        "id_prelevement_ticpe": id_prelevement_ticpe,
        "id_prelevement_plafonnee": id_prelevement_plafonnee,
        "id_categorie": id_categorie,
    }


class TestResolver(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

    def test_resout_le_bon_taux_selon_la_date_ancienne(self):
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_tva"], "2010-06-15")
        self.assertAlmostEqual(regle["taux"], 0.196)

    def test_resout_le_bon_taux_selon_la_date_recente(self):
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_tva"], "2026-06-15")
        self.assertAlmostEqual(regle["taux"], 0.20)

    def test_leve_exception_si_aucune_regle(self):
        with self.assertRaises(AucuneRegleApplicable):
            resolver.resoudre_regle(self.conn, self.ids["id_prelevement_tva"], "1990-01-01")

    def test_detecte_chevauchement(self):
        # On insère volontairement une règle qui chevauche la période 2014-...
        self.conn.execute(
            """INSERT INTO regle_prelevement
               (prelevement_id, date_debut, date_fin, type_regle, taux, source_reference)
               VALUES (?, '2015-01-01', '2016-01-01', 'taux_fixe', 0.21, 'Test chevauchement')""",
            (self.ids["id_prelevement_tva"],),
        )
        self.conn.commit()
        with self.assertRaises(ReglesChevauchantes):
            resolver.resoudre_regle(self.conn, self.ids["id_prelevement_tva"], "2015-06-01")

        anomalies = resolver.verifier_absence_chevauchement(self.conn, self.ids["id_prelevement_tva"])
        self.assertTrue(len(anomalies) >= 1)


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

    def test_calcul_taux_fixe_ttc_inclus(self):
        # TVA : la base est un montant TTC (10€), il faut EXTRAIRE la TVA incluse,
        # pas l'ajouter par-dessus. 10 / 1.20 = 8.3333 (HT) ; TVA incluse = 1.6667
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_tva"], "2026-01-01")
        resultat = calculator.calculer_montant(self.conn, regle, montant=10.0)
        self.assertAlmostEqual(resultat["montant"], 1.6666666667, places=6)
        self.assertAlmostEqual(resultat["base_calcul"], 8.3333333333, places=6)
        self.assertAlmostEqual(resultat["taux_applique"], 0.20)

    def test_calcul_taux_fixe_base_directe(self):
        # Cotisation sur salaire brut : le taux s'applique tel quel sur la base.
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_cotis"], "2026-01-01")
        resultat = calculator.calculer_montant(self.conn, regle, montant=2000.0)
        self.assertAlmostEqual(resultat["montant"], 200.0)
        self.assertAlmostEqual(resultat["base_calcul"], 2000.0)
        self.assertAlmostEqual(resultat["taux_applique"], 0.10)

    def test_calcul_bareme_progressif(self):
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_ir"], "2026-03-01")
        # Base de 15000 : 10000 premiers à 0%, 5000 restants à 11% => 550
        resultat = calculator.calculer_montant(self.conn, regle, montant=15000.0)
        self.assertAlmostEqual(resultat["montant"], 550.0)

    def test_bareme_sans_tranches_leve_exception(self):
        # On clôture la règle IR existante avant d'en ajouter une nouvelle,
        # pour ne pas déclencher une détection de chevauchement (testée par
        # ailleurs dans TestResolver.test_detecte_chevauchement).
        self.conn.execute(
            "UPDATE regle_prelevement SET date_fin = '2026-12-31' WHERE prelevement_id = ?",
            (self.ids["id_prelevement_ir"],),
        )
        # Règle bareme_progressif sans aucune tranche associée
        self.conn.execute(
            """INSERT INTO regle_prelevement
               (prelevement_id, date_debut, date_fin, type_regle, source_reference)
               VALUES (?, '2027-01-01', NULL, 'bareme_progressif', 'Test sans tranches')""",
            (self.ids["id_prelevement_ir"],),
        )
        self.conn.commit()
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_ir"], "2027-06-01")
        with self.assertRaises(DonneesBaremeManquantes):
            calculator.calculer_montant(self.conn, regle, montant=15000.0)


class TestFormula(unittest.TestCase):
    def test_formule_simple(self):
        resultat = formula.evaluer_formule("base * 0.05", {"base": 200.0})
        self.assertAlmostEqual(resultat, 10.0)

    def test_formule_avec_plafond(self):
        resultat = formula.evaluer_formule("min(base * 0.03, 50)", {"base": 5000.0})
        self.assertAlmostEqual(resultat, 50.0)  # 3% de 5000 = 150, plafonné à 50

    def test_formule_avec_abattement(self):
        resultat = formula.evaluer_formule("max(base - 1000, 0) * 0.05", {"base": 800.0})
        self.assertAlmostEqual(resultat, 0.0)  # en dessous de l'abattement

    def test_formule_refuse_code_arbitraire(self):
        with self.assertRaises(FormuleInvalide):
            formula.evaluer_formule("__import__('os').system('echo hack')", {"base": 1.0})

    def test_formule_refuse_variable_inconnue(self):
        with self.assertRaises(FormuleInvalide):
            formula.evaluer_formule("base * taux_secret", {"base": 1.0})


class TestMontantParUnite(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

    def test_calcul_montant_par_unite_meme_unite(self):
        # 40 litres à 0.6829 EUR/L => 27.316 EUR
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_ticpe"], "2026-01-01")
        resultat = calculator.calculer_montant(self.conn, regle, montant=60.0, quantite=40.0, unite_quantite="L")
        self.assertAlmostEqual(resultat["montant"], 27.316, places=3)
        self.assertAlmostEqual(resultat["base_calcul"], 40.0)
        self.assertAlmostEqual(resultat["taux_applique"], 0.6829)

    def test_calcul_montant_par_unite_avec_conversion(self):
        # La ligne est saisie en centilitres (4000 cl = 40 L) : le moteur doit convertir.
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_ticpe"], "2026-01-01")
        resultat = calculator.calculer_montant(self.conn, regle, montant=60.0, quantite=4000.0, unite_quantite="cl")
        self.assertAlmostEqual(resultat["montant"], 27.316, places=3)
        self.assertAlmostEqual(resultat["base_calcul"], 40.0)  # converti en litres

    def test_calcul_montant_par_unite_dimension_incompatible(self):
        # La règle attend des litres (volume), la ligne fournit des kg (masse) : incompatible.
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_ticpe"], "2026-01-01")
        with self.assertRaises(UniteIncompatible):
            calculator.calculer_montant(self.conn, regle, montant=60.0, quantite=40.0, unite_quantite="kg")

    def test_conversion_unite_inconnue(self):
        with self.assertRaises(UniteIncompatible):
            units.convertir_quantite(10.0, "gallon", "L")

    def test_conversion_meme_dimension(self):
        self.assertAlmostEqual(units.convertir_quantite(1.5, "kg", "g"), 1500.0)
        self.assertAlmostEqual(units.convertir_quantite(250, "ml", "L"), 0.25)


class TestParametresEtPlafonnement(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

    def test_resoudre_parametre(self):
        valeur = parameters.resoudre_parametre(self.conn, "PMSS_TEST", "FR", "2026-06-01")
        self.assertAlmostEqual(valeur, 4000.0)

    def test_resoudre_parametre_inexistant(self):
        with self.assertRaises(AucuneValeurParametreApplicable):
            parameters.resoudre_parametre(self.conn, "PARAMETRE_INCONNU", "FR", "2026-06-01")

    def test_charger_parametres_disponibles(self):
        parametres = parameters.charger_parametres_disponibles(self.conn, "FR", "2026-06-01")
        self.assertIn("PMSS_TEST", parametres)
        self.assertAlmostEqual(parametres["PMSS_TEST"], 4000.0)

    def test_formule_sous_le_plafond(self):
        # base = 3000, plafond = 4000 -> pas de plafonnement, calcul normal
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_plafonnee"], "2026-06-01")
        resultat = calculator.calculer_montant(
            self.conn, regle, montant=3000.0, date_reference="2026-06-01", pays_code="FR"
        )
        self.assertAlmostEqual(resultat["montant"], 3000.0 * 0.069)

    def test_formule_au_dessus_du_plafond(self):
        # base = 5000, plafond = 4000 -> le calcul est plafonné à 4000
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_plafonnee"], "2026-06-01")
        resultat = calculator.calculer_montant(
            self.conn, regle, montant=5000.0, date_reference="2026-06-01", pays_code="FR"
        )
        self.assertAlmostEqual(resultat["montant"], 4000.0 * 0.069)  # PAS 5000 * 0.069

    def test_formule_sans_date_reference_leve_variable_inconnue(self):
        # Sans date_reference, le paramètre PMSS_TEST n'est pas chargé : la
        # formule qui le référence doit échouer explicitement (pas de calcul
        # silencieusement faux).
        regle = resolver.resoudre_regle(self.conn, self.ids["id_prelevement_plafonnee"], "2026-06-01")
        with self.assertRaises(FormuleInvalide):
            calculator.calculer_montant(self.conn, regle, montant=5000.0)  # pas de date_reference


class TestOrchestrateurAvecQuantite(unittest.TestCase):
    """Vérifie que l'orchestrateur transmet bien quantite/unite_quantite au
    calculateur pour une ligne d'achat de type 'montant_par_unite' (ex : un
    plein de carburant sur un ticket).
    """

    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

        conn = self.conn
        conn.execute(
            "INSERT INTO type_depense (code, libelle_fr) VALUES ('CARBURANT', 'Carburant')"
        )
        id_type_dep_carburant = conn.execute(
            "SELECT id FROM type_depense WHERE code = 'CARBURANT'"
        ).fetchone()["id"]
        conn.execute(
            """INSERT INTO categorie_produit (code, libelle_fr, type_depense_id)
               VALUES ('ESSENCE_TEST', 'Essence (test)', ?)""",
            (id_type_dep_carburant,),
        )
        id_categorie_essence = conn.execute(
            "SELECT id FROM categorie_produit WHERE code = 'ESSENCE_TEST'"
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id) VALUES (?, ?)",
            (id_categorie_essence, self.ids["id_prelevement_ticpe"]),
        )

        curseur = conn.execute(
            "INSERT INTO document (type_document, date_document) VALUES ('ticket_caisse', '2026-03-01')"
        )
        id_document = curseur.lastrowid
        curseur = conn.execute(
            """INSERT INTO ligne_document
               (document_id, libelle_brut, montant, quantite, unite_quantite, categorie_produit_id)
               VALUES (?, 'Plein essence SP95', 60.0, 40.0, 'L', ?)""",
            (id_document, id_categorie_essence),
        )
        self.id_ligne = curseur.lastrowid
        conn.commit()

    def test_traitement_ligne_avec_quantite(self):
        ids_inseres = orchestrator.traiter_ligne_document(self.conn, self.id_ligne, "2026-03-01")
        self.assertEqual(len(ids_inseres), 1)
        resultat = self.conn.execute(
            "SELECT montant_calcule, base_calcul FROM prelevement_calcule WHERE id = ?", (ids_inseres[0],)
        ).fetchone()
        self.assertAlmostEqual(resultat["montant_calcule"], 27.316, places=3)
        self.assertAlmostEqual(resultat["base_calcul"], 40.0)


class TestOrchestratorEtAggregator(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        self.ids = _inserer_donnees_de_base(self.conn)

        # Un document (ticket de caisse) avec une ligne d'épicerie salée à 10€ TTC
        curseur = self.conn.execute(
            "INSERT INTO document (type_document, date_document) VALUES ('ticket_caisse', '2026-03-01')"
        )
        self.id_document = curseur.lastrowid
        curseur = self.conn.execute(
            """INSERT INTO ligne_document (document_id, libelle_brut, montant, categorie_produit_id)
               VALUES (?, 'Pates 500g', 10.0, ?)""",
            (self.id_document, self.ids["id_categorie"]),
        )
        self.id_ligne = curseur.lastrowid
        self.conn.commit()

    def test_traitement_ligne_achat_calcule_la_tva(self):
        ids_inseres = orchestrator.traiter_ligne_document(self.conn, self.id_ligne, "2026-03-01")
        self.assertEqual(len(ids_inseres), 1)

        resultat = self.conn.execute(
            "SELECT montant_calcule FROM prelevement_calcule WHERE id = ?", (ids_inseres[0],)
        ).fetchone()
        # 10€ TTC à 20% de TVA, assiette 'ttc_inclus' => TVA incluse = 10 - 10/1.20 ≈ 1.6667
        self.assertAlmostEqual(resultat["montant_calcule"], 1.6666666667, places=6)

    def test_aggregation_totaux(self):
        orchestrator.traiter_ligne_document(self.conn, self.id_ligne, "2026-03-01")

        total = aggregator.total_global(self.conn, "2026-01-01", "2026-12-31")
        self.assertAlmostEqual(total, 1.6666666667, places=6)

        ventilation_typo = aggregator.ventilation_par_typologie(self.conn, "2026-01-01", "2026-12-31")
        self.assertEqual(len(ventilation_typo), 1)
        self.assertEqual(ventilation_typo[0]["typologie_code"], "TVA")

        ventilation_dep = aggregator.ventilation_par_type_depense(self.conn, "2026-01-01", "2026-12-31")
        self.assertEqual(ventilation_dep[0]["type_depense_code"], "ALIMENTATION")


if __name__ == "__main__":
    unittest.main()
