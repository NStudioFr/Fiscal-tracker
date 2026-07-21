"""Calcul des prélèvements sociaux sur une pension de retraite : CSG (dont
le taux dépend du revenu fiscal de référence, via le mécanisme générique
'bareme_a_seuil'), puis CRDS et CASA appliquées CONDITIONNELLEMENT selon la
tranche de CSG retenue.

Comme fiscal_engine.foyer et fiscal_engine.independant, ce module orchestre
le moteur générique (resolver/calculator) pour produire un résultat
composite propre à ce type de revenu, plutôt que d'être lui-même une
donnée fiscale.

RÈGLE DE CONDITIONNEMENT (vérifiée par sources concordantes) :
  - Taux CSG 0% (exonération)      -> CRDS = 0, CASA = 0
  - Taux CSG 3,8% (réduit)         -> CRDS = 0,5%, CASA = 0
  - Taux CSG 6,6% (médian)         -> CRDS = 0,5%, CASA = 0,3%
  - Taux CSG 8,3% (normal)         -> CRDS = 0,5%, CASA = 0,3%
Autrement dit : CRDS s'applique dès que la CSG n'est pas nulle ; CASA ne
s'applique qu'aux deux tranches les plus hautes.

LIMITES ASSUMÉES (voir aussi seed_data/fr_seed_lot3.sql) :
  - Seuils RFR 2026 estimés par recoupement de sources spécialisées, PAS
    vérifiés sur un texte réglementaire officiel — à confirmer par
    l'utilisateur sur son propre avis d'imposition.
  - Seuls les foyers à 1 ou 2 parts sont couverts.
  - Le mécanisme de "lissage" (un franchissement de seuil ponctuel ne fait
    changer de tranche qu'après 2 années consécutives) n'est PAS géré : ce
    module applique toujours le taux correspondant strictement au RFR fourni.
  - La part déductible de la CSG (partielle selon le taux) n'est pas
    calculée ici — seul le montant prélevé est produit.
"""

import sqlite3

from .calculator import calculer_montant
from .resolver import resoudre_regle

_CODES_CSG_PAR_PARTS = {
    1: "CSG_RETRAITE_1PART",
    2: "CSG_RETRAITE_2PARTS",
}


def calculer_prelevements_retraite(
    conn: sqlite3.Connection,
    nombre_parts: int,
    revenu_fiscal_reference: float,
    pension_brute: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule CSG + CRDS + CASA sur une pension de retraite.

    Args:
        nombre_parts: 1 ou 2 UNIQUEMENT (voir limites du module).
        revenu_fiscal_reference: RFR du foyer (détermine le taux de CSG).
        pension_brute: montant brut de la pension sur la période (ex :
            mensuelle), base à laquelle le taux trouvé est appliqué.
        date_reference: date à utiliser pour résoudre les seuils en vigueur.

    Returns:
        {
            "taux_csg": float,
            "montant_csg": float,
            "montant_crds": float,
            "montant_casa": float,
            "total_preleve": float,
            "pension_nette": float,
        }

    Raises:
        ValueError: si nombre_parts n'est ni 1 ni 2.
    """
    if nombre_parts not in _CODES_CSG_PAR_PARTS:
        raise ValueError(
            f"nombre_parts={nombre_parts} non géré : seuls 1 et 2 parts sont couverts par ce module "
            f"(voir limites documentées dans fiscal_engine/retraite.py)."
        )

    code_csg = _CODES_CSG_PAR_PARTS[nombre_parts]
    id_csg = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code_csg, pays_code)
    ).fetchone()["id"]
    regle_csg = resoudre_regle(conn, id_csg, date_reference)
    resultat_csg = calculer_montant(
        conn, regle_csg, montant=pension_brute, valeur_seuil=revenu_fiscal_reference
    )
    taux_csg = resultat_csg["taux_applique"]
    montant_csg = resultat_csg["montant"]

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
    }
