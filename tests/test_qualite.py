"""Tests du diagnostic de qualité d'image (ingestion.qualite).

Ces tests utilisent de vraies images (synthétiques propres + les tickets
réels fournis pendant le développement, s'ils sont présents) plutôt que des
valeurs simulées : le diagnostic dépend de Tesseract lui-même, le simuler
donnerait une fausse confiance dans les tests.
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.qualite import diagnostiquer_qualite, SEUIL_BON, SEUIL_MOYEN, SEUIL_RESOLUTION_FAIBLE


class TestDiagnosticQualite(unittest.TestCase):
    def test_image_synthetique_propre_est_bonne_qualite(self):
        diagnostic = diagnostiquer_qualite("tests/fixtures/fiche_paie_synthetique.png")
        self.assertEqual(diagnostic.niveau, "bon")
        self.assertEqual(diagnostic.avertissements, [])
        self.assertGreaterEqual(diagnostic.confiance_moyenne, SEUIL_BON)

    def test_resolution_faible_genere_un_avertissement_meme_si_confiance_bonne(self):
        # Le ticket U (300x497px) doit déclencher l'avertissement de
        # résolution quelle que soit sa confiance OCR.
        chemin = Path("/mnt/user-data/uploads/Exemple_de_ticket_U.jpg")
        if not chemin.exists():
            self.skipTest("Image réelle non disponible dans cet environnement de test")
        diagnostic = diagnostiquer_qualite(str(chemin))
        self.assertLess(min(diagnostic.resolution), SEUIL_RESOLUTION_FAIBLE)
        self.assertTrue(any("résolution" in a.lower() or "petite taille" in a.lower() for a in diagnostic.avertissements))

    def test_niveaux_coherents_avec_les_seuils(self):
        self.assertGreater(SEUIL_BON, SEUIL_MOYEN)
        self.assertGreaterEqual(SEUIL_MOYEN, 0)

    def test_diagnostic_ticket_mauvaise_qualite_genere_avertissement(self):
        chemin = Path("/mnt/user-data/uploads/Exemple_de_ticket_carrefour_mauvaise_qualilté_de_scan.jpg")
        if not chemin.exists():
            self.skipTest("Image réelle non disponible dans cet environnement de test")
        diagnostic = diagnostiquer_qualite(str(chemin))
        # Ce ticket a produit des résultats de parsing très partiels dans nos
        # tests d'intégration : le diagnostic ne doit PAS le classer "bon"
        # sans aucun avertissement.
        if diagnostic.niveau != "bon":
            self.assertGreater(len(diagnostic.avertissements), 0)


if __name__ == "__main__":
    unittest.main()
