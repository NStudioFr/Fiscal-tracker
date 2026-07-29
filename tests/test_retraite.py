"""Tests unitaires du module fiscal_engine.retraite, contre les vrais seuils
RFR 2026 sourcés sur seed_data/fr_seed_lot3.sql.

Contrairement à tests/test_engine.py (qui teste le MÉCANISME générique avec
des seuils ronds arbitraires), ce fichier teste les vraies DONNÉES fiscales
2026 telles qu'insérées en base, sur le modèle de tests/test_alcool.py.

Seuils vérifiés le 2026-07-29 sur la source officielle « L'Assurance
Retraite » (CNAV) :
https://www.lassuranceretraite.fr/portail-info/hors-menu/actualites-nationales/retraite/2026/prelevements-sociaux-2025.html

À cette occasion, une erreur a été trouvée et corrigée dans le seed : le
seuil médian/normal à 2 parts était à 39 886 € (valeur 2025 non
revalorisée) au lieu de 40 604 € (valeur 2026 officielle). Les tests
autour de cette frontière (test_2parts_...) verrouillent spécifiquement
cette correction contre toute régression future.
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import retraite

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"

DATE_REF = "2026-06-01"
PENSION_BRUTE = 1000.0  # base ronde pour simplifier la lecture des montants attendus


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestSeuils1Part(unittest.TestCase):
    """Foyer à 1 part : exonération < 13048, réduit 13048-17057,
    médian 17057-26472, normal > 26472 (source CNAV, tableau officiel)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_exonere_juste_sous_le_seuil(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=13000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertEqual(r["taux_csg"], 0.0)
        self.assertEqual(r["montant_crds"], 0.0)
        self.assertEqual(r["montant_casa"], 0.0)
        self.assertEqual(r["pension_nette"], PENSION_BRUTE)

    def test_taux_reduit_au_milieu_de_tranche(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=15000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.038)
        self.assertAlmostEqual(r["montant_csg"], PENSION_BRUTE * 0.038)
        self.assertAlmostEqual(r["montant_crds"], PENSION_BRUTE * 0.005)
        self.assertEqual(r["montant_casa"], 0.0)  # CASA pas due au taux réduit

    def test_taux_median_au_milieu_de_tranche(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=20000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)
        self.assertAlmostEqual(r["montant_crds"], PENSION_BRUTE * 0.005)
        self.assertAlmostEqual(r["montant_casa"], PENSION_BRUTE * 0.003)  # CASA due au médian

    def test_taux_normal_au_dela_du_seuil(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=30000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.083)
        self.assertAlmostEqual(r["montant_crds"], PENSION_BRUTE * 0.005)
        self.assertAlmostEqual(r["montant_casa"], PENSION_BRUTE * 0.003)

    def test_pension_nette_coherente(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=30000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        total_attendu = PENSION_BRUTE * (0.083 + 0.005 + 0.003)
        self.assertAlmostEqual(r["total_preleve"], total_attendu)
        self.assertAlmostEqual(r["pension_nette"], PENSION_BRUTE - total_attendu)


class TestSeuils2Parts(unittest.TestCase):
    """Foyer à 2 parts : exonération < 20016, réduit 20016-26167,
    médian 26167-40604, normal > 40604.

    La frontière médian/normal (40604) est celle qui contenait l'erreur
    corrigée le 2026-07-29 (était à 39886, valeur 2025 non revalorisée) :
    les deux tests ci-dessous verrouillent spécifiquement cette valeur.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_exonere_juste_sous_le_seuil(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2, revenu_fiscal_reference=19000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertEqual(r["taux_csg"], 0.0)

    def test_juste_sous_le_seuil_corrige_est_encore_median(self):
        # 40000 est strictement inférieur au seuil réel de 40604 : doit
        # rester au taux médian (6,6%), PAS au taux normal. Avec l'ancien
        # seuil erroné (39886), ce RFR aurait été classé à tort en taux
        # normal (8,3%) : ce test aurait échoué avant la correction.
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2, revenu_fiscal_reference=40000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)
        self.assertAlmostEqual(r["montant_casa"], PENSION_BRUTE * 0.003)

    def test_juste_au_dela_du_seuil_corrige_passe_au_taux_normal(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2, revenu_fiscal_reference=41000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.083)

    def test_valeur_exacte_du_seuil_haut_reste_median(self):
        # A la borne exacte 40604, le moteur retient encore le taux médian
        # (6,6%), pas le taux normal : dans calculator._trouver_taux_par_seuil,
        # les tranches sont bornées en <= des deux côtés et évaluées dans
        # l'ordre croissant des borne_min, donc la tranche médian (dont
        # borne_max == 40604) l'emporte avant la tranche normal (dont
        # borne_min == 40604). C'est le même comportement, déjà existant et
        # cohérent, que pour le seuil 1 part à 26472 (voir test_engine.py /
        # vérification manuelle) : ce n'est PAS un bug introduit par la
        # correction du 2026-07-29, juste une convention de borne à un euro
        # près par rapport au libellé "RFR > 40 604 €" de la source CNAV.
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2, revenu_fiscal_reference=40604,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)


class TestNombreDePartsInvalide(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_3_parts_leve_value_error(self):
        with self.assertRaises(ValueError):
            retraite.calculer_prelevements_retraite(
                self.conn, nombre_parts=3, revenu_fiscal_reference=20000,
                pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            )


if __name__ == "__main__":
    unittest.main()
