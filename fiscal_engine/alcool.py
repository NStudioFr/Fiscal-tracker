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
L.313-15, L.313-20, L.313-21, L.313-23 et L.313-24/25 du code des
impositions sur les biens et services (CIBS), l'article L.245-9 du code de
la sécurité sociale pour les cotisations additionnelles, et l'article 1613
bis du CGI (Légifrance) pour la taxe prémix. Voir seed_data/
fr_seed_lot3.sql pour le détail des références par prélèvement.

FIABILISÉ le 2026-07-29 (PROJECT_STATE.md section 7.6) : les 4 limites
listées ci-dessous à cette date (petites brasseries, rhums DOM, VDN/VDL
AOP, prémix) sont désormais couvertes via de nouveaux paramètres optionnels
et 2 nouvelles fonctions. Voir chaque fonction pour le détail et les
sources.

LIMITES RÉSIDUELLES :
  - Rhums DOM : le contingent annuel (quota au-delà duquel une "soulte" de
    304,90€/hlap s'ajoute) n'est PAS vérifié — le tarif réduit est toujours
    appliqué quand `rhum_dom=True`, en assumant l'usage le plus courant.
  - VDN/VDL AOP : pour les "autres produits intermédiaires" (non AOP)
    titrant plus de 18% vol., la cotisation sécu correspondante n'est pas
    gérée (cas rare).
  - Prémix : la fonction ne détermine pas elle-même si un produit RELÈVE de
    la définition légale du prémix (Art. 1613 bis I CGI) — c'est à
    l'appelant de le déterminer. Elle ne fait que calculer le bon tarif
    UNE FOIS qu'on sait que c'est un prémix, et distingue seulement les 2
    catégories tarifaires (vin/fermenté vs autre), avec 'autre' comme
    valeur par défaut car majoritaire sur le marché.
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
    petite_brasserie_independante: bool = False,
) -> dict:
    """Calcule le droit d'accise sur une bière.

    Args:
        degre_alcool: titre alcoométrique volumique (ex : 5.0 pour 5% vol).
        volume_hl: volume de la boisson en hectolitres (ex : 0.0033 pour
            une canette de 33cl).
        date_reference: date à utiliser pour résoudre le tarif en vigueur.
        petite_brasserie_independante: True si la bière est produite par une
            brasserie indépendante produisant au plus 200 000 hL par an —
            ouvre droit, par dérogation, au tarif "légère" (4,12€/hL·degré)
            même si degre_alcool > 2,8% vol. Sans effet si degre_alcool
            <= 2,8% vol (le tarif léger s'applique déjà pour cette raison).
            Cette information n'est généralement pas déductible d'un simple
            ticket de caisse — à fournir explicitement par l'appelant s'il
            la connaît (ex : import d'un catalogue fournisseur).

    Returns:
        {"montant": float, "tarif_par_hl_degre": float, "categorie_degre": str}
    """
    if degre_alcool <= _SEUIL_DEGRE_BIERE:
        code = "ACCISE_BIERE_LEGERE"
        categorie_degre = "≤2,8% vol"
    elif petite_brasserie_independante:
        code = "ACCISE_BIERE_PETITE_BRASSERIE"
        categorie_degre = ">2,8% vol, petite brasserie indépendante (≤200 000 hL/an)"
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
    rhum_dom: bool = False,
) -> dict:
    """Calcule le droit de consommation (+ cotisation sécu additionnelle si
    applicable) sur un spiritueux.

    Args:
        degre_alcool: titre alcoométrique volumique (ex : 40.0 pour 40% vol).
        volume_hl: volume de la boisson en hectolitres (ex : 0.007 pour une
            bouteille de 70cl).
        date_reference: date à utiliser pour résoudre les tarifs en vigueur.
        rhum_dom: True si c'est un rhum traditionnel des départements
            d'outre-mer — ouvre droit au tarif réduit (966,75€/hlap au lieu
            de 1932,42€/hlap). Le contingent annuel n'est PAS vérifié (voir
            limite résiduelle en tête de fichier) : le tarif réduit est
            appliqué systématiquement dès que ce paramètre vaut True. La
            cotisation sécu (si degré > 18%) s'applique de la même façon
            que pour tout autre spiritueux (pas de réduction connue liée au
            statut DOM pour cette cotisation).

    Returns:
        {
            "droit_consommation": float,
            "cotisation_secu": float,       # 0.0 si degré <= 18%
            "total": float,
        }
    """
    code_droit = "ACCISE_SPIRITUEUX_RHUM_DOM" if rhum_dom else "ACCISE_SPIRITUEUX"
    id_droit = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code_droit, pays_code)
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


