"""Extraction de texte brut depuis une image de document, via Tesseract OCR.

Tesseract est utilisé en local via pytesseract — aucun appel réseau, aucune
dépendance à un service cloud (Google Vision, AWS Textract, etc.), conforme
à l'objectif de confidentialité du projet posé dès le départ.

PRÉTRAITEMENT : la qualité du prétraitement d'image a un impact considérable
sur la fiabilité de l'OCR — constaté empiriquement sur de vrais tickets de
caisse fournis pendant le développement (voir tests/fixtures/tickets_reels/).
Un simple passage en niveaux de gris + contraste (v1 de ce module) donnait
des résultats significativement dégradés sur une photo de ticket avec
ombres/plis par rapport à un pipeline plus complet :
  1. Niveaux de gris
  2. Redimensionnement (upscale x1.5) — améliore la résolution effective du
     texte, utile sur les photos de petite taille ou les petits caractères
     de ticket de caisse.
  3. Débruitage (fastNlMeansDenoising) — réduit le grain/bruit de capteur
     photo qui perturbe la reconnaissance de caractères fins.
  4. PAS de binarisation/seuillage. Deux approches ont été testées (seuil
     adaptatif, puis seuil global d'Otsu) et toutes deux se sont révélées
     CONTRE-PRODUCTIVES sur certains documents : elles introduisaient des
     confusions de chiffres (ex : '0' lu comme '8') qui n'apparaissaient PAS
     sans binarisation. Le simple niveaux de gris + débruitage s'est avéré
     le meilleur compromis sur l'ensemble des documents testés (synthétiques
     ET vraie photo de ticket bruitée) — la binarisation n'a donc pas été
     retenue dans la version finale de ce pipeline.

Ce pipeline utilise OpenCV (cv2) plutôt que PIL seul pour ces étapes, OpenCV
étant nettement mieux outillé pour ce type de traitement d'image. Un
fallback vers un prétraitement PIL plus simple est prévu si OpenCV n'est pas
installé sur la machine (fonctionnalité dégradée mais pas d'erreur bloquante).

LIMITES ASSUMÉES :
  - Pas de correction de perspective/rotation (photo prise de travers) —
    Tesseract reste sensible à une inclinaison prononcée.
  - Les paramètres de seuillage (taille de bloc, constante C) sont des
    valeurs par défaut raisonnables, pas calibrées automatiquement par image
    — une image très atypique peut nécessiter un réglage différent.
  - La langue par défaut est le français ('fra'). Le pack de langue
    correspondant doit être installé sur la machine.
  - Quelle que soit la qualité du prétraitement, l'OCR reste probabiliste :
    chaque document importé reste 'a_valider' par défaut (schema.sql).
"""

from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageOps

LANGUE_PAR_DEFAUT = "fra"
_SEUIL_PETITE_RESOLUTION = 400  # pixels ; en-dessous, un upscale aide l'OCR

try:
    import cv2

    _CV2_DISPONIBLE = True
except ImportError:
    _CV2_DISPONIBLE = False


def _pretraiter_avec_cv2(chemin_image: str | Path) -> Image.Image:
    image_cv = cv2.imread(str(chemin_image))
    gris = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

    # Le redimensionnement (upscale) n'aide QUE les images de petite
    # résolution (ex : 300x497px) — appliqué systématiquement, il dégrade
    # au contraire l'analyse de mise en page de Tesseract sur des images
    # déjà bien dimensionnées (régression détectée en testant : une image
    # nette de 900x650px voyait ses colonnes libellé/montant scindées à
    # tort après upscale). Seuil : on ne redimensionne que si la plus
    # petite dimension est sous SEUIL_PETITE_RESOLUTION.
    hauteur, largeur = gris.shape
    if min(hauteur, largeur) < _SEUIL_PETITE_RESOLUTION:
        gris = cv2.resize(gris, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    debruite = cv2.fastNlMeansDenoising(gris, h=10)
    return Image.fromarray(debruite)


def _pretraiter_avec_pil(chemin_image: str | Path) -> Image.Image:
    """Repli utilisé si OpenCV n'est pas installé — moins performant sur
    des photos difficiles (ombres, plis), mais fonctionnel.
    """
    with Image.open(chemin_image) as image:
        image_grise = image.convert("L")
        return ImageOps.autocontrast(image_grise)


def extraire_texte_image(
    chemin_image: str | Path, langue: str = LANGUE_PAR_DEFAUT, psm: int = 4
) -> str:
    """Extrait le texte brut d'une image via Tesseract OCR.

    Args:
        chemin_image: chemin vers le fichier image (jpg, png...).
        langue: code langue Tesseract (défaut : 'fra'). Le pack de langue
            correspondant doit être installé sur la machine
            (ex : `apt install tesseract-ocr-fra` sous Ubuntu/Debian).
        psm: mode de segmentation de page Tesseract ("Page Segmentation
            Mode"). 4 (défaut) suppose une colonne de texte de tailles
            variables — plus adapté aux tickets de caisse et factures qu'au
            mode par défaut de Tesseract (conçu pour une page de texte
            homogène). Voir `tesseract --help-psm` pour les autres valeurs.

    Returns:
        Le texte brut reconnu, tel quel (aucune interprétation structurelle
        — c'est le rôle des modules de parsing dans ingestion/*.py).
    """
    image_pretraitee = _pretraiter_avec_cv2(chemin_image) if _CV2_DISPONIBLE else _pretraiter_avec_pil(chemin_image)
    return pytesseract.image_to_string(image_pretraitee, lang=langue, config=f"--psm {psm}")


def extraire_texte_avec_diagnostic(
    chemin_image: str | Path, langue: str = LANGUE_PAR_DEFAUT, psm: int = 4
):
    """Point d'entrée recommandé pour une interface utilisateur : renvoie à
    la fois le texte OCR ET un diagnostic de qualité prêt à afficher.

    Contrairement à extraire_texte_image (texte seul), cette fonction permet
    à l'appelant de savoir si le résultat est fiable avant de le présenter
    à l'utilisateur comme s'il était certain — voir ingestion.qualite pour
    le détail du diagnostic (seuils calibrés sur de vrais tickets de caisse).

    Returns:
        Un tuple (texte: str, diagnostic: ingestion.qualite.DiagnosticQualite).
    """
    from .qualite import diagnostiquer_qualite  # import local pour éviter un cycle (qualite importe déjà ocr)

    texte = extraire_texte_image(chemin_image, langue=langue, psm=psm)
    diagnostic = diagnostiquer_qualite(chemin_image, langue=langue, psm=psm)
    return texte, diagnostic
