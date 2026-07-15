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
- [x] Lot 2 : moteur de règles applicatif — 27/27 tests unitaires passent
- [x] Correctif TVA-sur-TTC
- [x] Extension quantité/unité (montant_par_unite + units.py)
- [x] Lot 3 : contenu fiscal France (TVA, CSG/CRDS, cotisation vieillesse, IR, TICPE)
- [x] Plafonnement générique (Point 1 de l'ordre de traitement) : nouvelles tables
  parametre_reference / valeur_parametre_reference + module fiscal_engine/parameters.py.
  Réutilise le moteur de formules existant (pas de colonne "plafond" dédiée).
  CSG/CRDS et cotisation vieillesse plafonnée recalculées avec seuils réels (PMSS,
  4×PMSS) — validé sur un cas de haut salaire (20000€/mois) où le plafonnement change
  effectivement le résultat par rapport à un calcul non plafonné.

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)

## Prochaine étape (ordre convenu)
Point 2 : taxes écologiques par quantité (déjà en grande partie fait via TICPE) +
taxe foncière/habitation (lignes à prélèvement explicite, type fiche de paie)
