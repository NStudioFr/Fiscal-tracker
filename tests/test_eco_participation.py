"""Tests unitaires de l'éco-participation DEEE (fiscal_engine, via le
mécanisme générique calculator.calculer_montant), contre le vrai barème
officiel Ecologic 2026 (seed_data/fr_seed_lot3.sql), sur le modèle de
tests/test_alcool.py et tests/test_tabac.py.

Ajouté le 2026-08-02 (PROJECT_STATE.md sections 7.8/7.10), suite à la
discussion du 2026-07-29 sur les sous-catégories fines
électroménager/informatique et à la comparaison COICOP vs Ecologic.
Source EXCLUSIVEMENT officielle : barème Ecologic EEE Ménagers 2026,
récupéré en intégralité par lecture directe le 2026-08-02.

Rappel du périmètre (voir commentaire détaillé dans
seed_data/fr_seed_lot3.sql) : 17 équipements représentatifs parmi les
~150 lignes du barème réel, tarif DE BASE uniquement (sans les 6 critères
de modulation possibles), 4 des 8 familles officielles non couvertes du
tout (Sport & mobilité électrique, Jouet/loisirs, Bricolage/jardinage/
domotique, Génie thermique & climatique).
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import resolver, calculator

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


def _eco_part(conn, code_prelevement, valeur_seuil=None, quantite=1.0):
    pid = conn.execute("SELECT id FROM prelevement WHERE code = ?", (code_prelevement,)).fetchone()["id"]
    regle = resolver.resoudre_regle(conn, pid, DATE_REF)
    resultat = calculator.calculer_montant(conn, regle, montant=0.0, quantite=quantite, valeur_seuil=valeur_seuil)
    return resultat["montant"]


class TestEcoPartBrackets(unittest.TestCase):
    """Les 3 équipements à tarif dépendant du poids/de la taille."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_refrigerateur_tranche_basse(self):
        self.assertAlmostEqual(
            _eco_part(self.conn, "ECO_PART_REFRIGERATEUR_CONGELATEUR", valeur_seuil=30), 12.23
        )

    def test_refrigerateur_tranche_moyenne(self):
        self.assertAlmostEqual(
            _eco_part(self.conn, "ECO_PART_REFRIGERATEUR_CONGELATEUR", valeur_seuil=60), 20.20
        )

    def test_refrigerateur_tranche_haute(self):
        self.assertAlmostEqual(
            _eco_part(self.conn, "ECO_PART_REFRIGERATEUR_CONGELATEUR", valeur_seuil=100), 25.17
        )

    def test_refrigerateur_valeur_exacte_de_borne(self):
        # A 40kg pile, la tranche INFERIEURE l'emporte (convention du
        # moteur : bornes inclusives des deux cotes, premiere tranche
        # correspondante dans l'ordre croissant des borne_min — cohérent
        # avec le comportement déjà observé pour les seuils CSG retraite).
        self.assertAlmostEqual(
            _eco_part(self.conn, "ECO_PART_REFRIGERATEUR_CONGELATEUR", valeur_seuil=40), 12.23
        )

    def test_televiseur_petit_ecran(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_TELEVISEUR", valeur_seuil=24), 5.08)

    def test_televiseur_ecran_moyen(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_TELEVISEUR", valeur_seuil=43), 9.26)

    def test_televiseur_grand_ecran(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_TELEVISEUR", valeur_seuil=65), 12.65)

    def test_imprimante_legere(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_IMPRIMANTE", valeur_seuil=3), 0.86)

    def test_imprimante_moyenne(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_IMPRIMANTE", valeur_seuil=7), 1.21)

    def test_imprimante_lourde(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_IMPRIMANTE", valeur_seuil=15), 2.15)


class TestEcoPartTarifsFixes(unittest.TestCase):
    """Les 14 équipements à tarif fixe (indépendant du poids/de la taille)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_lave_linge(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_LAVE_LINGE"), 12.85)

    def test_seche_linge(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_SECHE_LINGE"), 12.85)

    def test_lave_vaisselle(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_LAVE_VAISSELLE"), 12.85)

    def test_cuisiniere(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_CUISINIERE"), 12.20)

    def test_four_micro_ondes(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_FOUR_MICRO_ONDES"), 3.17)

    def test_aspirateur(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_ASPIRATEUR"), 1.45)

    def test_bouilloire(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_BOUILLOIRE"), 0.34)

    def test_cafetiere(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_CAFETIERE"), 0.46)

    def test_fer_a_repasser(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_FER_A_REPASSER"), 0.30)

    def test_soin_personnel(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_SOIN_PERSONNEL"), 0.10)

    def test_smartphone(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_SMARTPHONE"), 2.56)

    def test_ordinateur_portable(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_ORDINATEUR_PORTABLE"), 3.32)

    def test_ordinateur_fixe(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_ORDINATEUR_FIXE"), 2.52)

    def test_tablette(self):
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_TABLETTE"), 0.85)

    def test_quantite_multiple_multiplie_le_montant(self):
        # 3 bouilloires achetees sur la meme ligne
        self.assertAlmostEqual(_eco_part(self.conn, "ECO_PART_BOUILLOIRE", quantite=3.0), 3 * 0.34)


class TestRattachementCategorieProduit(unittest.TestCase):
    """Vérifie le rattachement categorie_produit -> ECO_PART_* (1:1) ET
    que la TVA reste calculable en parallèle (même mécanisme que pour les
    autres catégories du projet)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_17_categories_rattachees_a_leur_eco_part(self):
        rattachements = {
            "ELECTROMENAGER_REFRIGERATEUR_CONGELATEUR": "ECO_PART_REFRIGERATEUR_CONGELATEUR",
            "ELECTROMENAGER_LAVE_LINGE": "ECO_PART_LAVE_LINGE",
            "ELECTROMENAGER_SECHE_LINGE": "ECO_PART_SECHE_LINGE",
            "ELECTROMENAGER_LAVE_VAISSELLE": "ECO_PART_LAVE_VAISSELLE",
            "ELECTROMENAGER_CUISINIERE": "ECO_PART_CUISINIERE",
            "ELECTROMENAGER_FOUR_MICRO_ONDES": "ECO_PART_FOUR_MICRO_ONDES",
            "ELECTROMENAGER_ASPIRATEUR": "ECO_PART_ASPIRATEUR",
            "ELECTROMENAGER_BOUILLOIRE": "ECO_PART_BOUILLOIRE",
            "ELECTROMENAGER_CAFETIERE": "ECO_PART_CAFETIERE",
            "ELECTROMENAGER_FER_A_REPASSER": "ECO_PART_FER_A_REPASSER",
            "ELECTROMENAGER_SOIN_PERSONNEL": "ECO_PART_SOIN_PERSONNEL",
            "EGP_TELEVISEUR": "ECO_PART_TELEVISEUR",
            "INFORMATIQUE_SMARTPHONE": "ECO_PART_SMARTPHONE",
            "INFORMATIQUE_ORDINATEUR_PORTABLE": "ECO_PART_ORDINATEUR_PORTABLE",
            "INFORMATIQUE_ORDINATEUR_FIXE": "ECO_PART_ORDINATEUR_FIXE",
            "INFORMATIQUE_TABLETTE": "ECO_PART_TABLETTE",
            "INFORMATIQUE_IMPRIMANTE": "ECO_PART_IMPRIMANTE",
        }
        self.assertEqual(len(rattachements), 17)
        for code_categorie, code_prelevement_attendu in rattachements.items():
            ligne = self.conn.execute(
                """
                SELECT p.code FROM categorie_prelevement cpr
                JOIN categorie_produit cp ON cp.id = cpr.categorie_produit_id
                JOIN prelevement p ON p.id = cpr.prelevement_id
                WHERE cp.code = ? AND p.code LIKE 'ECO_PART_%'
                """,
                (code_categorie,),
            ).fetchone()
            self.assertIsNotNone(ligne, f"Aucun ECO_PART_* rattaché à {code_categorie}")
            self.assertEqual(ligne["code"], code_prelevement_attendu)

    def test_tva_normale_toujours_rattachee_en_parallele(self):
        for code_categorie in ("ELECTROMENAGER_REFRIGERATEUR_CONGELATEUR", "INFORMATIQUE_SMARTPHONE"):
            ligne = self.conn.execute(
                """
                SELECT p.code FROM categorie_prelevement cpr
                JOIN categorie_produit cp ON cp.id = cpr.categorie_produit_id
                JOIN prelevement p ON p.id = cpr.prelevement_id
                WHERE cp.code = ? AND p.code = 'TVA_NORMAL'
                """,
                (code_categorie,),
            ).fetchone()
            self.assertIsNotNone(ligne, f"TVA_NORMAL non rattachée à {code_categorie}")

    def test_categories_generiques_toujours_presentes_en_filet_de_securite(self):
        # ELECTROMENAGER / INFORMATIQUE_MULTIMEDIA (génériques) doivent
        # continuer d'exister pour tout ce qui n'entre pas dans les 17
        # sous-catégories fines.
        for code in ("ELECTROMENAGER", "INFORMATIQUE_MULTIMEDIA"):
            ligne = self.conn.execute("SELECT id FROM categorie_produit WHERE code = ?", (code,)).fetchone()
            self.assertIsNotNone(ligne)


if __name__ == "__main__":
    unittest.main()
