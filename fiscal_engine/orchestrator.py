"""Orchestration : relie resolver + calculator pour traiter une ligne de document.

Deux cas de figure, cf. docs/architecture.md :
  1. La ligne vient d'un ticket/facture (achat) : on connaît la catégorie
     produit, il faut retrouver via `categorie_prelevement` quels
     prélèvements s'appliquent, puis les calculer un par un.
  2. La ligne vient d'une fiche de paie : le prélèvement est déjà nommé
     explicitement (ligne_document.prelevement_id renseigné) et son montant
     est déjà connu (lu directement sur le document) — pas de calcul à faire,
     juste un enregistrement pour la traçabilité et les rapports.

FIABILISÉ le 2026-07-29 (PROJECT_STATE.md section 7.5) : cette
orchestration sait désormais gérer les règles de type
'montant_par_unite_a_seuil' (ex : les 2 taxes sur les boissons
sucrées/édulcorées) quand elles sont rattachées à une catégorie de produit
dans `categorie_prelevement` — auparavant elles ne l'étaient pas du tout
car ce type de règle a besoin d'une donnée PAR PRODUIT (`valeur_seuil`,
ex : teneur en sucre), pas seulement de la catégorie. Voir
`_resoudre_valeur_seuil_produit` ci-dessous pour le détail et ses limites
(la donnée n'est pas toujours disponible, auquel cas ce prélevement précis
est silencieusement absent du résultat pour cette ligne — voir
PROJECT_STATE.md pour la liste des cas gérés/non gérés).
"""

import sqlite3

from .calculator import calculer_montant
from .resolver import resoudre_regle


def _resoudre_valeur_seuil_produit(
    conn: sqlite3.Connection, ligne: sqlite3.Row, prelevement_id: int
) -> float | None:
    """Pour une règle de type 'montant_par_unite_a_seuil', retrouve la
    valeur_seuil à partir des données du produit identifié sur la ligne
    (`produit_reference`, via `ligne_document.produit_reference_id`), quand
    c'est possible.

    Renvoie None si la donnée n'est pas disponible — l'appelant doit alors
    ne PAS calculer ce prélèvement pour cette ligne plutôt que de deviner
    une valeur.

    Ad-hoc et volontairement limité aux 2 taxes sur les boissons
    sucrées/édulcorées (les seules de ce type à ce jour) plutôt qu'un
    mécanisme générique — à généraliser si d'autres taxes de ce type
    apparaissent (voir PROJECT_STATE.md section 7.5).
    """
    if ligne["produit_reference_id"] is None:
        return None
    produit = conn.execute(
        "SELECT * FROM produit_reference WHERE id = ?", (ligne["produit_reference_id"],)
    ).fetchone()
    if produit is None:
        return None

    code_prelevement = conn.execute(
        "SELECT code FROM prelevement WHERE id = ?", (prelevement_id,)
    ).fetchone()["code"]

    if code_prelevement == "TAXE_BOISSONS_SUCRE":
        # teneur_sucre_100g (champ OFF 'sugars_100g', en g/100g ou g/100mL)
        # est utilisé DIRECTEMENT comme kg de sucres ajoutés par hectolitre
        # (même valeur numérique : 100mL x 1000 = 1hL) — approximation déjà
        # documentée dans imports/off_import.py. Peut être None (produit
        # sans donnée nutritionnelle connue) : dans ce cas on renvoie bien
        # None, l'appelant doit alors s'abstenir de calculer.
        return produit["teneur_sucre_100g"]

    if code_prelevement == "TAXE_BOISSONS_EDULCORANT":
        # LIMITE CONNUE (PROJECT_STATE.md section 7.5) : OFF ne fournit que
        # la PRÉSENCE d'un édulcorant de synthèse (contient_edulcorants),
        # jamais sa CONCENTRATION en mg/L — pourtant nécessaire pour choisir
        # la bonne tranche du barème (seuil à 120mg/L). Impossible de
        # déterminer valeur_seuil à partir des seules données OFF
        # aujourd'hui, même quand contient_edulcorants=1 : ce prélèvement
        # n'est donc JAMAIS calculé automatiquement par ce module. Un
        # utilisateur redevable de cette contribution doit la vérifier
        # manuellement.
        return None

    # Autre règle 'montant_par_unite_a_seuil' non prévue par ce code ad-hoc :
    # on ne devine rien, il faudra étendre cette fonction si un nouveau cas
    # apparaît.
    return None


