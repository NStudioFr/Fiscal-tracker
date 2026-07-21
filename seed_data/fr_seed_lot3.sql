-- =========================================================================
-- Fiscal Tracker — Contenu fiscal France (Lot 3)
-- =========================================================================
-- Chaque règle est sourcée (colonne source_reference). Périmètre de ce lot :
--   - TVA (4 taux)
--   - CSG déductible / non déductible + CRDS sur salaire, AVEC plafonnement
--     réel de l'abattement de 1,75 % à 4 PMSS/mois
--   - Cotisation vieillesse salariale (plafonnée / déplafonnée), AVEC
--     plafonnement réel de la part plafonnée au PMSS
--   - Barème de l'impôt sur le revenu 2026 (revenus 2025)
--   - TICPE essence SP95-E5 et gazole (taux national, hors majoration régionale)
--   - TICGN (accise gaz naturel), taxe foncière et THRS (voir plus bas)
--   - Quotient familial + son plafonnement + décote (paramètres ci-dessous,
--     calcul orchestré par fiscal_engine/foyer.py — voir limites détaillées
--     dans ce module : garde alternée, handicap, plafonds spécifiques
--     veuf/invalide non gérés)
--   - Quelques catégories produit d'exemple (mapping non exhaustif à ce stade)
--
-- Le plafonnement s'appuie sur de nouveaux paramètres de référence versionnés
-- (table parametre_reference / valeur_parametre_reference), utilisables comme
-- variables dans n'importe quelle règle de type 'formule' — voir
-- fiscal_engine/parameters.py.
--
-- HORS PÉRIMÈTRE (limitation assumée, cf. PROJECT_STATE.md) :
--   - Majoration régionale de la TICPE (chaque région peut moduler dans une
--     limite encadrée) : seul le taux national est modélisé ici.
--   - Cotisations patronales (hors périmètre : ce logiciel comptabilise les
--     prélèvements payés PAR la personne, pas le coût total employeur).
--   - Régime des indépendants : à ajouter dans un lot ultérieur dédié.
-- =========================================================================

-- -------------------------------------------------------------------------
-- Pays
-- -------------------------------------------------------------------------
INSERT INTO pays (code, nom) VALUES ('FR', 'France');

-- -------------------------------------------------------------------------
-- Typologies de prélèvement
-- -------------------------------------------------------------------------
INSERT INTO typologie_prelevement (code, libelle_fr, libelle_en, libelle_es) VALUES
    ('TVA',          'Taxe sur la valeur ajoutée',      'Value Added Tax',        'Impuesto sobre el Valor Añadido'),
    ('COTIS_SOC',    'Cotisations sociales',            'Social contributions',   'Cotizaciones sociales'),
    ('IMPOT_REVENU', 'Impôt sur le revenu',             'Income tax',             'Impuesto sobre la renta'),
    ('TAXE_ECO',     'Taxes écologiques / énergétiques','Environmental/energy taxes', 'Impuestos ecológicos/energéticos'),
    ('IMPOTS_LOCAUX','Impôts locaux',                   'Local taxes',            'Impuestos locales');

-- -------------------------------------------------------------------------
-- Types de dépense (axe de ventilation n°2)
-- -------------------------------------------------------------------------
INSERT INTO type_depense (code, libelle_fr, libelle_en, libelle_es) VALUES
    ('ALIMENTATION', 'Alimentation',        'Food',           'Alimentación'),
    ('CARBURANT',    'Carburant',           'Fuel',           'Combustible'),
    ('ENERGIE',      'Énergie du logement (gaz, électricité)', 'Home energy (gas, electricity)', 'Energía del hogar (gas, electricidad)'),
    ('LOGEMENT',     'Logement (taxes et impôts locaux)', 'Housing (local taxes)', 'Vivienda (impuestos locales)'),
    ('HYGIENE_ENTRETIEN', 'Hygiène, beauté et entretien', 'Hygiene, beauty and household cleaning', 'Higiene, belleza y limpieza del hogar'),
    ('SALAIRE',      'Salaire',             'Salary',         'Salario'),
    ('AUTRE',        'Autres dépenses',     'Other expenses', 'Otros gastos');

-- =========================================================================
-- TVA — 4 taux en vigueur (article 278 et suivants du CGI)
-- =========================================================================
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TVA_NORMAL', 'TVA taux normal (20 %)', 'VAT standard rate (20%)', 'IVA tipo normal (20%)',
       'Montant TTC de la ligne', 'Art. 278 CGI'
FROM typologie_prelevement WHERE code = 'TVA';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TVA_INTERMEDIAIRE', 'TVA taux intermédiaire (10 %)', 'VAT intermediate rate (10%)', 'IVA tipo intermedio (10%)',
       'Montant TTC de la ligne', 'Art. 278 bis et 279 CGI'
FROM typologie_prelevement WHERE code = 'TVA';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TVA_REDUIT', 'TVA taux réduit (5,5 %)', 'VAT reduced rate (5.5%)', 'IVA tipo reducido (5,5%)',
       'Montant TTC de la ligne', 'Art. 278-0 bis CGI'
FROM typologie_prelevement WHERE code = 'TVA';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TVA_PARTICULIER', 'TVA taux particulier (2,1 %)', 'VAT special rate (2.1%)', 'IVA tipo especial (2,1%)',
       'Montant TTC de la ligne', 'Art. 281 quater et s. CGI'
