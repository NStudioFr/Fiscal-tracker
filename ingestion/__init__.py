"""ingestion — couche d'alimentation en données du logiciel : OCR local
(Tesseract) et parsing de documents (fiche de paie, ticket de caisse, avis
d'imposition/facture).

Contrairement à fiscal_engine (déterministe, versionné, sourcé), cette
couche est probabiliste par nature : la qualité de reconnaissance dépend de
la photo/scan fourni. Chaque document importé reste donc 'a_valider' par
défaut (voir schema.sql) — l'OCR est une aide à la saisie, jamais une
source de vérité automatique.

Modules :
    ocr           — extraction de texte brut depuis une image (Tesseract, local)
    fiche_paie    — parsing d'une fiche de paie (reconnaissance par mots-clés)
"""

__version__ = "0.1.0"
