"""Tests unitaires de la taxe soda de bout en bout : rattachement
BOISSONS_SUCREES -> TAXE_BOISSONS_SUCRE/EDULCORANT dans
seed_data/fr_categories_produits.sql, et résolution de valeur_seuil depuis
produit_reference dans fiscal_engine/orchestrator.py.

Fiabilisé le 2026-07-29 (PROJECT_STATE.md section 7.5) : avant cette date,
même avec un produit_reference correctement renseigné (teneur_sucre_100g),
rien dans le code n'aurait automatiquement calculé cette taxe — la
catégorie n'était pas rattachée ET l'orchestrateur ne savait pas résoudre
valeur_seuil depuis un produit. Ce fichier verrouille les deux à la fois,
sur les vraies données du seed (tarifs 2026 vérifiés directement sur BOFiP,
voir seed_data/fr_seed_lot3.sql).
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import orchestrator

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED_FISCAL = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"
CHEMIN_SEED_CATEGORIES = Path(__file__).resolve().parent.parent / "seed_data" / "fr_categories_produits.sql"

DATE_REF = "2026-06-01"


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED_FISCAL, CHEMIN_SEED_CATEGORIES):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


def _creer_document_avec_ligne(conn, produit_reference_id=None, montant=100.0, quantite=100.0):
    """Crée un document + une ligne d'achat de boisson sucrée (catégorie
    BOISSONS_SUCREES, 100 L par défaut pour des calculs faciles à vérifier
    à la main : 100L = 1hL).
    """
    id_categorie = conn.execute(
        "SELECT id FROM categorie_produit WHERE code = 'BOISSONS_SUCREES'"
    ).fetchone()["id"]
    curseur = conn.execute(
        "INSERT INTO document (type_document, date_document) VALUES ('ticket_caisse', ?)", (DATE_REF,)
    )
    id_document = curseur.lastrowid
    curseur = conn.execute(
        """INSERT INTO ligne_document
           (document_id, libelle_brut, montant, quantite, unite_quantite,
            categorie_produit_id, produit_reference_id)
           VALUES (?, 'Soda test', ?, ?, 'L', ?, ?)""",
        (id_document, montant, quantite, id_categorie, produit_reference_id),
    )
    conn.commit()
    return curseur.lastrowid


def _creer_produit(conn, teneur_sucre_100g=None, contient_edulcorants=None):
    id_categorie = conn.execute(
        "SELECT id FROM categorie_produit WHERE code = 'BOISSONS_SUCREES'"
    ).fetchone()["id"]
    curseur = conn.execute(
        """INSERT INTO produit_reference
           (code_barre, nom, source, categorie_produit_id, teneur_sucre_100g, contient_edulcorants)
           VALUES (?, 'Soda test', 'manuel', ?, ?, ?)""",
        (f"code-{id(object())}", id_categorie, teneur_sucre_100g, contient_edulcorants),
    )
    conn.commit()
    return curseur.lastrowid


def _montants_par_prelevement(conn, ids_inseres):
    resultat = {}
    for id_pc in ids_inseres:
        ligne = conn.execute(
            """SELECT p.code, pc.montant_calcule
               FROM prelevement_calcule pc JOIN prelevement p ON p.id = pc.prelevement_id
               WHERE pc.id = ?""",
            (id_pc,),
        ).fetchone()
        resultat[ligne["code"]] = ligne["montant_calcule"]
    return resultat


class TestTaxeSucreCalculee(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_produit_avec_teneur_sucre_connue_calcule_la_taxe(self):
        # 100L = 1hL, teneur 6 kg/hL -> tranche "5 a 8" -> 21.38E/hL * 1hL
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=6.0)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertIn("TAXE_BOISSONS_SUCRE", montants)
        self.assertAlmostEqual(montants["TAXE_BOISSONS_SUCRE"], 21.38)
        # La TVA doit toujours etre calculee normalement en parallele
        self.assertIn("TVA_NORMAL", montants)

    def test_tranche_basse_sous_5kg(self):
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=3.0)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertAlmostEqual(montants["TAXE_BOISSONS_SUCRE"], 4.07)

    def test_tranche_haute_au_dela_de_8kg(self):
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=10.0)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertAlmostEqual(montants["TAXE_BOISSONS_SUCRE"], 35.63)


class TestTaxeSucreNonCalculableSansDonnee(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_sans_produit_reference_la_taxe_sucre_est_absente_mais_pas_la_tva(self):
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=None, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertNotIn("TAXE_BOISSONS_SUCRE", montants)
        self.assertIn("TVA_NORMAL", montants)

    def test_produit_reference_sans_teneur_sucre_connue(self):
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=None)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertNotIn("TAXE_BOISSONS_SUCRE", montants)
        self.assertIn("TVA_NORMAL", montants)

    def test_aucune_exception_levee_ligne_traitee_normalement(self):
        # Ne doit JAMAIS lever d'exception, meme sans aucune donnee produit.
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=None, quantite=100.0)
        try:
            orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        except Exception as exc:  # pragma: no cover - le test echoue si ca arrive
            self.fail(f"traiter_ligne_document a leve une exception inattendue : {exc}")


class TestTaxeEdulcorantJamaisCalculeeAutomatiquement(unittest.TestCase):
    """Limite assumee et documentee : OFF ne fournit que la presence d'un
    edulcorant, jamais sa concentration -> jamais de calcul automatique.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_produit_avec_edulcorant_detecte_taxe_jamais_calculee(self):
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=0.0, contient_edulcorants=1)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        ids = orchestrator.traiter_ligne_document(self.conn, id_ligne, DATE_REF)
        montants = _montants_par_prelevement(self.conn, ids)
        self.assertNotIn("TAXE_BOISSONS_EDULCORANT", montants)
        # La taxe sucre (0 kg/hL -> tranche basse) doit quand meme etre calculee
        self.assertIn("TAXE_BOISSONS_SUCRE", montants)
        self.assertAlmostEqual(montants["TAXE_BOISSONS_SUCRE"], 4.07)


