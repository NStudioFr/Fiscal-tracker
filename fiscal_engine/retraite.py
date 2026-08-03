"""Calcul des prélèvements sociaux sur une pension de retraite : CSG (dont
le taux dépend du revenu fiscal de référence et du nombre de parts du
foyer), puis CRDS et CASA appliquées CONDITIONNELLEMENT selon la tranche de
CSG retenue.

Comme fiscal_engine.foyer et fiscal_engine.independant, ce module orchestre
le moteur générique (resolver/calculator, ici seulement pour CRDS/CASA qui
sont des taux fixes) pour produire un résultat composite propre à ce type
de revenu, plutôt que d'être lui-même une donnée fiscale.

RÈGLE DE CONDITIONNEMENT (vérifiée par sources concordantes) :
  - Taux CSG 0% (exonération)      -> CRDS = 0, CASA = 0
  - Taux CSG 3,8% (réduit)         -> CRDS = 0,5%, CASA = 0
  - Taux CSG 6,6% (médian)         -> CRDS = 0,5%, CASA = 0,3%
  - Taux CSG 8,3% (normal)         -> CRDS = 0,5%, CASA = 0,3%
Autrement dit : CRDS s'applique dès que la CSG n'est pas nulle ; CASA ne
s'applique qu'aux deux tranches les plus hautes.

FIABILISÉ le 2026-07-29 puis ÉTENDU le 2026-08-02 (PROJECT_STATE.md
section 7.2) :
  - Les seuils RFR ne sont plus limités à 1 et 2 parts : n'importe quel
    nombre de parts multiple de 0,5 (>= 1) est géré, par la règle officielle
    "chaque demi-part supplémentaire ajoute un montant fixe à chacun des 3
    seuils" (voir `_calculer_seuils` ci-dessous). Cette règle par
    incrément a été elle-même vérifiée par cohérence arithmétique : les
    seuils 1 part et 2 parts déjà validés (source CNAV directe) sont
    EXACTEMENT égaux à seuil_1_part + 2 x incrément_demi_part pour les 3
    seuils, ce qui confirme la règle d'incrément trouvée par ailleurs
    (capretraite.fr, cohérente avec la source CNAV).
  - Le mécanisme de "lissage" est désormais géré (voir
    `calculer_prelevements_retraite`, paramètre optionnel
    `revenu_fiscal_reference_n_moins_3`). Portée du lissage précisément
    documentée par la source officielle CNAV : il protège SPÉCIFIQUEMENT
    les retraités DONT LE RFR N-3 les plaçait déjà à la tranche "réduit"
    (3,8%) — si leur RFR N-2 les ferait franchir un seuil supérieur, le
    taux réduit est maintenu un an de plus. Cette protection ne s'étend PAS
    (documentation officielle disponible) au passage médian -> normal, ni
    (limite résiduelle, non confirmée par une source officielle explicite)
    au passage exonéré -> réduit : seul le cas explicitement documenté
    (réduit -> tranche supérieure) est couvert par ce module.

LIMITES ASSUMÉES (voir aussi seed_data/fr_seed_lot3.sql) :
  - `revenu_fiscal_reference_n_moins_3` est OPTIONNEL : si l'appelant ne le
    fournit pas, le lissage n'est pas appliqué (taux déterminé strictement
    par le RFR N-2 fourni) — c'est une simplification assumée pour les
    appelants qui n'ont pas cet historique, pas une garantie que le lissage
    ne s'applique pas dans la réalité.
  - La part déductible de la CSG (partielle selon le taux) n'est pas
    calculée ici — seul le montant prélevé est produit.
"""

import sqlite3

from .calculator import calculer_montant
from .parameters import resoudre_parametre
from .resolver import resoudre_regle

_ORDRE_TRANCHES = ["exonere", "reduit", "median", "normal"]
_TAUX_PAR_TRANCHE = {"exonere": 0.0, "reduit": 0.038, "median": 0.066, "normal": 0.083}


def _valider_nombre_parts(nombre_parts: float) -> None:
    if nombre_parts < 1 or round(nombre_parts * 2) != nombre_parts * 2:
        raise ValueError(
            f"nombre_parts={nombre_parts!r} invalide : doit être un multiple de 0,5, supérieur ou égal à 1 "
            f"(1, 1.5, 2, 2.5, 3, 3.5, ...)."
        )


def _calculer_seuils(
    conn: sqlite3.Connection, nombre_parts: float, pays_code: str, date_reference: str
) -> dict:
    """Calcule les 3 seuils RFR (exonération, réduit, normal) pour un nombre
    de parts quelconque, par extrapolation officielle "par demi-part
    supplémentaire" à partir des seuils vérifiés pour 1 part.

    Returns:
        {"exonere": float, "reduit": float, "normal": float}
        (le seuil "médian" n'existe pas en tant que tel : c'est la tranche
        entre "reduit" et "normal")
    """
    _valider_nombre_parts(nombre_parts)

    seuil_exo_1part = resoudre_parametre(conn, "CSG_RETRAITE_SEUIL_EXONERE_1PART", pays_code, date_reference)
    seuil_reduit_1part = resoudre_parametre(conn, "CSG_RETRAITE_SEUIL_REDUIT_1PART", pays_code, date_reference)
    seuil_normal_1part = resoudre_parametre(conn, "CSG_RETRAITE_SEUIL_NORMAL_1PART", pays_code, date_reference)

    nombre_demi_parts_supplementaires = round((nombre_parts - 1) * 2)
    if nombre_demi_parts_supplementaires == 0:
        return {"exonere": seuil_exo_1part, "reduit": seuil_reduit_1part, "normal": seuil_normal_1part}

    increment_exo = resoudre_parametre(conn, "CSG_RETRAITE_INCREMENT_DEMI_PART_EXONERE", pays_code, date_reference)
    increment_reduit = resoudre_parametre(conn, "CSG_RETRAITE_INCREMENT_DEMI_PART_REDUIT", pays_code, date_reference)
    increment_normal = resoudre_parametre(conn, "CSG_RETRAITE_INCREMENT_DEMI_PART_NORMAL", pays_code, date_reference)

    return {
        "exonere": seuil_exo_1part + nombre_demi_parts_supplementaires * increment_exo,
        "reduit": seuil_reduit_1part + nombre_demi_parts_supplementaires * increment_reduit,
        "normal": seuil_normal_1part + nombre_demi_parts_supplementaires * increment_normal,
    }


