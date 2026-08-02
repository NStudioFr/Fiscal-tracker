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

FIABILISÉ le 2026-07-29 (PROJECT_STATE.md section 7.3) : 3 des 4 limites
listées ci-dessous à cette date sont désormais couvertes.
  1. Taux CIPAV (`type_activite='bnc_cipav'`) : 23,2% pour 2026, distinct
     du taux BNC régime général (25,6%). Le versement libératoire et
     l'abattement forfaitaire restent identiques au BNC régime général
     (seule la cotisation sociale diffère) — voir `_CODES_VERSEMENT_LIBERATOIRE`
     et `_CODES_ABATTEMENT` ci-dessous.
  2. Plafonds de chiffre d'affaires du régime micro : nouvelle fonction
     `verifier_plafond_ca_micro`.
  3. Éligibilité au versement libératoire (condition de RFR) : nouvelle
     fonction `verifier_eligibilite_versement_liberatoire`.

LIMITES ASSUMÉES (documentées, pas gérées par ce module) :
  - Location de meublés de tourisme classés (taux à 6%) : non gérée.
  - ACRE (réduction de cotisations la première année d'activité) : non gérée.
  - `verifier_plafond_ca_micro` ne vérifie le dépassement que sur UNE année
    civile donnée : la mécanique de sortie du régime (qui n'intervient
    qu'après un dépassement sur 2 années CONSÉCUTIVES) n'est pas gérée, ce
    module n'ayant connaissance que du CA de la période courante, pas de
    l'historique.
  - `verifier_eligibilite_versement_liberatoire` ne vérifie pas que le RFR
    fourni par l'appelant est bien celui de la bonne année de référence
    (N-2) — c'est à l'appelant de fournir le bon montant.
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
    "bnc_cipav": "MICRO_COTIS_CIPAV",
}
_CODES_VERSEMENT_LIBERATOIRE = {
    "vente": "MICRO_VL_VENTE",
    "services_bic": "MICRO_VL_SERVICES_BIC",
    "bnc": "MICRO_VL_BNC",
    "bnc_cipav": "MICRO_VL_BNC",  # même taux que le BNC régime général : seule la cotisation sociale diffère pour la CIPAV
}
_CODES_ABATTEMENT = {
    "vente": "ABATTEMENT_MICRO_VENTE",
    "services_bic": "ABATTEMENT_MICRO_SERVICES_BIC",
    "bnc": "ABATTEMENT_MICRO_BNC",
    "bnc_cipav": "ABATTEMENT_MICRO_BNC",  # idem : même abattement que le BNC régime général
}
_CODES_PLAFOND_CA = {
    "vente": "PLAFOND_CA_MICRO_VENTE",
    "services_bic": "PLAFOND_CA_MICRO_SERVICES",
    "bnc": "PLAFOND_CA_MICRO_SERVICES",
    "bnc_cipav": "PLAFOND_CA_MICRO_SERVICES",
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


def verifier_plafond_ca_micro(
    conn: sqlite3.Connection,
    type_activite: str,
    chiffre_affaires_annuel: float,
    date_reference: str,
    pays_code: str = "FR",
    chiffre_affaires_services_si_mixte: float | None = None,
) -> dict:
    """Vérifie si un chiffre d'affaires annuel dépasse le plafond du régime
    micro applicable à cette activité (2026-2028 : 203 100€ pour la
    vente/hébergement, 83 600€ pour les prestations de services BIC/BNC,
    y compris CIPAV).

    Args:
        type_activite: 'vente', 'services_bic', 'bnc', ou 'bnc_cipav'.
        chiffre_affaires_annuel: chiffre d'affaires encaissé sur l'année
            civile complète. Pour une activité 'vente' en cas d'activité
            MIXTE (vente + services au sein de la même micro-entreprise),
            il s'agit du chiffre d'affaires GLOBAL (vente + services).
        date_reference: date à utiliser pour résoudre le plafond en vigueur.
        chiffre_affaires_services_si_mixte: en cas d'activité mixte
            (vente ET services), la part du chiffre d'affaires
            correspondant aux services — permet de vérifier EN PLUS le
            sous-plafond services (83 600€), qui s'applique même si le
            plafond global (203 100€) n'est pas dépassé. Sans effet si
            type_activite != 'vente'.

    Returns:
        {
            "plafond_applicable": float,
            "depasse": bool,                        # plafond principal
            "depasse_sous_plafond_services": bool | None,  # None si non pertinent
        }

    Note : ne vérifie le dépassement que pour l'année fournie — la sortie
    effective du régime micro ne survient qu'après un dépassement sur 2
    années civiles CONSÉCUTIVES, mécanique non gérée ici (voir tête de
    fichier).
    """
    _verifier_type_activite(type_activite)
    code_plafond = _CODES_PLAFOND_CA[type_activite]
    plafond = resoudre_parametre(conn, code_plafond, pays_code, date_reference)

    resultat = {
        "plafond_applicable": plafond,
        "depasse": chiffre_affaires_annuel > plafond,
        "depasse_sous_plafond_services": None,
    }

    if type_activite == "vente" and chiffre_affaires_services_si_mixte is not None:
        plafond_services = resoudre_parametre(conn, "PLAFOND_CA_MICRO_SERVICES", pays_code, date_reference)
        resultat["depasse_sous_plafond_services"] = chiffre_affaires_services_si_mixte > plafond_services

    return resultat


def verifier_eligibilite_versement_liberatoire(
    conn: sqlite3.Connection,
    nombre_parts: float,
    revenu_fiscal_reference_n_moins_2: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Vérifie l'éligibilité à l'option du versement libératoire de l'IR
    (Art. 151-0 CGI), au regard de la condition de revenu fiscal de
    référence (RFR) du foyer.

    Le seuil (29 315€ pour 1 part en 2026) est STRICTEMENT PROPORTIONNEL au
    nombre de parts du foyer (majoration de 50% par demi-part, 25% par
    quart de part — vérifié : seuil = 29315 x nombre_parts).

    Args:
        nombre_parts: nombre de parts du foyer fiscal — typiquement obtenu
            via fiscal_engine.foyer.calculer_nombre_parts (ce module n'a
            volontairement pas de dépendance vers fiscal_engine.foyer,
            pour éviter un couplage inutile : c'est à l'appelant de
            calculer le nombre de parts et de le fournir ici).
        revenu_fiscal_reference_n_moins_2: RFR du foyer de l'année N-2 (pour
            une éligibilité en 2026 : RFR 2024, figurant sur l'avis
            d'imposition 2025). Ce module NE VÉRIFIE PAS que la valeur
            fournie est bien celle de la bonne année — c'est à l'appelant
            de fournir le bon montant.
        date_reference: date à utiliser pour résoudre le seuil en vigueur
            (l'année du barème, pas l'année du RFR pris en compte).

    Returns:
        {"seuil_applicable": float, "eligible": bool}
    """
    seuil_1_part = resoudre_parametre(
        conn, "PLAFOND_RFR_VERSEMENT_LIBERATOIRE_1_PART", pays_code, date_reference
    )
    seuil_applicable = seuil_1_part * nombre_parts
    return {
        "seuil_applicable": seuil_applicable,
        "eligible": revenu_fiscal_reference_n_moins_2 <= seuil_applicable,
    }
