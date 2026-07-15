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
- [x] Lot 1, Lot 2, correctifs TVA/quantité, Lot 3 (voir historique précédent)
- [x] Point 1 : plafonnement générique (PMSS) via parametre_reference
- [x] Point 2 : taxes écologiques par quantité + impôts locaux — 29/29 tests passent
  - Nouveau type_regle 'montant_declare' (montant lu directement sur le document,
    pour les prélèvements sans taux national : taxe foncière, THRS)
  - TICGN ajoutée (accise gaz naturel, 16,39 €/MWh) — validée contre exemple officiel
    (180,29€ pour 11000 kWh/an)
  - Taxe foncière + taxe d'habitation résidence secondaire (THRS) ajoutées
  - Point de vigilance vérifié : la taxe d'habitation sur la RÉSIDENCE PRINCIPALE
    est supprimée depuis 2023, seule la THRS (résidences secondaires) subsiste

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)

## Prochaine étape (ordre convenu)
Point 3 : foyer fiscal → quotient familial → décote (bloc séquentiel, nécessite
un nouveau concept structurel de "foyer" absent du schéma actuel)
