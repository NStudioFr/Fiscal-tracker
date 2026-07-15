"""Calcul de l'impôt sur le revenu d'un foyer fiscal complet : nombre de
parts (quotient familial), plafonnement de l'avantage du quotient familial,
et décote.

Ce module se situe au-dessus du moteur générique (resolver/calculator) : il
orchestre plusieurs résolutions de règles et de paramètres pour produire un
résultat composite, propre à l'impôt sur le revenu. Contrairement aux
prélèvements "simples" du reste du moteur, la composition du foyer
(situation familiale, enfants) N'EST PAS une donnée fiscale versionnée en
base — c'est une donnée personnelle de l'utilisateur, fournie en argument à
chaque appel plutôt que stockée dans une table dédiée. Les MONTANTS légaux
utilisés (plafond du quotient familial, seuils/forfaits de la décote), eux,
sont bien versionnés via fiscal_engine.parameters comme le reste du droit
fiscal.

LIMITES ASSUMÉES DE CE MODULE (périmètre volontairement restreint) :
  - Garde alternée : NON gérée (le quotient réduit de moitié — 0,25 part par
    enfant au lieu de 0,5 — n'est pas implémenté ; ce module suppose une
    garde exclusive/principale classique).
  - Enfants en situation de handicap (demi-part supplémentaire), anciens
    combattants, cartes d'invalidité : NON gérés.
  - Plafonds spécifiques "personne seule ayant élevé un enfant" (1079€) et
    "veuf avec personne à charge" (5625€) : NON gérés — seuls les deux cas
    les plus courants sont modélisés (plafond standard 1807€/demi-part et
    plafond parent isolé 4262€ pour le premier enfant).
  - Rattachement d'enfants majeurs, pensions alimentaires versées/reçues,
    déductions PER, etc. : NON gérés — `revenu_net_imposable` est supposé
    déjà net de tout cela (donnée d'entrée, pas calculée par ce module).
  - Époux/pacsés en imposition séparée : NON géré (seul le cas standard
    d'imposition commune est traité).
Ces limites doivent être communiquées clairement à l'utilisateur dans
l'interface — ce module ne prétend pas remplacer une déclaration officielle.
"""

from dataclasses import dataclass

import sqlite3

from .calculator import calculer_montant
from .parameters import resoudre_parametre
from .resolver import resoudre_regle


@dataclass
class SituationFoyer:
    """Description de la composition d'un foyer fiscal pour une année donnée.

    Attributes:
        situation_familiale: 'celibataire', 'marie', 'pacse', 'veuf', ou 'divorce'.
        nombre_enfants_a_charge: nombre d'enfants mineurs (ou majeurs
            rattachés) à charge, garde exclusive/principale.
        parent_isole: True si le contribuable élève seul ses enfants sans
            vivre en couple (case "parent isolé" — ouvre droit au plafond
            majoré de 4262€ sur la part du premier enfant).
    """

    situation_familiale: str
    nombre_enfants_a_charge: int = 0
    parent_isole: bool = False


def calculer_nombre_parts(situation: SituationFoyer) -> float:
    """Calcule le nombre de parts de quotient familial.

    Règles appliquées (cf. limites du module en tête de fichier) :
      - 1 part de base pour une personne seule (célibataire, divorcé) ;
      - 2 parts de base pour un couple marié/pacsé ;
      - 2 parts de base pour un veuf/veuve AVEC au moins un enfant à charge
        (maintien du quotient conjugal) ; 1 part sinon ;
      - + 0,5 part pour chacun des deux premiers enfants à charge ;
      - + 1 part pour chaque enfant à charge à partir du troisième ;
      - + 0,5 part supplémentaire si parent isolé avec au moins un enfant.
    """
    if situation.situation_familiale in ("marie", "pacse"):
        base = 2.0
    elif situation.situation_familiale == "veuf" and situation.nombre_enfants_a_charge > 0:
        base = 2.0
    else:
        base = 1.0

    n = situation.nombre_enfants_a_charge
    parts_enfants = 0.5 * min(n, 2) + 1.0 * max(n - 2, 0)

    parts_parent_isole = 0.5 if (situation.parent_isole and n > 0) else 0.0

    return base + parts_enfants + parts_parent_isole


def _parts_de_base(situation: SituationFoyer) -> float:
    """Le nombre de parts de référence AVANT toute majoration (enfants,
    parent isolé) — c'est ce nombre qui sert de comparaison pour calculer
    l'avantage procuré par le quotient familial (voir calculer_impot_foyer).
    """
    if situation.situation_familiale in ("marie", "pacse"):
        return 2.0
    if situation.situation_familiale == "veuf" and situation.nombre_enfants_a_charge > 0:
        return 2.0
    return 1.0


