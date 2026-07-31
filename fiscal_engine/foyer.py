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
utilisés (plafonds du quotient familial, seuils/forfaits de la décote), eux,
sont bien versionnés via fiscal_engine.parameters comme le reste du droit
fiscal.

FIABILISÉ le 2026-07-29 : ce module couvrait initialement seulement le cas
standard (couple/célibataire, enfants en garde exclusive, parent isolé
simple). Quatre angles morts ont été comblés à cette date, sourcés sur
BOFiP (BOI-IR-LIQ-10-20, BOI-IR-LIQ-20-20-20) et service-public.gouv.fr
(fiches F2702, F2705, F387, F34088, F35127) :
  1. Garde alternée (quart de part au lieu de demi-part, plafond halved).
  2. Invalidité/ancien combattant : demi-part supplémentaire pour le
     contribuable/conjoint lui-même (plafond majoré 3608€) ET pour les
     personnes à charge titulaires de la carte "mobilité inclusion"
     invalidité (plafond standard 1807€, ou 904€ en garde partagée).
  3. Plafonds spécifiques "personne seule ayant élevé un enfant" (1079€)
     et "veuf avec personne à charge" (5625€ combinés sur les 2 premières
     demi-parts).
  4. Imposition séparée des époux/pacsés (`imposition_separee=True`) :
     traite chaque déclarant comme une part de base, même si légalement
     marié/pacsé.

