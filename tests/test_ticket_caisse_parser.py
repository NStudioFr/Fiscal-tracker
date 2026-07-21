"""Tests unitaires du parser de ticket de caisse.

Les tests de bloc TVA/totaux catégorie ci-dessous reprennent des extraits
RÉELS (texte OCR obtenu via un vrai pipeline Tesseract, pas une saisie
manuelle) d'un ticket Carrefour fourni pendant le développement — y compris
ses imperfections d'OCR (symbole '%' parfois perdu, '€' collé aux chiffres,
tokens parasites). Ce sont ces imperfections précises qui ont permis de
détecter et corriger deux bugs réels avant livraison (voir texte_utils.py
et ticket_caisse.py pour le détail).
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.ticket_caisse import (
    extraire_tva_ticket,
    extraire_totaux_categories,
    detecter_rayons,
)


class TestExtraireTvaTicket(unittest.TestCase):
    def test_bloc_tva_reel_carrefour(self):
        # Extrait OCR réel (avec ses imperfections : '%' perdu ligne 1,
        # tokens parasites 'na', '9' lignes 2-3).
        texte = (
            "TVA 4: 5,50% € 34,14 1,91\n"
            "TVA 5:10,00% € na 3,99€ 9 0,39\n"
            "TVA 6:20,00% € mT 1,44\n"
            "==== TOTAL TVA € 3,14\n"
        )
        lignes = extraire_tva_ticket(texte)
        self.assertEqual(len(lignes), 3)  # la ligne "TOTAL TVA" ne doit PAS être comptée comme un taux
        self.assertEqual(lignes[0].code_prelevement, "TVA_REDUIT")
        self.assertAlmostEqual(lignes[0].montant, 1.91)
        self.assertEqual(lignes[1].code_prelevement, "TVA_INTERMEDIAIRE")
        self.assertAlmostEqual(lignes[1].montant, 0.39)  # PAS 90.39 (bug de fusion corrigé)
        self.assertEqual(lignes[2].code_prelevement, "TVA_NORMAL")
        self.assertAlmostEqual(lignes[2].montant, 1.44)

    def test_pourcent_perdu_par_ocr_toujours_reconnu(self):
        # Le signe '%' de la ligne reelle a ete lu "5,504" (le '%' confondu
        # avec un '4') : le taux doit quand meme etre reconnu par proximite.
        ligne = "TVA 4: 5,504 € 34,14 1,91"
        lignes = extraire_tva_ticket(ligne)
        self.assertEqual(len(lignes), 1)
        self.assertAlmostEqual(lignes[0].taux_detecte, 5.504)
        self.assertEqual(lignes[0].code_prelevement, "TVA_REDUIT")  # 5.504 reste dans la tolerance de 5.5

    def test_somme_des_tva_egale_au_vrai_total(self):
        texte = (
            "TVA 4: 5,50% € 34,74 1,91\n"
            "TVA 5:10,00% € 3,95 0,39\n"
            "TVA 6:20,00% € 7,17 1,44\n"
        )
        lignes = extraire_tva_ticket(texte)
        self.assertAlmostEqual(sum(l.montant for l in lignes), 3.74)

    def test_taux_inconnu_renvoie_code_none(self):
        ligne = "TVA 9: 8,00% € 10,00 0,80"
        lignes = extraire_tva_ticket(ligne)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0].code_prelevement)

    def test_ligne_sans_tva_ignoree(self):
        texte = "Total Alimentaire 42,14\n17 ARTICLES TOTAL A PAYER 49,60"
        lignes = extraire_tva_ticket(texte)
        self.assertEqual(len(lignes), 0)


class TestExtraireTotauxCategories(unittest.TestCase):
    def test_totaux_reels_carrefour(self):
        texte = (
            "Total Alimentaire 42,14\n"
            "Total Entretien Hyg-Beauté 2,41\n"
            "Total Non Aliment: 4,99\n"
        )
        totaux = extraire_totaux_categories(texte)
        self.assertEqual(len(totaux), 3)
        self.assertEqual(totaux[0].type_depense_code, "ALIMENTATION")
        self.assertAlmostEqual(totaux[0].montant, 42.14)
        self.assertEqual(totaux[1].type_depense_code, "HYGIENE_ENTRETIEN")
        self.assertEqual(totaux[2].type_depense_code, "AUTRE")
        self.assertAlmostEqual(totaux[2].montant, 4.99)

    def test_total_a_payer_et_total_tva_exclus(self):
        texte = (
            "17 ARTICLES TOTAL A PAYER 49,60\n"
            "==== TOTAL TVA € 3,74\n"
            "Total Alimentaire 42,14\n"
        )
        totaux = extraire_totaux_categories(texte)
        self.assertEqual(len(totaux), 1)
        self.assertEqual(totaux[0].type_depense_code, "ALIMENTATION")

    def test_categorie_inconnue_conservee_sans_code(self):
        texte = "Total Bazar 15,00"
        totaux = extraire_totaux_categories(texte)
        self.assertEqual(len(totaux), 1)
        self.assertIsNone(totaux[0].type_depense_code)


class TestDetecterRayons(unittest.TestCase):
    def test_en_tetes_etoiles(self):
        texte = (
            "** FRUITS FRAIS\n"
            "50027 ANANAS L\n"
            "50028 ANANAS IMPORT\n"
            "** LEGUMES FRAIS\n"
            "50061 OIGNON SEC BQP\n"
        )
        rayons = detecter_rayons(texte)
        self.assertEqual(len(rayons), 2)
        self.assertEqual(rayons[0][0], "FRUITS FRAIS")
        self.assertEqual(len(rayons[0][1]), 2)
        self.assertEqual(rayons[1][0], "LEGUMES FRAIS")

    def test_en_tetes_chevrons_nombre_variable(self):
        # Le nombre de '>' reconnus par l'OCR peut varier (2, 3, ou 4).
        texte = ">>> ENTRETIEN\nNETT.CUIS/SDB 2,18\n>> EPICERIE\nCAFE 5,55\n"
        rayons = detecter_rayons(texte)
        self.assertEqual(rayons[0][0], "ENTRETIEN")
        self.assertEqual(rayons[1][0], "EPICERIE")

    def test_lignes_avant_premier_rayon_ignorees(self):
        texte = "NOM DU MAGASIN\nAdresse\n** EPICERIE\nProduit 1,00\n"
        rayons = detecter_rayons(texte)
        self.assertEqual(len(rayons), 1)
        self.assertEqual(rayons[0][0], "EPICERIE")


if __name__ == "__main__":
    unittest.main()
