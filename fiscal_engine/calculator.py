"""Calcul du montant d'un prélèvement, une fois la règle applicable résolue.

Ce module ne fait AUCUN choix de règle (c'est le rôle de resolver.py) : il se
contente d'appliquer une règle déjà déterminée aux données d'une ligne de
document. Séparer les deux responsabilités permet de tester le calcul
indépendamment de la logique de résolution temporelle.

Six types de règles sont gérés, chacun utilisant une donnée différente de
la ligne comme assiette :
  - 'taux_fixe' (assiette 'base_directe' ou 'ttc_inclus') : utilise `montant`.
  - 'montant_fixe' : ignore `montant`/`quantite`, renvoie un montant constant.
  - 'formule' : utilise `montant` et `quantite`, disponibles comme variables
    'base' et 'quantite' dans la formule, ENRICHIES de tous les paramètres
    de référence versionnés en vigueur à `date_reference` (ex : 'PMSS_MENSUEL').
    C'est ce mécanisme qui permet d'exprimer un plafonnement ou un seuil
    (ex : "min(base, PMSS_MENSUEL) * 0.069") sans ajouter de colonne dédiée
    à regle_prelevement à chaque nouveau cas de plafond rencontré.
  - 'montant_par_unite' : utilise `quantite` (ex : nombre de litres), PAS
    `montant`. Nécessite que l'unité de la ligne (`unite_quantite`) soit
    compatible avec l'unité de la règle (`unite`) — voir units.py.
  - 'bareme_progressif' : utilise `montant`, découpé en tranches CUMULATIVEMENT
    (voir tranche_bareme) — chaque tranche contribue sa part au résultat.
  - 'bareme_a_seuil' : sélectionne UNE SEULE tranche selon `valeur_seuil`
    (qui peut être une grandeur DIFFÉRENTE de `montant` — ex : le revenu
    fiscal de référence détermine le taux de CSG retraite, mais ce taux
    s'applique ensuite à la pension brute). Pas de cumul progressif : c'est
    un mécanisme "tout ou rien par palier".
  - 'montant_declare' : PAS calculable par ce module — le montant est déjà
    connu, lu directement sur le document source (ex : taxe foncière sur un
    avis d'imposition, dont le taux est voté par chaque commune, donc non
    modélisable nationalement). Appeler calculer_montant() sur une règle de
    ce type lève une ValueError explicite ; le flux normal passe par
    orchestrator.py qui court-circuite le calcul pour ce cas.

Point d'attention (corrigé suite à revue) : pour les règles de type
'taux_fixe', deux cas de figure existent et sont distingués via la colonne
`assiette` de regle_prelevement :
  - 'base_directe' : le taux s'applique tel quel sur le montant fourni.
    Cas typique : une cotisation calculée sur un salaire brut affiché en
    clair sur une fiche de paie.
  - 'ttc_inclus'   : le montant fourni est déjà TTC et contient le
    prélèvement ; il faut l'EXTRAIRE, pas l'ajouter par-dessus.
    Cas typique : la TVA sur un article de ticket de caisse, où le prix
    affiché (ex : 10,00 €) est déjà toutes taxes comprises.
"""

import sqlite3

from .exceptions import AucuneTrancheApplicable, DonneesBaremeManquantes
from .formula import evaluer_formule
from .parameters import charger_parametres_disponibles
from .units import convertir_quantite