def calculer_impot_foyer(
    conn: sqlite3.Connection,
    situation: SituationFoyer,
    revenu_net_imposable: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule l'impôt sur le revenu final d'un foyer, avec le détail de
    chaque étape (quotient familial, plafonnement, décote) pour traçabilité.

    Args:
        conn: connexion SQLite.
        situation: composition du foyer (voir SituationFoyer).
        revenu_net_imposable: revenu net imposable du foyer, déjà net de tout
            abattement/déduction (ce module ne les calcule pas).
        date_reference: date à utiliser pour résoudre le barème IR et les
            paramètres de plafonnement/décote en vigueur.
        pays_code: pays concerné (défaut 'FR').

    Returns:
        Un dict détaillant chaque étape du calcul :
        {
            "nombre_parts": float,
            "impot_avec_quotient_familial": float,   # avant plafonnement
            "impot_sans_quotient_familial": float,    # référence (parts de base)
            "avantage_quotient_familial": float,      # gain brut du QF
            "avantage_quotient_familial_plafonne": float,
            "impot_apres_plafonnement": float,
            "decote": float,
            "impot_final": float,
        }
    """
    id_ir = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'IR_BAREME' AND pays_code = ?", (pays_code,)
    ).fetchone()
    if id_ir is None:
        raise ValueError(f"Aucun prélèvement 'IR_BAREME' trouvé pour le pays {pays_code!r}.")
    regle_bareme = resoudre_regle(conn, id_ir["id"], date_reference)

    nombre_parts = calculer_nombre_parts(situation)
    parts_base = _parts_de_base(situation)

    impot_par_part_avec_qf = calculer_montant(conn, regle_bareme, montant=revenu_net_imposable / nombre_parts)["montant"]
    impot_avec_qf = impot_par_part_avec_qf * nombre_parts

    impot_par_part_sans_qf = calculer_montant(conn, regle_bareme, montant=revenu_net_imposable / parts_base)["montant"]
    impot_sans_qf = impot_par_part_sans_qf * parts_base

    avantage_qf = max(impot_sans_qf - impot_avec_qf, 0.0)

    # Plafonnement de l'avantage du quotient familial
    plafond_demi_part = resoudre_parametre(conn, "PLAFOND_QF_DEMI_PART", pays_code, date_reference)
    demi_parts_supplementaires = round((nombre_parts - parts_base) * 2)

    if situation.parent_isole and situation.nombre_enfants_a_charge > 0 and demi_parts_supplementaires > 0:
        plafond_parent_isole = resoudre_parametre(
            conn, "PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT", pays_code, date_reference
        )
        # Le plafond majoré ne s'applique qu'à la toute première demi-part
        # (celle du premier enfant) ; les demi-parts suivantes restent au
        # plafond standard.
        plafond_total = plafond_parent_isole + max(demi_parts_supplementaires - 1, 0) * plafond_demi_part
    else:
        plafond_total = demi_parts_supplementaires * plafond_demi_part

    avantage_qf_plafonne = min(avantage_qf, plafond_total)
    impot_apres_plafonnement = impot_sans_qf - avantage_qf_plafonne

    # Décote
    est_couple = situation.situation_familiale in ("marie", "pacse")
    code_seuil = "DECOTE_SEUIL_COUPLE" if est_couple else "DECOTE_SEUIL_CELIBATAIRE"
    code_forfait = "DECOTE_FORFAIT_COUPLE" if est_couple else "DECOTE_FORFAIT_CELIBATAIRE"
    seuil_decote = resoudre_parametre(conn, code_seuil, pays_code, date_reference)
    forfait_decote = resoudre_parametre(conn, code_forfait, pays_code, date_reference)
    taux_decote = resoudre_parametre(conn, "DECOTE_TAUX", pays_code, date_reference)

    if impot_apres_plafonnement < seuil_decote:
        decote = max(forfait_decote - taux_decote * impot_apres_plafonnement, 0.0)
    else:
        decote = 0.0

    impot_final = max(impot_apres_plafonnement - decote, 0.0)

    return {
        "nombre_parts": nombre_parts,
        "impot_avec_quotient_familial": impot_avec_qf,
        "impot_sans_quotient_familial": impot_sans_qf,
        "avantage_quotient_familial": avantage_qf,
        "avantage_quotient_familial_plafonne": avantage_qf_plafonne,
        "impot_apres_plafonnement": impot_apres_plafonnement,
        "decote": decote,
        "impot_final": impot_final,
    }
