"""Import des dumps Open Food Facts (OFF) et de ses bases sœurs — Open
Beauty Facts (OBF) et Open Pet Food Facts (OPFF) — dans la base locale.

ÉTENDU le 2026-08-02 (PROJECT_STATE.md section 7.10) : suite à la
recherche de sources complémentaires fiables pour enrichir le mapping
produits, ce module couvre désormais 3 sources au lieu d'une seule. Les 3
projets partagent la MÊME infrastructure (Product Opener), la même
licence (ODbL), et un schéma de colonnes très proche :
  - OFF (food.parquet)   -> catégories alimentaires (déjà existant)
  - OBF (beauty.parquet) -> PRODUITS_HYGIENE_BEAUTE (nouveau)
  - OPFF (CSV/TSV gzip)  -> ALIMENTATION_ANIMAUX (nouveau — pas encore de
    dump Parquet publié pour cette base au moment de cette recherche,
    contrairement à OFF et OBF ; import via CSV/TSV avec DuckDB à la place)
Open Products Facts (base "tout le reste", non alimentaire/cosmétique)
n'est PAS intégré à ce stade : encore très peu fourni en pratique au
2026-08-02 (quelques dizaines à centaines de produits observés pour la
France), le rapport effort/bénéfice ne le justifiait pas encore — à
reconsidérer si sa couverture grandit.

PRINCIPE : "n'importer que le nécessaire" (posé dès la conception du
projet). Les dumps complets font plusieurs Go (OFF) à quelques dizaines de
Mo (OBF) et contiennent des centaines de colonnes ; ce module :
  1. Filtre à la SOURCE (via DuckDB, sans tout charger en mémoire) : ne
     garde que les produits commercialisés en France, et seulement les
     colonnes utiles à ce logiciel (code-barres, nom, catégories, données
     nutritionnelles pertinentes pour les taxes sur les boissons — pour OFF
     uniquement, non pertinent pour OBF/OPFF).
  2. Écrit ce sous-ensemble dans un fichier local, nettement plus petit,
     qui devient la seule donnée conservée sur la machine.
  3. Importe ce sous-ensemble filtré dans la base SQLite locale
     (produit_reference), avec résolution automatique de la catégorie
     fiscale (categorie_produit) à partir des tags de la source.

IMPORTANT — LIMITE DE CET ENVIRONNEMENT DE DÉVELOPPEMENT : les domaines
Open Food Facts et ses bases sœurs (world.openfoodfacts.org,
world.openbeautyfacts.org, static.openpetfoodfacts.org, huggingface.co) ne
sont PAS accessibles depuis l'environnement d'exécution utilisé pour
construire ce logiciel (liste blanche de domaines réseau restreinte). Les
fonctions `telecharger_dump_*` ci-dessous sont donc fournies mais N'ONT PAS
PU être testées avec un vrai téléchargement ici — conçues et documentées
avec soin, à exécuter et vérifier par l'utilisateur sur sa propre machine.
Le reste du pipeline (filtrage, mapping, import BDD) a en revanche été
testé de bout en bout avec des échantillons SYNTHÉTIQUES reproduisant
fidèlement les schémas réels (voir tests/fixtures/ et tests/test_off_import.py,
tests/test_beauty_petfood_import.py). Pour OBF/OPFF spécifiquement : les
noms de colonnes supposés (code, product_name, categories_tags,
countries_tags) sont ceux du schéma OFF, réutilisés par analogie puisque
les 3 projets partagent la même plateforme technique (Product Opener) —
CETTE HYPOTHÈSE N'A PAS PU ÊTRE VÉRIFIÉE directement sur un vrai fichier
(accès réseau restreint), à confirmer par l'utilisateur au premier usage
réel.

USAGE RECOMMANDÉ (à exécuter une fois, sur la machine de l'utilisateur) :
    python3 -m imports.off_import --telecharger --filtrer --importer ma_base.db
    python3 -m imports.off_import --source beauty --telecharger --filtrer --importer ma_base.db
    python3 -m imports.off_import --source petfood --telecharger --filtrer --importer ma_base.db

LIMITES ASSUMÉES DU MAPPING CATÉGORIE ET DES DONNÉES NUTRITIONNELLES :
  - Le mapping tag -> categorie_produit (MAPPING_CATEGORIES_OFF/OBF/OPFF)
    ne couvre qu'un sous-ensemble de tags parmi les dizaines de milliers
    existants — un produit dont aucun tag ne correspond reste importé mais
    SANS categorie_produit_id (donc sans prélèvement calculable
    automatiquement tant qu'une catégorie n'est pas assignée manuellement
    ou que le mapping n'est pas enrichi).
  - `teneur_sucre_100g` (champ OFF 'sugars_100g') est utilisé comme
    approximation du "kg de sucres ajoutés par hectolitre" requis par le
    barème officiel de la taxe soda (voir schema.sql) : OFF ne distingue
    pas sucres ajoutés / sucres naturellement présents, et la déclaration
    nutritionnelle est par 100g OU 100mL selon l'état physique du produit
    sans que cela soit toujours distingué clairement. C'est une
    approximation raisonnable pour des boissons, pas une valeur légale
    certifiée. Sans objet pour OBF/OPFF (colonnes non importées, aucune
    taxe de ce projet ne dépend de la composition d'un cosmétique ou d'un
    aliment pour animaux).
  - `contient_edulcorants` détecte uniquement la PRÉSENCE d'un édulcorant
    de synthèse connu (via les additifs déclarés) — le barème officiel de
    la contribution correspondante nécessite la CONCENTRATION en mg/L, que
    OFF ne fournit PAS (recherche de source alternative menée le
    2026-08-02, sans résultat — voir PROJECT_STATE.md section 7.5).
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

# URL officielle du dump Parquet "beauty" (cosmétiques/soins), même dépôt
# HuggingFace que food.parquet, confirmée sur world.openbeautyfacts.org/data.
URL_OBF_BEAUTY_PARQUET = (
    "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/beauty.parquet?download=true"
)

# URL officielle du dump CSV/TSV complet (alimentation animale) — pas de
# dump Parquet publié pour cette base au 2026-08-02, contrairement à
# food/beauty. Confirmée sur fr.openpetfoodfacts.org/data. Fichier tabulé
# (caractère de séparation = tabulation, malgré l'extension .csv), compressé
# gzip.
URL_OPFF_PETFOOD_CSV_GZ = "https://static.openpetfoodfacts.org/data/en.openpetfoodfacts.org.products.csv.gz"

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

# Mapping (partiel) tag Open Beauty Facts -> code categorie_produit.
# Sourcé par analogie avec la taxonomie OFF standard (catégories
# "hygiène/beauté" les plus fréquentes) — à enrichir au fil de l'usage réel,
# comme MAPPING_CATEGORIES_OFF.
MAPPING_CATEGORIES_OBF: dict[str, str] = {
    "en:cosmetics": "PRODUITS_HYGIENE_BEAUTE",
    "en:body-hygiene": "PRODUITS_HYGIENE_BEAUTE",
    "en:hair-care": "PRODUITS_HYGIENE_BEAUTE",
    "en:skin-care": "PRODUITS_HYGIENE_BEAUTE",
    "en:oral-hygiene": "PRODUITS_HYGIENE_BEAUTE",
    "en:make-up": "PRODUITS_HYGIENE_BEAUTE",
    "en:perfumes": "PRODUITS_HYGIENE_BEAUTE",
    "en:deodorants": "PRODUITS_HYGIENE_BEAUTE",
    "en:soaps": "PRODUITS_HYGIENE_BEAUTE",
    "en:shampoos": "PRODUITS_HYGIENE_BEAUTE",
}

# Mapping (partiel) tag Open Pet Food Facts -> code categorie_produit.
MAPPING_CATEGORIES_OPFF: dict[str, str] = {
    "en:pet-food": "ALIMENTATION_ANIMAUX",
    "en:dog-food": "ALIMENTATION_ANIMAUX",
    "en:cat-food": "ALIMENTATION_ANIMAUX",
    "en:dry-dog-food": "ALIMENTATION_ANIMAUX",
    "en:wet-dog-food": "ALIMENTATION_ANIMAUX",
    "en:dry-cat-food": "ALIMENTATION_ANIMAUX",
    "en:wet-cat-food": "ALIMENTATION_ANIMAUX",
    "en:pet-treats": "ALIMENTATION_ANIMAUX",
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


def _resoudre_categorie_produit(
    conn: sqlite3.Connection, categories_tags: list, mapping: dict[str, str] = MAPPING_CATEGORIES_OFF
) -> int | None:
    """Détermine le categorie_produit_id à partir des tags d'un produit
    (premier tag du mapping trouvé dans la liste).

    Args:
        mapping: dict tag -> code categorie_produit à utiliser (par défaut
            MAPPING_CATEGORIES_OFF, pour rétrocompatibilité — passer
            MAPPING_CATEGORIES_OBF ou MAPPING_CATEGORIES_OPFF pour les
            autres sources).
    """
    if not categories_tags:
        return None
    for tag in categories_tags:
        code_categorie = mapping.get(tag)
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


def telecharger_dump_beauty(chemin_destination: str | Path, url: str = URL_OBF_BEAUTY_PARQUET) -> None:
    """Télécharge le dump Parquet "beauty" d'Open Beauty Facts.

    Beaucoup plus petit que le dump OFF food (quelques dizaines de Mo,
    vs plusieurs Go) — même limite réseau que telecharger_dump_off, voir
    docstring du module.
    """
    import urllib.request

    chemin_destination = Path(chemin_destination)
    chemin_destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement de {url} vers {chemin_destination}...")
    urllib.request.urlretrieve(url, chemin_destination)
    print("Téléchargement terminé.")


def filtrer_produits_beauty_france(chemin_parquet_source: str | Path, chemin_parquet_sortie: str | Path) -> int:
    """Filtre le dump OBF pour ne garder que les produits commercialisés en
    France, et seulement les colonnes utiles (pas de données nutritionnelles
    ni d'additifs, non pertinentes pour un cosmétique dans ce projet).
    """
    requete = f"""
        COPY (
            SELECT code, product_name, categories_tags
            FROM read_parquet('{chemin_parquet_source}')
            WHERE list_contains(countries_tags, 'en:france')
              AND code IS NOT NULL
              AND code != ''
        ) TO '{chemin_parquet_sortie}' (FORMAT PARQUET)
    """
    duckdb.sql(requete)
    resultat = duckdb.sql(f"SELECT COUNT(*) AS n FROM read_parquet('{chemin_parquet_sortie}')").fetchone()
    return resultat[0]


def importer_beauty_dans_bdd(conn: sqlite3.Connection, chemin_parquet_filtre: str | Path) -> dict:
    """Importe le sous-ensemble filtré OBF dans produit_reference.

    Contrairement à importer_dans_bdd (OFF), aucune donnée nutritionnelle
    n'est importée (teneur_sucre_100g / contient_edulcorants restent NULL /
    False) : aucune taxe de ce projet ne dépend de la composition d'un
    cosmétique, seule sa catégorie compte.
    """
    resultat_requete = duckdb.sql(
        f"SELECT code, product_name, categories_tags FROM read_parquet('{chemin_parquet_filtre}')"
    ).fetchall()

    total = 0
    avec_categorie = 0

    for code, nom, categories_tags in resultat_requete:
        total += 1
        id_categorie = _resoudre_categorie_produit(conn, categories_tags or [], mapping=MAPPING_CATEGORIES_OBF)
        if id_categorie is not None:
            avec_categorie += 1

        conn.execute(
            """
            INSERT INTO produit_reference (code_barre, nom, source, categorie_produit_id)
            VALUES (?, ?, 'OBF', ?)
            ON CONFLICT(code_barre) DO UPDATE SET
                nom = excluded.nom,
                categorie_produit_id = excluded.categorie_produit_id
            """,
            (code, nom, id_categorie),
        )

    conn.commit()
    return {"total": total, "avec_categorie": avec_categorie, "sans_categorie": total - avec_categorie}


def telecharger_dump_petfood(chemin_destination: str | Path, url: str = URL_OPFF_PETFOOD_CSV_GZ) -> None:
    """Télécharge le dump CSV/TSV compressé gzip d'Open Pet Food Facts.

    Pas de dump Parquet disponible pour cette base au 2026-08-02
    (contrairement à OFF/OBF) — voir filtrer_produits_petfood_france pour
    le traitement via DuckDB read_csv à la place. Même limite réseau que
    telecharger_dump_off, voir docstring du module.
    """
    import urllib.request

    chemin_destination = Path(chemin_destination)
    chemin_destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement de {url} vers {chemin_destination}...")
    urllib.request.urlretrieve(url, chemin_destination)
    print("Téléchargement terminé.")


def filtrer_produits_petfood_france(chemin_csv_gz_source: str | Path, chemin_parquet_sortie: str | Path) -> int:
    """Filtre le dump CSV/TSV (gzip) OPFF pour ne garder que les produits
    commercialisés en France, et écrit le résultat en Parquet (plus
    compact, cohérent avec le reste du pipeline).

    DuckDB lit directement le CSV/TSV gzippé sans décompression manuelle
    préalable (`read_csv` détecte la compression depuis l'extension
    '.gz'). Séparateur = tabulation (convention historique des exports
    complets Open Food Facts et bases sœurs, malgré l'extension '.csv').

    Contrairement au Parquet OFF/OBF (où categories_tags/countries_tags
    sont déjà des listes natives), le CSV brut les représente comme des
    chaînes séparées par des virgules — `string_split` les convertit ici
    en listes pour que le fichier Parquet produit ait le MÊME format que
    les autres sources (et reste utilisable tel quel par
    _resoudre_categorie_produit, qui itère sur une liste de tags).
    """
    requete = f"""
        COPY (
            SELECT
                code,
                product_name,
                string_split(categories_tags, ',') AS categories_tags
            FROM read_csv('{chemin_csv_gz_source}', delim='\\t', header=true, compression='gzip')
            WHERE list_contains(string_split(countries_tags, ','), 'en:france')
              AND code IS NOT NULL
              AND code != ''
        ) TO '{chemin_parquet_sortie}' (FORMAT PARQUET)
    """
    duckdb.sql(requete)
    resultat = duckdb.sql(f"SELECT COUNT(*) AS n FROM read_parquet('{chemin_parquet_sortie}')").fetchone()
    return resultat[0]


def importer_petfood_dans_bdd(conn: sqlite3.Connection, chemin_parquet_filtre: str | Path) -> dict:
    """Importe le sous-ensemble filtré OPFF dans produit_reference (même
    logique qu'importer_beauty_dans_bdd — pas de données nutritionnelles
    pertinentes pour les taxes de ce projet).
    """
    resultat_requete = duckdb.sql(
        f"SELECT code, product_name, categories_tags FROM read_parquet('{chemin_parquet_filtre}')"
    ).fetchall()

    total = 0
    avec_categorie = 0

    for code, nom, categories_tags in resultat_requete:
        total += 1
        id_categorie = _resoudre_categorie_produit(conn, categories_tags or [], mapping=MAPPING_CATEGORIES_OPFF)
        if id_categorie is not None:
            avec_categorie += 1

        conn.execute(
            """
            INSERT INTO produit_reference (code_barre, nom, source, categorie_produit_id)
            VALUES (?, ?, 'OPFF', ?)
            ON CONFLICT(code_barre) DO UPDATE SET
                nom = excluded.nom,
                categorie_produit_id = excluded.categorie_produit_id
            """,
            (code, nom, id_categorie),
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
    parseur = argparse.ArgumentParser(
        description="Import des dumps Open Food Facts et bases sœurs (Open Beauty Facts, Open Pet Food Facts) dans la base locale."
    )
    parseur.add_argument("base_donnees", help="Chemin de la base SQLite (doit déjà contenir le schéma).")
    parseur.add_argument(
        "--source", choices=["food", "beauty", "petfood"], default="food",
        help="Source à importer : food (OFF, défaut), beauty (OBF), ou petfood (OPFF).",
    )
    parseur.add_argument("--telecharger", action="store_true", help="Télécharger le dump complet de la source choisie.")
    parseur.add_argument("--filtrer", action="store_true", help="Filtrer le dump pour ne garder que la France.")
    parseur.add_argument("--importer", action="store_true", help="Importer le sous-ensemble filtré dans la base.")
    parseur.add_argument("--dump-complet", default=None, help="Chemin du dump complet (défaut dépend de --source).")
    parseur.add_argument("--dump-filtre", default=None, help="Chemin du dump filtré (défaut dépend de --source).")
    return parseur


_DEFAUTS_PAR_SOURCE = {
    "food": {"dump_complet": "off_food_complet.parquet", "dump_filtre": "off_food_france.parquet"},
    "beauty": {"dump_complet": "obf_beauty_complet.parquet", "dump_filtre": "obf_beauty_france.parquet"},
    "petfood": {"dump_complet": "opff_petfood_complet.csv.gz", "dump_filtre": "opff_petfood_france.parquet"},
}


if __name__ == "__main__":
    args = _construire_cli().parse_args()
    defauts = _DEFAUTS_PAR_SOURCE[args.source]
    dump_complet = args.dump_complet or defauts["dump_complet"]
    dump_filtre = args.dump_filtre or defauts["dump_filtre"]

    if args.telecharger:
        if args.source == "food":
            telecharger_dump_off(dump_complet)
        elif args.source == "beauty":
            telecharger_dump_beauty(dump_complet)
        else:
            telecharger_dump_petfood(dump_complet)

    if args.filtrer:
        if args.source == "food":
            n = filtrer_produits_france(dump_complet, dump_filtre)
        elif args.source == "beauty":
            n = filtrer_produits_beauty_france(dump_complet, dump_filtre)
        else:
            n = filtrer_produits_petfood_france(dump_complet, dump_filtre)
        print(f"{n} produits retenus après filtrage France ({args.source}).")

    if args.importer:
        connexion = sqlite3.connect(args.base_donnees)
        connexion.execute("PRAGMA foreign_keys = ON;")
        if args.source == "food":
            resume = importer_dans_bdd(connexion, dump_filtre)
        elif args.source == "beauty":
            resume = importer_beauty_dans_bdd(connexion, dump_filtre)
        else:
            resume = importer_petfood_dans_bdd(connexion, dump_filtre)
        print(f"Import terminé ({args.source}) : {resume}")
