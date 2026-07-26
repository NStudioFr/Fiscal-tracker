"""Import du dump Open Food Facts (OFF) dans la base locale.

PRINCIPE : "n'importer que le nécessaire" (posé dès la conception du
projet). Le dump complet OFF fait plusieurs Go et contient des centaines de
colonnes ; ce module :
  1. Filtre à la SOURCE (via DuckDB, sans tout charger en mémoire) : ne
     garde que les produits commercialisés en France, et seulement les
     colonnes utiles à ce logiciel (code-barres, nom, catégories, données
     nutritionnelles pertinentes pour les taxes sur les boissons).
  2. Écrit ce sous-ensemble dans un fichier Parquet local, nettement plus
     petit (quelques dizaines de Mo au lieu de plusieurs Go), qui devient
     la seule donnée OFF conservée sur la machine.
  3. Importe ce sous-ensemble filtré dans la base SQLite locale
     (produit_reference), avec résolution automatique de la catégorie
     fiscale (categorie_produit) à partir des tags OFF.

IMPORTANT — LIMITE DE CET ENVIRONNEMENT DE DÉVELOPPEMENT : les domaines
Open Food Facts (world.openfoodfacts.org, huggingface.co) ne sont PAS
accessibles depuis l'environnement d'exécution utilisé pour construire ce
logiciel (liste blanche de domaines réseau restreinte). La fonction
`telecharger_dump_off` ci-dessous est donc fournie mais N'A PAS PU être
testée avec un vrai téléchargement ici — elle a été conçue et documentée
avec soin, à exécuter et vérifier par l'utilisateur sur sa propre machine
(sans cette restriction réseau). Le reste du pipeline (filtrage, mapping,
import BDD) a en revanche été testé de bout en bout avec un échantillon
SYNTHÉTIQUE reproduisant fidèlement le schéma réel du fichier Parquet OFF
(voir tests/fixtures/off_echantillon_synthetique.parquet et
tests/test_off_import.py).

USAGE RECOMMANDÉ (à exécuter une fois, sur la machine de l'utilisateur) :
    python3 -m imports.off_import --telecharger --filtrer --importer ma_base.db

LIMITES ASSUMÉES DU MAPPING CATÉGORIE ET DES DONNÉES NUTRITIONNELLES :
  - Le mapping OFF -> categorie_produit (MAPPING_CATEGORIES_OFF) ne couvre
    qu'un sous-ensemble de tags OFF parmi les dizaines de milliers existants
    — un produit dont aucun tag ne correspond reste importé mais SANS
    categorie_produit_id (donc sans prélèvement calculable automatiquement
    tant qu'une catégorie n'est pas assignée manuellement ou que le mapping
    n'est pas enrichi).
  - `teneur_sucre_100g` (champ OFF 'sugars_100g') est utilisé comme
    approximation du "kg de sucres ajoutés par hectolitre" requis par le
    barème officiel de la taxe soda (voir schema.sql) : OFF ne distingue
    pas sucres ajoutés / sucres naturellement présents, et la déclaration
    nutritionnelle est par 100g OU 100mL selon l'état physique du produit
    sans que cela soit toujours distingué clairement. C'est une
    approximation raisonnable pour des boissons, pas une valeur légale
    certifiée.
  - `contient_edulcorants` détecte uniquement la PRÉSENCE d'un édulcorant
    de synthèse connu (via les additifs déclarés) — le barème officiel de
    la contribution correspondante nécessite la CONCENTRATION en mg/L, que
    OFF ne fournit PAS. Ce champ permet de savoir QU'une contribution
    s'applique probablement, pas de calculer son montant exact sans
    donnée complémentaire.
"""

import argparse
import sqlite3
from pathlib import Path

import duckdb

# URL officielle du dump Parquet "food" (produits alimentaires), confirmée
# sur la page officielle world.openfoodfacts.org/data (section Parquet).
URL_OFF_FOOD_PARQUET = (
    "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet?download=true"
)

# Codes E des édulcorants de synthèse les plus courants (Annexe II du
# règlement CE n°1333/2008 sur les additifs alimentaires, catégorie
# "édulcorants" E420-E968 — liste non exhaustive, limitée aux plus
# fréquemment rencontrés dans les produits de grande consommation).
CODES_E_EDULCORANTS = {
    "en:e420", "en:e421", "en:e950", "en:e951", "en:e952", "en:e954",
    "en:e955", "en:e960", "en:e961", "en:e962", "en:e965", "en:e966",
    "en:e967", "en:e968",
}

