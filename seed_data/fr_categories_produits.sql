-- =========================================================================
-- Fiscal Tracker — Mapping produits par catégories (niveau "familles")
-- =========================================================================
-- Ce fichier s'exécute APRÈS seed_data/fr_seed_lot3.sql (dépend de : pays FR,
-- typologie_prelevement TVA, prélèvements TVA_NORMAL/REDUIT/INTERMEDIAIRE/
-- PARTICULIER, ainsi que des type_depense déjà créés).
--
-- OBJECTIF ET PÉRIMÈTRE (rappel de la discussion de conception) : ce
-- fichier reste au niveau "FAMILLE de produit", volontairement plus large
-- qu'un référentiel produit exhaustif (type Open Food Facts) — l'idée est
-- qu'une famille suffise à déterminer les prélèvements GÉNÉRIQUES (TVA) et
-- CATÉGORIELS (taxes spécifiques) applicables, sans avoir besoin
-- d'identifier chaque référence produit individuellement.
--
-- LIMITES ASSUMÉES (volontairement hors périmètre de ce fichier) :
--   - Taxe sur les boissons sucrées/édulcorées ("taxe soda") : RÉELLE et
--     NON modélisée ici. Deux raisons : (1) son barème 2026 est progressif
--     selon la teneur exacte en sucre/édulcorant (en kg ou mg par
--     hectolitre), une donnée que nous n'avons pas au niveau "famille" —
--     elle nécessiterait une donnée par produit (via Open Food Facts par
--     exemple, teneur en sucre) ; (2) les sources consultées pour ce
--     barème 2026 se contredisaient significativement entre elles (écarts
--     de plusieurs euros par hectolitre selon la source), un niveau
--     d'incertitude jugé trop élevé pour être codé en dur avec confiance.
--     Seule la TVA (20%, taux normal) est donc modélisée sur les boissons
--     sucrées dans ce fichier.
--   - Droits d'accise sur les boissons alcoolisées : RÉELS et NON modélisés
--     (barème complexe par type de boisson et degré d'alcool — hors
--     périmètre de ce lot, pourrait faire l'objet d'un ajout ultérieur
--     similaire à la TICPE si le besoin se confirme).
--   - Taux de TVA "outre-mer" (Guadeloupe, Martinique, Réunion...), qui
--     diffèrent du régime métropolitain : non gérés (seuls les taux
--     métropolitains ci-dessous s'appliquent).
-- =========================================================================

-- -------------------------------------------------------------------------
-- Nouveaux types de dépense (au-delà de ceux déjà créés dans fr_seed_lot3.sql)
-- -------------------------------------------------------------------------
INSERT INTO type_depense (code, libelle_fr, libelle_en, libelle_es) VALUES
    ('HABILLEMENT',      'Habillement et chaussures', 'Clothing and footwear', 'Ropa y calzado'),
    ('EQUIPEMENT_MAISON', 'Équipement de la maison (électroménager, meubles, informatique)', 'Home equipment (appliances, furniture, IT)', 'Equipamiento del hogar'),
    ('CULTURE_LOISIRS',  'Culture et loisirs (livres, presse, spectacles, jouets)', 'Culture and leisure (books, press, shows, toys)', 'Cultura y ocio'),
    ('SANTE',            'Santé (médicaments)', 'Health (medication)', 'Salud (medicamentos)'),
    ('TRANSPORT',        'Transport de voyageurs', 'Passenger transport', 'Transporte de pasajeros');

-- -------------------------------------------------------------------------
-- Alimentation — familles supplémentaires (au-delà d'ALIMENTATION_GENERALE,
-- CONFISERIE_CHOCOLAT, RESTAURATION_SUR_PLACE déjà créées)
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PRODUITS_LAITIERS', 'Produits laitiers (lait, yaourts, fromages)', 'Dairy products', 'Productos lácteos', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'VIANDES_POISSONS_FRAIS', 'Viandes et poissons frais', 'Fresh meat and fish', 'Carne y pescado frescos', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'FRUITS_LEGUMES_FRAIS', 'Fruits et légumes frais', 'Fresh fruit and vegetables', 'Frutas y verduras frescas', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PAIN_PATISSERIE', 'Pain et pâtisserie', 'Bread and pastries', 'Pan y pastelería', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PLATS_PREPARES_TRAITEUR', 'Plats préparés et traiteur', 'Ready meals and deli', 'Platos preparados', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'EAU_BOISSONS_NON_SUCREES', 'Eau et boissons non alcoolisées non sucrées', 'Water and unsweetened non-alcoholic drinks', 'Agua y bebidas no azucaradas', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'BOISSONS_SUCREES', 'Boissons sucrées / sodas', 'Sugary drinks / sodas', 'Bebidas azucaradas', id
FROM type_depense WHERE code = 'ALIMENTATION';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'BOISSONS_ALCOOLISEES', 'Boissons alcoolisées', 'Alcoholic beverages', 'Bebidas alcohólicas', id
FROM type_depense WHERE code = 'ALIMENTATION';

-- Contre-intuitif à souligner : l'alimentation pour animaux domestiques est
-- au taux NORMAL (20%), pas au taux réduit alimentaire (5,5%).
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ALIMENTATION_ANIMAUX', 'Alimentation pour animaux domestiques', 'Pet food', 'Alimento para mascotas', id
FROM type_depense WHERE code = 'AUTRE';

-- -------------------------------------------------------------------------
-- Habillement
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'VETEMENTS', 'Vêtements', 'Clothing', 'Ropa', id FROM type_depense WHERE code = 'HABILLEMENT';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'CHAUSSURES', 'Chaussures', 'Footwear', 'Calzado', id FROM type_depense WHERE code = 'HABILLEMENT';

-- -------------------------------------------------------------------------
-- Équipement de la maison
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER', 'Électroménager', 'Home appliances', 'Electrodomésticos', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'MEUBLES', 'Meubles', 'Furniture', 'Muebles', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_MULTIMEDIA', 'Informatique et multimédia', 'IT and multimedia equipment', 'Informática y multimedia', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PRODUITS_ENTRETIEN_MENAGER', 'Produits d''entretien ménager', 'Household cleaning products', 'Productos de limpieza del hogar', id FROM type_depense WHERE code = 'HYGIENE_ENTRETIEN';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PRODUITS_HYGIENE_BEAUTE', 'Produits d''hygiène et de beauté', 'Hygiene and beauty products', 'Productos de higiene y belleza', id FROM type_depense WHERE code = 'HYGIENE_ENTRETIEN';

-- -------------------------------------------------------------------------
-- Culture et loisirs
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'LIVRES', 'Livres', 'Books', 'Libros', id FROM type_depense WHERE code = 'CULTURE_LOISIRS';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'PRESSE', 'Presse et périodiques', 'Press and periodicals', 'Prensa y publicaciones periódicas', id FROM type_depense WHERE code = 'CULTURE_LOISIRS';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'BILLETTERIE_SPECTACLE', 'Billetterie (cinéma, spectacle vivant)', 'Tickets (cinema, live performance)', 'Entradas (cine, espectáculos)', id FROM type_depense WHERE code = 'CULTURE_LOISIRS';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'JOUETS', 'Jouets', 'Toys', 'Juguetes', id FROM type_depense WHERE code = 'CULTURE_LOISIRS';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'FOURNITURES_SCOLAIRES', 'Fournitures scolaires et papeterie', 'School and stationery supplies', 'Material escolar y papelería', id FROM type_depense WHERE code = 'CULTURE_LOISIRS';

-- -------------------------------------------------------------------------
-- Santé
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'MEDICAMENTS_REMBOURSABLES', 'Médicaments remboursables par l''Assurance Maladie', 'Reimbursable medication', 'Medicamentos reembolsables', id FROM type_depense WHERE code = 'SANTE';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'MEDICAMENTS_NON_REMBOURSABLES', 'Médicaments non remboursables', 'Non-reimbursable medication', 'Medicamentos no reembolsables', id FROM type_depense WHERE code = 'SANTE';

-- -------------------------------------------------------------------------
-- Transport et logement
-- -------------------------------------------------------------------------
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'TRANSPORT_VOYAGEURS', 'Transport public de voyageurs', 'Public passenger transport', 'Transporte público de pasajeros', id FROM type_depense WHERE code = 'TRANSPORT';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'TRAVAUX_RENOVATION_ENERGETIQUE', 'Travaux de rénovation énergétique du logement', 'Home energy renovation work', 'Obras de renovación energética', id FROM type_depense WHERE code = 'LOGEMENT';

INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'TRAVAUX_AMELIORATION_LOGEMENT', 'Travaux d''amélioration/entretien du logement (hors rénovation énergétique)', 'Home improvement/maintenance work (non-energy)', 'Obras de mejora del hogar (no energéticas)', id FROM type_depense WHERE code = 'LOGEMENT';

-- =========================================================================
-- Mapping catégorie -> taux de TVA applicable
-- =========================================================================
-- 5,5 % (taux réduit) : produits alimentaires de base, livres, spectacle
-- vivant/cinéma, travaux de rénovation énergétique
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code IN ('PRODUITS_LAITIERS', 'VIANDES_POISSONS_FRAIS', 'FRUITS_LEGUMES_FRAIS', 'PAIN_PATISSERIE',
                   'PLATS_PREPARES_TRAITEUR', 'EAU_BOISSONS_NON_SUCREES', 'LIVRES', 'BILLETTERIE_SPECTACLE',
                   'TRAVAUX_RENOVATION_ENERGETIQUE')
  AND p.code = 'TVA_REDUIT';

-- 2,1 % (taux particulier) : presse, médicaments remboursables
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code IN ('PRESSE', 'MEDICAMENTS_REMBOURSABLES')
  AND p.code = 'TVA_PARTICULIER';

-- 10 % (taux intermédiaire) : médicaments non remboursables, transport de
-- voyageurs, travaux d'amélioration non énergétique
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code IN ('MEDICAMENTS_NON_REMBOURSABLES', 'TRANSPORT_VOYAGEURS', 'TRAVAUX_AMELIORATION_LOGEMENT')
  AND p.code = 'TVA_INTERMEDIAIRE';

-- 20 % (taux normal) : tout le reste de cette liste, y compris les deux cas
-- "contre-intuitifs" à souligner : boissons sucrées/alcoolisées ET
-- alimentation pour animaux domestiques (PAS taux réduit alimentaire).
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code IN ('BOISSONS_SUCREES', 'BOISSONS_ALCOOLISEES', 'ALIMENTATION_ANIMAUX',
                   'VETEMENTS', 'CHAUSSURES', 'ELECTROMENAGER', 'MEUBLES', 'INFORMATIQUE_MULTIMEDIA',
                   'PRODUITS_ENTRETIEN_MENAGER', 'PRODUITS_HYGIENE_BEAUTE', 'JOUETS', 'FOURNITURES_SCOLAIRES')
  AND p.code = 'TVA_NORMAL';

-- =========================================================================
-- Fin du mapping produits par catégories
-- =========================================================================