FROM typologie_prelevement WHERE code = 'TVA';

-- Règles associées : les 4 taux sont stables depuis 2014, appliqués en mode
-- 'ttc_inclus' car le montant lu sur un ticket/facture est déjà TTC.
INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2014-01-01', NULL, 'taux_fixe', 0.20, 'ttc_inclus', 'Art. 278 CGI, en vigueur depuis le 01/01/2014'
FROM prelevement WHERE code = 'TVA_NORMAL';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2014-01-01', NULL, 'taux_fixe', 0.10, 'ttc_inclus', 'Art. 278 bis et 279 CGI, en vigueur depuis le 01/01/2014'
FROM prelevement WHERE code = 'TVA_INTERMEDIAIRE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2014-01-01', NULL, 'taux_fixe', 0.055, 'ttc_inclus', 'Art. 278-0 bis CGI, en vigueur depuis le 01/01/2014'
FROM prelevement WHERE code = 'TVA_REDUIT';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2014-01-01', NULL, 'taux_fixe', 0.021, 'ttc_inclus', 'Art. 281 quater et s. CGI, en vigueur depuis le 01/01/2014'
FROM prelevement WHERE code = 'TVA_PARTICULIER';

-- =========================================================================
-- Paramètres de référence versionnés (utilisés comme seuils/plafonds
-- dans les formules ci-dessous)
-- =========================================================================
INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'PMSS_MENSUEL', 'Plafond mensuel de la Sécurité sociale', 'Monthly Social Security ceiling', 'Techo mensual de la Seguridad Social');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL', 'Plafond mensuel de l''abattement de 1,75 % pour frais professionnels (CSG/CRDS)', 'Monthly cap of the 1.75% standard deduction (CSG/CRDS)', 'Techo mensual de la deducción del 1,75 % (CSG/CRDS)');

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 4005.0, 'Arrêté relatif aux valeurs 2026 du plafond de la Sécurité sociale'
FROM parametre_reference WHERE code = 'PMSS_MENSUEL';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 16020.0, 'Égal à 4 PMSS 2026 (4 x 4005 €) — Art. L136-8 CSS pour le principe du plafonnement de l''abattement'
FROM parametre_reference WHERE code = 'PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL';

-- Paramètres du quotient familial et de la décote (revenus 2025, imposition
-- 2026). Sources concordantes (LégiFiscal citant actualité BOFiP du
-- 07/04/2026 - BOI-IR-LIQ-20-10 §40 ; Meilleurtaux Placement).
INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'PLAFOND_QF_DEMI_PART', 'Plafond de l''avantage du quotient familial par demi-part supplémentaire', 'Family quotient benefit cap per additional half-share', 'Techo de la ventaja del cociente familiar por media parte adicional');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT', 'Plafond de l''avantage du quotient familial pour la part de parent isolé (1er enfant)', 'Family quotient benefit cap for single-parent share (first child)', 'Techo de la ventaja del cociente familiar para el padre/madre soltero/a (primer hijo)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'DECOTE_SEUIL_CELIBATAIRE', 'Seuil d''impôt brut en-deçà duquel la décote s''applique (personne seule)', 'Gross tax threshold below which the tax rebate applies (single)', 'Umbral de impuesto bruto por debajo del cual se aplica la reducción (soltero)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'DECOTE_SEUIL_COUPLE', 'Seuil d''impôt brut en-deçà duquel la décote s''applique (couple)', 'Gross tax threshold below which the tax rebate applies (couple)', 'Umbral de impuesto bruto por debajo del cual se aplica la reducción (pareja)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'DECOTE_FORFAIT_CELIBATAIRE', 'Montant forfaitaire de la formule de décote (personne seule)', 'Flat amount in the tax rebate formula (single)', 'Importe fijo de la fórmula de reducción (soltero)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'DECOTE_FORFAIT_COUPLE', 'Montant forfaitaire de la formule de décote (couple)', 'Flat amount in the tax rebate formula (couple)', 'Importe fijo de la fórmula de reducción (pareja)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'DECOTE_TAUX', 'Taux appliqué à l''impôt brut dans la formule de décote', 'Rate applied to gross tax in the tax rebate formula', 'Tasa aplicada al impuesto bruto en la fórmula de reducción');

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 1807.0, 'Art. 197 CGI — LégiFiscal citant actualité BOFiP du 07/04/2026 (BOI-IR-LIQ-20-10 §40), revenus 2025'
FROM parametre_reference WHERE code = 'PLAFOND_QF_DEMI_PART';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 4262.0, 'Art. 197 CGI — LégiFiscal citant actualité BOFiP du 07/04/2026 (BOI-IR-LIQ-20-10 §40), revenus 2025'
FROM parametre_reference WHERE code = 'PLAFOND_QF_PARENT_ISOLE_1ER_ENFANT';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 1982.0, 'Art. 197 CGI — LégiFiscal (BOFiP 07/04/2026) et Meilleurtaux Placement, revenus 2025'
FROM parametre_reference WHERE code = 'DECOTE_SEUIL_CELIBATAIRE';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 3277.0, 'Art. 197 CGI — Meilleurtaux Placement, cohérent avec le seuil célibataire (1982) et le forfait couple (1483) via taux 45,25%, revenus 2025'
FROM parametre_reference WHERE code = 'DECOTE_SEUIL_COUPLE';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 897.0, 'Art. 197 CGI — LégiFiscal (BOFiP 07/04/2026) et Meilleurtaux Placement, revenus 2025'
FROM parametre_reference WHERE code = 'DECOTE_FORFAIT_CELIBATAIRE';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 1483.0, 'Art. 197 CGI — Meilleurtaux Placement, revenus 2025'
FROM parametre_reference WHERE code = 'DECOTE_FORFAIT_COUPLE';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 0.4525, 'Art. 197 CGI — LégiFiscal (BOFiP 07/04/2026) et Meilleurtaux Placement, revenus 2025'
FROM parametre_reference WHERE code = 'DECOTE_TAUX';

