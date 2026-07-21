"""Diagnostic de qualité d'une image avant/après OCR — pour avertir
l'utilisateur quand la reconnaissance risque d'être peu fiable, plutôt que
de lui présenter silencieusement des données probablement fausses.

CALIBRAGE : les seuils ci-dessous ont été choisis empiriquement à partir de
3 vrais tickets de caisse fournis pendant le développement (qualités très
différentes : un ticket net, un ticket "mauvaise qualité de scan", et un
ticket à très basse résolution), en comparant le score de confiance moyen
de Tesseract à la qualité RÉELLE des données extraites sur chacun.

Point méthodologique important : une métrique de netteté classique (la
variance du Laplacien de l'image, méthode usuelle de détection de flou) a
été testée EN PREMIER LIEU mais s'est révélée peu fiable sur ces images
réelles — elle ne se corrélait pas avec la qualité effective de
reconnaissance (perturbée par la texture de l'arrière-plan, les artefacts
JPEG, les plis du papier...). La confiance native retournée par Tesseract
lui-même (pytesseract.image_to_data) s'est avérée un bien meilleur
indicateur, car elle reflète directement l'incertitude du moteur de
reconnaissance plutôt qu'une caractéristique indirecte de l'image.

LIMITES ASSUMÉES :
  - Seuils calibrés sur seulement 3 images réelles — à affiner avec l'usage
    réel du logiciel (plus d'exemples variés).
  - La confiance Tesseract peut être basse sur un document par ailleurs
    lisible mais atypique (police inhabituelle, mise en page complexe) —
    ce n'est pas une garantie absolue, seulement un signal utile.
  - N'évalue pas la pertinence du CONTENU (ex : un document flou pour un
    humain mais où les zones de texte utiles sont nettes ne sera pas
    forcément mal noté, et inversement).
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytesseract
from pytesseract import Output

from .ocr import LANGUE_PAR_DEFAUT, _pretraiter_avec_cv2, _pretraiter_avec_pil, _CV2_DISPONIBLE

# Seuils de confiance moyenne Tesseract (0-100), calibrés empiriquement —
# voir docstring du module.
SEUIL_BON = 65.0
SEUIL_MOYEN = 45.0

# Résolution minimale recommandée (plus petite dimension, en pixels) — en
# dessous, on avertit même si la confiance OCR est correcte, car une
# résolution trop faible limite structurellement la reconnaissance possible.
SEUIL_RESOLUTION_FAIBLE = 500


@dataclass
class DiagnosticQualite:
    """Résultat du diagnostic de qualité d'une image.

    Attributes:
        niveau: 'bon', 'moyen', ou 'insuffisant'.
        confiance_moyenne: score de confiance moyen Tesseract (0-100).
        resolution: (largeur, hauteur) en pixels.
        avertissements: messages en français, prêts à afficher à
            l'utilisateur, expliquant les problèmes détectés. Liste vide si
            niveau == 'bon'.
    """

    niveau: str
    confiance_moyenne: float
    resolution: tuple[int, int]
    avertissements: list[str] = field(default_factory=list)


def _calculer_confiance_ocr(image_pretraitee, langue: str, psm: int) -> float:
    donnees = pytesseract.image_to_data(
        image_pretraitee, lang=langue, config=f"--psm {psm}", output_type=Output.DICT
    )
    confiances = [int(c) for c in donnees["conf"] if int(c) >= 0]
    return sum(confiances) / len(confiances) if confiances else 0.0


def diagnostiquer_qualite(
    chemin_image: str | Path, langue: str = LANGUE_PAR_DEFAUT, psm: int = 4
) -> DiagnosticQualite:
    """Évalue la qualité d'une image pour l'OCR et produit des avertissements
    prêts à afficher à l'utilisateur si la reconnaissance risque d'être peu
    fiable.

    Args:
        chemin_image: chemin vers le fichier image.
        langue: code langue Tesseract (défaut : 'fra').
        psm: mode de segmentation Tesseract (voir ocr.py).

    Returns:
        Un DiagnosticQualite. Toujours à afficher à l'utilisateur si
        `avertissements` n'est pas vide — mais ne bloque JAMAIS l'import :
        le document reste 'a_valider', l'utilisateur reste libre de valider
        ou corriger les données malgré l'avertissement.
    """
    from PIL import Image

    with Image.open(chemin_image) as image:
        resolution = image.size  # (largeur, hauteur)

    image_pretraitee = _pretraiter_avec_cv2(chemin_image) if _CV2_DISPONIBLE else _pretraiter_avec_pil(chemin_image)
    confiance_moyenne = _calculer_confiance_ocr(image_pretraitee, langue, psm)

    avertissements: list[str] = []

    if confiance_moyenne >= SEUIL_BON:
        niveau = "bon"
    elif confiance_moyenne >= SEUIL_MOYEN:
        niveau = "moyen"
        avertissements.append(
            "La qualité de reconnaissance de ce document est moyenne : certains montants "
            "ou libellés peuvent être mal reconnus. Vérifiez attentivement les valeurs "
            "extraites avant de valider."
        )
    else:
        niveau = "insuffisant"
        avertissements.append(
            "La qualité de reconnaissance de ce document semble insuffisante pour une "
            "extraction fiable. Si possible, reprenez la photo avec un meilleur éclairage, "
            "une meilleure mise au point, et en évitant les plis ou reflets sur le papier — "
            "ou scannez le document plutôt que de le photographier."
        )

    if min(resolution) < SEUIL_RESOLUTION_FAIBLE:
        avertissements.append(
            f"L'image fournie est de petite taille ({resolution[0]}x{resolution[1]} pixels). "
            f"Une résolution plus élevée (photo prise de plus près, ou scan plutôt que photo) "
            f"améliorerait la fiabilité de la reconnaissance."
        )

    return DiagnosticQualite(
        niveau=niveau,
        confiance_moyenne=confiance_moyenne,
        resolution=resolution,
        avertissements=avertissements,
    )
