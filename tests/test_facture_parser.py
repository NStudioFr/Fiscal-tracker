import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.facture import parser_facture


class TestParserFacture(unittest.TestCase):
    def test_tva_normale_20_pourcent(self):
        texte = "TVA 20,0% 45,20 €"
        lignes = parser_facture(texte)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].code_prelevement, "TVA_NORMAL")
        self.assertAlmostEqual(lignes[0].montant, 45.20)

    def test_tva_reduite_5_5_pourcent(self):
        texte = "TVA 5,5% 12,10"
        lignes = parser_facture(texte)
        self.assertEqual(lignes[0].code_prelevement, "TVA_REDUIT")
        self.assertAlmostEqual(lignes[0].montant, 12.10)

    def test_tva_intermediaire_10_pourcent(self):
        texte = "TVA (10%) : 8,50"
        lignes = parser_facture(texte)
        self.assertEqual(lignes[0].code_prelevement, "TVA_INTERMEDIAIRE")
        self.assertAlmostEqual(lignes[0].montant, 8.50)

    def test_tva_particulier_2_1_pourcent(self):
        texte = "TVA 2,1% 3,15"
        lignes = parser_facture(texte)
        self.assertEqual(lignes[0].code_prelevement, "TVA_PARTICULIER")
        self.assertAlmostEqual(lignes[0].montant, 3.15)

    def test_taux_inconnu_hors_tolerance(self):
        # 8% ne correspond à aucun taux français connu (le plus proche est
        # 10%, à 2 points d'écart -> hors tolérance de 0.3 point).
        texte = "TVA 8% 4,00"
        lignes = parser_facture(texte)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0].code_prelevement)
        self.assertAlmostEqual(lignes[0].taux_detecte, 8.0)

    def test_ligne_sans_tva_ignoree(self):
        texte = "Total HT 226,00 €\nTotal TTC 271,20 €"
        lignes = parser_facture(texte)
        self.assertEqual(len(lignes), 0)

    def test_facture_multi_lignes_plusieurs_taux(self):
        texte = (
            "FACTURE N° 2026-0142\n"
            "Prestation de conseil ............ 500,00 € HT\n"
            "TVA 20,0% .......................... 100,00 €\n"
            "Livre technique .................... 45,00 € HT\n"
            "TVA 5,5% ............................ 2,48 €\n"
            "Total TTC ........................... 647,48 €\n"
        )
        lignes = parser_facture(texte)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0].code_prelevement, "TVA_NORMAL")
        self.assertAlmostEqual(lignes[0].montant, 100.00)
        self.assertEqual(lignes[1].code_prelevement, "TVA_REDUIT")
        self.assertAlmostEqual(lignes[1].montant, 2.48)


if __name__ == "__main__":
    unittest.main()