-- =========================================================================
-- CSG / CRDS sur salaire
-- =========================================================================
-- Assiette commune : 98,25 % du salaire brut (abattement forfaitaire de
-- 1,75 % pour frais professionnels), MAIS cet abattement est plafonné à
-- 4 PMSS/mois : au-delà de ce seuil, la part excédentaire du salaire est
-- soumise à CSG/CRDS sur 100 % (pas d'abattement).
-- Formule : (min(base, PLAFOND) * 0.9825 + max(base - PLAFOND, 0) * 1) * taux
--   - Si base <= PLAFOND : équivaut à base * 0.9825 * taux (abattement plein)
--   - Si base >  PLAFOND : la part au-delà du plafond n'a pas d'abattement
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CSG_DEDUCTIBLE', 'CSG déductible', 'Deductible CSG', 'CSG deducible',
       'Salaire brut mensuel (abattement 1,75 % plafonné à 4 PMSS)', 'Art. L136-1 et s. CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CSG_NON_DEDUCTIBLE', 'CSG non déductible', 'Non-deductible CSG', 'CSG no deducible',
       'Salaire brut mensuel (abattement 1,75 % plafonné à 4 PMSS)', 'Art. L136-1 et s. CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CRDS', 'CRDS', 'CRDS (social debt repayment contribution)', 'CRDS',
       'Salaire brut mensuel (abattement 1,75 % plafonné à 4 PMSS)', 'Ordonnance n°96-50 du 24/01/1996'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, formule, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'formule',
       '(min(base, PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL) * 0.9825 + max(base - PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL, 0)) * 0.068',
       'Art. L136-8 CSS — taux inchangé depuis la LFSS 2018 ; plafond d''abattement = 4 PMSS 2026',
       'Abattement de 1,75% plafonné à 4 PMSS/mois (16020 € en 2026), conformément à la réglementation URSSAF'
FROM prelevement WHERE code = 'CSG_DEDUCTIBLE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, formule, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'formule',
       '(min(base, PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL) * 0.9825 + max(base - PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL, 0)) * 0.024',
       'Art. L136-8 CSS — taux inchangé depuis la LFSS 2018 ; plafond d''abattement = 4 PMSS 2026',
       'Abattement de 1,75% plafonné à 4 PMSS/mois (16020 € en 2026)'
FROM prelevement WHERE code = 'CSG_NON_DEDUCTIBLE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, formule, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'formule',
       '(min(base, PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL) * 0.9825 + max(base - PLAFOND_ABATTEMENT_CSG_CRDS_MENSUEL, 0)) * 0.005',
       'Ordonnance n°96-50 du 24/01/1996 — taux de 0,5 % inchangé ; plafond d''abattement = 4 PMSS 2026',
       'Abattement de 1,75% plafonné à 4 PMSS/mois (16020 € en 2026)'
FROM prelevement WHERE code = 'CRDS';

-- =========================================================================
-- Cotisation vieillesse salariale (régime général, plafonnée + déplafonnée)
-- =========================================================================
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'COTIS_VIEILLESSE_PLAF', 'Cotisation vieillesse plafonnée (salariale)', 'Old-age pension contribution (capped, employee share)', 'Cotización de vejez limitada (parte del asalariado)',
       'Salaire brut mensuel, plafonné au PMSS', 'Art. L241-3 CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'COTIS_VIEILLESSE_DEPLAF', 'Cotisation vieillesse déplafonnée (salariale)', 'Old-age pension contribution (uncapped, employee share)', 'Cotización de vejez sin límite (parte del asalariado)',
       'Salaire brut mensuel intégral', 'Art. L241-3 CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

-- Plafonnée : le taux ne s'applique que sur la part du salaire jusqu'au PMSS
-- (ex : sur un salaire de 5000€/mois avec un PMSS à 4005€, la cotisation
-- porte sur 4005€, pas sur 5000€). Exprimé via 'formule' pour réutiliser le
-- paramètre PMSS_MENSUEL plutôt que d'ajouter une colonne dédiée au schéma.
INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, formule, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'formule', 'min(base, PMSS_MENSUEL) * 0.069',
       'Art. L241-3 CSS, taux 2026 ; plafond = PMSS 2026 (4005 €/mois)',
       'La cotisation ne porte que sur la part du salaire brut inférieure ou égale au PMSS'
FROM prelevement WHERE code = 'COTIS_VIEILLESSE_PLAF';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.004, 'base_directe',
       'Art. L241-3 CSS, taux 2026'
FROM prelevement WHERE code = 'COTIS_VIEILLESSE_DEPLAF';

-- =========================================================================
-- Impôt sur le revenu — barème 2026 (revenus 2025), par part de quotient familial
-- =========================================================================
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'IR_BAREME', 'Impôt sur le revenu (barème progressif)', 'Income tax (progressive schedule)', 'Impuesto sobre la renta (escala progresiva)',
       'Revenu net imposable divisé par le nombre de parts de quotient familial (résultat à multiplier par le nombre de parts)',
       'Art. 4 de la loi n°2026-103 du 19/02/2026 de finances pour 2026'
FROM typologie_prelevement WHERE code = 'IMPOT_REVENU';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'bareme_progressif',
       'Art. 4 de la loi n°2026-103 du 19/02/2026 de finances pour 2026 (barème applicable aux revenus 2025)',
       'Résultat exprimé PAR PART. Le quotient familial, son plafonnement, et la décote sont calculés séparément par fiscal_engine/foyer.py (calculer_impot_foyer), qui appelle ce barème par-part comme brique de base.'
FROM prelevement WHERE code = 'IR_BAREME';

INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 0,      11600,  0.00
FROM regle_prelevement rp JOIN prelevement p ON p.id = rp.prelevement_id WHERE p.code = 'IR_BAREME';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 11600,  29579,  0.11
FROM regle_prelevement rp JOIN prelevement p ON p.id = rp.prelevement_id WHERE p.code = 'IR_BAREME';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 29579,  84577,  0.30
FROM regle_prelevement rp JOIN prelevement p ON p.id = rp.prelevement_id WHERE p.code = 'IR_BAREME';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 84577,  181917, 0.41
FROM regle_prelevement rp JOIN prelevement p ON p.id = rp.prelevement_id WHERE p.code = 'IR_BAREME';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 181917, NULL,   0.45
FROM regle_prelevement rp JOIN prelevement p ON p.id = rp.prelevement_id WHERE p.code = 'IR_BAREME';

-- =========================================================================
-- TICPE — essence SP95-E5 et gazole (taux national, hors majoration régionale)
-- =========================================================================
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TICPE_SANS_PLOMB', 'TICPE essence SP95-E5', 'Fuel excise duty - unleaded petrol', 'Impuesto especial sobre hidrocarburos - gasolina',
       'Volume en litres', 'Art. 265 du code des douanes — taux national 2026'
FROM typologie_prelevement WHERE code = 'TAXE_ECO';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TICPE_GAZOLE', 'TICPE gazole', 'Fuel excise duty - diesel', 'Impuesto especial sobre hidrocarburos - gasóleo',
       'Volume en litres', 'Art. 265 du code des douanes — taux national 2026'
FROM typologie_prelevement WHERE code = 'TAXE_ECO';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, montant_unitaire, unite, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'montant_par_unite', 0.6829, 'L',
       'Art. 265 du code des douanes, taux national 2026 (source concordante : FIPECO, DGEC)',
       'Taux national hors majoration régionale (les régions peuvent moduler ce taux dans une limite encadrée, non gérée dans ce lot)'
FROM prelevement WHERE code = 'TICPE_SANS_PLOMB';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, montant_unitaire, unite, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'montant_par_unite', 0.5940, 'L',
       'Art. 265 du code des douanes, taux national 2026 (source concordante : FIPECO, DGEC)',
       'Taux national hors majoration régionale (les régions peuvent moduler ce taux dans une limite encadrée, non gérée dans ce lot)'
FROM prelevement WHERE code = 'TICPE_GAZOLE';

-- =========================================================================
-- TICGN — accise sur le gaz naturel (chauffage domestique)
-- =========================================================================
-- Assise en €/MWh, ce qui en fait un deuxième exemple naturel de prélèvement
-- de type 'montant_par_unite' (au-delà du carburant), pour la consommation
-- énergétique courante d'un particulier (chauffage, eau chaude, cuisson).
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TICGN', 'Accise sur le gaz naturel (ex-TICGN)', 'Natural gas excise duty (former TICGN)', 'Impuesto especial sobre el gas natural',
       'Consommation en MWh (ou kWh, converti automatiquement)', 'Art. 266 quinquies du code des douanes / Code des impositions sur les biens et services'
FROM typologie_prelevement WHERE code = 'TAXE_ECO';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, montant_unitaire, unite, source_reference, commentaire)
SELECT id, '2026-02-01', NULL, 'montant_par_unite', 16.39, 'MWh',
       'BOFiP, taux normal applicable au 01/02/2026 pour un usage combustible ménager (sources concordantes : Opéra Energie, Fiscalead, Selectra)',
       'Taux ménages/usage combustible. Ne couvre pas le taux réduit GNV (5,23 €/MWh, usage carburant) ni les taux réduits industriels.'
