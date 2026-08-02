"""Tests unitaires du module fiscal_engine.independant, contre les vraies
données 2026 du seed (seed_data/fr_seed_lot3.sql), sur le modèle de
tests/test_alcool.py et tests/test_retraite.py.

Fiabilisé le 2026-07-29 (PROJECT_STATE.md section 7.3) : ce fichier teste
les 3 points couverts à cette date :
  1. Taux CIPAV (23,2%, distinct du BNC régime général à 25,6%).
  2. Plafonds de chiffre d'affaires du régime micro (203 100€ / 83 600€).
  3. Éligibilité au versement libératoire selon le RFR N-2 (29 315€/part).
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import independant

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"

DATE_REF = "2026-06-01"


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestCipav(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_taux_cipav_23_2_pourcent(self):
        # Exemple officiel (arapl.org) : 30000E de recettes -> 6960E de cotisations
        r = independant.calculer_cotisations_micro(
            self.conn, "bnc_cipav", chiffre_affaires=30000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r["montant"], 6960.0)

    def test_taux_cipav_distinct_du_bnc_regime_general(self):
        r_cipav = independant.calculer_cotisations_micro(
            self.conn, "bnc_cipav", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        r_bnc = independant.calculer_cotisations_micro(
            self.conn, "bnc", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r_cipav["montant"], 2320.0)  # 23.2%
        self.assertAlmostEqual(r_bnc["montant"], 2560.0)    # 25.6%
        self.assertNotAlmostEqual(r_cipav["montant"], r_bnc["montant"])

    def test_versement_liberatoire_cipav_identique_au_bnc_general(self):
        r_cipav = independant.calculer_versement_liberatoire(
            self.conn, "bnc_cipav", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        r_bnc = independant.calculer_versement_liberatoire(
            self.conn, "bnc", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r_cipav["montant"], r_bnc["montant"])
        self.assertAlmostEqual(r_cipav["montant"], 220.0)  # 2.2%

    def test_abattement_cipav_identique_au_bnc_general(self):
        revenu_cipav = independant.calculer_revenu_imposable_micro(
            self.conn, "bnc_cipav", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        revenu_bnc = independant.calculer_revenu_imposable_micro(
            self.conn, "bnc", chiffre_affaires=10000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(revenu_cipav, revenu_bnc)
        self.assertAlmostEqual(revenu_cipav, 6600.0)  # abattement 34%


class TestPlafondsCaMicro(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_vente_sous_le_plafond(self):
        r = independant.verifier_plafond_ca_micro(
            self.conn, "vente", chiffre_affaires_annuel=150000.0, date_reference=DATE_REF
        )
        self.assertEqual(r["plafond_applicable"], 203100.0)
        self.assertFalse(r["depasse"])

    def test_vente_au_dela_du_plafond(self):
        r = independant.verifier_plafond_ca_micro(
            self.conn, "vente", chiffre_affaires_annuel=210000.0, date_reference=DATE_REF
        )
        self.assertTrue(r["depasse"])

    def test_services_bic_plafond_83600(self):
        r = independant.verifier_plafond_ca_micro(
            self.conn, "services_bic", chiffre_affaires_annuel=90000.0, date_reference=DATE_REF
        )
        self.assertEqual(r["plafond_applicable"], 83600.0)
        self.assertTrue(r["depasse"])

    def test_bnc_cipav_meme_plafond_que_bnc(self):
        r_cipav = independant.verifier_plafond_ca_micro(
            self.conn, "bnc_cipav", chiffre_affaires_annuel=50000.0, date_reference=DATE_REF
        )
        self.assertEqual(r_cipav["plafond_applicable"], 83600.0)

    def test_activite_mixte_sous_plafond_global_mais_au_dela_du_sous_plafond_services(self):
        # CA global 150000E (< 203100, OK), dont 90000E de services (> 83600)
        r = independant.verifier_plafond_ca_micro(
            self.conn, "vente", chiffre_affaires_annuel=150000.0, date_reference=DATE_REF,
            chiffre_affaires_services_si_mixte=90000.0,
        )
        self.assertFalse(r["depasse"])
        self.assertTrue(r["depasse_sous_plafond_services"])

    def test_sans_mixte_sous_plafond_services_est_none(self):
        r = independant.verifier_plafond_ca_micro(
            self.conn, "vente", chiffre_affaires_annuel=150000.0, date_reference=DATE_REF
        )
        self.assertIsNone(r["depasse_sous_plafond_services"])


class TestEligibiliteVersementLiberatoire(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_1_part_sous_le_seuil_eligible(self):
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=1.0, revenu_fiscal_reference_n_moins_2=25000.0, date_reference=DATE_REF
        )
        self.assertEqual(r["seuil_applicable"], 29315.0)
        self.assertTrue(r["eligible"])

    def test_1_part_au_dela_du_seuil_non_eligible(self):
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=1.0, revenu_fiscal_reference_n_moins_2=35000.0, date_reference=DATE_REF
        )
        self.assertFalse(r["eligible"])

    def test_2_parts_seuil_double(self):
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=2.0, revenu_fiscal_reference_n_moins_2=55000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r["seuil_applicable"], 58630.0)
        self.assertTrue(r["eligible"])

    def test_2_5_parts_exemple_officiel(self):
        # Exemple officiel (clictreso.fr) : couple + 1 enfant = 2.5 parts -> 73288E
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=2.5, revenu_fiscal_reference_n_moins_2=73000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r["seuil_applicable"], 73287.5)

    def test_3_parts_exemple_officiel(self):
        # Exemple officiel : couple + 2 enfants = 3 parts -> 87945E
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=3.0, revenu_fiscal_reference_n_moins_2=80000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(r["seuil_applicable"], 87945.0)

    def test_egalite_au_seuil_est_eligible(self):
        r = independant.verifier_eligibilite_versement_liberatoire(
            self.conn, nombre_parts=1.0, revenu_fiscal_reference_n_moins_2=29315.0, date_reference=DATE_REF
        )
        self.assertTrue(r["eligible"])


if __name__ == "__main__":
    unittest.main()
