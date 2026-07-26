"""imports — alimentation de la base locale à partir de sources de données
externes (Open Food Facts pour l'instant).

Principe directeur (posé dès le début du projet) : aucun appel réseau à la
volée pendant l'usage normal du logiciel. Ce package sert exclusivement à
un import BATCH, ponctuel, déclenché explicitement par l'utilisateur — pas
un accès réseau caché dans le flux de calcul fiscal.
"""

__version__ = "0.1.0"
