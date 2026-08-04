"""Tests unitaires des pipelines d'import Open Beauty Facts (OBF) et Open
Pet Food Facts (OPFF), ajoutés le 2026-08-02 (PROJECT_STATE.md section
7.10), sur le modèle de tests/test_off_import.py.

Utilise des échantillons SYNTHÉTIQUES (tests/fixtures/obf_echantillon_synthetique.parquet
et tests/fixtures/opff_echantillon_synthetique.csv.gz) reproduisant le
schéma supposé des vrais fichiers (voir imports/off_import.py pour la
limite documentée : cette hypothèse de schéma n'a pas pu être vérifiée sur
un vrai fichier, accès réseau restreint dans cet environnement).
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from imports import off_import

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED_FISCAL = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"
CHEMIN_SEED_CATEGORIES = Path(__file__).resolve().parent.parent / "seed_data" / "fr_categories_produits.sql"
CHEMIN_FIXTURE_BEAUTY = Path(__file__).resolve().parent / "fixtures" / "obf_echantillon_synthetique.parquet"
CHEMIN_FIXTURE_PETFOOD = Path(__file__).resolve().parent / "fixtures" / "opff_echantillon_synthetique.csv.gz"


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED_FISCAL, CHEMIN_SEED_CATEGORIES):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestImportBeauty(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()
        self.tmp = tempfile.TemporaryDirectory()
        self.chemin_filtre = str(Path(self.tmp.name) / "beauty_filtre.parquet")
        off_import.filtrer_produits_beauty_france(str(CHEMIN_FIXTURE_BEAUTY), self.chemin_filtre)

    def tearDown(self):
        self.tmp.cleanup()

    def test_filtrage_exclut_les_produits_hors_france(self):
        # 4 produits dans la fixture, 1 hors France -> 3 retenus
        resultat = off_import.filtrer_produits_beauty_france(str(CHEMIN_FIXTURE_BEAUTY), self.chemin_filtre)
        self.assertEqual(resultat, 3)

    def test_produit_avec_categorie_reconnue(self):
        resume = off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        self.assertEqual(resume["total"], 3)
        self.assertEqual(resume["avec_categorie"], 2)  # b1 (hair-care) et b2 (perfumes)
        self.assertEqual(resume["sans_categorie"], 1)  # b3 (tag inconnu)

    def test_produit_importe_avec_bonne_categorie(self):
        off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        produit = off_import.resoudre_produit_par_code_barre(self.conn, "barcode-b1")
        self.assertIsNotNone(produit)
        self.assertEqual(produit["source"], "OBF")
        categorie = self.conn.execute(
            "SELECT code FROM categorie_produit WHERE id = ?", (produit["categorie_produit_id"],)
        ).fetchone()
        self.assertEqual(categorie["code"], "PRODUITS_HYGIENE_BEAUTE")

    def test_produit_hors_france_absent(self):
        off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        produit = off_import.resoudre_produit_par_code_barre(self.conn, "barcode-b4")
        self.assertIsNone(produit)

    def test_pas_de_donnee_nutritionnelle_importee(self):
        off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        produit = off_import.resoudre_produit_par_code_barre(self.conn, "barcode-b1")
        self.assertIsNone(produit["teneur_sucre_100g"])
        self.assertIsNone(produit["contient_edulcorants"])

    def test_reimport_met_a_jour_sans_dupliquer(self):
        off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        off_import.importer_beauty_dans_bdd(self.conn, self.chemin_filtre)
        n = self.conn.execute("SELECT COUNT(*) AS n FROM produit_reference WHERE source = 'OBF'").fetchone()["n"]
        self.assertEqual(n, 3)


class TestImportPetfood(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()
        self.tmp = tempfile.TemporaryDirectory()
        self.chemin_filtre = str(Path(self.tmp.name) / "petfood_filtre.parquet")
        off_import.filtrer_produits_petfood_france(str(CHEMIN_FIXTURE_PETFOOD), self.chemin_filtre)

    def tearDown(self):
        self.tmp.cleanup()

    def test_filtrage_exclut_les_produits_hors_france(self):
        resultat = off_import.filtrer_produits_petfood_france(str(CHEMIN_FIXTURE_PETFOOD), self.chemin_filtre)
        self.assertEqual(resultat, 3)

    def test_categories_tags_bien_decoupees_en_liste(self):
        # Verifie que le CSV brut (categories_tags = chaine separee par
        # virgules) a bien ete converti en liste exploitable
        resume = off_import.importer_petfood_dans_bdd(self.conn, self.chemin_filtre)
        self.assertEqual(resume["avec_categorie"], 2)  # p1 (dry-dog-food) et p2 (wet-cat-food)
        self.assertEqual(resume["sans_categorie"], 1)  # p3 (tag inconnu)

    def test_produit_importe_avec_bonne_categorie(self):
        off_import.importer_petfood_dans_bdd(self.conn, self.chemin_filtre)
        produit = off_import.resoudre_produit_par_code_barre(self.conn, "barcode-p1")
        self.assertIsNotNone(produit)
        self.assertEqual(produit["source"], "OPFF")
        categorie = self.conn.execute(
            "SELECT code FROM categorie_produit WHERE id = ?", (produit["categorie_produit_id"],)
        ).fetchone()
        self.assertEqual(categorie["code"], "ALIMENTATION_ANIMAUX")

    def test_produit_hors_france_absent(self):
        off_import.importer_petfood_dans_bdd(self.conn, self.chemin_filtre)
        produit = off_import.resoudre_produit_par_code_barre(self.conn, "barcode-p4")
        self.assertIsNone(produit)


class TestResoudreCategorieProduitMultiSource(unittest.TestCase):
    """Vérifie que _resoudre_categorie_produit respecte bien le mapping
    passé en paramètre (et pas seulement le mapping OFF par défaut)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_mapping_off_par_defaut(self):
        id_cat = off_import._resoudre_categorie_produit(self.conn, ["en:sodas"])
        categorie = self.conn.execute("SELECT code FROM categorie_produit WHERE id = ?", (id_cat,)).fetchone()
        self.assertEqual(categorie["code"], "BOISSONS_SUCREES")

    def test_mapping_obf_explicite(self):
        id_cat = off_import._resoudre_categorie_produit(
            self.conn, ["en:shampoos"], mapping=off_import.MAPPING_CATEGORIES_OBF
        )
        categorie = self.conn.execute("SELECT code FROM categorie_produit WHERE id = ?", (id_cat,)).fetchone()
        self.assertEqual(categorie["code"], "PRODUITS_HYGIENE_BEAUTE")

    def test_tag_off_absent_du_mapping_obf(self):
        # 'en:sodas' n'existe pas dans MAPPING_CATEGORIES_OBF
        id_cat = off_import._resoudre_categorie_produit(
            self.conn, ["en:sodas"], mapping=off_import.MAPPING_CATEGORIES_OBF
        )
        self.assertIsNone(id_cat)


if __name__ == "__main__":
    unittest.main()
