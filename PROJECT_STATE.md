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
- [x] OCR (Tesseract local, prétraitement gris+débruitage) + parsing des 4 types de
  documents (fiche de paie, avis d'imposition, facture, ticket de caisse) — 84/84 tests
  - ticket_caisse.py : bloc récapitulatif de TVA par taux (signal le plus fiable) +
    totaux par catégorie ("Total Alimentaire"...) + détection indicative de rayons
  - Validé sur 3 VRAIS tickets fournis par l'utilisateur (Carrefour x2, Magasin U) —
    pipeline complet image → OCR → parsing → BDD → calcul fiscal tracé, exact au
    centime près sur le ticket de bonne qualité (TVA totale : 3,74€)
  - 3 bugs réels détectés et corrigés grâce à ces vrais tickets (prétraitement OCR,
    regex de bloc TVA, fusion de milliers) — confirme la valeur de tester sur du réel
- [x] Refactor : ingestion/texte_utils.py (normalisation, extraction de nombres,
  nettoyage des symboles monétaires) partagé entre tous les parsers
- [x] Diagnostic de qualité d'image (ingestion/qualite.py) — 88/88 tests au total
  - Calibré empiriquement sur les 3 vrais tickets fournis (confiance OCR native de
    Tesseract plus fiable qu'une métrique de flou classique, testée puis écartée)
  - extraire_texte_avec_diagnostic() : point d'entrée recommandé pour l'UI, renvoie
    texte + niveau (bon/moyen/insuffisant) + messages d'avertissement en français
  - Jamais bloquant : le document reste 'a_valider', l'utilisateur décide

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)
- Aucune identification produit par produit (relève du "mapping produits", hors périmètre pour l'instant)
- Fiabilité entièrement dépendante de la qualité du scan/photo (démontré sur les 3
  exemples fournis : très bon sur le ticket net, très partiel sur le ticket dégradé)
- Rayons détectés = affichage indicatif seulement, aucun prélèvement n'en est déduit

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

## Limite connue et documentée de fiche_paie.py
CSG non déductible et CRDS apparaissent souvent combinées sur une ligne réelle
("CSG/CRDS non déductible") : la ligne est attribuée entièrement à CSG_NON_DEDUCTIBLE,
la CRDS n'est pas isolée séparément dans ce cas (le total reste correct, la
ventilation par typologie est légèrement imprécise dans ce cas précis).

## Ordre de traitement initial (convenu il y a plusieurs échanges) — TERMINÉ
1. ✅ Plafonnement générique (PMSS)
2. ✅ Taxes écologiques par quantité + impôts locaux
3. ✅ Foyer fiscal → quotient familial → décote
4. ✅ Régime des indépendants

## État global du projet
Moteur fiscal (Lots 1-4, Points 1-4) + ingestion complète (fiche de paie, avis
d'imposition, facture, ticket de caisse) = les deux piliers du projet sont posés.

## Prochaines pistes possibles
- UI (saisie, dashboard, exports)
- Enrichissement du mapping produits (tâche de fond)
- Autres prélèvements FR (taxe d'habitation, régime réel indépendant...)
- Import Open Food Facts pour enrichir l'identification produit

## Prochaine étape (ordre convenu)
1. Autres prélèvements FR (taxe d'habitation sur résidence principale — déjà supprimée,
   à retirer de la liste — régime réel indépendant, etc.)
2. Mapping produits par catégories (niveaux "familles" suffisants pour déterminer les
   prélèvements génériques ET catégoriels — pas de granularité produit fine)
3. Import Open Food Facts (uniquement les champs nécessaires, pas le dump complet)
