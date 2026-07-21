"""Parsing d'un ticket de caisse à partir du texte OCR brut.

APPROCHE — POURQUOI PAS UNE IDENTIFICATION PRODUIT PAR PRODUIT :
Contrairement à la fiche de paie (libellés officiels standardisés) ou à la
facture (taux de TVA obligatoirement affiché par ligne), un ticket de caisse
utilise des abréviations propres à chaque enseigne, absolument pas
standardisées ("TC MAXI MOZZA", "OY 180G BROWNIE CH", "4X85G+10F NOUILLE
BO"...). Tenter de les décoder précisément produit par produit relève du
travail de "mapping produits" évoqué ailleurs dans ce projet — hors
périmètre de ce module. CE MODULE EXPLOITE À LA PLACE DEUX SIGNAUX BIEN PLUS
FIABLES, présents sur de nombreux tickets de grande distribution (vérifié
empiriquement sur un vrai ticket Carrefour fourni pendant le développement) :

  1. Le BLOC RÉCAPITULATIF DE TVA en bas du ticket (ex : "TVA 4: 5,50% €
     34,74   1,91"), qui donne directement, PAR TAUX, le montant de TVA
     déjà calculé par la caisse — sans avoir besoin d'identifier un seul
     produit. C'est la source la plus fiable de ce module.
  2. Les LIGNES "Total <Catégorie>" (ex : "Total Alimentaire", "Total
     Entretien Hyg-Beauté", "Total Non Aliment.") qu'impriment certaines
     enseignes, permettant une ventilation par type de dépense sans
     identification produit par produit non plus.

Un troisième mécanisme, plus faible, tente de repérer les EN-TÊTES DE RAYON
(lignes préfixées par "**", ">>>", "»»»"...) pour un regroupement indicatif
des lignes produit brutes — mais SANS leur associer de prélèvement calculé
(juste un regroupement d'affichage pour aide à la revue manuelle).

LEÇON IMPORTANTE (constatée en testant sur de vraies photos, cf.
ingestion/ocr.py) : LA QUALITÉ DE L'OCR CONDITIONNE ENTIÈREMENT LA
FIABILITÉ DE CE PARSER. Sur un ticket photographié dans de mauvaises
conditions (flou, plis, reflets), certains chiffres peuvent être mal
reconnus (ex : un "7" lu comme un "1"). Un signal encourageant observé :
sommer les montants de TVA extraits PAR CE MODULE peut être plus fiable que
de faire confiance à la ligne "TOTAL TVA" elle-même imprimée sur le ticket,
si cette dernière a été mal océrisée alors que les lignes individuelles ne
l'ont pas été — mais ce n'est pas garanti, d'où le statut 'a_valider'
systématique.

LIMITES ASSUMÉES :
  - Aucune identification produit par produit (voir plus haut).
  - Le bloc TVA n'est reconnu que s'il suit le format "TVA <code>: <taux>
    [%] ... <montant>" — d'autres présentations (tableau récapitulatif
    séparé, alignement en colonnes strictes) peuvent échouer.
  - Les libellés de catégorie reconnus dans ALIAS_TOTAL_CATEGORIE sont ceux
    observés sur les enseignes testées ; une enseigne avec un vocabulaire
    différent ("Total Bazar", "Total Textile"...) ne sera pas reconnue sans
    ajout de l'alias correspondant.
  - Le regroupement par rayon (detecter_rayons) est purement indicatif :
    aucun prélèvement n'est calculé à partir de ces en-têtes.
"""

import re
from dataclasses import dataclass

from .texte_utils import extraire_dernier_montant, normaliser

# --------------------------------------------------------------------
# 1. Bloc récapitulatif de TVA
# --------------------------------------------------------------------
# Capture le taux (le nombre décimal après "tva", un éventuel code de bloc
# à 1-2 chiffres, et ':'), tolérant à une perte OCR du signe '%' (observé en
# pratique : "5,50%" parfois lu "5,504"). Le code de bloc ("TVA 4:", "TVA 5:"...)
# doit être modélisé explicitement (\d{0,2}) : un simple \D générique ne peut
# pas "sauter" par-dessus ce chiffre puisqu'il exclut justement les chiffres
# (bug détecté en testant sur un vrai ticket : la regex précédente échouait
# purement et simplement sur "TVA 4: 5,50%").
_REGEX_TVA_TAUX = re.compile(r"tva\s*\d{0,2}\s*:?\s*(\d+[.,]\d+)", re.IGNORECASE)

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
class LigneTvaTicket:
    libelle_brut: str
    taux_detecte: float
    montant: float
    code_prelevement: str | None