def calculer_montant(
    conn: sqlite3.Connection,
    regle: sqlite3.Row,
    montant: float,
    quantite: float = 1.0,
    unite_quantite: str = "unite",
    date_reference: str | None = None,
    pays_code: str = "FR",
    valeur_seuil: float | None = None,
) -> dict:
    """Calcule le montant d'un prélèvement pour une règle et une ligne données.

    Args:
        conn: connexion SQLite (nécessaire pour aller chercher les tranches
            en cas de barème progressif, ou les paramètres de référence en
            cas de formule).
        regle: ligne de `regle_prelevement` (issue de resolver.resoudre_regle).
        montant: montant en euros de la ligne (ex : montant TTC d'une ligne
            de ticket, salaire brut mensuel...). Utilisé par 'taux_fixe' et
            'formule' (variable 'base').
        quantite: quantité de la ligne dans l'unité `unite_quantite` (ex :
            40.0 si la ligne représente 40 litres). Utilisée par
            'montant_par_unite' et disponible dans 'formule' (variable
            'quantite'). Vaut 1.0 par défaut pour les lignes sans notion de
            quantité physique (ex : une ligne de cotisation sociale).
        unite_quantite: unité dans laquelle `quantite` est exprimée (ex :
            'L', 'kg', 'unite'). Voir fiscal_engine.units pour les unités
            reconnues.
        date_reference: date à utiliser pour résoudre les paramètres de
            référence (PMSS, etc.) disponibles dans une formule. Uniquement
            nécessaire pour type_regle = 'formule' ; si omis, la formule
            n'aura accès qu'à 'base' et 'quantite' (pas aux paramètres de
            référence — une formule qui en a besoin lèvera alors
            FormuleInvalide pour variable inconnue).
        pays_code: pays dont les paramètres de référence doivent être
            chargés (défaut 'FR' — ce projet est mono-pays à ce stade).
        valeur_seuil: pour type_regle = 'bareme_a_seuil' UNIQUEMENT : la
            valeur utilisée pour déterminer QUELLE tranche s'applique (ex :
            le revenu fiscal de référence pour la CSG sur pension de
            retraite). ATTENTION : cette valeur peut être DIFFÉRENTE de
            `montant` (la base à laquelle le taux trouvé sera appliqué) —
            ex : le seuil est le RFR, mais le taux trouvé s'applique à la
            pension brute, pas au RFR lui-même. Si omis, `montant` est
            utilisé comme valeur de seuil par défaut (cas où seuil et base
            sont la même grandeur).

    Returns:
        Un dict {"montant": float, "base_calcul": float, "taux_applique": float | None}
        prêt à être inséré dans la table `prelevement_calcule`. Pour une
        règle 'montant_par_unite', "base_calcul" contient la quantité
        convertie dans l'unité de la règle, et "taux_applique" contient le
        montant unitaire appliqué (réutilisation du champ, pas un taux au
        sens strict).
    """
    type_regle = regle["type_regle"]

    if type_regle == "taux_fixe":
        taux = regle["taux"]
        assiette = regle["assiette"]

        if assiette == "ttc_inclus":
            # `montant` est un montant TTC qui contient déjà le prélèvement.
            # Montant HT (hors ce prélèvement) = montant / (1 + taux)
            # Montant du prélèvement inclus     = montant - montant_HT
            # Ex : 10€ TTC à 20% de TVA -> HT = 8.33€, TVA incluse = 1.67€
            base_hors_prelevement = montant / (1 + taux)
            montant_calcule = montant - base_hors_prelevement
            return {"montant": montant_calcule, "base_calcul": base_hors_prelevement, "taux_applique": taux}

        # assiette == "base_directe" : le taux s'applique tel quel
        montant_calcule = montant * taux
        return {"montant": montant_calcule, "base_calcul": montant, "taux_applique": taux}

    if type_regle == "montant_fixe":
        return {"montant": regle["montant_fixe"], "base_calcul": montant, "taux_applique": None}

    if type_regle == "formule":
        variables = {"base": montant, "quantite": quantite}
        if date_reference is not None:
            variables.update(charger_parametres_disponibles(conn, pays_code, date_reference))
        montant_calcule = evaluer_formule(regle["formule"], variables)
        return {"montant": montant_calcule, "base_calcul": montant, "taux_applique": None}

    if type_regle == "montant_par_unite":
        quantite_convertie = convertir_quantite(quantite, unite_quantite, regle["unite"])
        montant_calcule = quantite_convertie * regle["montant_unitaire"]
        return {"montant": montant_calcule, "base_calcul": quantite_convertie, "taux_applique": regle["montant_unitaire"]}

    if type_regle == "bareme_progressif":
        montant_calcule, taux_marginal = _calculer_bareme_progressif(conn, regle["id"], montant)
        return {"montant": montant_calcule, "base_calcul": montant, "taux_applique": taux_marginal}

    if type_regle == "bareme_a_seuil":
        valeur_a_utiliser = valeur_seuil if valeur_seuil is not None else montant
        taux_trouve = _trouver_taux_par_seuil(conn, regle["id"], valeur_a_utiliser)
        montant_calcule = montant * taux_trouve
        return {"montant": montant_calcule, "base_calcul": montant, "taux_applique": taux_trouve}

    if type_regle == "montant_declare":
        # Ce type marque un prélèvement dont le montant n'est pas calculable
        # (pas de taux national) et doit être lu directement sur le document
        # source par l'utilisateur (cf. orchestrator.py, branche
        # ligne_document.prelevement_id renseigné). Appeler calculer_montant
        # dessus est une erreur de programmation, pas un cas normal : on le
        # signale explicitement plutôt que de renvoyer un montant à 0 ou
        # incorrect silencieusement.
        raise ValueError(
            f"La règle id={regle['id']} est de type 'montant_declare' : son montant doit être "
            f"lu directement sur le document source (ligne_document.montant), pas calculé. "
            f"calculer_montant() ne doit pas être appelé pour ce type de règle."
        )

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


def _trouver_taux_par_seuil(conn: sqlite3.Connection, regle_id: int, valeur_seuil: float) -> float:
    """Trouve LE taux applicable (une seule tranche, pas de cumul) pour une
    règle de type 'bareme_a_seuil', selon la tranche où tombe `valeur_seuil`.

    Contrairement à _calculer_bareme_progressif, il n'y a ici AUCUNE somme
    cumulative : une seule tranche est sélectionnée et son taux est renvoyé
    tel quel, à appliquer par l'appelant à la base de son choix (qui peut
    être une grandeur complètement différente de `valeur_seuil` — voir
    calculer_montant).
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
            f"La règle id={regle_id} est de type 'bareme_a_seuil' mais n'a "
            f"aucune tranche associée dans tranche_bareme."
        )

    for tranche in tranches:
        borne_min = tranche["borne_min"]
        borne_max = tranche["borne_max"]  # None = pas de plafond (dernière tranche)
        if valeur_seuil >= borne_min and (borne_max is None or valeur_seuil <= borne_max):
            return tranche["taux"]

    raise AucuneTrancheApplicable(
        f"Aucune tranche de la règle id={regle_id} ne couvre la valeur de seuil {valeur_seuil}. "
        f"Vérifier la continuité des bornes dans tranche_bareme."
    )
