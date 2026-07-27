"""Tests unitaires du module fiscal_engine.alcool, contre les vrais tarifs
2026 sourcés exclusivement douane.gouv.fr (voir seed_data/fr_seed_lot3.sql).
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import alcool

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestDroitBiere(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_biere_legere_2_8_pourcent_ou_moins(self):
        r = alcool.calculer_droit_biere(self.conn, degre_alcool=2.5, volume_hl=0.0033, date_reference="2026-06-01")
        self.assertEqual(r["categorie_degre"], "≤2,8% vol")
        self.assertAlmostEqual(r["montant"], 0.0033 * 2.5 * 4.12, places=6)

    def test_biere_normale_plus_de_2_8_pourcent(self):
        r = alcool.calculer_droit_biere(self.conn, degre_alcool=5.0, volume_hl=0.0033, date_reference="2026-06-01")
        self.assertEqual(r["categorie_degre"], ">2,8% vol")
        self.assertAlmostEqual(r["montant"], 0.0033 * 5.0 * 8.24, places=6)

    def test_seuil_exact_2_8_est_categorie_legere(self):
        # <= 2.8 doit rester dans la categorie legere (limite incluse)
        r = alcool.calculer_droit_biere(self.conn, degre_alcool=2.8, volume_hl=0.0033, date_reference="2026-06-01")
        self.assertEqual(r["categorie_degre"], "≤2,8% vol")

    def test_montant_croit_avec_le_degre(self):
        r_faible = alcool.calculer_droit_biere(self.conn, degre_alcool=4.0, volume_hl=0.005, date_reference="2026-06-01")
        r_fort = alcool.calculer_droit_biere(self.conn, degre_alcool=8.0, volume_hl=0.005, date_reference="2026-06-01")
        self.assertLess(r_faible["montant"], r_fort["montant"])


class TestDroitSpiritueux(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_spiritueux_40_pourcent_avec_cotisation_secu(self):
        r = alcool.calculer_droit_spiritueux(self.conn, degre_alcool=40.0, volume_hl=0.007, date_reference="2026-06-01")
        self.assertAlmostEqual(r["droit_consommation"], 0.007 * 0.40 * 1932.42, places=4)
        self.assertAlmostEqual(r["cotisation_secu"], 0.007 * 0.40 * 620.47, places=4)
        self.assertAlmostEqual(r["total"], r["droit_consommation"] + r["cotisation_secu"])

    def test_spiritueux_sous_18_pourcent_pas_de_cotisation_secu(self):
        r = alcool.calculer_droit_spiritueux(self.conn, degre_alcool=15.0, volume_hl=0.007, date_reference="2026-06-01")
        self.assertGreater(r["droit_consommation"], 0.0)  # le droit de conso s'applique quand meme
        self.assertEqual(r["cotisation_secu"], 0.0)  # mais pas la cotisation secu

    def test_seuil_exact_18_pas_de_cotisation_secu(self):
        # Le seuil est "plus de 18%", donc exactement 18% ne doit PAS declencher la cotisation
        r = alcool.calculer_droit_spiritueux(self.conn, degre_alcool=18.0, volume_hl=0.007, date_reference="2026-06-01")
        self.assertEqual(r["cotisation_secu"], 0.0)

    def test_juste_au_dessus_18_declenche_cotisation_secu(self):
        r = alcool.calculer_droit_spiritueux(self.conn, degre_alcool=18.1, volume_hl=0.007, date_reference="2026-06-01")
        self.assertGreater(r["cotisation_secu"], 0.0)


class TestVinCidreProduitsIntermediaires(unittest.TestCase):
    """Le vin/cidre/produits intermédiaires n'ont pas besoin d'orchestration
    (tarif fixe par hL, indépendant du degré) — vérifié directement via le
    moteur générique plutôt que via fiscal_engine.alcool.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_vin_tranquille(self):
        from fiscal_engine import resolver, calculator

        pid = self.conn.execute("SELECT id FROM prelevement WHERE code='ACCISE_VIN_TRANQUILLE'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, pid, "2026-06-01")
        r = calculator.calculer_montant(self.conn, regle, montant=0.0, quantite=0.0075, unite_quantite="hL")
        self.assertAlmostEqual(r["montant"], 0.0075 * 4.19, places=6)

    def test_cidre(self):
        from fiscal_engine import resolver, calculator

        pid = self.conn.execute("SELECT id FROM prelevement WHERE code='ACCISE_CIDRE_POIRE_HYDROMEL'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, pid, "2026-06-01")
        r = calculator.calculer_montant(self.conn, regle, montant=0.0, quantite=0.0075, unite_quantite="hL")
        self.assertAlmostEqual(r["montant"], 0.0075 * 1.46, places=6)


if __name__ == "__main__":
    unittest.main()
