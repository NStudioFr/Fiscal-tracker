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
- [x] Points 1-2 (voir historique précédent)
- [x] Point 3 : foyer fiscal → quotient familial → décote — 39/39 tests passent
  - Nouveau module fiscal_engine/foyer.py (SituationFoyer, calculer_nombre_parts,
    calculer_impot_foyer) — orchestration haut niveau au-dessus du moteur générique
  - Nouveaux paramètres versionnés : PLAFOND_QF_DEMI_PART (1807€), 
    PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT (4262€), DECOTE_SEUIL/FORFAIT_CELIBATAIRE/COUPLE,
    DECOTE_TAUX (0,4525) — revenus 2025, sourcés LégiFiscal (citant BOFiP 07/04/2026) + 
    Meilleurtaux Placement (deux sources indépendantes, cohérentes mathématiquement)
  - Validé : décote à l'euro près (444,50€ pour impôt brut 1000€ célibataire) et
    plafonnement QF exact (avantage brut 6896€ écrêté à 3614€ = 2×1807€ pour un couple
    2 enfants à 90000€)

## Limites assumées de foyer.py (documentées dans le module)
- Garde alternée non gérée (quart de part au lieu de demi-part)
- Enfants handicapés, anciens combattants, cartes d'invalidité : non gérés
- Plafonds spécifiques "personne seule ayant élevé un enfant" (1079€) et
  "veuf avec personne à charge" (5625€) non gérés — seuls plafond standard (1807€)
  et parent isolé 1er enfant (4262€) sont implémentés
- Imposition séparée des époux/pacsés non gérée
- revenu_net_imposable supposé déjà net (abattements/déductions non calculés ici)

## Points ouverts / limitations assumées
- Majoration régionale de la TICPE non gérée (taux national uniquement)
- Quotient familial, décote, plafonnement IR non gérés
- Plafonnement PMSS des cotisations non appliqué automatiquement
- Régime des indépendants non couvert
- Mapping catégorie produit → prélèvement encore très partiel (5 catégories d'exemple)

## Prochaine étape (ordre convenu)
Point 4 : régime des indépendants (micro/réel) — dernier point de l'ordre initial,
volontairement isolé car autonome
