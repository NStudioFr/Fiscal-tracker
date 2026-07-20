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

EXTRACTION DU MONTANT — POSITIONNEMENT DES COLONNES :
Une ligne de cotisation standard suit le format :
    Libellé   Base   Taux_salarial   Montant_salarial   [Taux_patronal   Montant_patronal]
(vérifié empiriquement sur un vrai bulletin généré par un logiciel de paie
commercial - QuickPaie - où le montant PATRONAL apparaît bien après le
montant salarial quand les deux existent). Prendre "le dernier nombre de la
ligne" donnerait donc le montant PATRONAL au lieu du montant SALARIAL qui
nous intéresse (ce logiciel comptabilise les prélèvements payés PAR la
personne). Ce module repère donc la position du montant salarial :
  - 1 seul nombre en fin de ligne -> on le prend tel quel (formats très
    simplifiés, une seule colonne de montant).
  - 2 nombres en fin de ligne -> on prend le dernier (formats à 2 colonnes :
    taux puis montant, sans distinction salarial/patronal explicite).
  - 3 nombres ou plus en fin de ligne -> on suppose le format standard
    [base, taux_salarial, montant_salarial, ...] et on prend le 3ᵉ
    (index 2) : c'est le montant salarial, qu'une part patronale suive
    ensuite ou non.

