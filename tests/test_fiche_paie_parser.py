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

from ingestion.fiche_paie import (
    parser_fiche_paie,
    _extraire_montant_salarial,
    _identifier_code_prelevement,
    _normaliser,
)


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


class TestParserFichePaieFormatReel(unittest.TestCase):
    """Tests basés sur le texte d'un vrai bulletin de paie généré par un
    logiciel de paie commercial (QuickPaie.com), avec colonnes salarial ET
    patronal explicites et des taux à 4 décimales — révèle des cas que le
    format simplifié de test (2 colonnes) ne couvrait pas.
    """

    def test_csg_deductible_ligne_reelle_sans_part_patronale(self):
        # Ligne réelle : "Dont déductible de l'impôt sur le revenu   3 733,50   6,8000   253,88   -"
        # Le tiret final indique l'absence de part patronale sur cette ligne.
        ligne = "Dont déductible de l'impôt sur le revenu 3 733,50 6,8000 253,88 -"
        montant = _extraire_montant_salarial(ligne)
        self.assertAlmostEqual(montant, 253.88)
        code = _identifier_code_prelevement(_normaliser(ligne))
        self.assertEqual(code, "CSG_DEDUCTIBLE")

    def test_csg_non_deductible_ligne_reelle(self):
        ligne = "Dont non déductible de l'impôt sur le revenu 3 733,50 2,9000 108,27 -"
        montant = _extraire_montant_salarial(ligne)
        self.assertAlmostEqual(montant, 108.27)
        code = _identifier_code_prelevement(_normaliser(ligne))
        self.assertEqual(code, "CSG_NON_DEDUCTIBLE")

    def test_retraite_plafonnee_avec_part_patronale_prend_bien_le_salarial(self):
        # Ligne réelle avec LES DEUX parts : salarial (262,20) ET patronal (324,90).
        # Le piège : prendre "le dernier nombre" donnerait 324,90 (patronal),
        # alors qu'on veut 262,20 (salarial, ce que paie réellement la personne).
        ligne = "Retraite plafonnée 3 800,00 6,9000 262,20 8,5500 324,90"
        montant = _extraire_montant_salarial(ligne)
        self.assertAlmostEqual(montant, 262.20)  # PAS 324.90
        code = _identifier_code_prelevement(_normaliser(ligne))
        self.assertEqual(code, "COTIS_VIEILLESSE_PLAF")

    def test_retraite_deplafonnee_avec_part_patronale(self):
        ligne = "Retraite déplafonnée 3 800,00 0,4000 15,20 2,0200 76,76"
        montant = _extraire_montant_salarial(ligne)
        self.assertAlmostEqual(montant, 15.20)  # PAS 76.76
        code = _identifier_code_prelevement(_normaliser(ligne))
        self.assertEqual(code, "COTIS_VIEILLESSE_DEPLAF")

    def test_ligne_100_pourcent_patronale_sans_part_salariale_ignoree(self):
        # "Allocations familiales" : taux salarial = "-" (aucune part salariale).
        # Le module ne doit PAS extraire le taux/montant patronal par erreur.
        ligne = "Allocations familiales 3 800,00 - 5,2500 199,50"
        montant = _extraire_montant_salarial(ligne)
        self.assertIsNone(montant)

    def test_document_reel_quickpaie_extrait_les_bons_montants(self):
        # Extrait fidèle (texte) du bulletin réel QuickPaie "Cadre Syntec +
        # Titres restaurant" (01-marie-laurent.pdf), pour validation de bout
        # en bout sur un format professionnel réel.
        texte = (
            "Salaire de base 151,67 25,0500 3 800,00\n"
            "Cotisation maladie - maternité - invalidité - décès 3 800,00 0,0000 - 13,0000 494,00\n"
            "Retraite plafonnée 3 800,00 6,9000 262,20 8,5500 324,90\n"
            "Retraite déplafonnée 3 800,00 0,4000 15,20 2,0200 76,76\n"
            "Dont déductible de l'impôt sur le revenu 3 733,50 6,8000 253,88 -\n"
            "Dont non déductible de l'impôt sur le revenu 3 733,50 2,9000 108,27 -\n"
        )
        lignes = parser_fiche_paie(texte)
        par_code = {l.code_prelevement: l.montant for l in lignes if l.code_prelevement}
        self.assertAlmostEqual(par_code["COTIS_VIEILLESSE_PLAF"], 262.20)
        self.assertAlmostEqual(par_code["COTIS_VIEILLESSE_DEPLAF"], 15.20)
        self.assertAlmostEqual(par_code["CSG_DEDUCTIBLE"], 253.88)
        self.assertAlmostEqual(par_code["CSG_NON_DEDUCTIBLE"], 108.27)
        # La ligne "Cotisation maladie" n'a pas d'alias reconnu (hors périmètre),
        # mais ne doit pas non plus faire planter le parsing.


if __name__ == "__main__":
    unittest.main()
