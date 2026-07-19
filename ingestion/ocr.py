"""Extraction de texte brut depuis une image de document, via Tesseract OCR.

Tesseract est utilisé en local via pytesseract — aucun appel réseau, aucune
dépendance à un service cloud (Google Vision, AWS Textract, etc.), conforme
à l'objectif de confidentialité du projet posé dès le départ.

Un prétraitement d'image minimal (niveaux de gris + amélioration du
contraste) est appliqué avant l'OCR : Tesseract est nettement plus fiable
sur une image nette en noir et blanc que sur une photo brute (ombres,
légère inclinaison, arrière-plan coloré d'un ticket de caisse...).

LIMITES ASSUMÉES :
  - Le prétraitement ici est volontairement simple (pas de correction de
    perspective/rotation, pas de suppression de bruit avancée). Une photo
    prise de travers ou floue dégradera la qualité de reconnaissance —
    c'est pourquoi chaque document importé reste 'a_valider' par défaut
    (voir schema.sql), jamais automatiquement approuvé.
  - La langue par défaut est le français ('fra'). D'autres langues peuvent
    être passées explicitement (ex : 'eng', 'spa') si le pack correspondant
    est installé sur la machine.
"""

from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

LANGUE_PAR_DEFAUT = "fra"


def _pretraiter_image(image: Image.Image) -> Image.Image:
    """Convertit en niveaux de gris et étire le contraste — améliore
    sensiblement la reconnaissance sur des photos de tickets/documents pris
    dans des conditions d'éclairage variables.
    """
    image_grise = image.convert("L")
    return ImageOps.autocontrast(image_grise)


def extraire_texte_image(chemin_image: str | Path, langue: str = LANGUE_PAR_DEFAUT) -> str:
    """Extrait le texte brut d'une image via Tesseract OCR.

    Args:
        chemin_image: chemin vers le fichier image (jpg, png...).
        langue: code langue Tesseract (défaut : 'fra'). Le pack de langue
            correspondant doit être installé sur la machine
            (ex : `apt install tesseract-ocr-fra` sous Ubuntu/Debian).

    Returns:
        Le texte brut reconnu, tel quel (aucune interprétation structurelle
        — c'est le rôle des modules de parsing dans ingestion/*_parser.py
        ou ingestion/fiche_paie.py etc.).
    """
    with Image.open(chemin_image) as image:
        image_pretraitee = _pretraiter_image(image)
        return pytesseract.image_to_string(image_pretraitee, lang=langue)