def traiter_ligne_document(conn: sqlite3.Connection, ligne_document_id: int, date_reference: str) -> list[int]:
    """Calcule et enregistre le(s) prélèvement(s) applicable(s) à une ligne.

    Args:
        conn: connexion SQLite.
        ligne_document_id: identifiant de la ligne à traiter.
        date_reference: date à utiliser pour résoudre les règles en vigueur
            (typiquement document.date_document).

    Returns:
        Liste des identifiants insérés dans `prelevement_calcule`.
    """
    ligne = conn.execute(
        "SELECT * FROM ligne_document WHERE id = ?", (ligne_document_id,)
    ).fetchone()
    if ligne is None:
        raise ValueError(f"ligne_document introuvable : id={ligne_document_id}")

    ids_inseres = []

    if ligne["prelevement_id"] is not None:
        # Cas fiche de paie : le prélèvement et son montant sont déjà connus.
        # On enregistre quand même via la règle en vigueur pour tracer quelle
        # version du taux légal correspond à ce montant (utile en cas de
        # contrôle ou de comparaison avec le barème officiel).
        regle = resoudre_regle(conn, ligne["prelevement_id"], date_reference)
        id_insere = _enregistrer(
            conn,
            ligne_document_id=ligne_document_id,
            prelevement_id=ligne["prelevement_id"],
            regle_id=regle["id"],
            montant=ligne["montant"],
            base_calcul=None,
            taux_applique=regle["taux"],
        )
        ids_inseres.append(id_insere)
        return ids_inseres

    if ligne["categorie_produit_id"] is not None:
        # Cas achat (ticket/facture) : on retrouve tous les prélèvements
        # applicables à cette catégorie de produit.
        prelevements = conn.execute(
            """
            SELECT prelevement_id
            FROM categorie_prelevement
            WHERE categorie_produit_id = ?
            """,
            (ligne["categorie_produit_id"],),
        ).fetchall()

        for row in prelevements:
            prelevement_id = row["prelevement_id"]
            pays_code = conn.execute(
                "SELECT pays_code FROM prelevement WHERE id = ?", (prelevement_id,)
            ).fetchone()["pays_code"]
            regle = resoudre_regle(conn, prelevement_id, date_reference)

            valeur_seuil = None
            if regle["type_regle"] == "montant_par_unite_a_seuil":
                valeur_seuil = _resoudre_valeur_seuil_produit(conn, ligne, prelevement_id)
                if valeur_seuil is None:
                    # Donnée produit manquante (pas de produit identifié sur
                    # la ligne, ou champ nutritionnel requis absent/non
                    # calculable — voir _resoudre_valeur_seuil_produit) : on
                    # ne peut pas deviner un montant, donc CE prélèvement
                    # précis n'est pas calculé pour cette ligne. Ce n'est pas
                    # une erreur : les autres prélèvements de la ligne (ex :
                    # TVA) sont bien calculés normalement, voir la suite de
                    # la boucle.
                    continue

            resultat = calculer_montant(
                conn,
                regle,
                montant=ligne["montant"],
                quantite=ligne["quantite"],
                unite_quantite=ligne["unite_quantite"],
                date_reference=date_reference,
                pays_code=pays_code,
                valeur_seuil=valeur_seuil,
            )
            id_insere = _enregistrer(
                conn,
                ligne_document_id=ligne_document_id,
                prelevement_id=prelevement_id,
                regle_id=regle["id"],
                montant=resultat["montant"],
                base_calcul=resultat["base_calcul"],
                taux_applique=resultat["taux_applique"],
            )
            ids_inseres.append(id_insere)
        return ids_inseres

    # Ni prélèvement explicite, ni catégorie produit : rien à calculer.
    # Ce n'est pas une erreur en soi (ex : ligne "TOTAL" d'un ticket qu'on
    # choisit de ne pas catégoriser) mais on ne calcule rien silencieusement.
    return ids_inseres


def _enregistrer(
    conn: sqlite3.Connection,
    ligne_document_id: int,
    prelevement_id: int,
    regle_id: int,
    montant: float,
    base_calcul: float | None,
    taux_applique: float | None,
) -> int:
    curseur = conn.execute(
        """
        INSERT INTO prelevement_calcule
            (ligne_document_id, prelevement_id, regle_id, montant_calcule, base_calcul, taux_applique)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ligne_document_id, prelevement_id, regle_id, montant, base_calcul, taux_applique),
    )
    conn.commit()
    return curseur.lastrowid