FROM prelevement WHERE code = 'TICGN';

-- =========================================================================
-- Impôts locaux — taxe foncière et taxe d'habitation sur les résidences
-- secondaires (THRS)
-- =========================================================================
-- Ces deux impôts n'ont PAS de taux national : la base (valeur locative
-- cadastrale) est nationale, mais le taux appliqué est voté par chaque
-- commune/EPCI/département et varie donc fortement d'un endroit à l'autre.
-- Le moteur ne peut donc pas les calculer — leur montant, déjà déterminé
-- par l'administration fiscale, est lu directement sur l'avis d'imposition
-- (type_regle = 'montant_declare', voir schema.sql et calculator.py).
--
-- Rappel important (vérifié) : la taxe d'habitation sur la RÉSIDENCE
-- PRINCIPALE est supprimée depuis le 1er janvier 2023 pour tous les
-- contribuables. Elle ne subsiste que sur les résidences secondaires (THRS).
-- Ne pas modéliser de "taxe d'habitation résidence principale" comme si
-- elle existait encore.
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TAXE_FONCIERE', 'Taxe foncière sur les propriétés bâties', 'Property tax (built properties)', 'Impuesto sobre bienes inmuebles (construidos)',
       'Montant lu directement sur l''avis de taxe foncière (taux voté par la commune/EPCI/département, non modélisable nationalement)',
       'Art. 1380 et s. CGI'
