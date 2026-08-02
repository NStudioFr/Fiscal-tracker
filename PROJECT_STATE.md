# Fiscal Tracker — État complet du projet et document de reprise

**Dernière mise à jour de ce document : 28/07/2026**
**Dépôt GitHub : https://github.com/NStudioFr/Fiscal-tracker (public)**

---

## 0. Comment utiliser ce document

Ce document remplace et consolide tous les `PROJECT_STATE.md` précédents,
devenus trop longs et redondants au fil du développement. Il est conçu pour
pouvoir reprendre le projet sans rien perdre.

**Pour reprendre le développement dans une nouvelle conversation**, commence
ton message par quelque chose comme :

> "Je continue le développement du projet Fiscal Tracker. Voici l'état
> complet : [colle ce document ou son URL]. Le repo est
> https://github.com/NStudioFr/Fiscal-tracker — peux-tu le récupérer
> toi-même et vérifier l'état des tests avant qu'on continue ?"

Claude peut récupérer le contenu du repo directement via son environnement
d'exécution (`codeload.github.com`, pas `github.com` — voir section 8).

---

## 1. Objectif du projet (rappel)

Logiciel **local, open source, respectueux de la vie privée** qui
comptabilise l'ensemble des prélèvements obligatoires (taxes, impôts,
cotisations) payés par un particulier ou indépendant sur une année, à
partir de scans/photos de documents (tickets de caisse, fiches de paie,
avis d'imposition, factures). Zéro connexion réseau pendant l'usage normal
(sauf mises à jour explicites des barèmes/bases produit). Architecture
pensée comme des "packs pays" indépendants (France en premier, cf. logique
GPS TomTom évoquée en tout début de conversation), langues cibles FR/EN/ES.

---

## 2. Convention de travail établie avec l'utilisateur

- **Chaque fichier livré est toujours complet et autonome** — jamais un
  diff, jamais un extrait. Un fichier modifié est republié en entier.
- Le dépôt GitHub est **public** (choix assumé : le code n'est pas un
  secret, seules les données personnelles de l'utilisateur — jamais
  commitées — sont sensibles).
- Les fichiers **binaires** (ex : `.parquet`) doivent être téléchargés puis
  **uploadés tels quels** sur GitHub (bouton "choose your files"), jamais
  copiés-collés dans l'éditeur texte de GitHub (le glisser-déposer a posé
  problème à l'utilisateur — la sélection via l'explorateur de fichiers a
  fonctionné).
- Toute donnée fiscale (taux, seuil, barème) doit être **sourcée**
  (colonne `source_reference` ou `reference_legale`), en préférant
  systématiquement les sources **officielles/gouvernementales**
  (douane.gouv.fr, BOFiP, Légifrance, service-public.gouv.fr) aux sites
  tiers, qui se sont avérés à plusieurs reprises contradictoires entre eux
  au cours du projet.
- Chaque nouvelle règle/mécanisme est **testé contre un exemple chiffré
  officiel** quand disponible, pas seulement par des tests unitaires
  abstraits.
- Philosophie d'honnêteté sur les limites : documenter explicitement ce qui
  n'est PAS couvert plutôt que d'approximer silencieusement.

---

## 3. ✅ Anomalies résolues (session du 2026-07-29)

