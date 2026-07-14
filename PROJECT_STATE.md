# État du projet - 14/07/2026

## Décisions actées
- BDD locale : SQLite
- Langage moteur applicatif : Python
- Moteur de règles : versioning des taux par date_debut/date_fin, sourcé (reference_legale)
- Extensibilité pays : table `pays` + colonne `pays_code` sur `prelevement` (pas de nouvelle table par pays)
- Catégories produit : taxonomie fiscale maison, pas de dépendance à une base produit exhaustive non-alimentaire (Open Products Facts trop pauvre)

## Modules terminés
- [x] Lot 1 : schéma BDD (schema/schema.sql) + doc architecture (docs/architecture.md) — validé par chargement SQLite

## Modules en cours
- [ ] Lot 2 : moteur de règles applicatif (Python)

## Prochaine étape
Lot 2 : moteur de résolution de règle par date + interpréteur de formules + agrégation pour rapports