class TestDiagnostiquerTaxesNonCalculees(unittest.TestCase):
    """Ajouté le 2026-08-02 (PROJECT_STATE.md section 7.5) : alerte quand
    une taxe soda n'a pas pu être calculée, sans casser le traitement
    principal de la ligne.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_taxe_sucre_calculable_seul_avertissement_est_edulcorant(self):
        # La teneur en sucre est connue -> TAXE_BOISSONS_SUCRE ne genere pas
        # d'avertissement. TAXE_BOISSONS_EDULCORANT en genere TOUJOURS un
        # (jamais calculable, quelles que soient les donnees disponibles).
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=6.0)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        avertissements = orchestrator.diagnostiquer_taxes_non_calculees(self.conn, id_ligne, DATE_REF)
        self.assertEqual(len(avertissements), 1)
        self.assertIn("édulcorant", avertissements[0].lower())

    def test_sans_produit_reference_avertissement_pour_taxe_sucre(self):
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=None, quantite=100.0)
        avertissements = orchestrator.diagnostiquer_taxes_non_calculees(self.conn, id_ligne, DATE_REF)
        self.assertTrue(any("TAXE_BOISSONS_SUCRE" in a or "sucre" in a.lower() for a in avertissements))

    def test_produit_sans_teneur_sucre_avertissement(self):
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=None)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        avertissements = orchestrator.diagnostiquer_taxes_non_calculees(self.conn, id_ligne, DATE_REF)
        # 2 avertissements : sucre (teneur inconnue) + edulcorant (toujours,
        # quelles que soient les donnees disponibles)
        self.assertEqual(len(avertissements), 2)

    def test_edulcorant_toujours_dans_les_avertissements(self):
        # Meme avec toutes les donnees connues (teneur sucre presente), la
        # taxe edulcorant genere TOUJOURS un avertissement (jamais calculable)
        id_produit = _creer_produit(self.conn, teneur_sucre_100g=6.0, contient_edulcorants=1)
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=id_produit, quantite=100.0)
        avertissements = orchestrator.diagnostiquer_taxes_non_calculees(self.conn, id_ligne, DATE_REF)
        self.assertEqual(len(avertissements), 1)
        self.assertIn("édulcorant", avertissements[0].lower())

    def test_ligne_sans_categorie_produit_aucun_avertissement(self):
        curseur = self.conn.execute(
            "INSERT INTO document (type_document, date_document) VALUES ('ticket_caisse', ?)", (DATE_REF,)
        )
        id_document = curseur.lastrowid
        curseur = self.conn.execute(
            "INSERT INTO ligne_document (document_id, libelle_brut, montant) VALUES (?, 'Ligne TOTAL', 0)",
            (id_document,),
        )
        self.conn.commit()
        avertissements = orchestrator.diagnostiquer_taxes_non_calculees(self.conn, curseur.lastrowid, DATE_REF)
        self.assertEqual(avertissements, [])

    def test_ne_leve_jamais_dexception(self):
        id_ligne = _creer_document_avec_ligne(self.conn, produit_reference_id=None, quantite=100.0)
        try:
            orchestrator.diagnostiquer_taxes_non_calculees(self.conn, id_ligne, DATE_REF)
        except Exception as exc:  # pragma: no cover
            self.fail(f"diagnostiquer_taxes_non_calculees a levé une exception inattendue : {exc}")


if __name__ == "__main__":
    unittest.main()
