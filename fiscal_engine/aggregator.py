"""Agrégations pour les rapports : total, ventilation par typologie de
prélèvement, ventilation par type de dépense — conformément à la demande
initiale du projet (total + ventilation par typologie ET par type de dépense).

Ce module ne fait que lire (aucune écriture) : il interroge les résultats
déjà enregistrés dans `prelevement_calcule` par orchestrator.py.
"""

import sqlite3


def total_global(conn: sqlite3.Connection, date_debut: str, date_fin: str) -> float:
    """Somme de tous les prélèvements calculés sur une période, tous types confondus."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(pc.montant_calcule), 0) AS total
        FROM prelevement_calcule pc
        JOIN ligne_document ld ON ld.id = pc.ligne_document_id
        JOIN document d ON d.id = ld.document_id
        WHERE d.date_document BETWEEN ? AND ?
        """,
        (date_debut, date_fin),
    ).fetchone()
    return row["total"]


def ventilation_par_typologie(conn: sqlite3.Connection, date_debut: str, date_fin: str) -> list[dict]:
    """Ventilation par grande typologie de prélèvement (TVA, cotisations sociales,
    impôt sur le revenu, taxes écologiques...), triée par montant décroissant.
    """
    lignes = conn.execute(
        """
        SELECT
            tp.code AS typologie_code,
            tp.libelle_fr AS typologie_libelle,
            SUM(pc.montant_calcule) AS montant_total
        FROM prelevement_calcule pc
        JOIN prelevement p ON p.id = pc.prelevement_id
        JOIN typologie_prelevement tp ON tp.id = p.typologie_id
        JOIN ligne_document ld ON ld.id = pc.ligne_document_id
        JOIN document d ON d.id = ld.document_id
        WHERE d.date_document BETWEEN ? AND ?
        GROUP BY tp.id
        ORDER BY montant_total DESC
        """,
        (date_debut, date_fin),
    ).fetchall()
    return [dict(l) for l in lignes]


def ventilation_par_type_depense(conn: sqlite3.Connection, date_debut: str, date_fin: str) -> list[dict]:
    """Ventilation par type de dépense (alimentation, énergie, salaire...).

    Note : pour les lignes de fiche de paie (pas de categorie_produit), le
    type de dépense doit être déterminé autrement — v1 simplifiée : on se
    base uniquement sur categorie_produit -> type_depense pour les achats.
    Les prélèvements sur salaire apparaîtront donc groupés séparément
    (type_depense_code IS NULL) jusqu'à ce qu'on décide, au lot fiscal FR,
    de leur assigner un type_depense "Salaire" dédié.
    """
    lignes = conn.execute(
        """
        SELECT
            td.code AS type_depense_code,
            td.libelle_fr AS type_depense_libelle,
            SUM(pc.montant_calcule) AS montant_total
        FROM prelevement_calcule pc
        JOIN ligne_document ld ON ld.id = pc.ligne_document_id
        JOIN document d ON d.id = ld.document_id
        LEFT JOIN categorie_produit cp ON cp.id = ld.categorie_produit_id
        LEFT JOIN type_depense td ON td.id = cp.type_depense_id
        WHERE d.date_document BETWEEN ? AND ?
        GROUP BY td.id
        ORDER BY montant_total DESC
        """,
        (date_debut, date_fin),
    ).fetchall()
    return [dict(l) for l in lignes]


def ventilation_croisee(conn: sqlite3.Connection, date_debut: str, date_fin: str) -> list[dict]:
    """Ventilation croisée typologie x type de dépense — la vue la plus fine
    demandée dans le besoin initial (ex : "TVA sur alimentation" séparée de
    "TVA sur carburant").
    """
    lignes = conn.execute(
        """
        SELECT
            tp.code AS typologie_code,
            tp.libelle_fr AS typologie_libelle,
            td.code AS type_depense_code,
            td.libelle_fr AS type_depense_libelle,
            SUM(pc.montant_calcule) AS montant_total
        FROM prelevement_calcule pc
        JOIN prelevement p ON p.id = pc.prelevement_id
        JOIN typologie_prelevement tp ON tp.id = p.typologie_id
        JOIN ligne_document ld ON ld.id = pc.ligne_document_id
        JOIN document d ON d.id = ld.document_id
        LEFT JOIN categorie_produit cp ON cp.id = ld.categorie_produit_id
        LEFT JOIN type_depense td ON td.id = cp.type_depense_id
        WHERE d.date_document BETWEEN ? AND ?
        GROUP BY tp.id, td.id
        ORDER BY tp.code, montant_total DESC
        """,
        (date_debut, date_fin),
    ).fetchall()
    return [dict(l) for l in lignes]