FROM typologie_prelevement WHERE code = 'IMPOTS_LOCAUX';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'TAXE_HABITATION_RESIDENCE_SECONDAIRE', 'Taxe d''habitation sur une résidence secondaire (THRS)', 'Housing tax on secondary residences', 'Impuesto de vivienda sobre residencias secundarias',
       'Montant lu directement sur l''avis de THRS (taux voté localement, majoration possible en zone tendue, non modélisable nationalement)',
       'Art. 1407 et s. CGI — la taxe d''habitation sur la résidence principale est supprimée depuis le 01/01/2023'
FROM typologie_prelevement WHERE code = 'IMPOTS_LOCAUX';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'montant_declare',
       'Art. 1380 et s. CGI — taux fixé annuellement par chaque collectivité, aucun taux national',
       'Montant à saisir tel qu''affiché sur l''avis de taxe foncière, aucun calcul effectué par le moteur'
FROM prelevement WHERE code = 'TAXE_FONCIERE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'montant_declare',
       'Art. 1407 et s. CGI — taux fixé annuellement par chaque collectivité, aucun taux national ; majoration possible de 5 à 60% en zone tendue',
       'Montant à saisir tel qu''affiché sur l''avis de THRS, aucun calcul effectué par le moteur ; ne s''applique qu''aux résidences secondaires depuis 2023'
FROM prelevement WHERE code = 'TAXE_HABITATION_RESIDENCE_SECONDAIRE';

-- =========================================================================
-- Catégories produit d'exemple (mapping non exhaustif — illustration du
-- mécanisme, à compléter dans un lot dédié "catégorisation produits")
-- =========================================================================
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ALIMENTATION_GENERALE', 'Alimentation générale (épicerie)', 'General food (groceries)', 'Alimentación general', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'CONFISERIE_CHOCOLAT', 'Confiserie et chocolat', 'Confectionery and chocolate', 'Confitería y chocolate', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'RESTAURATION_SUR_PLACE', 'Restauration (consommation sur place)', 'Restaurant (dine-in)', 'Restauración (consumo en el local)', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'CARBURANT_SANS_PLOMB', 'Carburant essence sans plomb', 'Unleaded petrol', 'Gasolina sin plomo', id
FROM type_depense WHERE code = 'CARBURANT';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'CARBURANT_GAZOLE', 'Carburant gazole', 'Diesel fuel', 'Gasóleo', id
FROM type_depense WHERE code = 'CARBURANT';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'GAZ_NATUREL_CHAUFFAGE', 'Gaz naturel (chauffage/cuisson)', 'Natural gas (heating/cooking)', 'Gas natural (calefacción/cocina)', id
FROM type_depense WHERE code = 'ENERGIE';

-- Mapping catégorie -> prélèvement(s) applicable(s) :
--   - Alimentation générale (produits de base non transformés type pâtes,
--     riz, légumes...) -> TVA taux réduit 5,5%
--   - Confiserie/chocolat -> TVA taux NORMAL (20%) : la confiserie est
--     explicitement exclue du taux réduit par le CGI, contrairement à une
--     idée reçue fréquente.
--   - Restauration sur place -> TVA taux intermédiaire 10%
--   - Carburant essence -> TVA 20% + TICPE essence (deux prélèvements
--     cumulés sur la même ligne, chacun avec sa propre assiette : montant
--     pour la TVA, quantité en litres pour la TICPE)
--   - Carburant gazole -> TVA 20% + TICPE gazole
--   - Gaz naturel -> TVA 20% + TICGN (quantité en kWh/MWh)
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'ALIMENTATION_GENERALE' AND p.code = 'TVA_REDUIT';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'CONFISERIE_CHOCOLAT' AND p.code = 'TVA_NORMAL';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'RESTAURATION_SUR_PLACE' AND p.code = 'TVA_INTERMEDIAIRE';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'CARBURANT_SANS_PLOMB' AND p.code = 'TVA_NORMAL';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'CARBURANT_SANS_PLOMB' AND p.code = 'TICPE_SANS_PLOMB';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'CARBURANT_GAZOLE' AND p.code = 'TVA_NORMAL';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'CARBURANT_GAZOLE' AND p.code = 'TICPE_GAZOLE';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'GAZ_NATUREL_CHAUFFAGE' AND p.code = 'TVA_NORMAL';

INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'GAZ_NATUREL_CHAUFFAGE' AND p.code = 'TICGN';

