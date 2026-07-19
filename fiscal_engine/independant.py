"""Calcul des prélèvements d'un micro-entrepreneur (auto-entrepreneur) :
cotisations sociales, abattement forfaitaire pour frais professionnels, et
versement libératoire optionnel de l'impôt sur le revenu.

PÉRIMÈTRE VOLONTAIREMENT LIMITÉ : ce module ne couvre QUE le régime
micro-entrepreneur (micro-social + micro-fiscal). Le régime réel (BIC/BNC
au réel) n'est PAS couvert — il ne s'agit pas d'un ensemble de taux mais
d'un système comptable complet (charges réelles déductibles, amortissements,
TVA collectée/déductible...) qui dépasse le cadre de ce moteur de règles.

Comme fiscal_engine.foyer, ce module orchestre le moteur générique
(resolver/calculator) plutôt que d'être lui-même une donnée fiscale : le
chiffre d'affaires déclaré est une donnée d'entrée de l'utilisateur, pas une
règle versionnée.

LIMITES ASSUMÉES (documentées, pas gérées par ce module) :
  - Trois catégories d'activité seulement : vente de marchandises, prestations
    de services BIC, professions libérales BNC (régime général). Le taux
    spécifique CIPAV (professions libérales relevant de la CIPAV plutôt que
    du régime général, ex : architectes, psychologues) N'EST PAS modélisé
    séparément — utiliser 'bnc' sous-estimera légèrement leurs cotisations
    réelles si elles relèvent en réalité de la CIPAV.
  - Location de meublés de tourisme classés (taux à 6%) : non gérée.
  - ACRE (réduction de cotisations la première année d'activité) : non gérée.
  - Plafonds de chiffre d'affaires du régime micro (au-delà desquels le
    régime bascule au réel) : non vérifiés par ce module.
  - Condition de revenu fiscal de référence pour l'éligibilité au versement
    libératoire : non vérifiée — ce module calcule le montant SI l'option est
    choisie, sans valider que l'utilisateur y est éligible.
"""

import sqlite3

from .calculator import calculer_montant
from .parameters import resoudre_parametre
from .resolver import resoudre_regle

# Mapping type d'activité -> code de prélèvement (cotisations) et
# code de paramètre (abattement forfaitaire).
_CODES_COTISATION = {
    "vente": "MICRO_COTIS_VENTE",
    "services_bic": "MICRO_COTIS_SERVICES_BIC",
    "bnc": "MICRO_COTIS_BNC",
}
_CODES_VERSEMENT_LIBERATOIRE = {
    "vente": "MICRO_VL_VENTE",
    "services_bic": "MICRO_VL_SERVICES_BIC",
    "bnc": "MICRO_VL_BNC",
}
_CODES_ABATTEMENT = {
    "vente": "ABATTEMENT_MICRO_VENTE",
    "services_bic": "ABATTEMENT_MICRO_SERVICES_BIC",
    "bnc": "ABATTEMENT_MICRO_BNC",
}

TYPES_ACTIVITE_VALIDES = tuple(_CODES_COTISATION.keys())


def _verifier_type_activite(type_activite: str) -> None:
    if type_activite not in TYPES_ACTIVITE_VALIDES:
        raise ValueError(
            f"type_activite {type_activite!r} inconnu. Valeurs acceptées : {TYPES_ACTIVITE_VALIDES}."
        )


def calculer_cotisations_micro(
    conn: sqlite3.Connection,
    type_activite: str,
    chiffre_affaires: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule les cotisations sociales dues sur un chiffre d'affaires déclaré.

    Args:
        type_activite: 'vente', 'services_bic', ou 'bnc'.
        chiffre_affaires: chiffre d'affaires encaissé sur la période déclarée
            (ex : trimestre), en euros.
        date_reference: date à utiliser pour résoudre le taux en vigueur.

    Returns:
        Le dict retourné par calculator.calculer_montant (montant, base_calcul,
        taux_applique).
    """
    _verifier_type_activite(type_activite)
    code = _CODES_COTISATION[type_activite]
    id_prelevement = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code, pays_code)
    ).fetchone()
    if id_prelevement is None:
        raise ValueError(f"Aucun prélèvement {code!r} trouvé pour le pays {pays_code!r}.")
    regle = resoudre_regle(conn, id_prelevement["id"], date_reference)
    return calculer_montant(conn, regle, montant=chiffre_affaires)


def calculer_versement_liberatoire(
    conn: sqlite3.Connection,
    type_activite: str,
    chiffre_affaires: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule le versement libératoire de l'IR dû sur un chiffre d'affaires
    déclaré, POUR UN MICRO-ENTREPRENEUR AYANT OPTÉ POUR CE RÉGIME.

    Ne vérifie PAS l'éligibilité (condition de revenu fiscal de référence) —
    voir les limites en tête de module.
    """
    _verifier_type_activite(type_activite)
    code = _CODES_VERSEMENT_LIBERATOIRE[type_activite]
    id_prelevement = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code, pays_code)
    ).fetchone()
    if id_prelevement is None:
        raise ValueError(f"Aucun prélèvement {code!r} trouvé pour le pays {pays_code!r}.")
    regle = resoudre_regle(conn, id_prelevement["id"], date_reference)
    return calculer_montant(conn, regle, montant=chiffre_affaires)


def calculer_revenu_imposable_micro(
    conn: sqlite3.Connection,
    type_activite: str,
    chiffre_affaires: float,
    date_reference: str,
    pays_code: str = "FR",
) -> float:
    """Calcule le revenu imposable après abattement forfaitaire, POUR UN
    MICRO-ENTREPRENEUR N'AYANT PAS OPTÉ POUR LE VERSEMENT LIBÉRATOIRE.

    Ce revenu imposable doit ensuite être intégré au revenu net imposable
    global du foyer et soumis au barème progressif via
    fiscal_engine.foyer.calculer_impot_foyer — ce module ne fait QUE
    calculer l'abattement, pas le calcul d'impôt final (qui dépend de la
    situation du foyer entier, pas seulement de cette activité).

    Args:
        type_activite: 'vente', 'services_bic', ou 'bnc'.
        chiffre_affaires: chiffre d'affaires annuel encaissé, en euros.
        date_reference: date à utiliser pour résoudre le taux d'abattement.

    Returns:
        Le revenu imposable (chiffre_affaires * (1 - taux_abattement)).
    """
    _verifier_type_activite(type_activite)
    code = _CODES_ABATTEMENT[type_activite]
    taux_abattement = resoudre_parametre(conn, code, pays_code, date_reference)
    return chiffre_affaires * (1 - taux_abattement)
