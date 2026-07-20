"""Utilitaires partagés entre tous les parsers d'ingestion (fiche_paie,
avis_imposition, facture, ticket_caisse...) : normalisation de texte et
extraction robuste de nombres depuis du texte OCR imparfait.

Factorisé ici après le lot fiche de paie, pour éviter la duplication de
cette logique dans chaque nouveau parser — le comportement (et ses tests)
n'a besoin d'être validé qu'une seule fois.
"""

import re
import unicodedata

# Un token numérique isolé (après split() sur les espaces) : nombre décimal
# à n'importe quel nombre de décimales (certains documents affichent des
# taux à 4 décimales, ex "6,8000", contrairement aux montants qui en ont 2).
REGEX_TOKEN_NUMERIQUE = re.compile(r"^-?\d+[.,]\d+$")
# Un token "préfixe de milliers" : 1 à 3 chiffres seuls, à fusionner avec le
# token numérique suivant s'ils sont adjacents (ex : "3" + "733,50").
REGEX_TOKEN_MILLIERS = re.compile(r"^\d{1,3}$")
# Symboles monétaires à retirer avant tokenisation : qu'ils soient collés à
# un nombre ("45,20€") ou séparés par un espace ("45,20 €" / "45,20 EUR"),
# ils ne doivent jamais empêcher la reconnaissance du nombre qui précède.
_REGEX_SYMBOLE_MONETAIRE = re.compile(r"€|(?i:\beur\b)")


def nettoyer_symboles_monetaires(ligne: str) -> str:
    """Retire les symboles monétaires (€, EUR) d'une ligne, qu'ils soient
    collés à un nombre ou séparés par un espace — à appeler avant tout
    découpage en tokens pour ne pas les laisser interférer avec la
    détection du dernier nombre de la ligne.
    """
    return _REGEX_SYMBOLE_MONETAIRE.sub(" ", ligne)


def normaliser(texte: str) -> str:
    """Met en minuscules et retire les diacritiques (accents).

    Nécessaire car l'OCR perd fréquemment les accents ('déductible' devient
    'deductible') — comparer après normalisation des DEUX côtés (alias ET
    texte source) rend la reconnaissance robuste à cette perte.
    """
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return sans_accents.lower()


def parser_montant(texte_montant: str) -> float:
    """Convertit un texte de montant ('1 234,56', '45.20'...) en float."""
    nettoye = texte_montant.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return float(nettoye)


def fusionner_prefixes_milliers(tokens: list[str]) -> list[str]:
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
            and REGEX_TOKEN_MILLIERS.fullmatch(tokens[i])
            and REGEX_TOKEN_NUMERIQUE.fullmatch(tokens[i + 1])
        ):
            fusionnes.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            fusionnes.append(tokens[i])
            i += 1
    return fusionnes


def suffixe_numerique(tokens: list[str]) -> list[str]:
    """Renvoie le plus long suffixe de `tokens` composé uniquement de
    tokens numériques ou de tirets '-' (placeholder d'absence de valeur).
    """
    fin_index = len(tokens)
    for j in range(len(tokens) - 1, -1, -1):
        if tokens[j] == "-" or REGEX_TOKEN_NUMERIQUE.fullmatch(tokens[j]):
            fin_index = j
        else:
            break
    return tokens[fin_index:]


def extraire_dernier_montant(ligne: str) -> float | None:
    """Extrait le dernier nombre d'une ligne (fusionné si coupé par un
    séparateur de milliers). Adapté aux documents à UNE seule colonne de
    montant par ligne (avis d'imposition, factures simples) — pour un
    document à colonnes salarial/patronal (fiche de paie), voir
    fiche_paie._extraire_montant_salarial qui a une logique positionnelle
    différente et plus spécifique.
    """
    tokens = fusionner_prefixes_milliers(nettoyer_symboles_monetaires(ligne).split())
    suffixe = suffixe_numerique(tokens)
    if not suffixe:
        return None
    candidat = suffixe[-1]
    if candidat == "-":
        return None
    try:
        return parser_montant(candidat)
    except ValueError:
        return None
