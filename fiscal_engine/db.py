"""Connexion à la base de données locale SQLite.

Volontairement minimal : pas d'ORM. Le schéma (voir schema/schema.sql) est
assez stable et les requêtes assez ciblées pour que du SQL explicite reste
plus simple à lire, auditer et déboguer qu'une couche d'abstraction
supplémentaire — cohérent avec l'objectif "code facile à comprendre".
"""

import sqlite3
from pathlib import Path


def connecter(chemin_bdd: str | Path) -> sqlite3.Connection:
    """Ouvre une connexion à la base locale, avec les réglages nécessaires
    au bon fonctionnement du schéma (clés étrangères, lignes en dict-like).
    """
    conn = sqlite3.connect(chemin_bdd)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row  # permet d'accéder aux colonnes par nom : row["taux"]
    return conn


def initialiser_bdd(chemin_bdd: str | Path, chemin_schema: str | Path) -> sqlite3.Connection:
    """Crée une base neuve à partir du fichier schema.sql (utile pour les tests
    et pour le tout premier lancement de l'application).
    """
    conn = connecter(chemin_bdd)
    with open(chemin_schema, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn
