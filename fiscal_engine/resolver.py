"""Résolution de la règle applicable à un prélèvement pour une date donnée.

C'est la pièce centrale du versioning temporel décrit dans docs/architecture.md :
le moteur ne doit jamais choisir "le taux actuel", mais toujours "le taux qui
était en vigueur à la date de la dépense concernée".
"""

import sqlite3

from .exceptions import AucuneRegleApplicable, ReglesChevauchantes


def resoudre_regle(conn: sqlite3.Connection, prelevement_id: int, date_reference: str) -> sqlite3.Row:
    """Retrouve la règle en vigueur pour un prélèvement à une date donnée.

    Args:
        conn: connexion SQLite ouverte.
        prelevement_id: identifiant du prélèvement (table `prelevement`).
        date_reference: date au format ISO 'YYYY-MM-DD' (ex : date du ticket,
            date de la fiche de paie).

    Returns:
        La ligne (sqlite3.Row) de `regle_prelevement` en vigueur à cette date.

    Raises:
        AucuneRegleApplicable: si aucune règle ne couvre cette date — signale
            un trou dans la base de connaissance, à combler explicitement.
        ReglesChevauchantes: si plusieurs règles couvrent la même date — signale
            une incohérence de données à corriger, jamais à deviner.
    """
    lignes = conn.execute(
        """
        SELECT *
        FROM regle_prelevement
        WHERE prelevement_id = ?
          AND date_debut <= ?
          AND (date_fin IS NULL OR date_fin >= ?)
        """,
        (prelevement_id, date_reference, date_reference),
    ).fetchall()

    if len(lignes) == 0:
        raise AucuneRegleApplicable(
            f"Aucune règle en vigueur pour le prélèvement id={prelevement_id} "
            f"à la date {date_reference}. Vérifier la base de connaissance fiscale."
        )
    if len(lignes) > 1:
        ids = [str(l["id"]) for l in lignes]
        raise ReglesChevauchantes(
            f"Plusieurs règles se chevauchent pour le prélèvement id={prelevement_id} "
            f"à la date {date_reference} (règles id={', '.join(ids)}). "
            f"Corriger les périodes de validité dans regle_prelevement."
        )
    return lignes[0]


def verifier_absence_chevauchement(conn: sqlite3.Connection, prelevement_id: int) -> list[str]:
    """Contrôle de cohérence à lancer après tout import/ajout de règles :
    détecte les périodes qui se chevauchent pour un même prélèvement.

    SQLite ne permet pas nativement une contrainte d'exclusion de plage de
    dates (contrairement à PostgreSQL avec les types range) : ce contrôle
    applicatif la remplace.

    Returns:
        Liste de messages d'anomalies détectées (vide si tout est cohérent).
    """
    lignes = conn.execute(
        """
        SELECT id, date_debut, date_fin
        FROM regle_prelevement
        WHERE prelevement_id = ?
        ORDER BY date_debut
        """,
        (prelevement_id,),
    ).fetchall()

    anomalies = []
    for i in range(len(lignes) - 1):
        actuelle, suivante = lignes[i], lignes[i + 1]
        fin_actuelle = actuelle["date_fin"]
        if fin_actuelle is None or fin_actuelle >= suivante["date_debut"]:
            anomalies.append(
                f"Chevauchement entre la règle id={actuelle['id']} "
                f"(fin={fin_actuelle}) et la règle id={suivante['id']} "
                f"(début={suivante['date_debut']})"
            )
    return anomalies