# Mapping (partiel, voir limites en tête de module) tag OFF -> code
# categorie_produit (fiscal_engine). Le premier tag correspondant dans la
# liste categories_tags du produit détermine la catégorie retenue.
MAPPING_CATEGORIES_OFF: dict[str, str] = {
    "en:sodas": "BOISSONS_SUCREES",
    "en:carbonated-drinks": "BOISSONS_SUCREES",
    "en:sweetened-beverages": "BOISSONS_SUCREES",
    "en:diet-sodas": "BOISSONS_SUCREES",
    "en:energy-drinks": "BOISSONS_SUCREES",
    "en:waters": "EAU_BOISSONS_NON_SUCREES",
    "en:mineral-waters": "EAU_BOISSONS_NON_SUCREES",
    "en:fruit-juices": "EAU_BOISSONS_NON_SUCREES",
    "en:beers": "BOISSONS_ALCOOLISEES",
    "en:wines": "BOISSONS_ALCOOLISEES",
    "en:spirits": "BOISSONS_ALCOOLISEES",
    "en:dairies": "PRODUITS_LAITIERS",
    "en:milks": "PRODUITS_LAITIERS",
    "en:yogurts": "PRODUITS_LAITIERS",
    "en:cheeses": "PRODUITS_LAITIERS",
    "en:meats": "VIANDES_POISSONS_FRAIS",
    "en:fishes": "VIANDES_POISSONS_FRAIS",
    "en:fresh-vegetables": "FRUITS_LEGUMES_FRAIS",
    "en:fresh-fruits": "FRUITS_LEGUMES_FRAIS",
    "en:breads": "PAIN_PATISSERIE",
    "en:pastries": "PAIN_PATISSERIE",
    "en:prepared-meals": "PLATS_PREPARES_TRAITEUR",
    "en:chocolates": "CONFISERIE_CHOCOLAT",
    "en:candies": "CONFISERIE_CHOCOLAT",
    "en:pet-food": "ALIMENTATION_ANIMAUX",
    "en:dog-food": "ALIMENTATION_ANIMAUX",
    "en:cat-food": "ALIMENTATION_ANIMAUX",
}


def telecharger_dump_off(chemin_destination: str | Path, url: str = URL_OFF_FOOD_PARQUET) -> None:
    """Télécharge le dump Parquet "food" d'Open Food Facts.

    ATTENTION : nécessite un accès réseau vers huggingface.co, qui n'est PAS
    disponible dans l'environnement de développement utilisé pour construire
    ce module (voir docstring du module). Fonction non testée en conditions
    réelles ici — à vérifier lors de la première exécution.

    Le fichier fait plusieurs Go : prévoir du temps et de l'espace disque
    (l'espace peut être libéré après le filtrage via filtrer_produits_france,
    qui produit un fichier dérivé nettement plus petit).
    """
    import urllib.request

    chemin_destination = Path(chemin_destination)
    chemin_destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement de {url} vers {chemin_destination}...")
    urllib.request.urlretrieve(url, chemin_destination)
    print("Téléchargement terminé.")


def filtrer_produits_france(chemin_parquet_source: str | Path, chemin_parquet_sortie: str | Path) -> int:
    """Filtre le dump OFF complet pour ne garder que les produits
    commercialisés en France, et seulement les colonnes utiles à ce
    logiciel. Écrit le résultat dans un nouveau fichier Parquet, nettement
    plus petit.

    Utilise DuckDB, qui interroge le fichier Parquet directement sur disque
    (lecture columnar paresseuse) SANS charger l'intégralité du dump en
    mémoire — indispensable vu la taille du fichier source.

    Args:
        chemin_parquet_source: chemin du dump OFF complet (food.parquet).
        chemin_parquet_sortie: chemin où écrire le sous-ensemble filtré.

    Returns:
        Le nombre de lignes (produits) retenues après filtrage.
    """
    requete = f"""
        COPY (
            SELECT
                code,
                product_name,
                categories_tags,
                additives_tags,
                sugars_100g
            FROM read_parquet('{chemin_parquet_source}')
            WHERE list_contains(countries_tags, 'en:france')
              AND code IS NOT NULL
              AND code != ''
        ) TO '{chemin_parquet_sortie}' (FORMAT PARQUET)
    """
    duckdb.sql(requete)

    resultat = duckdb.sql(f"SELECT COUNT(*) AS n FROM read_parquet('{chemin_parquet_sortie}')").fetchone()
    return resultat[0]


