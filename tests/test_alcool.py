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


# Les 4 classes de test suivantes couvrent les points ajoutés le 2026-07-29
# (PROJECT_STATE.md section 7.6) : petites brasseries, rhums DOM, VDN/VDL
# AOP, taxe prémix.

class TestBierePetiteBrasserie(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_petite_brasserie_beneficie_du_tarif_leger_meme_au_dela_de_2_8(self):
        # 1hL a 5% vol, brasserie independante -> tarif leger 4.12E/hL.degre
        # au lieu du tarif normal 8.24E/hL.degre
        r = alcool.calculer_droit_biere(
            self.conn, degre_alcool=5.0, volume_hl=1.0, date_reference="2026-06-01",
            petite_brasserie_independante=True,
        )
        self.assertAlmostEqual(r["montant"], 1.0 * 5.0 * 4.12)
        self.assertIn("petite brasserie", r["categorie_degre"])

    def test_sans_petite_brasserie_tarif_normal_applique(self):
        r = alcool.calculer_droit_biere(
            self.conn, degre_alcool=5.0, volume_hl=1.0, date_reference="2026-06-01",
            petite_brasserie_independante=False,
        )
        self.assertAlmostEqual(r["montant"], 1.0 * 5.0 * 8.24)

    def test_petite_brasserie_sans_effet_sous_2_8_pourcent(self):
        # Deja au tarif leger de toute facon (seuil de degre prioritaire)
        r_normal = alcool.calculer_droit_biere(
            self.conn, degre_alcool=2.0, volume_hl=1.0, date_reference="2026-06-01",
            petite_brasserie_independante=False,
        )
        r_petite = alcool.calculer_droit_biere(
            self.conn, degre_alcool=2.0, volume_hl=1.0, date_reference="2026-06-01",
            petite_brasserie_independante=True,
        )
        self.assertAlmostEqual(r_normal["montant"], r_petite["montant"])


class TestSpiritueuxRhumDom(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_rhum_dom_beneficie_du_tarif_reduit(self):
        # 1hlap (1hL a 100%, pour simplifier) -> 966.75E au lieu de 1932.42E
        r = alcool.calculer_droit_spiritueux(
            self.conn, degre_alcool=40.0, volume_hl=1.0, date_reference="2026-06-01", rhum_dom=True
        )
        self.assertAlmostEqual(r["droit_consommation"], 1.0 * (40.0 / 100) * 966.75)

    def test_sans_rhum_dom_tarif_normal(self):
        r = alcool.calculer_droit_spiritueux(
            self.conn, degre_alcool=40.0, volume_hl=1.0, date_reference="2026-06-01", rhum_dom=False
        )
        self.assertAlmostEqual(r["droit_consommation"], 1.0 * (40.0 / 100) * 1932.42)

    def test_rhum_dom_titrant_plus_de_18_paie_quand_meme_la_cotisation_secu_normale(self):
        r = alcool.calculer_droit_spiritueux(
            self.conn, degre_alcool=40.0, volume_hl=1.0, date_reference="2026-06-01", rhum_dom=True
        )
        self.assertAlmostEqual(r["cotisation_secu"], 1.0 * (40.0 / 100) * 620.47)


class TestProduitIntermediaireVdnVdlAop(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_vdn_vdl_aop_accise_reduite(self):
        r = alcool.calculer_droit_produit_intermediaire(
            self.conn, degre_alcool=16.0, volume_hl=1.0, date_reference="2026-06-01", vdn_vdl_aop=True
        )
        self.assertAlmostEqual(r["droit_circulation"], 1.0 * 52.39)

    def test_autre_produit_intermediaire_accise_normale(self):
        r = alcool.calculer_droit_produit_intermediaire(
            self.conn, degre_alcool=16.0, volume_hl=1.0, date_reference="2026-06-01", vdn_vdl_aop=False
        )
        self.assertAlmostEqual(r["droit_circulation"], 1.0 * 209.53)

    def test_vdn_vdl_aop_plus_de_18_declenche_cotisation_secu_sur_produit_fini(self):
        r = alcool.calculer_droit_produit_intermediaire(
            self.conn, degre_alcool=20.0, volume_hl=1.0, date_reference="2026-06-01", vdn_vdl_aop=True
        )
        # Base = hL de produit fini (PAS hlap) : 1hL * 20.97E/hL = 20.97E
        self.assertAlmostEqual(r["cotisation_secu"], 1.0 * 20.97)

    def test_vdn_vdl_aop_sous_18_pas_de_cotisation_secu(self):
        r = alcool.calculer_droit_produit_intermediaire(
            self.conn, degre_alcool=16.0, volume_hl=1.0, date_reference="2026-06-01", vdn_vdl_aop=True
        )
        self.assertAlmostEqual(r["cotisation_secu"], 0.0)

    def test_autre_produit_intermediaire_plus_de_18_pas_de_cotisation_secu_geree(self):
        # Limite residuelle assumee : non geree pour les non-AOP
        r = alcool.calculer_droit_produit_intermediaire(
            self.conn, degre_alcool=20.0, volume_hl=1.0, date_reference="2026-06-01", vdn_vdl_aop=False
        )
        self.assertAlmostEqual(r["cotisation_secu"], 0.0)


class TestTaxePremix(unittest.TestCase):
    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_categorie_autre_par_defaut(self):
        r = alcool.calculer_taxe_premix(
            self.conn, degre_alcool=5.0, volume_hl=1.0, date_reference="2026-06-01"
        )
        self.assertEqual(r["categorie"], "autre")
        self.assertAlmostEqual(r["montant"], 1.0 * (5.0 / 100) * 11000)

    def test_categorie_vin_explicite(self):
        r = alcool.calculer_taxe_premix(
            self.conn, degre_alcool=5.0, volume_hl=1.0, date_reference="2026-06-01", categorie="vin"
        )
        self.assertAlmostEqual(r["montant"], 1.0 * (5.0 / 100) * 3000)

    def test_categorie_invalide_leve_value_error(self):
        with self.assertRaises(ValueError):
            alcool.calculer_taxe_premix(
                self.conn, degre_alcool=5.0, volume_hl=1.0, date_reference="2026-06-01",
                categorie="inconnue",
            )


if __name__ == "__main__":
    unittest.main()
