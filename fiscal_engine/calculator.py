"""Calcul du montant d'un prélèvement, une fois la règle applicable résolue.

Ce module ne fait AUCUN choix de règle (c'est le rôle de resolver.py) : il se
contente d'appliquer une règle déjà déterminée à une base de calcul donnée.
Séparer les deux responsabilités permet de tester le calcul indépendamment
de la logique de résolution temporelle.

Point d'attention (corrigé suite à revue) : pour les règles de type
'taux_fixe', deux cas de figure existent et sont distingués via la colonne
`assiette` de regle_prelevement :
  - 'base_directe' : le taux s'applique tel quel sur la base fournie.
    Cas typique : une cotisation calculée sur un salaire brut affiché en
    clair sur une fiche de paie.
  - 'ttc_inclus'   : la base fournie est déjà TTC et contient le
    prélèvement ; il faut l'EXTRAIRE, pas l'ajouter par-dessus.
    Cas typique : la TVA sur un article de ticket de caisse, où le prix
    affiché (ex : 10,00 €) est déjà toutes taxes comprises.
"""

import sqlite3

from .exceptions import DonneesBaremeManquantes
from .formula import evaluer_formule


def calculer_montant(conn: sqlite3.Connection, regle: sqlite3.Row, base: float) -> dict:
    """Calcule le montant d'un prélèvement pour une règle et une base données.

    Args:
        conn: connexion SQLite (nécessaire pour aller chercher les tranches
            en cas de barème progressif).
        regle: ligne de `regle_prelevement` (issue de resolver.resoudre_regle).
        base: montant de base sur lequel le prélèvement s'applique (ex :
            montant TTC d'une ligne de ticket, salaire brut mensuel...).

    Returns:
        Un dict {"montant": float, "base_calcul": float, "taux_applique": float | None}
        prêt à être inséré dans la table `prelevement_calcule`.
    """
    type_regle = regle["type_regle"]

    if type_regle == "taux_fixe":
        taux = regle["taux"]
        assiette = regle["assiette"]

        if assiette == "ttc_inclus":
            # `base` est un montant TTC qui contient déjà le prélèvement.
            # Montant HT (hors ce prélèvement) = base / (1 + taux)
            # Montant du prélèvement inclus     = base - montant_HT
            # Ex : 10€ TTC à 20% de TVA -> HT = 8.33€, TVA incluse = 1.67€
            base_hors_prelevement = base / (1 + taux)
            montant = base - base_hors_prelevement
            return {"montant": montant, "base_calcul": base_hors_prelevement, "taux_applique": taux}

        # assiette == "base_directe" : le taux s'applique tel quel
        montant = base * taux
        return {"montant": montant, "base_calcul": base, "taux_applique": taux}

    if type_regle == "montant_fixe":
        return {"montant": regle["montant_fixe"], "base_calcul": base, "taux_applique": None}

    if type_regle == "formule":
        montant = evaluer_formule(regle["formule"], {"base": base})
        return {"montant": montant, "base_calcul": base, "taux_applique": None}

    if type_regle == "bareme_progressif":
        montant, taux_marginal = _calculer_bareme_progressif(conn, regle["id"], base)
        return {"montant": montant, "base_calcul": base, "taux_applique": taux_marginal}

    raise ValueError(f"type_regle inconnu : {type_regle!r}")  # ne devrait jamais arriver (contrainte CHECK en base)


def _calculer_bareme_progressif(conn: sqlite3.Connection, regle_id: int, base: float) -> tuple[float, float | None]:
    """Applique un barème progressif par tranches (ex : barème de l'IR).

    Chaque tranche de la base est taxée au taux de SA tranche, pas au taux
    de la tranche la plus haute atteinte (calcul progressif standard).
    """
    tranches = conn.execute(
        """
        SELECT borne_min, borne_max, taux
        FROM tranche_bareme
        WHERE regle_id = ?
        ORDER BY borne_min
        """,
        (regle_id,),
    ).fetchall()

    if not tranches:
        raise DonneesBaremeManquantes(
            f"La règle id={regle_id} est de type 'bareme_progressif' mais n'a "
            f"aucune tranche associée dans tranche_bareme."
        )

    montant_total = 0.0
    taux_marginal = 0.0  # taux de la dernière tranche atteinte, utile pour affichage
    for tranche in tranches:
        borne_min = tranche["borne_min"]
        borne_max = tranche["borne_max"]  # None = pas de plafond
        taux = tranche["taux"]

        if base <= borne_min:
            break

        plafond_tranche = base if borne_max is None else min(base, borne_max)
        montant_dans_tranche = max(0.0, plafond_tranche - borne_min)
        montant_total += montant_dans_tranche * taux
        if montant_dans_tranche > 0:
            taux_marginal = taux

    return montant_total, taux_marginal
