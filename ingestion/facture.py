"""Parsing d'une facture (professionnelle ou commerce) à partir du texte
OCR brut : extraction des lignes de TVA par taux.

APPROCHE : contrairement à la fiche de paie (libellés variables selon
l'éditeur de paie) ou au ticket de caisse (libellés produits infiniment
variables), une facture française doit légalement afficher explicitement
le TAUX de TVA à côté de chaque montant de TVA (obligation de facturation,
art. 242 nonies A du CGI, annexe II). Ce module exploite cette régularité :
il cherche des lignes contenant "TVA" ET un taux en pourcentage, puis
rattache le montant de la ligne au prélèvement TVA correspondant à ce taux
(sans avoir besoin de connaître le libellé exact utilisé par le logiciel de
facturation, contrairement à la fiche de paie).

Le taux extrait est comparé aux 4 taux de TVA connus de fiscal_engine (20%,
10%, 5,5%, 2,1%) avec une tolérance de ±0,3 point (pour absorber une petite
imprécision OCR sur la décimale, ex "5,5%" mal lu "55%" serait hors
tolérance et à raison — mieux vaut ne rien reconnaître qu'associer au
mauvais taux). Si le taux ne correspond à aucun taux connu à cette
tolérance, la ligne est renvoyée avec code_prelevement=None (revue manuelle).

LIMITES ASSUMÉES :
  - Ne reconnaît que les lignes où le taux de TVA est EXPLICITEMENT présent
    sur la même ligne que son montant (format standard, mais une facture
    pourrait présenter un tableau récapitulatif dissocié — non géré ici).
  - Une facture avec plusieurs lignes à un même taux de TVA (une par
    produit) donnera plusieurs lignes reconnues avec le même
    code_prelevement — c'est correct, elles seront simplement sommées à
    l'agrégation (fiscal_engine.aggregator).
  - Ne calcule aucun rapprochement HT/TVA/TTC (ex : vérifier que TTC = HT +
    TVA) — cela reste à la charge de l'utilisateur (statut 'a_valider').
"""

import re
from dataclasses import dataclass

from .texte_utils import extraire_dernier_montant, normaliser

# Cherche un taux en pourcentage : "20%", "20,0 %", "5,5%"...
_REGEX_TAUX_POURCENTAGE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")

# Taux de TVA connus de fiscal_engine (voir seed_data/fr_seed_lot3.sql),
# avec le code de prélèvement correspondant. Tolérance de rapprochement :
# ±0,3 point, pour absorber une petite imprécision OCR sans risquer de
# confondre deux taux légitimement différents (ex : 10% et 5,5% restent
# bien distincts avec cette tolérance).
_TAUX_TVA_CONNUS = {
    20.0: "TVA_NORMAL",
    10.0: "TVA_INTERMEDIAIRE",
    5.5: "TVA_REDUIT",
    2.1: "TVA_PARTICULIER",
}
_TOLERANCE_TAUX = 0.3


def _identifier_taux_tva(taux_detecte: float) -> str | None:
    for taux_connu, code in _TAUX_TVA_CONNUS.items():
        if abs(taux_detecte - taux_connu) <= _TOLERANCE_TAUX:
            return code
    return None


@dataclass
class LigneFactureExtraite:
    """Une ligne de TVA reconnue sur une facture.

    Attributes:
        libelle_brut: texte de la ligne OCR, tel quel.
        montant: montant de TVA extrait de la ligne.
        taux_detecte: taux en pourcentage tel que lu sur le document (ex : 20.0).
        code_prelevement: code du prélèvement TVA correspondant (ex :
            'TVA_NORMAL'), ou None si le taux détecté ne correspond à aucun
            taux connu à la tolérance près.
    """

    libelle_brut: str
    montant: float
    taux_detecte: float
    code_prelevement: str | None


def parser_facture(texte_ocr: str) -> list[LigneFactureExtraite]:
    """Extrait les lignes de TVA d'une facture.

    Args:
        texte_ocr: texte brut renvoyé par ingestion.ocr.extraire_texte_image.

    Returns:
        Liste des lignes de TVA reconnues, dans l'ordre d'apparition.
        Seules les lignes contenant explicitement "TVA" ET un taux en
        pourcentage ET un montant sont retenues.
    """
    lignes_extraites: list[LigneFactureExtraite] = []

    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            continue

        ligne_normalisee = normaliser(ligne)
        if "tva" not in ligne_normalisee:
            continue

        match_taux = _REGEX_TAUX_POURCENTAGE.search(ligne)
        if not match_taux:
            continue
        try:
            taux_detecte = float(match_taux.group(1).replace(",", "."))
        except ValueError:
            continue

        montant = extraire_dernier_montant(ligne)
        if montant is None:
            continue

        code = _identifier_taux_tva(taux_detecte)
        lignes_extraites.append(
            LigneFactureExtraite(libelle_brut=ligne, montant=montant, taux_detecte=taux_detecte, code_prelevement=code)
        )

    return lignes_extraites
