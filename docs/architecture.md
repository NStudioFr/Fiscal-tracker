# Architecture — Lot 1 : Schéma de base de données & moteur de règles

## 1. Objectifs de conception

Ce schéma doit permettre, dès la v1, de :
1. Stocker des **règles fiscales versionnées dans le temps** (un taux de TVA ou un barème IR change chaque année : on ne doit jamais écraser une ancienne valeur, seulement la clore et en ouvrir une nouvelle).
2. **Tracer chaque règle** jusqu'à sa source légale (article de loi, BOFiP, date d'entrée en vigueur) — indispensable pour la confiance utilisateur et pour identifier facilement une règle obsolète à mettre à jour.
3. Être **extensible par pays sans changer la structure des tables** (le principe "pack GPS" évoqué au départ) : ajouter l'Espagne ou le Royaume-Uni doit consister à ajouter des *lignes* de données (nouvelles règles, nouvelles catégories), jamais de nouvelles tables.
4. Séparer clairement **trois niveaux de connaissance** qui évoluent à des vitesses différentes :
   - la *typologie* des prélèvements (quasi stable : "TVA", "cotisations sociales", "impôt sur le revenu"...) ;
   - les *règles* de calcul (taux, barèmes — changent chaque année) ;
   - les *données produit* (catégories de dépenses, mapping produit → catégorie — évoluent au fil des imports).
5. Permettre la **ventilation croisée** demandée : par typologie de prélèvement (TVA / cotisations / IR / taxes écologiques...) **et** par type de dépense (alimentation / énergie / salaire...).
6. Support **multilingue** (FR/EN/ES) sur tous les libellés affichés à l'utilisateur.

## 2. Vue d'ensemble des entités

```
pays ─────────────┐
                   │
typologie_prelevement          type_depense (hiérarchique)
        │                              │
        ▼                              ▼
   prelevement (par pays)  ◄──── categorie_produit (hiérarchique)
        │                          │        │
        ▼                          │        ▼
  regle_prelevement            │   produit_reference (cache OFF/OPF)
   (versionnée dans le temps)  │
        │                      │
        ▼                      │
  tranche_bareme                │
  (barèmes progressifs, IR...)  │
                                 │
document ──► ligne_document ◄───┘
                   │
                   ▼
          prelevement_calcule
```

## 3. Détail des tables et rationale

### `pays`
Table de référence des modules pays disponibles (`FR`, `ES`, `EN`...). C'est le point d'entrée de l'extensibilité géographique : chaque prélèvement est rattaché à un `pays_code`, jamais codé en dur dans la structure.

### `typologie_prelevement`
La grande catégorisation demandée dans la question initiale : TVA, cotisations sociales, impôt sur le revenu, taxes écologiques, autres taxes/contributions. Volontairement **générique et stable dans le temps** — elle sert d'axe de ventilation n°1 dans les rapports.

### `type_depense`
Axe de ventilation n°2 : alimentation, énergie/carburant, logement, salaire, santé, etc. Structure **hiérarchique** (`parent_id`) pour permettre des sous-catégories (ex : "Alimentation" > "Boissons sucrées").

### `prelevement`
Le prélèvement concret et nommé : "TVA taux normal", "TICPE essence", "CSG déductible sur salaire", "Taxe sur les boissons sucrées". Rattaché à un pays et une typologie. Contient une `reference_legale` (texte libre : article de loi, BOFiP) — **chaque prélèvement doit être sourcé**, conformément à la limite d'exhaustivité qu'on a actée : si une règle n'a pas de source claire, elle ne doit pas entrer dans la base sans être marquée comme telle.

### `regle_prelevement`
**Le cœur du système de versioning.** Une règle a une `date_debut`, une `date_fin` (NULL = toujours en vigueur), et un `type_regle` :
- `taux_fixe` (ex : TVA 20 % → colonne `taux`)
- `montant_fixe` (ex : taxe forfaitaire → colonne `montant_fixe`)
- `bareme_progressif` (ex : IR → renvoie vers `tranche_bareme`)
- `formule` (cas complexes non réductibles à un taux simple — stockée en texte, interprétée par le moteur applicatif, pas par la BDD elle-même)

Le moteur de règles n'a donc **jamais** à choisir "le bon taux" tout seul : il interroge simplement `regle_prelevement` avec la date de la dépense, et prend la règle dont l'intervalle `[date_debut, date_fin]` couvre cette date. C'est ce qui permet de recalculer correctement un ticket de 2023 même si le taux a changé depuis.

### `tranche_bareme`
Décompose une règle de type `bareme_progressif` en tranches (borne min, borne max, taux) — utilisé pour l'IR notamment.

### `categorie_produit`
Taxonomie **fiscale simplifiée** des produits (pas une taxonomie nutritionnelle façon OFF). Hiérarchique, reliée à un `type_depense` pour la ventilation. C'est cette table, **et non une base produit exhaustive**, qui portera l'essentiel du mapping fiscal — cf. notre échange précédent sur les limites d'Open Products Facts.

### `categorie_prelevement`
Table de jonction : quels prélèvements s'appliquent à quelle catégorie de produit. Une catégorie peut avoir plusieurs prélèvements (ex : carburant → TVA + TICPE).

### `produit_reference`
Cache local d'un sous-ensemble du dump Open Food Facts (et, marginalement, Open Products Facts) : code-barres → catégorie fiscale. Alimenté par import batch, jamais par appel réseau à la volée (conforme à l'objectif "zéro connexion").

### `document` / `ligne_document`
Le document importé (ticket, facture, fiche de paie, avis d'imposition) et ses lignes. Le champ `texte_ocr_brut` conserve la sortie OCR brute pour audit/correction manuelle. `ligne_document.prelevement_id` est optionnel et sert au cas où le prélèvement est **déjà nommé explicitement** dans le document source (typiquement une fiche de paie : "CSG déductible ... 45,20 €" n'a pas besoin d'être déduit via une catégorie produit, il est lu directement).

### `prelevement_calcule`
Table de résultats : pour chaque ligne de document, le ou les prélèvements calculés, avec la règle exacte appliquée (`regle_id`) et la base de calcul retenue. C'est cette table qui alimente les totaux et ventilations demandés.

## 4. Ce que ce schéma ne couvre pas encore (limites assumées du lot 1)

- Le régime des indépendants (micro vs réel) n'a pas de table dédiée pour l'instant — à ajouter au lot "contenu fiscal FR" si besoin d'un statut spécifique par utilisateur.
- Pas de gestion des foyers fiscaux (quotient familial) dans ce lot — décision à prendre explicitement plus tard.
- Le champ `formule` (texte libre) suppose un petit interpréteur d'expressions côté applicatif — à concevoir au lot "moteur de règles applicatif", pas dans ce lot BDD.

## 5. Prochaine étape suggérée
Lot 2 : le moteur applicatif (Python) qui interroge ce schéma — résolution de la règle applicable à une date donnée, gestion des formules, agrégation pour les rapports.
