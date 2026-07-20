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
- [x] Points 1-4 du moteur fiscal (voir historique précédent) — 46/46 tests
- [x] OCR + parsing fiche de paie — 14/14 tests parser, 60/60 tests projet au total
  - Nouveau package ingestion/ (ocr.py, fiche_paie.py), séparé de fiscal_engine/
    (nature probabiliste vs déterministe)
  - OCR : Tesseract local (+ pack langue fra installé), prétraitement simple
    (niveaux de gris + contraste)
  - Parsing fiche de paie : reconnaissance par mots-clés, normalisation des
    accents (l'OCR perd souvent les diacritiques - bug détecté et corrigé
    en testant avec une vraie image, pas juste du texte à la main)
  - Pipeline complet validé de bout en bout : image → OCR → parsing → BDD
    (statut 'a_valider' par défaut) → calcul fiscal tracé (test avec image
    synthétique : 4/4 cotisations reconnues, total 557,97€ correctement calculé)
  - Correction majeure suite à un vrai bulletin QuickPaie.com :
    extraction positionnelle du montant SALARIAL (jamais patronal), robuste aux formats
    à 2 colonnes (simplifiés) ET 5 colonnes (base/taux_sal/montant_sal/taux_pat/montant_pat)
  - Nouveaux alias ajoutés : "Retraite plafonnée/déplafonnée", "Dont déductible/non
    déductible de l'impôt sur le revenu" (labels réels différents de ma première hypothèse)
  - Validé sur deux images synthétiques passées dans un vrai OCR (format simple + format
    réel à 5 colonnes) : tous les montants salariaux corrects, montants patronaux et
    lignes 100% patronales correctement écartés

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

## Limite connue et documentée (fiche_paie.py)
CSG non déductible et CRDS apparaissent souvent combinées sur une ligne réelle
("CSG/CRDS non déductible") : la ligne est attribuée entièrement à CSG_NON_DEDUCTIBLE,
la CRDS n'est pas isolée séparément dans ce cas (le total reste correct, la
ventilation par typologie est légèrement imprécise dans ce cas précis).

## Ordre de traitement initial (convenu il y a plusieurs échanges) — TERMINÉ
1. ✅ Plafonnement générique (PMSS)
2. ✅ Taxes écologiques par quantité + impôts locaux
3. ✅ Foyer fiscal → quotient familial → décote
4. ✅ Régime des indépendants

## Prochaine étape (ordre convenu)
2/3 : avis d'imposition / facture (montants déjà calculés, parsing plus simple)
3/3 : ticket de caisse (le plus complexe — formats très variables — mais le
plus important à bien affiner, usage quotidien le plus fréquent)