-- =========================================================================
-- Régime micro-entrepreneur (auto-entrepreneur) — voir fiscal_engine/independant.py
-- =========================================================================
-- Périmètre : 3 catégories d'activité (vente, services BIC, BNC régime
-- général). Le taux CIPAV, la location de meublés de tourisme classés,
-- l'ACRE, et le régime réel ne sont PAS couverts (voir limites détaillées
-- dans independant.py).
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_COTIS_VENTE', 'Cotisations sociales micro-entrepreneur (vente de marchandises)', 'Micro-entrepreneur social contributions (sale of goods)', 'Cotizaciones sociales de microempresario (venta de mercancías)',
       'Chiffre d''affaires encaissé sur la période déclarée', 'Décret n°2024-484 du 30/05/2024, taux 2026'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_COTIS_SERVICES_BIC', 'Cotisations sociales micro-entrepreneur (prestations de services BIC)', 'Micro-entrepreneur social contributions (BIC services)', 'Cotizaciones sociales de microempresario (servicios BIC)',
       'Chiffre d''affaires encaissé sur la période déclarée', 'Décret n°2024-484 du 30/05/2024, taux 2026'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_COTIS_BNC', 'Cotisations sociales micro-entrepreneur (professions libérales BNC, régime général)', 'Micro-entrepreneur social contributions (BNC, general scheme)', 'Cotizaciones sociales de microempresario (BNC, régimen general)',
       'Chiffre d''affaires encaissé sur la période déclarée. Ne couvre PAS le taux spécifique CIPAV.', 'Décret n°2024-484 du 30/05/2024, taux 2026'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.123, 'base_directe', 'Décret n°2024-484 du 30/05/2024 — sources concordantes (Abby, LegalPlace, Subventions.fr) ; cohérent avec le taux combiné 13,3% du versement libératoire publié par Service-Public.fr (12,3+1)'
FROM prelevement WHERE code = 'MICRO_COTIS_VENTE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.212, 'base_directe', 'Décret n°2024-484 du 30/05/2024 — sources concordantes (Abby, LegalPlace, Subventions.fr, SimuAuto)'
FROM prelevement WHERE code = 'MICRO_COTIS_SERVICES_BIC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.256, 'base_directe', 'Décret n°2024-484 du 30/05/2024 — sources concordantes (Abby, LegalPlace, Subventions.fr). Taux CIPAV (23,2%) non modélisé séparément.'
FROM prelevement WHERE code = 'MICRO_COTIS_BNC';

-- Versement libératoire de l'IR (optionnel, sous condition de RFR non
-- vérifiée par ce moteur — voir independant.py)
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_VL_VENTE', 'Versement libératoire de l''IR (vente de marchandises)', 'Final withholding income tax option (sale of goods)', 'Pago liberatorio del IRPF (venta de mercancías)',
       'Chiffre d''affaires encaissé, sur option et sous condition de revenu fiscal de référence', 'Art. 151-0 CGI'
FROM typologie_prelevement WHERE code = 'IMPOT_REVENU';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_VL_SERVICES_BIC', 'Versement libératoire de l''IR (prestations de services BIC)', 'Final withholding income tax option (BIC services)', 'Pago liberatorio del IRPF (servicios BIC)',
       'Chiffre d''affaires encaissé, sur option et sous condition de revenu fiscal de référence', 'Art. 151-0 CGI'
FROM typologie_prelevement WHERE code = 'IMPOT_REVENU';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'MICRO_VL_BNC', 'Versement libératoire de l''IR (professions libérales BNC)', 'Final withholding income tax option (BNC)', 'Pago liberatorio del IRPF (BNC)',
       'Chiffre d''affaires encaissé, sur option et sous condition de revenu fiscal de référence', 'Art. 151-0 CGI'
FROM typologie_prelevement WHERE code = 'IMPOT_REVENU';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.01, 'base_directe', 'Art. 151-0 CGI — sources concordantes (LegalPlace, Subventions.fr, SimuAuto) ; cohérent avec le taux combiné 13,3% de Service-Public.fr'
FROM prelevement WHERE code = 'MICRO_VL_VENTE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.017, 'base_directe', 'Art. 151-0 CGI — sources concordantes (LegalPlace, Subventions.fr, SimuAuto)'
FROM prelevement WHERE code = 'MICRO_VL_SERVICES_BIC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.022, 'base_directe', 'Art. 151-0 CGI — sources concordantes (LegalPlace, Subventions.fr, SimuAuto)'
FROM prelevement WHERE code = 'MICRO_VL_BNC';

-- Abattements forfaitaires pour frais professionnels (régime micro-fiscal
-- classique, hors versement libératoire) — versionnés comme paramètres de
-- référence car stables mais légalement susceptibles de changer.
INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'ABATTEMENT_MICRO_VENTE', 'Abattement forfaitaire micro-entrepreneur (vente de marchandises)', 'Micro-entrepreneur standard deduction (sale of goods)', 'Deducción estándar de microempresario (venta de mercancías)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'ABATTEMENT_MICRO_SERVICES_BIC', 'Abattement forfaitaire micro-entrepreneur (prestations de services BIC)', 'Micro-entrepreneur standard deduction (BIC services)', 'Deducción estándar de microempresario (servicios BIC)');

