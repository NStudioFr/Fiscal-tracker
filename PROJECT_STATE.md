# État du projet - 14/07/2026

## Décisions actées
- BDD locale : SQLite
- Langage moteur applicatif : Python
- Moteur de règles : versioning des taux par date_debut/date_fin, sourcé (reference_legale)
- Extensibilité pays : table `pays` + colonne `pays_code` sur `prelevement`
- Formules : interprétées via un sous-ensemble sécurisé du module `ast` (jamais eval() libre)
- Catégories produit : taxonomie fiscale maison (Open Products Facts trop pauvre)

## Modules terminés
- [x] Lot 1 : schéma BDD (schema/schema.sql) + doc architecture (docs/architecture.md)
- [x] Lot 2 : moteur de règles applicatif (fiscal_engine/) — 14/14 tests unitaires passent (tests/test_engine.py)

## Points ouverts / à trancher au lot fiscal FR
- TVA sur ticket de caisse : le montant de ligne est TTC, il faudra extraire la TVA
  incluse (montant_TTC - montant_TTC/(1+taux)) plutôt que taux x montant directement.
  Le calculator.py actuel applique taux x base tel quel (correct pour une fiche de paie,
  À CORRIGER pour les achats avant le lot OCR/parsing).

## Modules en cours
- [ ] Lot 3 : contenu fiscal France (TVA, CSG/CRDS, cotisations, IR réel, taxes écologiques)

## Prochaine étape
Lot 3, ou lot d'ajustement TVA-sur-TTC si tu préfères le corriger avant d'aller plus loin
