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
--   - Régime des indépendants, quotient familial, décote IR : à ajouter
--     dans un lot ultérieur dédié.
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
    ('TAXE_ECO',     'Taxes écologiques / énergétiques','Environmental/energy taxes', 'Impuestos ecológicos/energéticos');

-- -------------------------------------------------------------------------
-- Types de dépense (axe de ventilation n°2)
-- -------------------------------------------------------------------------
INSERT INTO type_depense (code, libelle_fr, libelle_en, libelle_es) VALUES
    ('ALIMENTATION', 'Alimentation',        'Food',           'Alimentación'),
    ('CARBURANT',    'Carburant',           'Fuel',           'Combustible'),
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
       'Résultat exprimé PAR PART. Le quotient familial (division/multiplication par le nombre de parts), le plafonnement du QF et la décote ne sont PAS gérés dans ce lot.'
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

-- =========================================================================
-- Fin du contenu fiscal — Lot 3
-- =========================================================================