INSERT INTO parametre_reference (pays_code, code, libelle_fr, libelle_en, libelle_es)
VALUES ('FR', 'ABATTEMENT_MICRO_BNC', 'Abattement forfaitaire micro-entrepreneur (professions libérales BNC)', 'Micro-entrepreneur standard deduction (BNC)', 'Deducción estándar de microempresario (BNC)');

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 0.71, 'Art. 50-0 CGI — sources concordantes (swim.legal, LegalPlace), stable depuis plusieurs années'
FROM parametre_reference WHERE code = 'ABATTEMENT_MICRO_VENTE';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 0.50, 'Art. 50-0 CGI — sources concordantes (swim.legal, LegalPlace), stable depuis plusieurs années'
FROM parametre_reference WHERE code = 'ABATTEMENT_MICRO_SERVICES_BIC';

INSERT INTO valeur_parametre_reference (parametre_id, date_debut, date_fin, valeur, source_reference)
SELECT id, '2026-01-01', NULL, 0.34, 'Art. 102 ter CGI — sources concordantes (swim.legal, LegalPlace, LegalPlace exemple Claire 36000E->23760E), stable depuis plusieurs années'
FROM parametre_reference WHERE code = 'ABATTEMENT_MICRO_BNC';

-- =========================================================================
-- Prélèvement Forfaitaire Unique (PFU / "flat tax") sur les revenus du
-- capital — dividendes, intérêts de comptes/livrets non réglementés,
-- plus-values mobilières, assurance-vie...
-- =========================================================================
-- Depuis le 01/01/2026 (LFSS 2026), le taux des prélèvements sociaux sur
-- les revenus du capital est passé de 17,2% à 18,6% pour la PLUPART des
-- produits (portant le total PFU à 31,4% au lieu de 30%) — MAIS
-- l'assurance-vie, le PEL et le CEL (ouverts depuis 2018) ont été
-- explicitement exclus de cette hausse et restent à 17,2% (total 30%).
-- Sources concordantes : Ramify, Victoris Avocat, Tantiem, AdvizExperts.
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'PFU_IR', 'Prélèvement forfaitaire unique - part impôt sur le revenu', 'Flat tax - income tax share', 'Tasa única - parte del impuesto sobre la renta',
       'Montant du revenu de capital perçu (dividendes, intérêts, plus-values...)', 'Art. 200 A du CGI'
FROM typologie_prelevement WHERE code = 'IMPOT_REVENU';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'PS_CAPITAL_STANDARD', 'Prélèvements sociaux sur revenus du capital (taux standard 2026)', 'Social levies on capital income (2026 standard rate)', 'Gravámenes sociales sobre rentas del capital (tipo estándar 2026)',
       'Montant du revenu de capital perçu (dividendes, intérêts non réglementés, plus-values mobilières)', 'Art. L136-7 CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'PS_CAPITAL_ASSURANCE_VIE', 'Prélèvements sociaux sur revenus du capital (assurance-vie, PEL/CEL - taux maintenu à 17,2%)', 'Social levies on capital income (life insurance, PEL/CEL - rate held at 17.2%)', 'Gravámenes sociales sobre rentas del capital (seguro de vida - tipo mantenido en 17,2%)',
       'Produits d''assurance-vie, PEL et CEL ouverts depuis 2018, explicitement exclus de la hausse 2026', 'Art. L136-7 CSS'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2018-01-01', NULL, 'taux_fixe', 0.128, 'base_directe', 'Art. 200 A du CGI, taux inchangé depuis la création du PFU en 2018'
FROM prelevement WHERE code = 'PFU_IR';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'taux_fixe', 0.186, 'base_directe', 'Art. L136-7 CSS — LFSS 2026 (loi n°2025-1403), hausse de 17,2% à 18,6% au 01/01/2026',
       'Ne s''applique PAS à l''assurance-vie/PEL/CEL, voir PS_CAPITAL_ASSURANCE_VIE'
FROM prelevement WHERE code = 'PS_CAPITAL_STANDARD';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference, commentaire)
SELECT id, '2018-01-01', NULL, 'taux_fixe', 0.172, 'base_directe', 'Art. L136-7 CSS — taux maintenu à 17,2% pour ces produits malgré la hausse générale 2026',
       'S''applique à l''assurance-vie, au PEL et au CEL ouverts depuis 2018'
FROM prelevement WHERE code = 'PS_CAPITAL_ASSURANCE_VIE';

