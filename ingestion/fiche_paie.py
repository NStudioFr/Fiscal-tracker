"""Parsing d'une fiche de paie française à partir du texte OCR brut.

APPROCHE : reconnaissance par mots-clés (alias), pas d'extraction générique.
Depuis 2018, les fiches de paie françaises suivent un modèle simplifié
obligatoire (arrêté du 25/02/2016) avec un nombre restreint de libellés
officiels standardisés — ce qui rend une reconnaissance par mots-clés
nettement plus fiable ici que sur un ticket de caisse (où les libellés de
produits sont infiniment variables d'une enseigne à l'autre).

Chaque ligne reconnue est associée, quand c'est possible, au CODE du
prélèvement correspondant dans fiscal_engine (ex : 'CSG_DEDUCTIBLE') — ce
code peut ensuite être résolu en prelevement_id via une requête SQL et
utilisé directement par fiscal_engine.orchestrator (branche ligne_document
avec prelevement_id renseigné, montant déjà connu).

LIMITES ASSUMÉES :
  - Seuls les prélèvements listés dans ALIAS_PRELEVEMENTS sont reconnus.
    Toute ligne de fiche de paie hors de ce périmètre (mutuelle, prévoyance,
    tickets-restaurant, avantages en nature...) n'est PAS extraite par ce
    module — elle reste dans le texte brut mais sans montant structuré.
  - CSG non déductible et CRDS apparaissent SOUVENT combinées sur une même
    ligne réelle ("CSG/CRDS non déductible"). Ce module reconnaît cette
    ligne combinée et l'attribue ENTIÈREMENT au code 'CSG_NON_DEDUCTIBLE' —
    la CRDS n'est donc PAS extraite séparément dans ce cas, ce qui sous-
    estime le détail par typologie (mais pas le total, qui reste correct
    dans la case CSG). Piste d'amélioration future : reconnaître aussi le
    format non combiné, ou stocker un taux nominal de référence par règle
    pour permettre une répartition proportionnelle fiable.
  - Suppose qu'un montant en euros figure en fin de ligne (format le plus
    courant sur les fiches de paie normalisées). Une mise en page en
    colonnes strictement alignées (montants non adjacents au libellé dans
    le texte OCR linéarisé) peut faire échouer la reconnaissance de la
    ligne — c'est un des risques inhérents à l'OCR sur document tabulaire.
  - Aucun contrôle de cohérence n'est effectué (ex : vérifier que la somme
    des lignes correspond à un "net à payer" annoncé) — cela reste à la
    charge de l'utilisateur au moment de la validation (statut 'a_valider').
"""

import re
import unicodedata
from dataclasses import dataclass

# Alias reconnus pour chaque code de prélèvement (fiscal_engine), sous forme
# de motifs textuels en minuscules à rechercher dans chaque ligne OCR.
# L'ORDRE compte : le premier alias qui correspond gagne (voir limite sur
# les lignes combinées CSG/CRDS ci-dessus).
ALIAS_PRELEVEMENTS: dict[str, list[str]] = {
    "CSG_NON_DEDUCTIBLE": ["csg/crds non déductible", "csg-crds non déductible", "csg non déductible"],
    "CSG_DEDUCTIBLE": ["csg déductible"],
    "CRDS": ["crds"],  # ne matchera que si "csg" n'apparaît pas sur la même ligne (voir parser_fiche_paie)
    "COTIS_VIEILLESSE_PLAF": ["assurance vieillesse plafonnée", "vieillesse plafonnée", "vieillesse plaf"],
    "COTIS_VIEILLESSE_DEPLAF": ["assurance vieillesse déplafonnée", "vieillesse déplafonnée", "vieillesse déplaf"],
}

# Capture un nombre décimal à 2 décimales, avec séparateur de milliers
# optionnel par groupes de 3 chiffres (espace normal ou insécable) :
# "1 234,56", "45.20", "668,25", "3336.74"... Le groupe de milliers, s'il est
# présent, est borné à exactement 3 chiffres pour éviter de fusionner par
# erreur plusieurs nombres adjacents séparés par de simples espaces de mise
# en page (bug corrigé après échec des tests : une regex précédente, trop
# permissive, absorbait "98,25    6,80    668,25" en un seul nombre erroné).
_REGEX_NOMBRE = re.compile(r"\d+(?:[\s\u00a0]\d{3})*[.,]\d{2}")


@dataclass
class LigneFichePaieExtraite:
    """Une ligne reconnue sur la fiche de paie.

    Attributes:
        libelle_brut: texte de la ligne OCR, tel quel.
        montant: montant en euros extrait de la ligne.
        code_prelevement: code du prélèvement fiscal_engine correspondant
            (ex : 'CSG_DEDUCTIBLE'), ou None si aucun alias ne correspond
            (la ligne est quand même conservée pour revue manuelle).
    """

    libelle_brut: str
    montant: float
    code_prelevement: str | None


def _parser_montant(texte_montant: str) -> float:
    nettoye = texte_montant.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return float(nettoye)


def _normaliser(texte: str) -> str:
    """Met en minuscules et retire les diacritiques (accents).

    Nécessaire car l'OCR perd fréquemment les accents ('déductible' devient
    'deductible') — comparer après normalisation des DEUX côtés (alias ET
    texte de la ligne) rend la reconnaissance robuste à cette perte,
    plutôt que de dépendre d'une reconnaissance Tesseract parfaite.
    """
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return sans_accents.lower()


# Alias pré-normalisés (accents retirés) une seule fois au chargement du module.
_ALIAS_NORMALISES: dict[str, list[str]] = {
    code: [_normaliser(alias) for alias in alias_liste] for code, alias_liste in ALIAS_PRELEVEMENTS.items()
}


def _identifier_code_prelevement(ligne_normalisee: str) -> str | None:
    for code, alias_liste in _ALIAS_NORMALISES.items():
        for alias in alias_liste:
            if alias in ligne_normalisee:
                return code
    return None


def parser_fiche_paie(texte_ocr: str) -> list[LigneFichePaieExtraite]:
    """Extrait les lignes de cotisations reconnues d'une fiche de paie.

    Args:
        texte_ocr: texte brut renvoyé par ingestion.ocr.extraire_texte_image.

    Returns:
        Liste des lignes reconnues, dans l'ordre d'apparition dans le texte.
        Les lignes sans montant identifiable en fin de ligne sont ignorées ;
        les lignes avec montant mais sans alias correspondant sont incluses
        avec code_prelevement=None (utile pour une revue manuelle en UI).
    """
    lignes_extraites: list[LigneFichePaieExtraite] = []

    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            continue

        occurrences_nombres = list(_REGEX_NOMBRE.finditer(ligne))
        if not occurrences_nombres:
            continue

        # Le montant est la valeur la plus à droite sur la ligne (colonne
        # "montant" sur une fiche de paie standard : base, taux, montant).
        try:
            montant = _parser_montant(occurrences_nombres[-1].group(0))
        except ValueError:
            continue

        code = _identifier_code_prelevement(_normaliser(ligne))
        lignes_extraites.append(LigneFichePaieExtraite(libelle_brut=ligne, montant=montant, code_prelevement=code))

    return lignes_extraites
