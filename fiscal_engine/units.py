"""Conversions d'unités pour les prélèvements de type 'montant_par_unite'
(ex : TICPE en €/litre, accise en €/kg, taxe carbone en €/kWh...).

Volontairement minimal : on ne gère qu'un nombre restreint d'unités
courantes pour la consommation d'un particulier, regroupées par dimension
physique (volume, masse, énergie, comptage). Convertir entre deux unités de
dimensions différentes (ex : litres vers kg) n'a pas de sens et lève une
erreur explicite plutôt que de produire un résultat silencieusement faux.
"""

from .exceptions import UniteIncompatible

# Chaque dimension a une unité "canonique" (facteur 1.0) et des unités
# dérivées exprimées en fraction/multiple de cette unité canonique.
_DIMENSIONS: dict[str, dict[str, float]] = {
    "volume": {
        "L": 1.0,
        "l": 1.0,
        "cl": 0.01,
        "ml": 0.001,
        "hL": 100.0,
    },
    "masse": {
        "kg": 1.0,
        "g": 0.001,
        "t": 1000.0,
    },
    "energie": {
        "kWh": 1.0,
        "MWh": 1000.0,
    },
    "comptage": {
        "unite": 1.0,
    },
}

# Index inverse : unité -> nom de la dimension, pour une recherche directe.
_UNITE_VERS_DIMENSION: dict[str, str] = {
    unite: dimension for dimension, unites in _DIMENSIONS.items() for unite in unites
}


def convertir_quantite(quantite: float, unite_source: str, unite_cible: str) -> float:
    """Convertit une quantité d'une unité vers une autre, si elles appartiennent
    à la même dimension physique (ex : cl -> L, mais pas cl -> kg).

    Args:
        quantite: valeur numérique à convertir.
        unite_source: unité dans laquelle `quantite` est exprimée (ex : 'cl').
        unite_cible: unité vers laquelle convertir (ex : 'L').

    Returns:
        La quantité convertie dans `unite_cible`.

    Raises:
        UniteIncompatible: si l'une des unités est inconnue, ou si les deux
            unités n'appartiennent pas à la même dimension physique.
    """
    if unite_source == unite_cible:
        return quantite

    dimension_source = _UNITE_VERS_DIMENSION.get(unite_source)
    dimension_cible = _UNITE_VERS_DIMENSION.get(unite_cible)

    if dimension_source is None:
        raise UniteIncompatible(f"Unité inconnue : {unite_source!r}")
    if dimension_cible is None:
        raise UniteIncompatible(f"Unité inconnue : {unite_cible!r}")
    if dimension_source != dimension_cible:
        raise UniteIncompatible(
            f"Impossible de convertir {unite_source!r} ({dimension_source}) "
            f"vers {unite_cible!r} ({dimension_cible}) : dimensions physiques différentes."
        )

    facteur_source = _DIMENSIONS[dimension_source][unite_source]
    facteur_cible = _DIMENSIONS[dimension_cible][unite_cible]
    return quantite * facteur_source / facteur_cible
