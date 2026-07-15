"""Orchestration : relie resolver + calculator pour traiter une ligne de document.

Deux cas de figure, cf. docs/architecture.md :
  1. La ligne vient d'un ticket/facture (achat) : on connaît la catégorie
     produit, il faut retrouver via `categorie_prelevement` quels
     prélèvements s'appliquent, puis les calculer un par un.
  2. La ligne vient d'une fiche de paie : le prélèvement est déjà nommé
     explicitement (ligne_document.prelevement_id renseigné) et son montant
     est déjà connu (lu directement sur le document) — pas de calcul à faire,
     juste un enregistrement pour la traçabilité et les rapports.
"""

import sqlite3

from .calculator import calculer_montant
from .resolver import resoudre_regle


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
            resultat = calculer_montant(
                conn,
                regle,
                montant=ligne["montant"],
                quantite=ligne["quantite"],
                unite_quantite=ligne["unite_quantite"],
                date_reference=date_reference,
                pays_code=pays_code,
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
