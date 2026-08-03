"""Tests unitaires du module fiscal_engine.retraite, contre les vrais seuils
RFR 2026 sourcés sur seed_data/fr_seed_lot3.sql.

Contrairement à tests/test_engine.py (qui teste des mécanismes génériques
avec des valeurs rondes arbitraires), ce fichier teste les vraies DONNÉES
fiscales 2026 telles qu'insérées en base, sur le modèle de
tests/test_alcool.py.

Seuils 1 part vérifiés le 2026-07-29 sur la source officielle
« L'Assurance Retraite » (CNAV) :
https://www.lassuranceretraite.fr/portail-info/hors-menu/actualites-nationales/retraite/2026/prelevements-sociaux-2025.html

ÉTENDU le 2026-08-02 (PROJECT_STATE.md section 7.2) : le module gère
désormais un nombre de parts arbitraire (multiple de 0,5, >= 1) par
extrapolation officielle "par demi-part supplémentaire", et le mécanisme
de lissage. Les tests de cette extension sont regroupés dans
TestExtrapolationParParts et TestLissage ci-dessous.
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
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2, revenu_fiscal_reference=40604,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)


class TestExtrapolationParParts(unittest.TestCase):
    """1,5 / 2,5 / 3 parts, et par demi-part supplémentaire — ajouté le
    2026-08-02. Seuils attendus = seuil_1_part + n x incrément_demi_part,
    avec incréments 3484€ (exo) / 4555€ (réduit) / 7066€ (normal),
    vérifiés par cohérence arithmétique avec les seuils 1/2 parts déjà
    officiels (voir seed_data/fr_seed_lot3.sql).
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_1_5_part_seuil_exonere(self):
        # 13048 + 1*3484 = 16532
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1.5, revenu_fiscal_reference=16500,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertEqual(r["taux_csg"], 0.0)

    def test_1_5_part_juste_au_dessus_bascule_reduit(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1.5, revenu_fiscal_reference=16600,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.038)

    def test_2_5_parts_seuil_normal(self):
        # 26472 + 3*7066 = 47670 (2.5 parts = 1 part + 3 demi-parts)
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2.5, revenu_fiscal_reference=47600,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)  # encore median

    def test_2_5_parts_juste_au_dessus_bascule_normal(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=2.5, revenu_fiscal_reference=47700,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.083)

    def test_3_parts_seuil_exonere_egal_a_2_parts_plus_un_increment(self):
        # 3 parts = 2 parts (deja officiel) + 2 demi-parts supplementaires
        # seuil exo attendu : 20016 + 2*3484 = 26984
        r_sous = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=3, revenu_fiscal_reference=26900,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        r_au_dela = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=3, revenu_fiscal_reference=27000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertEqual(r_sous["taux_csg"], 0.0)
        self.assertAlmostEqual(r_au_dela["taux_csg"], 0.038)

    def test_seuils_croissants_avec_le_nombre_de_parts(self):
        # A RFR fixe, plus de parts ne peut jamais donner un taux plus eleve
        rfr = 25000
        taux_par_parts = {}
        for parts in (1, 1.5, 2, 2.5, 3):
            r = retraite.calculer_prelevements_retraite(
                self.conn, nombre_parts=parts, revenu_fiscal_reference=rfr,
                pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            )
            taux_par_parts[parts] = r["taux_csg"]
        valeurs = list(taux_par_parts.values())
        self.assertEqual(valeurs, sorted(valeurs, reverse=True))


class TestNombreDePartsInvalide(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_moins_dune_part_leve_value_error(self):
        with self.assertRaises(ValueError):
            retraite.calculer_prelevements_retraite(
                self.conn, nombre_parts=0.5, revenu_fiscal_reference=20000,
                pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            )

    def test_multiple_non_valide_de_0_5_leve_value_error(self):
        with self.assertRaises(ValueError):
            retraite.calculer_prelevements_retraite(
                self.conn, nombre_parts=1.3, revenu_fiscal_reference=20000,
                pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            )

    def test_3_parts_est_desormais_valide(self):
        # Non-regression : avant le 2026-08-02, 3 parts levait ValueError.
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=3, revenu_fiscal_reference=20000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertEqual(r["taux_csg"], 0.0)


class TestLissage(unittest.TestCase):
    """Mécanisme de lissage (ajouté le 2026-08-02) : ne protège que le
    passage depuis la tranche réduite (déterminée par le RFR N-3) vers une
    tranche supérieure (déterminée par le RFR N-2) — voir docstring de
    fiscal_engine/retraite.py pour la portée précise et sa source.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_sans_rfr_n_moins_3_pas_de_lissage(self):
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=20000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)  # tranche reelle (median)
        self.assertFalse(r["lissage_applique"])

    def test_reduit_vers_median_protege_par_le_lissage(self):
        # RFR N-3 = 15000 (reduit, entre 13048 et 17057)
        # RFR N-2 = 20000 (aurait ete median, entre 17057 et 26472)
        # -> le lissage doit maintenir le taux reduit (3.8%)
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=20000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            revenu_fiscal_reference_n_moins_3=15000,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.038)
        self.assertTrue(r["lissage_applique"])

    def test_reduit_vers_normal_egalement_protege(self):
        # RFR N-3 encore reduit, RFR N-2 franchit directement jusqu'a normal
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=30000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            revenu_fiscal_reference_n_moins_3=15000,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.038)
        self.assertTrue(r["lissage_applique"])

    def test_median_vers_normal_non_protege(self):
        # RFR N-3 deja median (pas reduit) -> AUCUN lissage pour ce passage
        # (portee du lissage confirmee sur CNAV : reduit uniquement)
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=30000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            revenu_fiscal_reference_n_moins_3=20000,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.083)
        self.assertFalse(r["lissage_applique"])

    def test_rfr_n_moins_3_plus_haut_que_n_moins_2_pas_de_lissage(self):
        # Le RFR baisse d'une annee sur l'autre : pas de franchissement a
        # la hausse, donc pas de question de lissage (le taux du RFR N-2
        # s'applique directement)
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=15000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            revenu_fiscal_reference_n_moins_3=30000,
        )
        self.assertAlmostEqual(r["taux_csg"], 0.038)
        self.assertFalse(r["lissage_applique"])

    def test_deja_confirme_2_ans_de_suite_pas_de_lissage(self):
        # RFR N-3 ET N-2 tous deux au-dela du seuil reduit -> le
        # franchissement est confirme sur 2 ans, le nouveau taux s'applique
        r = retraite.calculer_prelevements_retraite(
            self.conn, nombre_parts=1, revenu_fiscal_reference=20000,
            pension_brute=PENSION_BRUTE, date_reference=DATE_REF,
            revenu_fiscal_reference_n_moins_3=19000,  # deja median (>17057)
        )
        self.assertAlmostEqual(r["taux_csg"], 0.066)
        self.assertFalse(r["lissage_applique"])


if __name__ == "__main__":
    unittest.main()
