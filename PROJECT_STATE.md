# État du projet - 15/07/2026

## Décisions actées
- BDD locale : SQLite ; langage moteur : Python
- Moteur de règles : versioning par date, sourcé (reference_legale)
- Extensibilité pays : table `pays` + colonne `pays_code`
- Formules : sous-ensemble sécurisé de `ast` (jamais eval() libre)
- TVA : mode 'ttc_inclus' (extraction), cotisations : mode 'base_directe' (application)
- Prélèvements à quantité (TICPE, etc.) : nouveau type_regle 'montant_par_unite' +
  module fiscal_engine/units.py (conversions L/cl/ml, kg/g/t, kWh/MWh ; erreur explicite
  si dimensions incompatibles, ex : L vs kg)

## Modules terminés
- [x] Lot 1 : schéma BDD + doc architecture
- [x] Lot 2 : moteur de règles applicatif — 21/21 tests unitaires passent
- [x] Correctif TVA-sur-TTC
- [x] Extension quantité/unité (montant_par_unite + units.py)
- [x] Lot 3 : contenu fiscal France — TVA (4 taux), CSG/CRDS + cotisation vieillesse
  salariale, barème IR 2026, TICPE essence/gazole (seed_data/fr_seed_lot3.sql)
  — validé contre 3 exemples officiels (IR : 2103,99€ sur 30000€/1part ; TICPE :
  5,94€/10L gazole ; cumul TVA+TICPE sur une ligne carburant)

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)

## Prochaine étape
Au choix : élargir le mapping catégories produit (lot dédié), démarrer l'OCR/parsing
de documents, ou ajouter d'autres prélèvements FR (taxe foncière, CSG sur autres
revenus, régime indépendant...)