def _tranche_pour_rfr(rfr: float, seuils: dict) -> str:
    if rfr <= seuils["exonere"]:
        return "exonere"
    if rfr <= seuils["reduit"]:
        return "reduit"
    if rfr <= seuils["normal"]:
        return "median"
    return "normal"


def _appliquer_lissage(tranche_n2: str, tranche_n3: str | None) -> tuple[str, bool]:
    """Applique le lissage si applicable. Retourne (tranche_retenue, lissage_applique).

    Portée précise (voir docstring du module) : ne protège que le passage
    depuis la tranche "reduit" (déterminée par le RFR N-3) vers une tranche
    supérieure (déterminée par le RFR N-2). Si tranche_n3 est None (non
    fourni par l'appelant), aucun lissage n'est appliqué.
    """
    if tranche_n3 is None:
        return tranche_n2, False
    if tranche_n3 == "reduit" and _ORDRE_TRANCHES.index(tranche_n2) > _ORDRE_TRANCHES.index("reduit"):
        return "reduit", True
    return tranche_n2, False


def calculer_prelevements_retraite(
    conn: sqlite3.Connection,
    nombre_parts: float,
    revenu_fiscal_reference: float,
    pension_brute: float,
    date_reference: str,
    pays_code: str = "FR",
    revenu_fiscal_reference_n_moins_3: float | None = None,
) -> dict:
    """Calcule CSG + CRDS + CASA sur une pension de retraite.

    Args:
        nombre_parts: nombre de parts du foyer, multiple de 0,5, >= 1 (1,
            1.5, 2, 2.5, 3, 3.5...). Typiquement obtenu via
            fiscal_engine.foyer.calculer_nombre_parts.
        revenu_fiscal_reference: RFR N-2 du foyer (détermine le taux de CSG
            en l'absence de lissage — voir revenu_fiscal_reference_n_moins_3).
        pension_brute: montant brut de la pension sur la période (ex :
            mensuelle), base à laquelle le taux trouvé est appliqué.
        date_reference: date à utiliser pour résoudre les seuils en vigueur.
        revenu_fiscal_reference_n_moins_3: RFR N-3 du foyer, OPTIONNEL —
            fourni, il active la vérification du mécanisme de lissage (voir
            docstring du module pour sa portée précise). Non fourni (None,
            valeur par défaut), le taux est déterminé strictement par
            revenu_fiscal_reference, sans lissage.

    Returns:
        {
            "taux_csg": float,
            "montant_csg": float,
            "montant_crds": float,
            "montant_casa": float,
            "total_preleve": float,
            "pension_nette": float,
            "lissage_applique": bool,
        }

    Raises:
        ValueError: si nombre_parts n'est pas un multiple de 0,5 >= 1.
    """
    seuils = _calculer_seuils(conn, nombre_parts, pays_code, date_reference)
    tranche_n2 = _tranche_pour_rfr(revenu_fiscal_reference, seuils)

    tranche_n3 = None
    if revenu_fiscal_reference_n_moins_3 is not None:
        tranche_n3 = _tranche_pour_rfr(revenu_fiscal_reference_n_moins_3, seuils)

    tranche_retenue, lissage_applique = _appliquer_lissage(tranche_n2, tranche_n3)
    taux_csg = _TAUX_PAR_TRANCHE[tranche_retenue]
    montant_csg = pension_brute * taux_csg

    montant_crds = 0.0
    montant_casa = 0.0

    if taux_csg > 0.0:
        id_crds = conn.execute(
            "SELECT id FROM prelevement WHERE code = 'CRDS_RETRAITE' AND pays_code = ?", (pays_code,)
        ).fetchone()["id"]
        regle_crds = resoudre_regle(conn, id_crds, date_reference)
        montant_crds = calculer_montant(conn, regle_crds, montant=pension_brute)["montant"]

    if taux_csg >= 0.066:  # tranches médian (6,6%) et normal (8,3%) uniquement
        id_casa = conn.execute(
            "SELECT id FROM prelevement WHERE code = 'CASA_RETRAITE' AND pays_code = ?", (pays_code,)
        ).fetchone()["id"]
        regle_casa = resoudre_regle(conn, id_casa, date_reference)
        montant_casa = calculer_montant(conn, regle_casa, montant=pension_brute)["montant"]

    total_preleve = montant_csg + montant_crds + montant_casa

    return {
        "taux_csg": taux_csg,
        "montant_csg": montant_csg,
        "montant_crds": montant_crds,
        "montant_casa": montant_casa,
        "total_preleve": total_preleve,
        "pension_nette": pension_brute - total_preleve,
        "lissage_applique": lissage_applique,
    }
