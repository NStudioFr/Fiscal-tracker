"""Résolution des paramètres de référence versionnés (PMSS, SMIC, et autres
constantes utilisées comme seuils/plafonds dans les règles de type 'formule').

Même logique de versioning temporel que resolver.py pour les règles fiscales
elles-mêmes : un paramètre a une valeur différente selon la date, et le
moteur ne doit jamais deviner "la valeur actuelle" quand une date de
référence différente est en jeu (ex : recalcul d'un ticket de 2023).
"""

import sqlite3

from .exceptions import AucuneValeurParametreApplicable


def resoudre_parametre(conn: sqlite3.Connection, code: str, pays_code: str, date_reference: str) -> float:
    """Retrouve la valeur d'un paramètre de référence à une date donnée.

    Args:
        conn: connexion SQLite ouverte.
        code: code du paramètre (ex : 'PMSS_MENSUEL').
        pays_code: pays concerné (ex : 'FR').
        date_reference: date au format ISO 'YYYY-MM-DD'.

    Returns:
        La valeur numérique en vigueur à cette date.

    Raises:
        AucuneValeurParametreApplicable: si le paramètre n'existe pas ou n'a
            aucune valeur définie pour cette date.
    """
    ligne = conn.execute(
        """
        SELECT vpr.valeur
        FROM valeur_parametre_reference vpr
        JOIN parametre_reference pr ON pr.id = vpr.parametre_id
        WHERE pr.code = ? AND pr.pays_code = ?
          AND vpr.date_debut <= ?
          AND (vpr.date_fin IS NULL OR vpr.date_fin >= ?)
        """,
        (code, pays_code, date_reference, date_reference),
    ).fetchone()

    if ligne is None:
        raise AucuneValeurParametreApplicable(
            f"Aucune valeur pour le paramètre {code!r} (pays={pays_code}) à la date {date_reference}."
        )
    return ligne["valeur"]


def charger_parametres_disponibles(conn: sqlite3.Connection, pays_code: str, date_reference: str) -> dict[str, float]:
    """Charge tous les paramètres de référence d'un pays ayant une valeur
    valide à une date donnée, sous forme de dict {code: valeur}.

    Utilisé pour alimenter les variables disponibles lors de l'évaluation
    d'une règle de type 'formule' (voir calculator.py) : un paramètre défini
    en base devient automatiquement utilisable par son code dans n'importe
    quelle formule, sans modification du moteur.

    Un paramètre sans valeur valide à cette date est simplement omis du
    résultat plutôt que de lever une erreur ici — si une formule l'utilise
    réellement, l'absence sera détectée par formula.evaluer_formule
    ('variable inconnue'), avec un message plus précis pour l'utilisateur.
    """
    lignes = conn.execute(
        """
        SELECT pr.code, vpr.valeur
        FROM parametre_reference pr
        JOIN valeur_parametre_reference vpr ON vpr.parametre_id = pr.id
        WHERE pr.pays_code = ?
          AND vpr.date_debut <= ?
          AND (vpr.date_fin IS NULL OR vpr.date_fin >= ?)
        """,
        (pays_code, date_reference, date_reference),
    ).fetchall()
    return {ligne["code"]: ligne["valeur"] for ligne in lignes}