**Lot 1 (2026-07-29, matin) — confirmé uploadé et vérifié sur GitHub** (repo
recloné à neuf, 143 tests passants à l'époque) :

1. **Fixture `.parquet` mal placée** (déjà connue avant la session,
   confirmée corrigée par l'utilisateur) : `off_echantillon_synthetique.parquet`
   est bien dans `tests/fixtures/`. Les 15 tests de `test_off_import.py` passent.
2. **Import cassé dans `tests/test_fiche_paie_parser.py`** : le test
   importait encore `_normaliser` depuis `ingestion.fiche_paie`, une
   fonction supprimée lors du refactor qui a créé
   `ingestion/texte_utils.py`. Corrigé : import de `normaliser` depuis
   `ingestion.texte_utils`.
3. **Fixture manquante `tests/fixtures/fiche_paie_synthetique.png`** :
   jamais committée. Régénérée (image de synthèse 1600×900, confiance OCR
   Tesseract ~91%, niveau "bon"). Nécessite le pack `tesseract-ocr-fra`
   (absent par défaut de l'environnement Claude, à installer via
   `apt-get install -y tesseract-ocr-fra`).
4. **Seuil RFR erroné pour la CSG retraite à 2 parts** (voir section 7.2) :
   39886€ (valeur 2025) au lieu de 40604€ (valeur 2026 officielle CNAV) —
   corrigé dans `seed_data/fr_seed_lot3.sql`, verrouillé par
   `tests/test_retraite.py`.

**Lot 2 (2026-07-29, après-midi) — confirmé uploadé et vérifié sur GitHub**
(repo recloné à neuf, 167 tests passants à l'époque) :

5. **Fiabilisation du quotient familial** (voir section 7.1 pour le
   détail complet) : `fiscal_engine/foyer.py` réécrit pour couvrir garde
   alternée, invalidité/anciens combattants, plafonds spécifiques
   "personne seule ayant élevé un enfant" (1079€) et "veuf avec personne à
   charge" (5625€), et imposition séparée des époux/pacsés. 5 nouveaux
   paramètres ajoutés dans `seed_data/fr_seed_lot3.sql`. Verrouillé par le
   nouveau fichier `tests/test_foyer.py` (24 tests). Suite complète passée
   de 143 à 167 tests.

**Lot 3 (2026-07-29, soir) — ⚠️ PAS ENCORE UPLOADÉ sur GitHub** :

6. **Fiabilisation de la taxe soda** (voir section 7.5 pour le détail
   complet) : les tarifs 2026 étaient déjà exacts (vérifiés par lecture
   directe de BOFiP BOI-BAREME-000038), le vrai trou était structurel —
   `BOISSONS_SUCREES` n'était relié à aucune des deux taxes dans
   `categorie_prelevement`, ET `fiscal_engine/orchestrator.py` n'avait
   aucun mécanisme pour résoudre `valeur_seuil` depuis un produit identifié
   (`produit_reference`). Les deux sont corrigés : le rattachement est
   ajouté dans `seed_data/fr_categories_produits.sql`, et l'orchestrateur
   sait désormais résoudre `teneur_sucre_100g` automatiquement pour
   `TAXE_BOISSONS_SUCRE`. `TAXE_BOISSONS_EDULCORANT` reste volontairement
   jamais calculée automatiquement (limite de données OFF, pas de bug).
   Verrouillé par le nouveau fichier `tests/test_taxe_soda.py` (7 tests).
   Suite complète passée de 167 à 174 tests.

**Lot 4 (2026-07-29, soir, suite) — ⚠️ PAS ENCORE UPLOADÉ sur GitHub** :

7. **Fiabilisation de l'alcool** (voir section 7.6 pour le détail complet) :
   les 4 points listés (rhums DOM, petites brasseries, VDN/VDL AOP, taxe
   prémix) sont désormais couverts, sourcés sur douane.gouv.fr et
   Légifrance (art. 1613 bis CGI), tous deux lus directement. 6 nouveaux
   prélèvements ajoutés dans `seed_data/fr_seed_lot3.sql`,
   `fiscal_engine/alcool.py` étendu (2 nouveaux paramètres optionnels sur
   les fonctions existantes, 2 nouvelles fonctions). Verrouillé par 14
   nouveaux tests dans `tests/test_alcool.py` (24 tests au total dans ce
   fichier). Suite complète passée de 174 à 188 tests.

**Lot 5 (2026-07-29, soir, suite) — ⚠️ PAS ENCORE UPLOADÉ sur GitHub** :

8. **Fiabilisation du tabac** (voir section 7.7 pour le détail complet) :
   paramètres de l'accise revérifiés par lecture directe de douane.gouv.fr
   — tous exacts (les 2 exemples chiffrés officiels sont désormais
   verrouillés par des tests). Le risque "tarifs changés en cours d'année"
   précédemment signalé est clarifié : ce sont les prix par référence qui
   changent souvent, pas les paramètres de l'accise. 2 catégories fiscales
   manquantes trouvées et ajoutées (narguilé/blunts, autres tabacs à
   chauffer). Nouveau fichier `tests/test_tabac.py` (7 tests). Suite
   complète passée de 188 à 195 tests.

**Lot 6 (2026-07-29, soir, fin) — ⚠️ PAS ENCORE UPLOADÉ sur GitHub** :

9. **Fiabilisation du régime indépendant** (voir section 7.3 pour le
   détail complet) : CIPAV (23,2%, nouveau `type_activite='bnc_cipav'`),
   plafonds de CA du régime micro (203 100€/83 600€, +7,6% loi de finances
   2026), et éligibilité au versement libératoire (seuil RFR N-2
   proportionnel au nombre de parts, 29 315€/part). Sourcé sur
   urssaf.fr/autoentrepreneur.urssaf.fr/economie.gouv.fr. Nouveau fichier
   `tests/test_independant.py` (16 tests). Suite complète passée de 195 à
   211 tests. **Ceci clôt le plan de fiabilisation en 4 points validé le
   2026-07-29 (7.5 → 7.6 → 7.7 → 7.3, tous faits).**

**Fichiers modifiés/créés localement à uploader sur GitHub pour les lots 3
à 6** (l'environnement Claude ne peut cloner/lire le repo, pas y pousser de
commits — ces lots n'ont pas encore été vérifiés par un reclonage depuis la
dernière confirmation d'upload, lot 2) :
- `fiscal_engine/orchestrator.py` (modifié — résolution de valeur_seuil)
- `fiscal_engine/alcool.py` (modifié — 4 nouveaux points gérés)
- `fiscal_engine/independant.py` (modifié — CIPAV, plafonds CA, éligibilité VL)
- `seed_data/fr_categories_produits.sql` (modifié — rattachement taxe soda)
- `seed_data/fr_seed_lot3.sql` (modifié — commentaires taxe soda + 6
  nouveaux prélèvements alcool + 2 nouvelles catégories tabac + CIPAV +
  plafonds CA + seuil RFR versement libératoire)
- `tests/test_taxe_soda.py` (nouveau)
- `tests/test_alcool.py` (modifié — 14 nouveaux tests)
- `tests/test_tabac.py` (nouveau)
- `tests/test_independant.py` (nouveau)
- `PROJECT_STATE.md` (ce document, mis à jour)

**⚠️ Si tu commences une nouvelle session sans avoir uploadé ces fichiers**,
ces mêmes anomalies (2, 3, 4) réapparaîtront et devront être re-corrigées.

---

## 4. Architecture générale

```
Fiscal-tracker/
├── schema/
│   └── schema.sql              — Schéma SQLite complet (14 tables)
├── seed_data/
│   ├── fr_seed_lot3.sql        — Contenu fiscal France (44 prélèvements)
│   └── fr_categories_produits.sql — Mapping produits (32 catégories)
├── fiscal_engine/               — Moteur de calcul, DÉTERMINISTE
│   ├── db.py                   — Connexion SQLite
│   ├── resolver.py             — Résolution de règle par date
│   ├── calculator.py           — Calcul du montant (8 types de règles)
│   ├── formula.py               — Interpréteur de formules sécurisé (ast)
│   ├── units.py                 — Conversions d'unités (L/kg/kWh...)
│   ├── parameters.py            — Paramètres de référence versionnés (PMSS...)
│   ├── orchestrator.py          — Orchestration par ligne de document
│   ├── aggregator.py            — Requêtes de reporting/ventilation
│   ├── foyer.py                 — Quotient familial, plafonnement, décote
│   ├── independant.py           — Régime micro-entrepreneur
│   ├── retraite.py              — CSG/CRDS/CASA sur pension de retraite
│   ├── alcool.py                 — Droits d'accise bière/spiritueux
│   └── exceptions.py            — Exceptions spécifiques au moteur
├── ingestion/                   — OCR + parsing, PROBABILISTE
│   ├── ocr.py                    — Extraction Tesseract + diagnostic qualité
│   ├── qualite.py                — Diagnostic de qualité d'image
│   ├── texte_utils.py            — Utilitaires partagés (normalisation, nombres)
│   ├── fiche_paie.py              — Parser fiche de paie
│   ├── avis_imposition.py         — Parser avis d'imposition
│   ├── facture.py                  — Parser facture (TVA par taux)
│   └── ticket_caisse.py            — Parser ticket de caisse
├── imports/                      — Import de sources de données externes
│   └── off_import.py              — Import Open Food Facts
├── tests/                        — 211 tests au total (tous passants,
│                                    2 skips intentionnels — voir section 3)
│   ├── test_engine.py
│   ├── test_alcool.py
│   ├── test_retraite.py            — Vraies données seed (pas de mécanisme générique) : ajouté le 2026-07-29
│   ├── test_foyer.py               — Idem, pour foyer.py (garde alternée, invalidité...) : ajouté le 2026-07-29
│   ├── test_taxe_soda.py           — Idem, orchestrateur + taxe soda : ajouté le 2026-07-29
│   ├── test_fiche_paie_parser.py
│   ├── test_avis_imposition_parser.py
│   ├── test_facture_parser.py
│   ├── test_ticket_caisse_parser.py
│   ├── test_qualite.py
│   ├── test_off_import.py
│   └── fixtures/                  — Images et .parquet de test
├── docs/
│   └── architecture.md            — Doc d'architecture initiale (Lot 1)
├── PROJECT_STATE.md               — À REMPLACER PAR CE DOCUMENT
└── README.md
```

**Principe directeur de séparation** : `fiscal_engine/` est déterministe
(même entrée → même sortie, toujours testable exactement) ; `ingestion/`
est probabiliste (dépend de la qualité du scan/photo, jamais garanti à
100%) ; `imports/` est un pont ponctuel et explicite vers des sources
externes (jamais d'appel réseau caché dans le flux normal).

---

## 5. Les 8 mécanismes de calcul du moteur fiscal (`regle_prelevement.type_regle`)

| Type | Usage | Exemple réel |
|---|---|---|
| `taux_fixe` (assiette `base_directe`) | Taux appliqué directement | Cotisation vieillesse |
| `taux_fixe` (assiette `ttc_inclus`) | Taux à EXTRAIRE d'un montant TTC | TVA sur ticket de caisse |
| `montant_fixe` | Montant constant | (peu utilisé actuellement) |
| `bareme_progressif` | Cumul par tranches (marginal) | Impôt sur le revenu |
| `formule` | Expression sécurisée (ast), variables `base`/`quantite`/`seuil`/paramètres | CSG/CRDS (abattement plafonné), tabac, bière |
| `montant_par_unite` | Montant fixe par unité de quantité (conversion auto L/kg/kWh) | TICPE, TICGN, vin, cidre |
| `montant_declare` | Montant lu directement sur le document, PAS calculé | Taxe foncière, THRS |
| `bareme_a_seuil` | Sélectionne UNE tranche (taux) selon une valeur de seuil différente de la base | CSG retraite (RFR détermine le taux, appliqué à la pension) |
| `montant_par_unite_a_seuil` | Sélectionne UNE tranche (montant/unité) selon un seuil | Taxe soda (teneur en sucre détermine le tarif/hL) |

**Paramètres de référence versionnés** (`parametre_reference` /
`valeur_parametre_reference`, 12 au total) : PMSS, plafonds QF, seuils et
forfaits de décote, abattements micro-entrepreneur — réutilisables dans
n'importe quelle formule sans modification du schéma.

---

## 6. Historique chronologique résumé (pour contexte, pas à refaire)

1. **Conception initiale** : schéma BDD (Lot 1), moteur Python (Lot 2),
   correctif TVA-sur-TTC, extension quantité/unité.
2. **Lot 3 — contenu fiscal FR initial** : TVA (4 taux), CSG/CRDS,
   cotisation vieillesse, barème IR 2026, TICPE.
3. **4 points d'amélioration du moteur fiscal** (ordre convenu et suivi) :
   plafonnement PMSS → taxes par quantité + impôts locaux → foyer fiscal
   (quotient familial/décote) → régime indépendant.
4. **OCR/ingestion** (3 sous-lots) : fiche de paie (corrigée grâce à un
   vrai bulletin QuickPaie fourni par l'utilisateur) → avis
   d'imposition/facture → ticket de caisse (corrigé grâce à 3 vrais
   tickets Carrefour/Magasin U fournis par l'utilisateur, révélant
   plusieurs bugs réels de regex/prétraitement OCR).
5. **Diagnostic de qualité d'image** (`ingestion/qualite.py`), calibré sur
   les vrais tickets fournis.
6. **Feuille de route utilisateur (3 points)** : autres prélèvements FR
   (PFU, CSG retraite via nouveau mécanisme `bareme_a_seuil`) → mapping
   produits (32 catégories) + taxe soda officielle (nouveau mécanisme
   `montant_par_unite_a_seuil`) → import Open Food Facts.
7. **Comblement des angles morts** (suite à une question directe de
   l'utilisateur sur l'exhaustivité) : tabac et alcool, sourcés
   exclusivement douane.gouv.fr, validés à l'euro près sur les exemples
   chiffrés officiels.

---

## 7. INDEX COMPLET DES LIMITES, POINTS EN SUSPENS ET TODO

### 7.1 Fiscalité France — quotient familial / foyer (`fiscal_engine/foyer.py`)
- **✅ Fiabilisé le 2026-07-29** — 4 des 5 limites listées ci-dessous sont
  désormais couvertes, sourcées sur BOFiP (BOI-IR-LIQ-10-20,
  BOI-IR-LIQ-20-20-20) et service-public.gouv.fr (fiches F2702, F2705,
  F387, F34088, F35127). Verrouillé par le nouveau fichier
  `tests/test_foyer.py` (24 tests, sur les vraies données du seed, voir
  aussi `tests/test_engine.py::TestFoyerFiscal` pour les tests génériques
  du mécanisme).
  1. **Garde alternée** : gérée (`nombre_enfants_garde_alternee` sur
     `SituationFoyer`) — quart de part par enfant (les 2 premiers), demi
     part à partir du 3e ; plafond spécifique 904€/quart-part (moitié du
     plafond standard), 2131€ pour le premier enfant si parent isolé en
     garde alternée exclusivement.
  2. **Invalidité / ancien combattant** : géré à 2 niveaux —
     `nombre_demi_parts_invalidite_ancien_combattant` (0 à 2, pour le
     contribuable et/ou son conjoint eux-mêmes, plafond majoré 3608€
     chacun) et `nombre_enfants_invalides_a_charge` /
     `nombre_enfants_invalides_garde_alternee` (personnes à charge
     titulaires de la CMI invalidité, +0,5 ou +0,25 part en plus de leur
     part normale d'enfant, plafond standard 1807€/904€).
  3. **Plafonds spécifiques** : "personne seule ayant élevé un enfant"
     (`personne_seule_ayant_eleve_enfant`, +0,5 part, plafond 1079€,
     incompatible avec des enfants à charge actuels — `ValueError` sinon)
     et "veuf avec personne à charge" (plafond combiné 5625€ pour les 2
     premières demi-parts d'enfants/personnes invalides à charge — voir
     limite résiduelle ci-dessous).
  4. **Imposition séparée** : gérée (`imposition_separee=True` sur
     `SituationFoyer`, valide seulement avec `situation_familiale` à
     'marie' ou 'pacse') — traite le déclarant comme 1 part de base même
     si légalement marié/pacsé.
- **Limite résiduelle sur le point 3 (veuf)** : le plafond combiné 5625€
  est appliqué dès qu'il y a AU MOINS une demi-part qualifiante (enfant ou
  personne invalide à charge), pas seulement à partir de 2 — l'articulation
  exacte du mécanisme BOFiP (réduction complémentaire de 2011€) pour le cas
  d'un veuf n'ayant qu'1 seul enfant n'a pas pu être confirmée avec
  certitude à cette session. Peut légèrement SURESTIMER l'avantage dans ce
  cas précis à très haut revenu. Voir docstring de `fiscal_engine/foyer.py`
  pour le détail complet. À vérifier sur BOFiP si ce cas se présente.
- Point 5, toujours NON couvert (hors périmètre de cette fiabilisation,
  volontairement) : `revenu_net_imposable` reste un paramètre d'entrée
  supposé déjà net — aucun calcul d'abattement/déduction en amont (pension
  alimentaire, PER, frais réels, rattachement d'enfants majeurs...) n'est
  effectué par ce module.
- Rattachement d'enfants majeurs, ascendants invalides recueillis : NON
  gérés (nouvelles limites identifiées lors de cette fiabilisation, à
  traiter dans une prochaine itération si besoin).

### 7.2 CSG retraite (`fiscal_engine/retraite.py`)
- **✅ Fiabilisé le 2026-07-29** : les seuils RFR 2026 sont désormais
  vérifiés sur la source officielle « L'Assurance Retraite » (CNAV),
  tableau mis à jour le 09/01/2026 :
  https://www.lassuranceretraite.fr/portail-info/hors-menu/actualites-nationales/retraite/2026/prelevements-sociaux-2025.html
  Seuils confirmés (1 part) : 13048€ / 17057€ / 26472€.
  Seuils confirmés (2 parts) : 20016€ / 26167€ / **40604€** (corrigé, voir
  ci-dessous).
  **Une erreur réelle a été trouvée et corrigée** : le seuil médian/normal
  à 2 parts était à 39886€ (valeur 2025, non revalorisée) au lieu de
  40604€ (valeur 2026 officielle, +1,8%). Verrouillé par
  `tests/test_retraite.py` (nouveau fichier, teste les vraies données du
  seed plutôt que des seuils ronds arbitraires comme `test_engine.py`).
- Convention de borne à noter (comportement du moteur générique, pas
  spécifique à ce module) : à la valeur RFR exactement égale à une borne
  haute (ex : RFR = 26472€ ou RFR = 40604€ pile), le taux INFÉRIEUR
  s'applique encore (ex : médian, pas normal) — décalage d'un euro par
  rapport au libellé CNAV "RFR > X€". Sans impact pratique réel, mais
  documenté et testé explicitement (`test_valeur_exacte_du_seuil_haut_reste_median`).
- Seuls les foyers à 1 ou 2 parts sont couverts (la source officielle
  donne aussi des seuils pour 1,5 / 2,5 / 3 parts et par demi-part
  supplémentaire — pourrait être ajouté dans une prochaine itération).
- Le mécanisme de "lissage" n'est pas géré. Précision apportée par la
  source officielle : ce lissage ne joue QUE pour le passage réduit
  (3,8%) → médian (6,6%) ; il n'existe AUCUN lissage pour le passage
  médian (6,6%) → normal (8,3%), qui s'applique immédiatement.

### 7.3 Régime indépendant (`fiscal_engine/independant.py`)
- **✅ Fiabilisé le 2026-07-29** — 3 des 4 points ci-dessous couverts,
  sourcés sur urssaf.fr / autoentrepreneur.urssaf.fr / economie.gouv.fr
  (dont 2 pages officielles lues directement) et recoupement de 5+ sources
  indépendantes pour le seuil RFR. Verrouillé par le nouveau fichier
  `tests/test_independant.py` (16 tests).
  1. **CIPAV** : `type_activite='bnc_cipav'` donne le bon taux (23,2% pour
     2026, vs 25,6% pour le BNC régime général — vérifié aussi que ce
     dernier taux, déjà présent, était bien exact malgré une trajectoire de
     hausse initialement prévue plus élevée, révisée par décret du
     08/09/2025). Le versement libératoire et l'abattement forfaitaire
     restent identiques au BNC régime général pour la CIPAV (seule la
     cotisation sociale diffère).
  2. **Plafonds de chiffre d'affaires du régime micro** : nouvelle fonction
     `verifier_plafond_ca_micro` — 203 100€ (vente/hébergement) / 83 600€
     (services BIC/BNC/CIPAV), valeurs 2026-2028 revalorisées de +7,6% par
     la loi de finances 2026. Gère aussi le sous-plafond services en cas
     d'activité mixte. Limite résiduelle : ne vérifie qu'une seule année
     civile, pas la mécanique de sortie après 2 années consécutives de
     dépassement (pas d'historique disponible).
  3. **Éligibilité au versement libératoire** : nouvelle fonction
     `verifier_eligibilite_versement_liberatoire` — seuil RFR N-2 de
     29 315€ pour 1 part (2026), qui s'avère être une simple règle
     PROPORTIONNELLE au nombre de parts du foyer (vérifié sur 4 exemples
     officiels différents : 1/2/2,5/3 parts). Ne vérifie pas que le RFR
     fourni est bien celui de la bonne année (N-2) — à la charge de
     l'appelant.
- **Non couvert (hors périmètre de cette fiabilisation)** : le régime réel
  (BIC/BNC au réel) reste un système comptable complet explicitement hors
  périmètre. Location de meublés de tourisme classés (taux à 6%) et ACRE
  (réduction de cotisations 1ère année) : toujours non gérés.

### 7.4 TICPE / TICGN
- Majoration régionale de la TICPE non gérée (chaque région peut moduler
  le taux national dans une limite encadrée) — seul le taux national
  s'applique.

### 7.5 Taxe soda (`TAXE_BOISSONS_SUCRE` / `TAXE_BOISSONS_EDULCORANT`)
- **✅ Fiabilisé le 2026-07-29** : tarifs 2026 vérifiés par lecture directe
  de la page BOFiP BOI-BAREME-000038 (mise à jour du 24/12/2025) — 4,07€ /
  21,38€ / 35,63€ par hL pour le sucre (0-5 / 5-8 / >8 kg/hL) et 4,50€ /
  6,00€ par hL pour l'édulcorant (≤120 / >120 mg/L), tous confirmés exacts.
- **Rattachement produit → taxe désormais opérationnel** (c'était le vrai
  trou avant cette date, pas les tarifs) : `BOISSONS_SUCREES` est
  maintenant relié aux deux prélèvements dans `categorie_prelevement`
  (`seed_data/fr_categories_produits.sql`), et
  `fiscal_engine/orchestrator.py` sait résoudre `valeur_seuil` depuis
  `produit_reference.teneur_sucre_100g` (via
  `ligne_document.produit_reference_id`) pour calculer automatiquement
  `TAXE_BOISSONS_SUCRE` sur une ligne d'achat identifiée à un produit connu
  (typiquement importé via OFF). Verrouillé par le nouveau fichier
  `tests/test_taxe_soda.py` (7 tests, sur les vraies données du seed).
- **`TAXE_BOISSONS_EDULCORANT` reste JAMAIS calculée automatiquement**
  (limite non résolue, comportement volontaire et testé) : OFF ne fournit
  que la PRÉSENCE d'un édulcorant (`contient_edulcorants`), jamais sa
  CONCENTRATION en mg/L pourtant nécessaire pour choisir la bonne tranche
  du barème. Le rattachement `categorie_prelevement` existe (prêt si une
  source de données fournit un jour la concentration), mais
  `orchestrator.py::_resoudre_valeur_seuil_produit` renvoie toujours `None`
  pour cette taxe précise, donc elle est silencieusement absente du
  résultat — pas de montant inventé. Un utilisateur redevable de cette
  contribution doit la vérifier manuellement.
- Comportement à connaître pour une future interface utilisateur : quand
  `TAXE_BOISSONS_SUCRE` ne peut pas être calculée (produit non identifié,
  ou identifié mais sans donnée de teneur en sucre), l'orchestrateur ne
  lève PAS d'exception et ne bloque pas le reste de la ligne (la TVA, par
  exemple, est toujours calculée normalement) — mais rien ne signale
  aujourd'hui à l'utilisateur final que cette taxe précise est absente du
  résultat. Une interface devra le faire explicitement.

### 7.6 Alcool (`fiscal_engine/alcool.py`)
- **✅ Fiabilisé le 2026-07-29** — les 4 points ci-dessous sont désormais
  gérés via de nouveaux paramètres optionnels et 2 nouvelles fonctions,
  sourcés sur douane.gouv.fr (lecture directe) et Légifrance (article 1613
  bis CGI, lecture directe). Verrouillé par 14 nouveaux tests ajoutés à
  `tests/test_alcool.py` (24 tests au total dans ce fichier).
  - **Rhums des DOM** : `calculer_droit_spiritueux(..., rhum_dom=True)`
    applique 966,75€/hlap au lieu de 1932,42€/hlap. Limite résiduelle : le
    contingent annuel (153 000 hlap au niveau national, réparti par
    distillerie — au-delà, une "soulte" de 304,90€/hlap s'ajoute) n'est PAS
    vérifié, le tarif réduit est toujours appliqué.
  - **Petites brasseries indépendantes** (≤200 000 hL/an) :
    `calculer_droit_biere(..., petite_brasserie_independante=True)`
    applique le tarif "léger" (4,12€/hL·degré) même au-delà de 2,8% vol.
  - **VDN/VDL AOP** : nouvelle fonction
    `calculer_droit_produit_intermediaire(..., vdn_vdl_aop=True)` — accise
    réduite (52,39€/hL au lieu de 209,53€/hL) et, si degré > 18%,
    cotisation sécu réduite ET sur une base différente (20,97€/hL de
    PRODUIT FINI, pas d'alcool pur). Limite résiduelle : la cotisation sécu
    des "autres produits intermédiaires" (non AOP) titrant plus de 18% vol.
    n'est pas gérée (cas rare).
  - **Taxe prémix** : nouvelle fonction `calculer_taxe_premix(...)` — 2
    tarifs selon catégorie (3000€/hlap "vin/fermenté" vs 11000€/hlap
    "autre", valeur par défaut). Limite résiduelle : la fonction ne
    détermine PAS elle-même si un produit relève légalement de la
    définition du prémix (Art. 1613 bis I CGI) — à la charge de l'appelant.

### 7.7 Tabac
- **✅ Fiabilisé le 2026-07-29** : paramètres de l'accise (taux/tarif/
  minimum de perception) revérifiés par lecture directe de la page
  douane.gouv.fr "La fiscalité appliquée aux tabacs manufacturés..." (mise
  à jour du 05/01/2026) — tous exacts, y compris les 2 exemples chiffrés
  officiels (paquet 11,50€ → accise 7,791€ ; paquet 13,50€ → accise
  8,891€), désormais verrouillés dans `tests/test_tabac.py`.
- **Clarification sur le risque "tarifs changés en cours d'année" (levée)**
  : ce qui change plusieurs fois par an (6 arrêtés d'homologation prévus en
  2026, dont un au 1er juin) ce sont les PRIX DE VENTE AU DÉTAIL par
  référence/marque commerciale — PAS les paramètres de l'accise
  (taux/tarif/minimum) eux-mêmes, qui restent stables pour toute l'année
  2026 sauf modification explicite de l'article L.314-24 CIBS. Le moteur
  prend le prix de vente en INPUT (lu sur le ticket), donc n'a jamais eu
  besoin de connaître le prix par référence — seuls les paramètres de
  l'accise doivent rester à jour, ce qui est confirmé le cas.
- **2 catégories fiscales manquantes trouvées et ajoutées** (absentes du
  seed initial, repérées en comparant ligne à ligne avec le tableau
  officiel) : "autres tabacs à fumer ou à inhaler après avoir été
  chauffés" (narguilé, blunts...) et "autres tabacs à chauffer" (hors
  bâtonnets).
- Limite residuelle inchangée : le prix de vente au détail est fixé par
  arrêté ministériel par référence/marque — le moteur calcule
  correctement l'accise SI on lui donne le prix payé (lisible sur un
  ticket), mais ne peut pas vérifier ou prédire ce prix lui-même.

### 7.8 Éco-contributions (DEEE, textile, mobilier...)
- **Non traitées du tout.** Réelles, mais gérées par des éco-organismes
  semi-privés (Ecologic, ecosystem, Citeo...) avec des barèmes techniques
  détaillés par catégorie/poids/matériau — pas un taux national simple.
  Nécessiterait un import dédié de grande ampleur, comparable à celui
  d'OFF. Piste explicitement laissée pour un lot futur si besoin confirmé.

### 7.9 Autres impôts non couverts (jamais recherchés)
- Impôt sur les sociétés (hors périmètre : particuliers/indépendants
  seulement).
- CSG sur revenus du patrimoine (loyers, etc.) autres que ceux déjà
  couverts (PFU sur capitaux mobiliers, retraite).
- Droits de mutation/succession, droits d'enregistrement.
- Malus écologique sur les véhicules.
- Toute fiscalité professionnelle au-delà du régime micro-entrepreneur.

### 7.10 Mapping produits (`fr_categories_produits.sql`)
- 32 catégories seulement, niveau "famille" — pas un référentiel produit
  exhaustif. Couvre l'alimentation courante, l'habillement, l'équipement
  maison, la culture/loisirs, la santé de base, le transport, mais reste
  loin d'une couverture complète du non-alimentaire (ex : pas de
  sous-catégories fines en électroménager/informatique).
- Le mapping OFF → categorie_produit
  (`imports/off_import.py::MAPPING_CATEGORIES_OFF`) ne couvre qu'environ
  **25 tags OFF** parmi les dizaines de milliers existants — à enrichir
  au fil de l'usage réel (un produit sans tag correspondant est importé
  mais reste sans catégorie, donc sans prélèvement calculable
  automatiquement).

### 7.11 Import Open Food Facts (`imports/off_import.py`)
- **Le vrai téléchargement n'a jamais été testé** — les domaines OFF
  (`world.openfoodfacts.org`, `huggingface.co`) sont bloqués dans
  l'environnement de développement utilisé pour construire ce module.
  Seul le pipeline de filtrage/mapping/import a été validé, contre un
  échantillon **synthétique** fabriqué à la main (10 produits fictifs).
  **Action à faire par l'utilisateur** : lancer
  `python3 -m imports.off_import ma_base.db --telecharger --filtrer --importer`
  sur sa propre machine et vérifier que ça fonctionne en conditions
  réelles (le vrai fichier fait plusieurs Go, prévoir du temps/espace disque).

### 7.12 OCR / Ingestion générale
- Fiabilité entièrement dépendante de la qualité du scan/photo (démontré
  empiriquement sur les 3 vrais tickets fournis par l'utilisateur : très
  bon sur le ticket net, très partiel sur le ticket dégradé).
- `ingestion/qualite.py` avertit l'utilisateur mais ne bloque jamais —
  seuils calibrés sur seulement 3 images réelles, à affiner avec l'usage.
- Ticket de caisse : **aucune identification produit par produit** — le
  parser s'appuie sur le bloc récapitulatif de TVA et les totaux par
  catégorie imprimés par la caisse (quand ils existent), pas sur une
  lecture ligne à ligne des articles. Une enseigne qui n'imprime ni bloc
  TVA ni totaux par catégorie ne sera pas exploitable au-delà du montant
  total.
- Fiche de paie : CSG non déductible et CRDS apparaissent souvent
  combinées sur une ligne réelle ("CSG/CRDS non déductible") — attribuées
  entièrement à `CSG_NON_DEDUCTIBLE`, la CRDS n'est pas isolée séparément
  dans ce cas (le total reste correct, la ventilation par typologie est
  légèrement imprécise).
- Détection de rayons (`ticket_caisse.py::detecter_rayons`) : purement
  indicative, aucun prélèvement n'en est déduit.

### 7.13 Ce qui n'existe pas du tout encore
- **Aucune interface utilisateur** (ni web, ni desktop). Tout le projet
  est actuellement une bibliothèque Python testée en ligne de commande.
- **Aucune notion de "foyer fiscal" persistante en base** — c'est un objet
  Python transitoire (`SituationFoyer`), pas une table (choix assumé, voir
  discussion initiale : donnée personnelle, pas une règle fiscale
  versionnée).
- Aucun mécanisme de **export** (CSV, PDF, etc.) des résultats.
- Aucune gestion multi-année réelle testée en usage (le versioning
  temporel existe dans le schéma, mais pas d'UI pour naviguer entre années).
- Aucun mécanisme d'**authentification/multi-utilisateur** (cohérent avec
  l'usage local mono-utilisateur visé, mais à garder en tête si le projet
  évolue).
- Pas de packaging/distribution (pas d'exécutable, pas d'installeur).
- Autres pays que la France : structure prête (table `pays`, colonne
  `pays_code` partout) mais aucun contenu réel pour un 2e pays.

---

## 8. Comment accéder au repo depuis un environnement Claude

Le domaine `github.com` est bloqué par les règles anti-robots pour un
accès automatisé. **Utiliser à la place** :
```bash
curl -sL -o repo.tar.gz https://codeload.github.com/NStudioFr/Fiscal-tracker/tar.gz/refs/heads/main
tar xzf repo.tar.gz
```
Ceci fonctionne car `codeload.github.com` (et `api.github.com`) sont sur la
liste blanche de domaines autorisés, contrairement à `github.com` lui-même.

---

## 9. Comment lancer les tests (après avoir récupéré le repo)

```bash
cd Fiscal-tracker-main   # ou le nom du dossier après extraction
python3 -m unittest discover -s tests -p "test_*.py" -v
```
Nécessite `duckdb` installé (`pip install duckdb --break-system-packages`)
pour les tests `test_off_import.py`, et `tesseract-ocr-fra` installé
(`apt-get install -y tesseract-ocr-fra`) pour les tests OCR en français,
notamment `test_qualite.py`.

**Au 2026-07-29 : 211 tests, tous passants (2 skips intentionnels)** —
voir section 3 pour l'historique des 4 anomalies trouvées et corrigées à
cette date, dont certaines nécessitent un upload GitHub non encore fait.

---

## 10. Pistes de prochaines étapes (non priorisées formellement, au choix)

- ✅ Anomalie parquet corrigée, seuils RFR CSG retraite fiabilisés, quotient
  familial/foyer fiabilisé sur 4 des 5 limites connues, taxe soda, alcool,
  tabac et régime indépendant fiabilisés (voir section 3) — reste à
  uploader les lots 3 à 6 sur GitHub (voir liste en section 3).
- **✅ Plan de fiabilisation du 2026-07-29 entièrement terminé** : 7.5 → 7.6
  → 7.7 → 7.3, les 4 étapes sont faites. Prochaines pistes non priorisées
  formellement (au choix, aucun plan validé pour la suite) :
- Ajouter les "grosses catégories" éco-taxes discutées le 2026-07-29 :
  éco-participation DEEE (électroménager/informatique, barème par famille
  de produit très granulaire) et rémunération pour copie privée (RCP,
  barème par capacité de stockage — smartphones, tablettes, disques durs
  externes, clés USB, cartes mémoire...) — gros chantier, nécessiterait le
  même travail de sourcing que pour l'alcool/tabac (ecologic-france.com,
  copiefrance.fr). Idem pour un futur régime réel indépendant, autres pays.
- Tester le vrai téléchargement OFF sur une machine sans restriction
  réseau (point 7.11).
- Construire une interface utilisateur minimale (au moins en ligne de
  commande ou web local simple) pour rendre le projet utilisable
  concrètement — actuellement tout est bibliothèque pure.
- Enrichir le mapping produits/OFF au fil de vrais tickets de caisse
  scannés (tâche de fond continue).

---

## 11. Rappel des chiffres clés (au 29/07/2026)

- **211 tests unitaires**, tous passants (2 skips intentionnels — voir
  section 3 pour l'historique des corrections de cette date).
- **44 prélèvements** définis en base, **32 catégories produit**, **17
  paramètres de référence** versionnés (12 + 5 nouveaux paramètres QF
  ajoutés le 2026-07-29, voir section 7.1).
- **8 mécanismes de calcul génériques** distincts dans le moteur.
- **~4665 lignes** de code Python au total (hors tests, hors SQL) — ce
  chiffre n'a pas été recompté après les ajouts du 2026-07-29
  (`foyer.py` réécrit et étoffé, `test_retraite.py`, `test_foyer.py`
  nouveaux) : à considérer comme approximatif/daté.
- **1 pays** couvert (France), architecture prête pour extension.
