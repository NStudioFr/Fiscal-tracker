import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.avis_imposition import parser_avis_imposition


class TestParserAvisImposition(unittest.TestCase):
    def test_impot_revenu_a_payer(self):
        texte = (
            "DIRECTION GENERALE DES FINANCES PUBLIQUES\n"
            "AVIS D'IMPOT SUR LE REVENU 2026\n"
            "Revenu net imposable                    38 500\n"
            "Impot sur le revenu net a payer          2 103,99\n"
        )
        resultat = parser_avis_imposition(texte)
        self.assertEqual(resultat.code_prelevement, "IR_BAREME")
        self.assertAlmostEqual(resultat.montant, 2103.99)

    def test_montant_a_rembourser_est_negatif(self):
        texte = "Montant a vous rembourser                 450,00"
        resultat = parser_avis_imposition(texte)
        self.assertEqual(resultat.code_prelevement, "IR_BAREME")
        self.assertAlmostEqual(resultat.montant, -450.00)

    def test_taxe_fonciere(self):
        texte = (
            "AVIS DE TAXE FONCIERE 2026\n"
            "Taxe foncière sur les propriétés bâties\n"
            "Montant total a payer avant le 15/10/2026    1 840,00\n"
        )
        resultat = parser_avis_imposition(texte)
        self.assertEqual(resultat.code_prelevement, "TAXE_FONCIERE")
        self.assertAlmostEqual(resultat.montant, 1840.00)

    def test_taxe_habitation_residence_secondaire(self):
        texte = "Taxe d'habitation sur les résidences secondaires    980,00"
        resultat = parser_avis_imposition(texte)
        self.assertEqual(resultat.code_prelevement, "TAXE_HABITATION_RESIDENCE_SECONDAIRE")
        self.assertAlmostEqual(resultat.montant, 980.00)

    def test_document_non_reconnu(self):
        texte = "Un document quelconque sans rapport avec les impots\nMontant : 42,00"
        resultat = parser_avis_imposition(texte)
        self.assertIsNone(resultat.code_prelevement)
        self.assertIsNone(resultat.montant)

    def test_montant_avec_symbole_euro(self):
        texte = "Solde a payer 556,00 €"
        resultat = parser_avis_imposition(texte)
        self.assertEqual(resultat.code_prelevement, "IR_BAREME")
        self.assertAlmostEqual(resultat.montant, 556.00)


if __name__ == "__main__":
    unittest.main()