def calculer_droit_produit_intermediaire(
    conn: sqlite3.Connection,
    degre_alcool: float,
    volume_hl: float,
    date_reference: str,
    pays_code: str = "FR",
    vdn_vdl_aop: bool = False,
) -> dict:
    """Calcule le droit de circulation (+ cotisation sécu additionnelle si
    applicable) sur un "produit intermédiaire" (vin doux naturel, vin de
    liqueur, autre produit titrant entre les vins et les spiritueux).

    Args:
        degre_alcool: titre alcoométrique volumique.
        volume_hl: volume de la boisson en hectolitres.
        date_reference: date à utiliser pour résoudre les tarifs en vigueur.
        vdn_vdl_aop: True si c'est un vin doux naturel ou un vin de liqueur
            à appellation d'origine protégée — ouvre droit à l'accise
            réduite (52,39€/hL au lieu de 209,53€/hL) ET, si degre_alcool >
            18%, à une cotisation sécu réduite et calculée SUR UNE BASE
            DIFFÉRENTE (20,97€ par hL de PRODUIT FINI, pas d'alcool pur —
            contrairement à COTIS_SOC_ALCOOL_FORT pour les spiritueux). Pour
            les produits intermédiaires NON AOP titrant plus de 18% vol., la
            cotisation sécu correspondante n'est pas gérée (limite
            résiduelle, cas rare — voir tête de fichier).

    Returns:
        {
            "droit_circulation": float,
            "cotisation_secu": float,       # 0.0 si non VDN/VDL AOP ou degré <= 18%
            "total": float,
        }
    """
    code_droit = "ACCISE_PRODUIT_INTERMEDIAIRE_VDN_VDL_AOP" if vdn_vdl_aop else "ACCISE_PRODUIT_INTERMEDIAIRE_AUTRE"
    id_droit = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code_droit, pays_code)
    ).fetchone()["id"]
    regle_droit = resoudre_regle(conn, id_droit, date_reference)
    droit_circulation = calculer_montant(
        conn, regle_droit, montant=0.0, quantite=volume_hl, unite_quantite="hL"
    )["montant"]

    cotisation_secu = 0.0
    if vdn_vdl_aop and degre_alcool > _SEUIL_DEGRE_COTISATION_SECU_ALCOOL_FORT:
        id_cotis = conn.execute(
            "SELECT id FROM prelevement WHERE code = 'COTIS_SOC_VDN_VDL_AOP' AND pays_code = ?", (pays_code,)
        ).fetchone()["id"]
        regle_cotis = resoudre_regle(conn, id_cotis, date_reference)
        # NB : base = volume en hL de produit fini, contrairement à
        # COTIS_SOC_ALCOOL_FORT (spiritueux) qui utilise l'alcool pur — donc
        # pas de valeur_seuil ici, le tarif est déjà "par hL" tout court.
        cotisation_secu = calculer_montant(
            conn, regle_cotis, montant=0.0, quantite=volume_hl, unite_quantite="hL"
        )["montant"]

    return {
        "droit_circulation": droit_circulation,
        "cotisation_secu": cotisation_secu,
        "total": droit_circulation + cotisation_secu,
    }


_CODES_TAXE_PREMIX = {
    "vin": "TAXE_PREMIX_VIN",
    "autre": "TAXE_PREMIX_AUTRE",
}


def calculer_taxe_premix(
    conn: sqlite3.Connection,
    degre_alcool: float,
    volume_hl: float,
    date_reference: str,
    pays_code: str = "FR",
    categorie: str = "autre",
) -> dict:
    """Calcule la taxe prémix (Art. 1613 bis CGI, versée à la CNAM).

    Cette fonction NE DÉTERMINE PAS si un produit relève de la définition
    légale du prémix (Art. 1613 bis I CGI : mélange alcool + boisson non
    alcoolisée, ou produit ne répondant pas aux définitions réglementaires
    de vin/spiritueux + >35g de sucre/L, avec un titre alcoométrique final
    entre 1,2% et 12% vol.) — c'est à l'appelant de le déterminer. Elle
    calcule uniquement le bon tarif une fois cette qualification établie.

    Args:
        degre_alcool: titre alcoométrique volumique du produit final.
        volume_hl: volume en hectolitres.
        date_reference: date à utiliser pour résoudre le tarif en vigueur.
        categorie: 'vin' (3€/décilitre d'alcool pur = 3000€/hlap — mélanges
            relevant des catégories fiscales des vins ou autres boissons
            fermentées, Art. 1613 bis II 1° CGI) ou 'autre' (11€/décilitre =
            11000€/hlap — tous les autres cas, notamment les prémix à base
            de spiritueux, Art. 1613 bis II 2° CGI). 'autre' est la valeur
            par défaut car elle couvre la majorité des prémix du marché.

    Returns:
        {"montant": float, "categorie": str}

    Raises:
        ValueError: si categorie n'est ni 'vin' ni 'autre'.
    """
    code = _CODES_TAXE_PREMIX.get(categorie)
    if code is None:
        raise ValueError(f"categorie de prémix inconnue : {categorie!r} (attendu 'vin' ou 'autre')")

    id_taxe = conn.execute(
        "SELECT id FROM prelevement WHERE code = ? AND pays_code = ?", (code, pays_code)
    ).fetchone()["id"]
    regle = resoudre_regle(conn, id_taxe, date_reference)
    resultat = calculer_montant(conn, regle, montant=0.0, quantite=volume_hl, valeur_seuil=degre_alcool)

    return {"montant": resultat["montant"], "categorie": categorie}
