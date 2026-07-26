"""Tests du pipeline d'import Open Food Facts.

Utilise un échantillon Parquet SYNTHÉTIQUE (tests/fixtures/off_echantillon_
synthetique.parquet), reproduisant fidèlement le schéma réel du dump OFF
(mêmes noms/types de colonnes), plutôt que le vrai dump — inaccessible
depuis cet environnement de développement (voir imports/off_import.py).
Le vrai téléchargement (telecharger_dump_off) n'est donc PAS testé ici,
seulement le filtrage/mapping/import qui en découlent.
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from imports.off_import import (
    filtrer_produits_france,
    importer_dans_bdd,
    resoudre_produit_par_code_barre,
    _resoudre_categorie_produit,
    _detecter_edulcorants,
    MAPPING_CATEGORIES_OFF,
)

CHEMIN_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "off_echantillon_synthetique.parquet"
CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED_FISCAL = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"
CHEMIN_SEED_CATEGORIES = Path(__file__).resolve().parent.parent / "seed_data" / "fr_categories_produits.sql"


def _creer_bdd_test() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED_FISCAL, CHEMIN_SEED_CATEGORIES):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestFiltrageFrance(unittest.TestCase):
    def test_filtre_uniquement_les_produits_france(self):
        n = filtrer_produits_france(str(CHEMIN_FIXTURE), "/tmp/test_off_filtre.parquet")
        self.assertEqual(n, 9)  # 10 produits dans l'échantillon, 1 exclu (marché allemand uniquement)


class TestDetecterEdulcorants(unittest.TestCase):
    def test_detecte_edulcorant_connu(self):
        self.assertTrue(_detecter_edulcorants(["en:e950", "en:e330"]))

    def test_aucun_edulcorant(self):
        self.assertFalse(_detecter_edulcorants(["en:e330", "en:e300"]))

    def test_liste_vide(self):
        self.assertFalse(_detecter_edulcorants([]))
        self.assertFalse(_detecter_edulcorants(None))


class TestResoudreCategorieProduit(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()

    def test_categorie_reconnue(self):
        id_cat = _resoudre_categorie_produit(self.conn, ["en:sodas", "en:carbonated-drinks"])
        self.assertIsNotNone(id_cat)
        code = self.conn.execute("SELECT code FROM categorie_produit WHERE id=?", (id_cat,)).fetchone()["code"]
        self.assertEqual(code, "BOISSONS_SUCREES")

    def test_categorie_inconnue_renvoie_none(self):
        id_cat = _resoudre_categorie_produit(self.conn, ["en:tag-completement-inconnu"])
        self.assertIsNone(id_cat)

    def test_liste_vide_renvoie_none(self):
        self.assertIsNone(_resoudre_categorie_produit(self.conn, []))

    def test_premier_tag_correspondant_gagne(self):
        # "en:spreads" n'est pas dans le mapping, "en:chocolates" y est -> doit matcher chocolates
        id_cat = _resoudre_categorie_produit(self.conn, ["en:spreads", "en:chocolates"])
        code = self.conn.execute("SELECT code FROM categorie_produit WHERE id=?", (id_cat,)).fetchone()["code"]
        self.assertEqual(code, "CONFISERIE_CHOCOLAT")


class TestImportComplet(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_test()
        filtrer_produits_france(str(CHEMIN_FIXTURE), "/tmp/test_off_filtre_import.parquet")
        self.resume = importer_dans_bdd(self.conn, "/tmp/test_off_filtre_import.parquet")

    def test_resume_import(self):
        self.assertEqual(self.resume["total"], 9)
        self.assertEqual(self.resume["avec_categorie"], 8)
        self.assertEqual(self.resume["sans_categorie"], 1)

    def test_produit_soda_correctement_importe(self):
        p = resoudre_produit_par_code_barre(self.conn, "5449000000996")
        self.assertIsNotNone(p)
        self.assertEqual(p["nom"], "Coca-Cola")
        self.assertAlmostEqual(p["teneur_sucre_100g"], 10.6)
        self.assertEqual(p["contient_edulcorants"], 0)
        self.assertEqual(p["source"], "OFF")

    def test_produit_avec_edulcorant_detecte(self):
        p = resoudre_produit_par_code_barre(self.conn, "5449000133328")
        self.assertEqual(p["contient_edulcorants"], 1)

    def test_produit_sans_categorie_reconnue_importe_quand_meme(self):
        p = resoudre_produit_par_code_barre(self.conn, "9999999999991")
        self.assertIsNotNone(p)  # importé...
        self.assertIsNone(p["categorie_produit_id"])  # ...mais sans catégorie résolue

    def test_produit_hors_france_absent(self):
        p = resoudre_produit_par_code_barre(self.conn, "1111111111111")
        self.assertIsNone(p)

    def test_reimport_met_a_jour_sans_dupliquer(self):
        # Réimporter le même fichier ne doit pas créer de doublons (ON CONFLICT).
        resume2 = importer_dans_bdd(self.conn, "/tmp/test_off_filtre_import.parquet")
        self.assertEqual(resume2["total"], 9)
        total_en_base = self.conn.execute("SELECT COUNT(*) AS n FROM produit_reference").fetchone()["n"]
        self.assertEqual(total_en_base, 9)  # pas 18


class TestBoucleFiscaleComplete(unittest.TestCase):
    """Vérifie que la donnée importée d'OFF (teneur en sucre) alimente
    correctement le calcul de la taxe soda (mécanisme montant_par_unite_a_seuil).
    """

    def setUp(self):
        self.conn = _creer_bdd_test()
        filtrer_produits_france(str(CHEMIN_FIXTURE), "/tmp/test_off_filtre_fiscal.parquet")
        importer_dans_bdd(self.conn, "/tmp/test_off_filtre_fiscal.parquet")

    def test_taxe_soda_calculee_a_partir_des_donnees_off(self):
        from fiscal_engine import resolver, calculator

        coca = resoudre_produit_par_code_barre(self.conn, "5449000000996")
        id_taxe = self.conn.execute("SELECT id FROM prelevement WHERE code='TAXE_BOISSONS_SUCRE'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, id_taxe, "2026-06-01")
        resultat = calculator.calculer_montant(
            self.conn, regle, montant=2.50, quantite=1.5, unite_quantite="L", valeur_seuil=coca["teneur_sucre_100g"]
        )
        self.assertAlmostEqual(resultat["taux_applique"], 35.63)  # 10.6 kg/hL -> tranche haute
        self.assertAlmostEqual(resultat["montant"], 0.015 * 35.63)


if __name__ == "__main__":
    unittest.main()
