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
- [x] Points 1-3 (voir historique précédent)
- [x] Point 4 : régime micro-entrepreneur — 46/46 tests passent
  - Nouveau module fiscal_engine/independant.py (calculer_cotisations_micro,
    calculer_versement_liberatoire, calculer_revenu_imposable_micro)
  - 3 catégories d'activité : vente (12,3%), services BIC (21,2%), BNC régime
    général (25,6%) ; versement libératoire optionnel (1% / 1,7% / 2,2%) ;
    abattements forfaitaires (71% / 50% / 34%)
  - Validé mot pour mot contre 2 exemples officiels LegalPlace (Marie BNC
    3000€ → 768€ cotis + 66€ VL = 834€ ; Claire BNC 36000€/an → 23760€ imposable)
    et cohérence du taux combiné Service-Public.fr (13,3% vente)

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)

## Limites assumées de foyer.py (documentées dans le module)
- Garde alternée non gérée (quart de part au lieu de demi-part)
- Enfants handicapés, anciens combattants, cartes d'invalidité : non gérés
- Plafonds spécifiques "personne seule ayant élevé un enfant" (1079€) et
  "veuf avec personne à charge" (5625€) non gérés — seuls plafond standard (1807€)
  et parent isolé 1er enfant (4262€) sont implémentés
- Imposition séparée des époux/pacsés non gérée
- revenu_net_imposable supposé déjà net (abattements/déductions non calculés ici)

## Limites assumées de independant.py (documentées dans le module)
- Régime réel (BIC/BNC au réel) non couvert — système comptable complet, hors périmètre
- Taux CIPAV non modélisé séparément (utiliser 'bnc' sous-estime les CIPAV)
- Location de meublés de tourisme classés (6%), ACRE, plafonds de CA du régime
  micro, éligibilité RFR au versement libératoire : non gérés

## Ordre de traitement initial (convenu il y a plusieurs échanges) — TERMINÉ
1. ✅ Plafonnement générique (PMSS)
2. ✅ Taxes écologiques par quantité + impôts locaux
3. ✅ Foyer fiscal → quotient familial → décote
4. ✅ Régime des indépendants

## Prochaine étape
Le mapping produits (tâche de fond, en continu) ou le lot OCR/parsing de documents
