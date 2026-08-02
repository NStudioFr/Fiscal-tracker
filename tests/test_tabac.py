"""Tests unitaires des accises tabac, contre les vraies données 2026 du
seed (seed_data/fr_seed_lot3.sql), sur le modèle de tests/test_alcool.py.

Fiabilisé le 2026-07-29 (PROJECT_STATE.md section 7.7) : les paramètres de
l'accise (taux/tarif/minimum de perception) ont été revérifiés par lecture
directe de la page douane.gouv.fr "La fiscalité appliquée aux tabacs
manufacturés..." (mise à jour du 05/01/2026) — tous corrects, mais 2
catégories fiscales manquaient entièrement au seed (ajoutées à cette
date) : "autres tabacs à fumer/inhaler après chauffage" et "autres tabacs
à chauffer".

Ce fichier verrouille en particulier les 2 exemples chiffrés OFFICIELS
publiés par la douane elle-même sur cette page (décomposition du prix
d'un paquet de 20 cigarettes à 11,50€ et à 13,50€), avec le détail exact
(accise = 7,791€ pour le paquet à 11,50€, 8,891€ pour celui à 13,50€ —
recalculé directement depuis les 2 composantes "taux" + "tarif" publiées,
qui l'emportent toutes deux sur le minimum de perception).
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import resolver, calculator

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


def _accise(conn, code_prelevement, prix_vente, quantite):
    pid = conn.execute("SELECT id FROM prelevement WHERE code = ?", (code_prelevement,)).fetchone()["id"]
    regle = resolver.resoudre_regle(conn, pid, DATE_REF)
    return calculator.calculer_montant(conn, regle, montant=prix_vente, quantite=quantite)["montant"]


class TestExemplesOfficielsCigarettes(unittest.TestCase):
    """Verrouille les 2 exemples chiffrés publiés directement par la douane
    (paquet de 20 cigarettes à 11,50E et à 13,50E), recalculés le 2026-07-29
    depuis les 2 composantes taux+tarif de la page officielle.
    """

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_paquet_bas_de_marche_11_50(self):
        # accise = max(0.55*11.50 + 73.30*20/1000, 381.90*20/1000)
        #        = max(6.325 + 1.466, 7.638) = max(7.791, 7.638) = 7.791
        montant = _accise(self.conn, "ACCISE_TABAC_CIGARETTES", prix_vente=11.50, quantite=20)
        self.assertAlmostEqual(montant, 7.791, places=3)

    def test_paquet_premium_13_50(self):
        # accise = max(0.55*13.50 + 73.30*20/1000, 381.90*20/1000)
        #        = max(7.425 + 1.466, 7.638) = max(8.891, 7.638) = 8.891
        montant = _accise(self.conn, "ACCISE_TABAC_CIGARETTES", prix_vente=13.50, quantite=20)
        self.assertAlmostEqual(montant, 8.891, places=3)

    def test_tva_en_dedans_coherente_avec_lexemple_officiel(self):
        pid = self.conn.execute("SELECT id FROM prelevement WHERE code = 'TVA_NORMAL'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, pid, DATE_REF)
        r = calculator.calculer_montant(self.conn, regle, montant=11.50)
        # 11.50 x 0.20/1.20 = 1.9167, coherent avec le 1,92E arrondi de
        # l'exemple officiel douane.gouv.fr
        self.assertAlmostEqual(r["montant"], 1.9167, places=3)


class TestNouvellesCategoriesTabacAChauffer(unittest.TestCase):
    """Les 2 catégories ajoutées le 2026-07-29 (absentes du seed initial)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_autre_a_fumer_apres_chauffage_sous_le_minimum(self):
        # 10g a 1E/g (10E) : 0.514*10 + 36.20*10/1000 = 5.14+0.362=5.502
        # vs minimum 153.70*10/1000=1.537 -> l'addition l'emporte
        montant = _accise(self.conn, "ACCISE_TABAC_AUTRE_A_FUMER_APRES_CHAUFFAGE", prix_vente=10.0, quantite=10)
        self.assertAlmostEqual(montant, 0.514 * 10 + 36.20 * 10 / 1000, places=4)

    def test_chauffer_autre_minimum_domine_a_prix_tres_bas(self):
        # prix tres bas (0.01E) pour 10g : addition quasi nulle, minimum
        # 1267.90*10/1000=12.679 doit l'emporter
        montant = _accise(self.conn, "ACCISE_TABAC_CHAUFFER_AUTRE", prix_vente=0.01, quantite=10)
        self.assertAlmostEqual(montant, 1267.90 * 10 / 1000, places=3)


class TestTabacPriserMacher(unittest.TestCase):
    """Taux ad valorem simple, sans tarif fixe ni minimum de perception."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_tabac_priser(self):
        pid = self.conn.execute("SELECT id FROM prelevement WHERE code = 'ACCISE_TABAC_PRISER'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, pid, DATE_REF)
        r = calculator.calculer_montant(self.conn, regle, montant=10.0)
        self.assertAlmostEqual(r["montant"], 10.0 * 0.581)

    def test_tabac_macher(self):
        pid = self.conn.execute("SELECT id FROM prelevement WHERE code = 'ACCISE_TABAC_MACHER'").fetchone()["id"]
        regle = resolver.resoudre_regle(self.conn, pid, DATE_REF)
        r = calculator.calculer_montant(self.conn, regle, montant=10.0)
        self.assertAlmostEqual(r["montant"], 10.0 * 0.407)


if __name__ == "__main__":
    unittest.main()
