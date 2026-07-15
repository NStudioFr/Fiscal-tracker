"""Exceptions spécifiques au moteur de règles fiscales.

On utilise des exceptions dédiées plutôt que des exceptions génériques
(ValueError, etc.) pour que l'appelant (UI, rapports) puisse distinguer
précisément un problème de donnée fiscale d'une erreur de programmation.
"""


class FiscalEngineError(Exception):
    """Classe de base pour toutes les erreurs du moteur."""


class AucuneRegleApplicable(FiscalEngineError):
    """Levée quand aucune règle n'est en vigueur pour un prélèvement à une date donnée.

    C'est volontairement bloquant : le moteur ne doit JAMAIS deviner ou
    appliquer une règle par défaut. Si la base de connaissance fiscale a
    un trou, l'utilisateur doit le voir explicitement plutôt que d'obtenir
    un chiffre silencieusement faux.
    """


class ReglesChevauchantes(FiscalEngineError):
    """Levée quand plusieurs règles actives couvrent la même date pour un même
    prélèvement — c'est une incohérence de données qui doit être corrigée
    dans la base de connaissance, jamais résolue arbitrairement par le moteur.
    """


class FormuleInvalide(FiscalEngineError):
    """Levée quand une formule stockée en base est syntaxiquement invalide
    ou utilise une opération non autorisée (sécurité : pas d'eval() libre).
    """


class DonneesBaremeManquantes(FiscalEngineError):
    """Levée quand une règle de type 'bareme_progressif' n'a aucune tranche
    associée en base — donnée incomplète, ne doit pas être calculée à 0 silencieusement.
    """


class UniteIncompatible(FiscalEngineError):
    """Levée quand une règle de type 'montant_par_unite' ne peut pas être
    appliquée à une ligne de document : unité inconnue, ou unité de la ligne
    incompatible avec l'unité de la règle (ex : la règle attend des litres,
    la ligne fournit des kilos). Le moteur ne doit jamais deviner une
    conversion arbitraire entre deux dimensions physiques différentes.
    """


class AucuneValeurParametreApplicable(FiscalEngineError):
    """Levée quand un paramètre de référence (ex : PMSS) est demandé
    explicitement à une date pour laquelle aucune valeur n'est définie.
    Note : lors du chargement groupé des paramètres pour l'évaluation d'une
    formule (fiscal_engine.parameters.charger_parametres_disponibles), un
    paramètre sans valeur à la date donnée est simplement omis plutôt que de
    lever cette exception — s'il est réellement utilisé dans la formule,
    l'erreur remonte alors naturellement via FormuleInvalide ('variable
    inconnue'), ce qui est un message plus actionnable pour l'utilisateur.
    """
