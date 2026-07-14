"""Interpréteur restreint pour les règles fiscales de type 'formule'.

Certaines règles ne se réduisent pas à un taux fixe ni à un barème simple
(ex : une taxe plafonnée, ou calculée sur un montant net d'un abattement).
Pour ces cas, la table regle_prelevement stocke une formule texte, ex :
    "min(base * 0.03, 500)"
    "max(base - 1000, 0) * 0.05"

On n'utilise JAMAIS eval() directement : une formule vient de la base de
données, potentiellement modifiée par un futur import de "pack pays", et
eval() libre serait une porte ouverte à l'exécution de code arbitraire.
On parse donc l'expression via le module `ast` et on n'autorise qu'un
sous-ensemble d'opérations mathématiques strictement nécessaires.
"""

import ast
import operator

from .exceptions import FormuleInvalide

# Opérateurs binaires et unaires autorisés
_OPERATEURS_BINAIRES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_OPERATEURS_UNAIRES = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
# Fonctions autorisées dans les formules
_FONCTIONS_AUTORISEES = {
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
}


def evaluer_formule(formule: str, variables: dict[str, float]) -> float:
    """Évalue une formule texte de façon sécurisée.

    Args:
        formule: expression, ex "max(base - 1000, 0) * 0.05"
        variables: dictionnaire des variables disponibles, ex {"base": 25000.0}

    Returns:
        Le résultat numérique de l'évaluation.

    Raises:
        FormuleInvalide: si la formule est syntaxiquement incorrecte ou
            utilise une construction non autorisée (nom inconnu, import,
            appel de fonction non listée, etc.)
    """
    try:
        arbre = ast.parse(formule, mode="eval")
    except SyntaxError as exc:
        raise FormuleInvalide(f"Formule syntaxiquement invalide : {formule!r}") from exc

    try:
        return _evaluer_noeud(arbre.body, variables)
    except FormuleInvalide:
        raise
    except Exception as exc:  # garde-fou générique, on ne laisse jamais fuiter une erreur brute
        raise FormuleInvalide(f"Erreur d'évaluation de la formule {formule!r} : {exc}") from exc


def _evaluer_noeud(noeud: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(noeud, ast.Constant):
        if isinstance(noeud.value, (int, float)):
            return noeud.value
        raise FormuleInvalide(f"Constante non numérique interdite : {noeud.value!r}")

    if isinstance(noeud, ast.Name):
        if noeud.id in variables:
            return variables[noeud.id]
        raise FormuleInvalide(f"Variable inconnue dans la formule : {noeud.id!r}")

    if isinstance(noeud, ast.BinOp):
        type_op = type(noeud.op)
        if type_op not in _OPERATEURS_BINAIRES:
            raise FormuleInvalide(f"Opérateur non autorisé : {type_op.__name__}")
        gauche = _evaluer_noeud(noeud.left, variables)
        droite = _evaluer_noeud(noeud.right, variables)
        return _OPERATEURS_BINAIRES[type_op](gauche, droite)

    if isinstance(noeud, ast.UnaryOp):
        type_op = type(noeud.op)
        if type_op not in _OPERATEURS_UNAIRES:
            raise FormuleInvalide(f"Opérateur unaire non autorisé : {type_op.__name__}")
        return _OPERATEURS_UNAIRES[type_op](_evaluer_noeud(noeud.operand, variables))

    if isinstance(noeud, ast.Call):
        if not isinstance(noeud.func, ast.Name) or noeud.func.id not in _FONCTIONS_AUTORISEES:
            raise FormuleInvalide("Seules les fonctions min/max/round/abs sont autorisées")
        arguments = [_evaluer_noeud(arg, variables) for arg in noeud.args]
        return _FONCTIONS_AUTORISEES[noeud.func.id](*arguments)

    raise FormuleInvalide(f"Construction non autorisée dans une formule : {type(noeud).__name__}")
