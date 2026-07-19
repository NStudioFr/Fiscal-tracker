"""Tests unitaires du parser de fiche de paie (Lot OCR/parsing).

Ces tests travaillent directement sur du texte (simulant une sortie OCR
imparfaite mais plausible), sans dépendre de Tesseract — rapides et
déterministes. Les tests avec une vraie image (OCR réel) sont dans
test_ocr_integration.py.
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.fiche_paie import parser_fiche_paie


class TestParserFichePaie(unittest.TestCase):
    def test_reconnait_csg_deductible(self):
        texte = "CSG déductible de l'impôt sur le revenu    98,25    6,80    668,25"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].code_prelevement, "CSG_DEDUCTIBLE")
        self.assertAlmostEqual(lignes[0].montant, 668.25)

    def test_reconnait_csg_crds_non_deductible_combinee(self):
        texte = "CSG/CRDS non déductible                    98,25    2,90    284,93"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].code_prelevement, "CSG_NON_DEDUCTIBLE")
        self.assertAlmostEqual(lignes[0].montant, 284.93)

    def test_reconnait_vieillesse_plafonnee(self):
        texte = "Assurance vieillesse plafonnée    3925.00    6.90    270.83"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(lignes[0].code_prelevement, "COTIS_VIEILLESSE_PLAF")
        self.assertAlmostEqual(lignes[0].montant, 270.83)

    def test_reconnait_vieillesse_deplafonnee(self):
        texte = "Assurance vieillesse déplafonnée    3925.00    0.40    15.70"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(lignes[0].code_prelevement, "COTIS_VIEILLESSE_DEPLAF")
        self.assertAlmostEqual(lignes[0].montant, 15.70)

    def test_ligne_sans_montant_ignoree(self):
        texte = "Bulletin de paie de Madame Dupont Jeanne\nPériode : Juin 2026"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(len(lignes), 0)

    def test_ligne_avec_montant_sans_alias_conservee_sans_code(self):
        texte = "Mutuelle obligatoire    45,50    12,30    35,20"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0].code_prelevement)
        self.assertAlmostEqual(lignes[0].montant, 35.20)

    def test_montant_avec_espace_insecable_milliers(self):
        texte = "Salaire brut                                    1\u00a0234,56"
        lignes = parser_fiche_paie(texte)
        self.assertEqual(len(lignes), 1)
        self.assertAlmostEqual(lignes[0].montant, 1234.56)

    def test_document_complet_plusieurs_lignes(self):
        texte = (
            "BULLETIN DE PAIE - Juin 2026\n"
            "Salaire de base                    151.67    22.00    3336.74\n"
            "CSG déductible de l'impôt sur le revenu    3280.86    6.80    223.10\n"
            "CSG/CRDS non déductible                    3280.86    2.90    95.14\n"
            "Assurance vieillesse plafonnée      3280.86    6.90    226.38\n"
            "Assurance vieillesse déplafonnée    3336.74    0.40    13.35\n"
            "Net à payer avant impôt                              2650.00\n"
        )
        lignes = parser_fiche_paie(texte)
        codes_trouves = [l.code_prelevement for l in lignes if l.code_prelevement]
        self.assertIn("CSG_DEDUCTIBLE", codes_trouves)
        self.assertIn("CSG_NON_DEDUCTIBLE", codes_trouves)
        self.assertIn("COTIS_VIEILLESSE_PLAF", codes_trouves)
        self.assertIn("COTIS_VIEILLESSE_DEPLAF", codes_trouves)
        # 6 lignes ont un montant en fin de ligne (salaire de base, 4 cotisations, net à payer)
        self.assertEqual(len(lignes), 6)


if __name__ == "__main__":
    unittest.main()
