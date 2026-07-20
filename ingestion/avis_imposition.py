"""Parsing d'un avis d'imposition à partir du texte OCR brut.

Contrairement à la fiche de paie (plusieurs lignes de cotisations à
reconnaître), un avis d'imposition contient UN montant "à retenir" par
document : le solde de l'impôt sur le revenu à payer (ou à rembourser), le
montant de la taxe foncière, ou celui de la taxe d'habitation sur une
résidence secondaire (THRS). Chaque sous-type d'avis est reconnu séparément
via ses libellés officiels caractéristiques.

Les libellés reconnus s'appuient sur la terminologie officielle DGFiP
(vérifiée via impots.gouv.fr et sources fiscales spécialisées) :
  - "Impôt sur le revenu net à payer" / "Montant net à payer" / "Solde à
    payer" -> montant dû au titre de l'IR (prélèvement 'IR_BAREME').
  - "Montant à vous rembourser" / "Somme à vous restituer" -> l'avis donne
    lieu à un remboursement plutôt qu'un paiement ; ce module renvoie alors
    un montant NÉGATIF (crédit d'impôt net), pour que ce cas ne soit jamais
    silencieusement confondu avec un paiement dû.
  - "Taxe foncière" -> 'TAXE_FONCIERE'.
  - "Taxe d'habitation" -> 'TAXE_HABITATION_RESIDENCE_SECONDAIRE' (rappel :
    n'existe plus que sur les résidences secondaires depuis 2023).

LIMITES ASSUMÉES :
  - Un seul montant est extrait par document (le premier libellé reconnu).
    Un avis d'IR contient d'autres chiffres (revenu net imposable, revenu
    fiscal de référence, nombre de parts...) que ce module n'extrait PAS —
    seul le montant effectivement dû/remboursé est capté, conformément à
    l'objet du logiciel (comptabiliser les prélèvements PAYÉS).
  - Si plusieurs libellés reconnus apparaissent sur le même document (cas
    rare), seul le premier rencontré dans le texte est retenu.
  - Comme pour tous les parsers de ce projet : aucun contrôle de cohérence,
    le document reste 'a_valider' par défaut.
"""

from dataclasses import dataclass

from .texte_utils import extraire_dernier_montant, normaliser

# Ordre important : les libellés les plus spécifiques doivent être vérifiés
# avant les plus génériques quand un chevauchement est possible.
ALIAS_MONTANT_A_REMBOURSER = [
    "montant a vous rembourser",
    "somme a vous restituer",
    "montant qui vous sera rembourse",
]
ALIAS_IR_A_PAYER = [
    "impot sur le revenu net a payer",
    "montant net a payer",
    "solde a payer",
    "impot sur les revenus nets a payer",
    "net a payer",
]
ALIAS_TAXE_FONCIERE = ["taxe fonciere"]
ALIAS_TAXE_HABITATION = ["taxe d'habitation", "taxe habitation"]


@dataclass
class AvisImpositionExtrait:
    """Résultat de l'extraction d'un avis d'imposition.

    Attributes:
        code_prelevement: 'IR_BAREME', 'TAXE_FONCIERE', ou
            'TAXE_HABITATION_RESIDENCE_SECONDAIRE' — None si aucun libellé
            reconnu n'a été trouvé dans le document.
        montant: montant dû (positif) ou remboursé (négatif, si un libellé
            de remboursement a été détecté). None si rien n'a été reconnu.
        libelle_brut: la ligne source ayant permis la reconnaissance.
    """

    code_prelevement: str | None
    montant: float | None
    libelle_brut: str | None


def parser_avis_imposition(texte_ocr: str) -> AvisImpositionExtrait:
    """Extrait le montant principal d'un avis d'imposition.

    Args:
        texte_ocr: texte brut renvoyé par ingestion.ocr.extraire_texte_image.

    Returns:
        Un AvisImpositionExtrait — tous les champs sont None si aucun
        libellé connu n'a été trouvé (document non reconnu, à saisir
        manuellement).
    """
    lignes = [l.strip() for l in texte_ocr.splitlines() if l.strip()]
    lignes_normalisees = [normaliser(l) for l in lignes]

    groupes_alias = [
        (ALIAS_MONTANT_A_REMBOURSER, "IR_BAREME", True),
        (ALIAS_TAXE_FONCIERE, "TAXE_FONCIERE", False),
        (ALIAS_TAXE_HABITATION, "TAXE_HABITATION_RESIDENCE_SECONDAIRE", False),
        (ALIAS_IR_A_PAYER, "IR_BAREME", False),
    ]

    for aliases, code_prelevement, est_remboursement in groupes_alias:
        for i, ligne_normalisee in enumerate(lignes_normalisees):
            if not any(alias in ligne_normalisee for alias in aliases):
                continue

            # Le montant est le plus souvent sur la même ligne que le
            # libellé, mais peut aussi figurer sur l'une des quelques lignes
            # suivantes (ex : le libellé "Taxe foncière" en titre de section,
            # suivi du montant quelques lignes plus bas) — fenêtre de
            # recherche volontairement courte pour éviter de capter un
            # montant sans rapport plus loin dans le document.
            for j in range(i, min(i + 4, len(lignes))):
                montant = extraire_dernier_montant(lignes[j])
                if montant is not None:
                    montant_final = -abs(montant) if est_remboursement else montant
                    return AvisImpositionExtrait(
                        code_prelevement=code_prelevement, montant=montant_final, libelle_brut=lignes[j]
                    )

    return AvisImpositionExtrait(code_prelevement=None, montant=None, libelle_brut=None)