def _resoudre_categorie_produit(conn: sqlite3.Connection, categories_tags: list) -> int | None:
    """Détermine le categorie_produit_id à partir des tags OFF d'un produit
    (premier tag du mapping trouvé dans la liste, voir MAPPING_CATEGORIES_OFF).
    """
    if not categories_tags:
        return None
    for tag in categories_tags:
        code_categorie = MAPPING_CATEGORIES_OFF.get(tag)
        if code_categorie is not None:
            ligne = conn.execute(
                "SELECT id FROM categorie_produit WHERE code = ?", (code_categorie,)
            ).fetchone()
            if ligne is not None:
                return ligne[0]
    return None


def _detecter_edulcorants(additives_tags: list) -> bool:
    if not additives_tags:
        return False
    return any(tag in CODES_E_EDULCORANTS for tag in additives_tags)


def importer_dans_bdd(conn: sqlite3.Connection, chemin_parquet_filtre: str | Path) -> dict:
    """Importe le sous-ensemble filtré OFF dans la table produit_reference.

    Args:
        conn: connexion SQLite ouverte (le schéma doit déjà être chargé).
        chemin_parquet_filtre: fichier produit par filtrer_produits_france.

    Returns:
        Un résumé {"total": int, "avec_categorie": int, "sans_categorie": int}.
    """
    resultat_requete = duckdb.sql(
        f"SELECT code, product_name, categories_tags, additives_tags, sugars_100g "
        f"FROM read_parquet('{chemin_parquet_filtre}')"
    ).fetchall()

    total = 0
    avec_categorie = 0

    for code, nom, categories_tags, additives_tags, sugars_100g in resultat_requete:
        total += 1
        id_categorie = _resoudre_categorie_produit(conn, categories_tags or [])
        if id_categorie is not None:
            avec_categorie += 1
        contient_edulcorants = _detecter_edulcorants(additives_tags or [])

        conn.execute(
            """
            INSERT INTO produit_reference
                (code_barre, nom, source, categorie_produit_id, teneur_sucre_100g, contient_edulcorants)
            VALUES (?, ?, 'OFF', ?, ?, ?)
            ON CONFLICT(code_barre) DO UPDATE SET
                nom = excluded.nom,
                categorie_produit_id = excluded.categorie_produit_id,
                teneur_sucre_100g = excluded.teneur_sucre_100g,
                contient_edulcorants = excluded.contient_edulcorants
            """,
            (code, nom, id_categorie, sugars_100g, int(contient_edulcorants)),
        )

    conn.commit()
    return {"total": total, "avec_categorie": avec_categorie, "sans_categorie": total - avec_categorie}


def resoudre_produit_par_code_barre(conn: sqlite3.Connection, code_barre: str) -> sqlite3.Row | None:
    """Recherche un produit importé par son code-barres — utile lors de la
    saisie d'une ligne de ticket pour pré-remplir sa catégorie fiscale.
    """
    conn.row_factory = sqlite3.Row
    return conn.execute("SELECT * FROM produit_reference WHERE code_barre = ?", (code_barre,)).fetchone()


def _construire_cli() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(description="Import du dump Open Food Facts dans la base locale.")
    parseur.add_argument("base_donnees", help="Chemin de la base SQLite (doit déjà contenir le schéma).")
    parseur.add_argument("--telecharger", action="store_true", help="Télécharger le dump complet OFF.")
    parseur.add_argument("--filtrer", action="store_true", help="Filtrer le dump pour ne garder que la France.")
    parseur.add_argument("--importer", action="store_true", help="Importer le sous-ensemble filtré dans la base.")
    parseur.add_argument("--dump-complet", default="off_food_complet.parquet", help="Chemin du dump complet.")
    parseur.add_argument("--dump-filtre", default="off_food_france.parquet", help="Chemin du dump filtré.")
    return parseur


if __name__ == "__main__":
    args = _construire_cli().parse_args()

    if args.telecharger:
        telecharger_dump_off(args.dump_complet)

    if args.filtrer:
        n = filtrer_produits_france(args.dump_complet, args.dump_filtre)
        print(f"{n} produits retenus après filtrage France.")

    if args.importer:
        connexion = sqlite3.connect(args.base_donnees)
        connexion.execute("PRAGMA foreign_keys = ON;")
        resume = importer_dans_bdd(connexion, args.dump_filtre)
        print(f"Import terminé : {resume}")