LIMITES ASSUMÉES :
  - Seuls les prélèvements listés dans ALIAS_PRELEVEMENTS sont reconnus.
    Toute cotisation hors de ce périmètre (mutuelle, prévoyance, titres
    restaurant...) n'est PAS extraite par ce module.
  - L'heuristique de position (ci-dessus) suppose que la base apparaît
    toujours en premier. Une ligne où la part salariale est absente (tiret
    "-" à la position du taux salarial, ex : "Allocations familiales" qui
    n'a qu'une part patronale) n'est pas mal interprétée : elle est
    détectée et ignorée (aucun montant salarial n'existe sur cette ligne).
  - CSG non déductible et CRDS apparaissent SOUVENT combinées sur une même
    ligne réelle (ligne "non déductible" à 2,9 % = 2,4 % CSG + 0,5 % CRDS
    combinés). Ce module attribue ce montant combiné ENTIÈREMENT au code
    'CSG_NON_DEDUCTIBLE' — la CRDS n'est pas isolée séparément dans ce cas
    (le total reste correct, la ventilation par typologie est imprécise).
  - Aucun contrôle de cohérence (ex : vérifier un "net à payer" annoncé)
    n'est effectué — cela reste à la charge de l'utilisateur (statut
    'a_valider').
"""

import re
import unicodedata
from dataclasses import dataclass

# Alias reconnus pour chaque code de prélèvement (fiscal_engine), sous forme
# de motifs textuels (accents retirés, minuscules) à rechercher dans chaque
# ligne OCR. L'ordre compte quand plusieurs alias pourraient chevaucher.
ALIAS_PRELEVEMENTS: dict[str, list[str]] = {
    "CSG_NON_DEDUCTIBLE": [
        "csg/crds non déductible",
        "csg-crds non déductible",
        "csg non déductible",
        "dont non déductible de l'impôt sur le revenu",
    ],
    "CSG_DEDUCTIBLE": [
        "csg déductible",
        "dont déductible de l'impôt sur le revenu",
    ],
    "CRDS": ["crds"],  # ne matchera que si aucun alias CSG_NON_DEDUCTIBLE n'a déjà capté la ligne
    "COTIS_VIEILLESSE_PLAF": [
        "assurance vieillesse plafonnée",
        "vieillesse plafonnée",
        "vieillesse plaf",
        "retraite plafonnée",
    ],
    "COTIS_VIEILLESSE_DEPLAF": [
        "assurance vieillesse déplafonnée",
        "vieillesse déplafonnée",
        "vieillesse déplaf",
        "retraite déplafonnée",
    ],
}

# Un token numérique isolé (après split sur les espaces) : nombre décimal à
# n'importe quel nombre de décimales (les taux ont souvent 4 décimales,
# ex "6,8000", contrairement aux montants qui en ont 2 — voir _extraire_montant_salarial).
_REGEX_TOKEN_NUMERIQUE = re.compile(r"^-?\d+[.,]\d+$")
# Un token "préfixe de milliers" : 1 à 3 chiffres seuls, à fusionner avec le
# token numérique suivant s'ils sont adjacents (ex : "3" + "733,50").
_REGEX_TOKEN_MILLIERS = re.compile(r"^\d{1,3}$")


@dataclass
class LigneFichePaieExtraite:
    """Une ligne reconnue sur la fiche de paie.

    Attributes:
        libelle_brut: texte de la ligne OCR, tel quel.
        montant: montant SALARIAL en euros extrait de la ligne.
        code_prelevement: code du prélèvement fiscal_engine correspondant
            (ex : 'CSG_DEDUCTIBLE'), ou None si aucun alias ne correspond
            (la ligne est quand même conservée pour revue manuelle).
    """

    libelle_brut: str
    montant: float
    code_prelevement: str | None


def _normaliser(texte: str) -> str:
    """Met en minuscules et retire les diacritiques (accents).

    Nécessaire car l'OCR perd fréquemment les accents ('déductible' devient
    'deductible') — comparer après normalisation des DEUX côtés (alias ET
    texte de la ligne) rend la reconnaissance robuste à cette perte.
    """
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return sans_accents.lower()


_ALIAS_NORMALISES: dict[str, list[str]] = {
    code: [_normaliser(alias) for alias in alias_liste] for code, alias_liste in ALIAS_PRELEVEMENTS.items()
}


def _identifier_code_prelevement(ligne_normalisee: str) -> str | None:
    for code, alias_liste in _ALIAS_NORMALISES.items():
        for alias in alias_liste:
            if alias in ligne_normalisee:
                return code
    return None


def _parser_montant(texte_montant: str) -> float:
    nettoye = texte_montant.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return float(nettoye)


def _fusionner_prefixes_milliers(tokens: list[str]) -> list[str]:
    """Fusionne un token '1-3 chiffres seuls' avec le token numérique
    suivant s'ils sont adjacents (ex : ['3', '733,50'] -> ['3733,50']),
    pour reconstituer un montant à séparateur de milliers coupé par le
    split() sur les espaces.
    """
    fusionnes: list[str] = []
    i = 0
    while i < len(tokens):
        if (
            i + 1 < len(tokens)
            and _REGEX_TOKEN_MILLIERS.fullmatch(tokens[i])
            and _REGEX_TOKEN_NUMERIQUE.fullmatch(tokens[i + 1])
        ):
            fusionnes.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            fusionnes.append(tokens[i])
            i += 1
    return fusionnes


def _suffixe_numerique(tokens: list[str]) -> list[str]:
    """Renvoie le plus long suffixe de `tokens` composé uniquement de
    tokens numériques ou de tirets '-' (placeholder d'absence de valeur).
    """
    fin_index = len(tokens)
    for j in range(len(tokens) - 1, -1, -1):
        if tokens[j] == "-" or _REGEX_TOKEN_NUMERIQUE.fullmatch(tokens[j]):
            fin_index = j
        else:
            break
    return tokens[fin_index:]


def _extraire_montant_salarial(ligne: str) -> float | None:
    """Applique l'heuristique de position décrite en tête de module pour
    isoler le montant SALARIAL (jamais le patronal) d'une ligne.
    """
    tokens = _fusionner_prefixes_milliers(ligne.split())
    suffixe = _suffixe_numerique(tokens)

    if not suffixe:
        return None

    if len(suffixe) == 1:
        candidat = suffixe[0]
    elif len(suffixe) == 2:
        candidat = suffixe[-1]
    else:
        # Format standard : [base, taux_salarial, montant_salarial, ...]
        if suffixe[1] == "-":
            return None  # pas de part salariale sur cette ligne (ex : cotisation 100% patronale)
        candidat = suffixe[2]

    if candidat == "-":
        return None

    try:
        return _parser_montant(candidat)
    except ValueError:
        return None


def parser_fiche_paie(texte_ocr: str) -> list[LigneFichePaieExtraite]:
    """Extrait les lignes de cotisations reconnues d'une fiche de paie.

    Args:
        texte_ocr: texte brut renvoyé par ingestion.ocr.extraire_texte_image.

    Returns:
        Liste des lignes reconnues, dans l'ordre d'apparition. Les lignes
        sans montant salarial identifiable sont ignorées ; les lignes avec
        montant mais sans alias correspondant sont incluses avec
        code_prelevement=None (utile pour une revue manuelle en UI).
    """
    lignes_extraites: list[LigneFichePaieExtraite] = []

    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            continue

        montant = _extraire_montant_salarial(ligne)
        if montant is None:
            continue

        code = _identifier_code_prelevement(_normaliser(ligne))
        lignes_extraites.append(LigneFichePaieExtraite(libelle_brut=ligne, montant=montant, code_prelevement=code))

    return lignes_extraites