-- =========================================================================
-- CSG / CRDS / CASA sur pensions de retraite
-- =========================================================================
-- Premier usage réel du mécanisme 'bareme_a_seuil' (voir schema.sql) : le
-- taux de CSG applicable dépend du REVENU FISCAL DE RÉFÉRENCE (RFR) du
-- foyer, mais s'applique ensuite à la PENSION BRUTE — deux grandeurs
-- différentes, d'où le paramètre valeur_seuil distinct de montant dans
-- calculer_montant().
--
-- AVERTISSEMENT DE SOURCING (à prendre au sérieux) : les seuils RFR exacts
-- pour 2026 varient sensiblement selon les sources spécialisées consultées
-- (deux groupes de sources donnent des seuils différents de plusieurs
-- centaines d'euros). Les valeurs retenues ci-dessous s'appuient sur le
-- groupe de sources le plus large et le plus cohérent entre elles trouvé
-- (5 sources indépendantes convergentes à quelques euros près, cohérentes
-- avec la revalorisation +1,8% annoncée pour 2026), mais restent une
-- ESTIMATION, pas une valeur officielle vérifiée sur le texte réglementaire
-- lui-même (BOFiP / décret). L'utilisateur doit vérifier ces seuils sur son
-- avis d'imposition ou via le simulateur officiel avant toute décision
-- s'appuyant dessus.
--
-- PÉRIMÈTRE : seuls 1 part et 2 parts sont modélisés (les foyers avec
-- d'autres nombres de parts, ex 1,5 ou 2,5, ne sont pas couverts — les
-- seuils intermédiaires ne suivent pas une simple règle proportionnelle
-- vérifiable facilement).
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CSG_RETRAITE_1PART', 'CSG sur pension de retraite (foyer à 1 part)', 'CSG on retirement pension (1 tax share household)', 'CSG sobre pensión de jubilación (hogar de 1 parte)',
       'Taux sélectionné selon le RFR du foyer, appliqué à la pension brute', 'Art. L136-8 CSS — seuils estimés, à vérifier sur l''avis d''imposition'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CSG_RETRAITE_2PARTS', 'CSG sur pension de retraite (foyer à 2 parts)', 'CSG on retirement pension (2 tax shares household)', 'CSG sobre pensión de jubilación (hogar de 2 partes)',
       'Taux sélectionné selon le RFR du foyer, appliqué à la pension brute', 'Art. L136-8 CSS — seuils estimés, à vérifier sur l''avis d''imposition'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'bareme_a_seuil',
       'Art. L136-8 CSS — seuils 2026 estimés (consensus de 5 sources : signal-alpha.fr, mabonneretraite.fr, quelles-aides.fr, la-juvenie.fr, cesdefrance.fr), +1,8% de revalorisation 2026',
       'Seuils RFR 2024 (avis d''imposition 2025), pour une pension versée en 2026, foyer à 1 part'
FROM prelevement WHERE code = 'CSG_RETRAITE_1PART';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, source_reference, commentaire)
SELECT id, '2026-01-01', NULL, 'bareme_a_seuil',
       'Art. L136-8 CSS — seuils 2026 estimés (consensus de 5 sources : signal-alpha.fr, mabonneretraite.fr, quelles-aides.fr, la-juvenie.fr, cesdefrance.fr), +1,8% de revalorisation 2026',
       'Seuils RFR 2024 (avis d''imposition 2025), pour une pension versée en 2026, foyer à 2 parts'
FROM prelevement WHERE code = 'CSG_RETRAITE_2PARTS';

-- Tranches 1 part : exonération / réduit 3,8% / médian 6,6% / normal 8,3%
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 0, 13048, 0.000 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_1PART';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 13048, 17057, 0.038 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_1PART';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 17057, 26472, 0.066 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_1PART';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 26472, NULL, 0.083 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_1PART';

-- Tranches 2 parts
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 0, 20016, 0.000 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_2PARTS';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 20016, 26167, 0.038 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_2PARTS';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 26167, 39886, 0.066 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_2PARTS';
INSERT INTO tranche_bareme (regle_id, borne_min, borne_max, taux)
SELECT rp.id, 39886, NULL, 0.083 FROM regle_prelevement rp JOIN prelevement p ON p.id=rp.prelevement_id WHERE p.code='CSG_RETRAITE_2PARTS';

-- CRDS retraite : 0,5%, due dès que le taux de CSG > 0% (donc pas en cas
-- d'exonération). CASA retraite : 0,3%, due uniquement aux taux médian et
-- normal. La logique de conditionnement (quand appliquer chacune) est gérée
-- par fiscal_engine/retraite.py, pas directement par ces deux règles qui
-- ne sont que des taux fixes simples.
INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CRDS_RETRAITE', 'CRDS sur pension de retraite', 'CRDS on retirement pension', 'CRDS sobre pensión de jubilación',
       'Pension brute, uniquement si non exonéré de CSG', 'Ordonnance n°96-50 du 24/01/1996'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO prelevement (pays_code, typologie_id, code, libelle_fr, libelle_en, libelle_es, base_calcul_desc, reference_legale)
SELECT 'FR', id, 'CASA_RETRAITE', 'CASA sur pension de retraite', 'CASA on retirement pension', 'CASA sobre pensión de jubilación',
       'Pension brute, uniquement aux taux de CSG médian (6,6%) et normal (8,3%)', 'Art. L14-10-4 CASF'
FROM typologie_prelevement WHERE code = 'COTIS_SOC';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2013-04-01', NULL, 'taux_fixe', 0.005, 'base_directe', 'Ordonnance n°96-50 du 24/01/1996, taux inchangé'
FROM prelevement WHERE code = 'CRDS_RETRAITE';

INSERT INTO regle_prelevement (prelevement_id, date_debut, date_fin, type_regle, taux, assiette, source_reference)
SELECT id, '2013-04-01', NULL, 'taux_fixe', 0.003, 'base_directe', 'Art. L14-10-4 CASF, taux inchangé depuis 2013'
FROM prelevement WHERE code = 'CASA_RETRAITE';

-- =========================================================================
-- Fin du contenu fiscal — Lot 3
-- =========================================================================
