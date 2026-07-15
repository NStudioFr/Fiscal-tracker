"""fiscal_engine — moteur de règles fiscales indépendant, local, versionné dans le temps.

Modules :
    db            — connexion à la base SQLite locale
    resolver      — résolution de la règle en vigueur à une date donnée
    calculator    — calcul du montant à partir d'une règle résolue
    formula       — interpréteur sécurisé pour les règles de type 'formule'
    units         — conversions d'unités pour les règles de type 'montant_par_unite'
    parameters    — résolution des paramètres de référence versionnés (PMSS, etc.),
                    utilisables comme variables dans une règle de type 'formule'
                    (mécanisme générique de plafonnement/seuil, sans colonne dédiée)
    orchestrator  — orchestration complète pour une ligne de document
    aggregator    — requêtes de reporting (totaux, ventilations)
    exceptions    — exceptions spécifiques au moteur
"""

__version__ = "0.3.0"
