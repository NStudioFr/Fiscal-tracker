"""Calcul des droits d'accise sur les boissons alcoolisées nécessitant une
orchestration (sélection de taux selon un seuil de degré, ou cumul
conditionnel d'une cotisation sécurité sociale additionnelle).

Comme fiscal_engine.foyer, .independant et .retraite, ce module orchestre
le moteur générique plutôt que d'être lui-même une donnée fiscale.

Le vin, le cidre et les "produits intermédiaires" n'ont PAS besoin
d'orchestration : leur tarif est un montant fixe par hectolitre,
indépendant du degré d'alcool — ils sont directement utilisables via
categorie_prelevement (voir seed_data/fr_seed_lot3.sql, prélèvements
ACCISE_VIN_TRANQUILLE, ACCISE_VIN_MOUSSEUX, ACCISE_CIDRE_POIRE_HYDROMEL).

La BIÈRE et les SPIRITUEUX en revanche nécessitent CE module :
  - Bière : le tarif par hL dépend d'un seuil de degré (≤2,8% vol vs
    >2,8% vol), et le montant final dépend ADDITIONNELLEMENT du degré
    exact (tarif par hL PAR DEGRÉ, pas par hL seul). Deux facteurs
    (volume ET degré) à combiner, d'où l'usage de type_regle='formule'
    avec la variable 'seuil' (voir calculator.py) pour porter le degré.
  - Spiritueux : le tarif est par hectolitre d'ALCOOL PUR (hlap), qu'il
    faut calculer depuis le volume et le degré (hlap = volume_hL x degré/100).
    Une cotisation sécurité sociale ADDITIONNELLE s'applique uniquement
    aux boissons titrant plus de 18% vol (cumulative avec le droit de
    consommation, pas une alternative).

SOURCE : exclusivement douane.gouv.fr, page "Droits des alcools et
boissons alcooliques" (mise à jour du 15/01/2026), tarifs 2026 fixés par
arrêté du 24/12/2025 (JORF n°0306 du 31/12/2025), citant les articles
L.313-15, L.313-20, L.313-23 et L.313-24/25 du code des impositions sur
les biens et services (CIBS), ainsi que l'article L.245-9 du code de la
sécurité sociale pour la cotisation additionnelle. Voir seed_data/
fr_seed_lot3.sql pour le détail des références par prélèvement.

LIMITES ASSUMÉES :
  - Taux réduit "petites brasseries" (≤200 000 hL/an) non géré — seul le
    taux normal (>2,8% ou ≤2,8%) est appliqué, quelle que soit la taille
    du brasseur (l'information n'est de toute façon pas déductible d'un
    ticket de caisse).
  - Rhums des DOM (tarif spécifique 966,75 €/hlap) non géré séparément —
    ce module traite tout spiritueux via le tarif "autres alcools"
    (1932,42 €/hlap). Une distinction géographique de provenance du rhum
    n'est pas une donnée disponible sur un ticket de caisse standard.
  - Taxe "prémix" (boissons mélangeant alcool et boisson non-alcoolisée)
    non gérée séparément — hors périmètre de ce module.
  - Taux réduit à 40% de la cotisation sécu pour les VDN/VDL AOP (produits
    intermédiaires) non géré — uniquement pertinent pour des produits
    intermédiaires titrant plus de 18% (rare, hors périmètre).
"""

import sqlite3

from .calculator import calculer_montant
from .resolver import resoudre_regle

_SEUIL_DEGRE_BIERE = 2.8
_SEUIL_DEGRE_COTISATION_SECU_ALCOOL_FORT = 18.0


def calculer_droit_biere(
    conn: sqlite3.Connection,
    degre_alcool: float,
    volume_hl: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule le droit d'accise sur une bière.

    Args:
        degre_alcool: titre alcoométrique volumique (ex : 5.0 pour 5% vol).
        volume_hl: volume de la boisson en hectolitres (ex : 0.0033 pour
            une canette de 33cl).
        date_reference: date à utiliser pour résoudre le tarif en vigueur.

    Returns:
        {"montant": float, "tarif_par_hl_degre": float, "categorie_degre": str}
    """
    if degre_alcool <= _SEUIL_DEGRE_BIERE:
        code = "ACCISE_BIERE_LEGERE"
        categorie_degre = "≤2,8% vol"
    else:
        code = "ACCISE_BIERE_NORMALE"
        categorie_degre = ">2,8% vol"

    id_prelevement = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code, pays_code)
    ).fetchone()["id"]
    regle = resoudre_regle(conn, id_prelevement, date_reference)
    resultat = calculer_montant(conn, regle, montant=0.0, quantite=volume_hl, valeur_seuil=degre_alcool)

    return {
        "montant": resultat["montant"],
        "tarif_par_hl_degre": None,  # non exposé directement par une formule (contrairement à taux_applique d'un montant_par_unite)
        "categorie_degre": categorie_degre,
    }


def calculer_droit_spiritueux(
    conn: sqlite3.Connection,
    degre_alcool: float,
    volume_hl: float,
    date_reference: str,
    pays_code: str = "FR",
) -> dict:
    """Calcule le droit de consommation (+ cotisation sécu additionnelle si
    applicable) sur un spiritueux.

    Args:
        degre_alcool: titre alcoométrique volumique (ex : 40.0 pour 40% vol).
        volume_hl: volume de la boisson en hectolitres (ex : 0.007 pour une
            bouteille de 70cl).
        date_reference: date à utiliser pour résoudre les tarifs en vigueur.

    Returns:
        {
            "droit_consommation": float,
            "cotisation_secu": float,       # 0.0 si degré <= 18%
            "total": float,
        }
    """
    id_droit = conn.execute(
        "SELECT id FROM prelevement WHERE code = 'ACCISE_SPIRITUEUX' AND pays_code = ?", (pays_code,)
    ).fetchone()["id"]
    regle_droit = resoudre_regle(conn, id_droit, date_reference)
    droit_consommation = calculer_montant(
        conn, regle_droit, montant=0.0, quantite=volume_hl, valeur_seuil=degre_alcool
    )["montant"]

    cotisation_secu = 0.0
    if degre_alcool > _SEUIL_DEGRE_COTISATION_SECU_ALCOOL_FORT:
        id_cotis = conn.execute(
            "SELECT id FROM prelevement WHERE code = 'COTIS_SOC_ALCOOL_FORT' AND pays_code = ?", (pays_code,)
        ).fetchone()["id"]
        regle_cotis = resoudre_regle(conn, id_cotis, date_reference)
        cotisation_secu = calculer_montant(
            conn, regle_cotis, montant=0.0, quantite=volume_hl, valeur_seuil=degre_alcool
        )["montant"]

    return {
        "droit_consommation": droit_consommation,
        "cotisation_secu": cotisation_secu,
        "total": droit_consommation + cotisation_secu,
    }