def extraire_tva_ticket(texte_ocr: str) -> list[LigneTvaTicket]:
    """Extrait le bloc récapitulatif de TVA d'un ticket de caisse.

    Reconnaît les lignes du type "TVA <code>: <taux>% ... <montant>" —
    format observé sur les tickets de grande distribution (ex : Carrefour).
    Le montant retenu est le DERNIER nombre de la ligne (le montant de TVA
    lui-même, après la base sur laquelle il est calculé).
    """

    lignes_extraites: list[LigneTvaTicket] = []
    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne or "tva" not in ligne.lower():
            continue

        match_taux = _REGEX_TVA_TAUX.search(ligne)
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
            LigneTvaTicket(libelle_brut=ligne, taux_detecte=taux_detecte, montant=montant, code_prelevement=code)
        )

    return lignes_extraites


# --------------------------------------------------------------------
# 2. Totaux par catégorie ("Total Alimentaire", etc.)
# --------------------------------------------------------------------
# Mappe un mot-clé (normalisé : minuscules, sans accents) trouvé sur une
# ligne "Total ..." vers un code type_depense de fiscal_engine.
ALIAS_TOTAL_CATEGORIE: dict[str, str] = {
    "alimentaire": "ALIMENTATION",
    "entretien": "HYGIENE_ENTRETIEN",
    "hygiene": "HYGIENE_ENTRETIEN",
    "beaute": "HYGIENE_ENTRETIEN",
    "non aliment": "AUTRE",
}


@dataclass
class TotalCategorieTicket:
    libelle_brut: str
    montant: float
    type_depense_code: str | None


def extraire_totaux_categories(texte_ocr: str) -> list[TotalCategorieTicket]:
    """Extrait les lignes 'Total <Catégorie>' d'un ticket de caisse.

    Args:
        texte_ocr: texte brut renvoyé par ingestion.ocr.extraire_texte_image.

    Returns:
        Liste des totaux de catégorie reconnus. Une ligne commençant par
        "total" mais dont le mot-clé n'est pas dans ALIAS_TOTAL_CATEGORIE
        est quand même incluse avec type_depense_code=None (revue manuelle),
        sauf s'il s'agit du "TOTAL A PAYER" / "TOTAL TVA" généraux (exclus
        car ce ne sont pas des totaux de CATÉGORIE de dépense).
    """

    _EXCLUSIONS = ["total a payer", "total tva"]

    resultats: list[TotalCategorieTicket] = []
    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            continue
        ligne_normalisee = normaliser(ligne)
        if "total" not in ligne_normalisee:
            continue
        if any(exclusion in ligne_normalisee for exclusion in _EXCLUSIONS):
            continue

        montant = extraire_dernier_montant(ligne)
        if montant is None:
            continue

        code_type_depense = None
        for mot_cle, code in ALIAS_TOTAL_CATEGORIE.items():
            if mot_cle in ligne_normalisee:
                code_type_depense = code
                break

        resultats.append(TotalCategorieTicket(libelle_brut=ligne, montant=montant, type_depense_code=code_type_depense))

    return resultats


# --------------------------------------------------------------------
# 3. Repérage indicatif des rayons (regroupement d'affichage uniquement)
# --------------------------------------------------------------------
_REGEX_PREFIXE_RAYON = re.compile(r"^\s*(\*\*|[>»]{2,4})\s*(.+)$")


def detecter_rayons(texte_ocr: str) -> list[tuple[str, list[str]]]:
    """Regroupe les lignes de produits sous leur en-tête de rayon détecté.

    Purement indicatif : ne calcule AUCUN prélèvement. Utile pour une
    interface de revue manuelle qui voudrait présenter les lignes groupées
    par rayon plutôt qu'en liste plate.

    Returns:
        Liste de tuples (nom_rayon, [lignes_produit_associees]). Les lignes
        précédant le premier en-tête détecté sont ignorées (en-tête de
        ticket : nom du magasin, adresse...).
    """
    groupes: list[tuple[str, list[str]]] = []
    rayon_courant: str | None = None
    lignes_courantes: list[str] = []

    for ligne_brute in texte_ocr.splitlines():
        ligne = ligne_brute.strip()
        if not ligne:
            continue

        match_rayon = _REGEX_PREFIXE_RAYON.match(ligne)
        if match_rayon:
            if rayon_courant is not None:
                groupes.append((rayon_courant, lignes_courantes))
            rayon_courant = match_rayon.group(2).strip()
            lignes_courantes = []
        elif rayon_courant is not None:
            lignes_courantes.append(ligne)

    if rayon_courant is not None:
        groupes.append((rayon_courant, lignes_courantes))

    return groupes