LIMITES RÉSIDUELLES DE CE MODULE (périmètre encore volontairement
restreint après cette fiabilisation) :
  - `revenu_net_imposable` est un paramètre d'entrée supposé déjà net —
    aucun calcul d'abattement/déduction en amont (pension alimentaire, PER,
    frais réels, rattachement d'enfants majeurs...) n'est effectué par ce
    module.
  - Le plafond majoré "veuf avec personne à charge" (5625€) est implémenté
    comme un plafond combiné couvrant les 2 premières demi-parts (enfants
    et/ou personnes invalides à charge, garde exclusive uniquement — pas
    modélisé en garde alternée). Le mécanisme précis BOFiP (l'avantage
    complémentaire de 2011€ s'applique-t-il dès 1 seule demi-part
    qualifiante, ou seulement à partir de 2 ?) n'a pas pu être confirmé
    avec certitude à cette session — ce module applique le plafond combiné
    5625€ dès qu'il y a AU MOINS une demi-part qualifiante, ce qui peut
    légèrement SURESTIMER l'avantage d'un veuf n'ayant qu'un seul enfant à
    charge et un revenu très élevé. À vérifier sur BOFiP-IR-LIQ-20-20-20 si
    ce cas se présente en pratique.
  - Un veuf(ve) ne peut pas cumuler dans ce module le statut "veuf avec
    personne à charge" (maintien du quotient conjugal) et "parent isolé"
    (`ValueError` si les deux sont demandés simultanément) : en pratique
    ces deux statuts sont mutuellement exclusifs, mais l'articulation
    exacte des cas limites n'est pas garantie à 100% conforme au BOFiP.
  - `personne_seule_ayant_eleve_enfant` (case "L", CGI art. 195 1-d)
    suppose qu'il n'y a plus AUCUN enfant à charge actuellement — ce
    module lève une `ValueError` sinon.
  - Rattachement d'enfants majeurs, situations d'ascendants invalides
    recueillis, etc. : toujours NON gérés.
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
        situation_familiale: 'celibataire', 'marie', 'pacse', 'veuf', ou
            'divorce'.
        nombre_enfants_a_charge: nombre d'enfants mineurs (ou majeurs
            rattachés) à charge, en garde exclusive/principale.
        nombre_enfants_garde_alternee: nombre d'enfants en résidence
            alternée (garde partagée à égalité avec l'autre parent) —
            donne un quart de part par enfant (les 2 premiers) au lieu
            d'une demi-part, la moitié d'une part à partir du 3e.
        parent_isole: True si le contribuable élève seul ses enfants sans
            vivre en couple (case "T" — ouvre droit au plafond majoré sur
            la part du premier enfant : 4262€ en garde exclusive, 2131€ si
            ce premier enfant est en garde alternée). Nécessite au moins
            un enfant (exclusif ou alterné).
        imposition_separee: True si des époux/partenaires de PACS
            légalement mariés/pacsés choisissent ou sont tenus de déposer
            des déclarations séparées (année du mariage/PACS/séparation,
            séparation de biens + résidences distinctes...). Dans ce cas,
            chaque déclaration est traitée comme une part de base (comme
            un célibataire) plutôt que 2 parts, MÊME SI
            `situation_familiale` reste 'marie' ou 'pacse'. Ne peut être
            utilisé qu'avec `situation_familiale` égal à 'marie' ou
            'pacse' (sinon la situation est déjà "séparée" par nature).
        nombre_demi_parts_invalidite_ancien_combattant: nombre de membres
            du foyer (le contribuable et/ou son conjoint) titulaires
            eux-mêmes d'une carte d'invalidité (CMI mention invalidité,
            taux ≥80%), d'une pension militaire/civile d'invalidité ≥40%,
            ou anciens combattants de plus de 74 ans titulaires de la
            carte du combattant — chacun ouvre droit à +0,5 part avec un
            plafond majoré spécifique (3608€ chacun). Doit valoir 0, 1 ou
            2 (le contribuable, son conjoint, ou les deux).
        nombre_enfants_invalides_a_charge: parmi les enfants en garde
            exclusive (`nombre_enfants_a_charge`), combien sont eux-mêmes
            titulaires d'une carte mobilité inclusion mention invalidité —
            ouvre droit à +0,5 part par enfant, EN PLUS de sa part normale
            d'enfant à charge (plafond standard 1807€ par enfant).
        nombre_enfants_invalides_garde_alternee: idem, mais parmi les
            enfants en garde alternée (`nombre_enfants_garde_alternee`) —
            +0,25 part par enfant (plafond 904€).
        personne_seule_ayant_eleve_enfant: True si le contribuable vit
            seul, n'a AUCUN enfant à charge actuellement, mais a élevé
            seul au moins un enfant par le passé pendant au moins 5 ans
            (case "L", CGI art. 195 1-d) — ouvre droit à +0,5 part avec un
            plafond spécifique de 1079€. Incompatible avec le fait d'avoir
            des enfants à charge actuellement ou d'être `parent_isole`
            (`ValueError` sinon).
    """

    situation_familiale: str
    nombre_enfants_a_charge: int = 0
    nombre_enfants_garde_alternee: int = 0
    parent_isole: bool = False
    imposition_separee: bool = False
    nombre_demi_parts_invalidite_ancien_combattant: int = 0
    nombre_enfants_invalides_a_charge: int = 0
    nombre_enfants_invalides_garde_alternee: int = 0
    personne_seule_ayant_eleve_enfant: bool = False


def _a_des_enfants(situation: "SituationFoyer") -> bool:
    return situation.nombre_enfants_a_charge > 0 or situation.nombre_enfants_garde_alternee > 0


def _valider_situation(situation: "SituationFoyer") -> None:
    """Vérifie la cohérence de la situation ; lève ValueError sinon.

    Ces vérifications reflètent des incompatibilités légales réelles (pas
    de simples contraintes de confort de ce module) — voir la docstring de
    SituationFoyer pour le détail de chaque cas.
    """
    for champ in (
        "nombre_enfants_a_charge",
        "nombre_enfants_garde_alternee",
        "nombre_enfants_invalides_a_charge",
        "nombre_enfants_invalides_garde_alternee",
    ):
        if getattr(situation, champ) < 0:
            raise ValueError(f"{champ} ne peut pas être négatif.")

    if situation.nombre_enfants_invalides_a_charge > situation.nombre_enfants_a_charge:
        raise ValueError(
            "nombre_enfants_invalides_a_charge ne peut pas dépasser nombre_enfants_a_charge."
        )
    if situation.nombre_enfants_invalides_garde_alternee > situation.nombre_enfants_garde_alternee:
        raise ValueError(
            "nombre_enfants_invalides_garde_alternee ne peut pas dépasser "
            "nombre_enfants_garde_alternee."
        )

    if situation.nombre_demi_parts_invalidite_ancien_combattant not in (0, 1, 2):
        raise ValueError(
            "nombre_demi_parts_invalidite_ancien_combattant doit valoir 0, 1 ou 2 "
            "(le contribuable, son conjoint, ou les deux)."
        )

    if situation.imposition_separee and situation.situation_familiale not in ("marie", "pacse"):
        raise ValueError(
            "imposition_separee=True n'a de sens que si situation_familiale vaut "
            "'marie' ou 'pacse' (un célibataire/divorcé/veuf est déjà imposé "
            "séparément par nature)."
        )

    if situation.parent_isole and not _a_des_enfants(situation):
        raise ValueError("parent_isole=True nécessite au moins un enfant à charge.")

    if situation.situation_familiale == "veuf" and situation.parent_isole:
        raise ValueError(
            "situation_familiale='veuf' et parent_isole=True est une combinaison non "
            "gérée par ce module : un veuf qui maintient le quotient conjugal "
            "(2 parts) et le statut de parent isolé (case T, qui suppose de ne pas "
            "en bénéficier) sont traités comme mutuellement exclusifs ici. Choisir "
            "l'un des deux selon la situation réelle du contribuable."
        )

    if situation.personne_seule_ayant_eleve_enfant:
        if _a_des_enfants(situation):
            raise ValueError(
                "personne_seule_ayant_eleve_enfant=True suppose qu'il n'y a plus "
                "AUCUN enfant à charge actuellement (c'est une demi-part accordée "
                "pour avoir élevé seul un enfant PAR LE PASSÉ, CGI art. 195 1-d). "
                "Si des enfants sont encore à charge, utiliser parent_isole à la "
                "place."
            )
        if situation.parent_isole:
            raise ValueError(
                "personne_seule_ayant_eleve_enfant et parent_isole ne peuvent pas "
                "être vrais simultanément."
            )


def calculer_nombre_parts(situation: "SituationFoyer") -> float:
    """Calcule le nombre de parts de quotient familial.

    Règles appliquées (cf. limites du module en tête de fichier) :
      - 1 part de base pour une personne seule (célibataire, divorcé), ou en
        cas d'imposition séparée d'époux/pacsés ;
      - 2 parts de base pour un couple marié/pacsé en imposition commune ;
      - 2 parts de base pour un veuf/veuve maintenant le quotient conjugal
        (au moins un enfant OU une personne invalide à charge) ; 1 part sinon ;
      - + 0,5 part pour chacun des deux premiers enfants à charge exclusive,
        + 1 part par enfant à charge exclusive à partir du 3e ;
      - + 0,25 part pour chacun des deux premiers enfants en garde
        alternée, + 0,5 part par enfant en garde alternée à partir du 3e ;
      - + 0,5 part supplémentaire par enfant invalide à charge exclusive
        (en plus de sa part normale d'enfant), + 0,25 part si en garde
        alternée ;
      - + 0,5 part supplémentaire si parent isolé avec au moins un enfant
        en garde exclusive, + 0,25 part si seulement des enfants en garde
        alternée ;
      - + 0,5 part par membre du foyer (contribuable/conjoint) invalide ou
        ancien combattant (0, 1 ou 2) ;
      - + 0,5 part si personne seule ayant élevé un enfant par le passé
        (sans enfant à charge actuellement).
    """
    _valider_situation(situation)

    a_charges = _a_des_enfants(situation) or (
        situation.nombre_enfants_invalides_a_charge > 0
        or situation.nombre_enfants_invalides_garde_alternee > 0
    )

    if situation.imposition_separee:
        base = 1.0
    elif situation.situation_familiale in ("marie", "pacse"):
        base = 2.0
    elif situation.situation_familiale == "veuf" and a_charges:
        base = 2.0
    else:
        base = 1.0

    n_exclusif = situation.nombre_enfants_a_charge
    n_alternee = situation.nombre_enfants_garde_alternee
    parts_enfants = (
        0.5 * min(n_exclusif, 2) + 1.0 * max(n_exclusif - 2, 0)
        + 0.25 * min(n_alternee, 2) + 0.5 * max(n_alternee - 2, 0)
    )

    parts_invalidite_charges = (
        0.5 * situation.nombre_enfants_invalides_a_charge
        + 0.25 * situation.nombre_enfants_invalides_garde_alternee
    )

    parts_invalidite_foyer = 0.5 * situation.nombre_demi_parts_invalidite_ancien_combattant

    if situation.parent_isole and n_exclusif > 0:
        parts_parent_isole = 0.5
    elif situation.parent_isole and n_alternee > 0:
        parts_parent_isole = 0.25
    else:
        parts_parent_isole = 0.0

    parts_personne_seule = 0.5 if situation.personne_seule_ayant_eleve_enfant else 0.0

    return (
        base + parts_enfants + parts_invalidite_charges + parts_invalidite_foyer
        + parts_parent_isole + parts_personne_seule
    )


def _parts_de_base(situation: "SituationFoyer") -> float:
    """Le nombre de parts de référence AVANT toute majoration (enfants,
    invalidité, parent isolé...) — c'est ce nombre qui sert de comparaison
    pour calculer l'avantage procuré par le quotient familial (voir
    calculer_impot_foyer).
    """
    if situation.imposition_separee:
        return 1.0
    if situation.situation_familiale in ("marie", "pacse"):
        return 2.0
    a_charges = _a_des_enfants(situation) or (
        situation.nombre_enfants_invalides_a_charge > 0
        or situation.nombre_enfants_invalides_garde_alternee > 0
    )
    if situation.situation_familiale == "veuf" and a_charges:
        return 2.0
    return 1.0


def _calculer_plafond_avantage_qf(
    conn: sqlite3.Connection, situation: "SituationFoyer", pays_code: str, date_reference: str
) -> float:
    """Calcule le plafond total de l'avantage du quotient familial, en
    répartissant chaque demi-part (ou quart de part) supplémentaire dans le
    bon "plafond spécifique" quand applicable, sinon au plafond standard.

    Voir la docstring du module pour le détail des plafonds gérés et leurs
    sources, et la limite documentée sur le cas "veuf avec 1 seule demi-part
    qualifiante".
    """
    plafond_total = 0.0

    # --- Invalidité / ancien combattant du contribuable ou du conjoint ---
    if situation.nombre_demi_parts_invalidite_ancien_combattant > 0:
        plafond_invalidite_foyer = resoudre_parametre(
            conn, "PLAFOND_QF_INVALIDITE_ANCIEN_COMBATTANT", pays_code, date_reference
        )
        plafond_total += situation.nombre_demi_parts_invalidite_ancien_combattant * plafond_invalidite_foyer

    # --- Personne seule ayant élevé un enfant (case L) ---
    if situation.personne_seule_ayant_eleve_enfant:
        plafond_total += resoudre_parametre(
            conn, "PLAFOND_QF_PERSONNE_SEULE_AYANT_ELEVE_ENFANT", pays_code, date_reference
        )

    # --- Pool "garde exclusive" : enfants normaux + bonus enfants invalides ---
    unites_normal_exclusif = (
        min(situation.nombre_enfants_a_charge, 2) + 2 * max(situation.nombre_enfants_a_charge - 2, 0)
    )
    unites_invalidite_exclusif = situation.nombre_enfants_invalides_a_charge

    if situation.parent_isole and unites_normal_exclusif > 0:
        plafond_total += resoudre_parametre(
            conn, "PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT", pays_code, date_reference
        )
        unites_normal_exclusif -= 1
    elif situation.situation_familiale == "veuf" and (unites_normal_exclusif + unites_invalidite_exclusif) > 0:
        plafond_veuf = resoudre_parametre(conn, "PLAFOND_QF_VEUF_AVEC_CHARGE", pays_code, date_reference)
        plafond_total += plafond_veuf
        unites_a_couvrir = min(2, unites_normal_exclusif + unites_invalidite_exclusif)
        consomme_normal = min(unites_a_couvrir, unites_normal_exclusif)
        unites_normal_exclusif -= consomme_normal
        unites_invalidite_exclusif -= (unites_a_couvrir - consomme_normal)

    unites_restantes_exclusif = unites_normal_exclusif + unites_invalidite_exclusif
    if unites_restantes_exclusif > 0:
        plafond_demi_part = resoudre_parametre(conn, "PLAFOND_QF_DEMI_PART", pays_code, date_reference)
        plafond_total += unites_restantes_exclusif * plafond_demi_part

    # --- Pool "garde alternée" : enfants normaux + bonus enfants invalides ---
    unites_normal_alternee = (
        min(situation.nombre_enfants_garde_alternee, 2)
        + 2 * max(situation.nombre_enfants_garde_alternee - 2, 0)
    )
    unites_invalidite_alternee = situation.nombre_enfants_invalides_garde_alternee

    if situation.parent_isole and situation.nombre_enfants_a_charge == 0 and unites_normal_alternee > 0:
        plafond_total += resoudre_parametre(
            conn, "PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT_GARDE_ALTERNEE", pays_code, date_reference
        )
        unites_normal_alternee -= 1

    unites_restantes_alternee = unites_normal_alternee + unites_invalidite_alternee
    if unites_restantes_alternee > 0:
        plafond_quart_part = resoudre_parametre(conn, "PLAFOND_QF_QUART_PART", pays_code, date_reference)
        plafond_total += unites_restantes_alternee * plafond_quart_part

    return plafond_total


def calculer_impot_foyer(
    conn: sqlite3.Connection,
    situation: "SituationFoyer",
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
    _valider_situation(situation)

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

    plafond_total = _calculer_plafond_avantage_qf(conn, situation, pays_code, date_reference)

    avantage_qf_plafonne = min(avantage_qf, plafond_total)
    impot_apres_plafonnement = impot_sans_qf - avantage_qf_plafonne

    # Décote
    est_couple = situation.situation_familiale in ("marie", "pacse") and not situation.imposition_separee
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
