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

-- Sous-catégories fines ajoutées le 2026-08-02 (PROJECT_STATE.md section
-- 7.10) pour permettre le calcul de l'éco-participation DEEE (voir
-- ECO_PART_* dans seed_data/fr_seed_lot3.sql), qui varie fortement par
-- type d'équipement précis (jusqu'à x30 entre un réfrigérateur et une
-- bouilloire) — un mapping au niveau "ELECTROMENAGER"/"INFORMATIQUE_MULTIMEDIA"
-- seul ne le permettrait pas. Sous-ensemble REPRÉSENTATIF (17 catégories)
-- des 8 familles du barème officiel Ecologic 2026, PAS une couverture
-- exhaustive des ~150 lignes du barème réel — voir PROJECT_STATE.md
-- section 7.8 pour le détail de ce qui est/n'est pas couvert. Les
-- catégories ELECTROMENAGER/INFORMATIQUE_MULTIMEDIA ci-dessus restent le
-- filet de sécurité (TVA seule) pour tout ce qui n'entre pas dans ces
-- sous-catégories.
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_REFRIGERATEUR_CONGELATEUR', 'Réfrigérateur, congélateur ou cave à vin', 'Refrigerator, freezer or wine cabinet', 'Frigorífico, congelador o vinoteca', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_LAVE_LINGE', 'Lave-linge ou lave-linge séchant', 'Washing machine or washer-dryer', 'Lavadora o lavadora-secadora', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_SECHE_LINGE', 'Sèche-linge', 'Tumble dryer', 'Secadora', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_LAVE_VAISSELLE', 'Lave-vaisselle', 'Dishwasher', 'Lavavajillas', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_CUISINIERE', 'Cuisinière', 'Cooker/range', 'Cocina', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_FOUR_MICRO_ONDES', 'Four micro-ondes', 'Microwave oven', 'Horno microondas', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_ASPIRATEUR', 'Aspirateur', 'Vacuum cleaner', 'Aspiradora', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_BOUILLOIRE', 'Bouilloire', 'Kettle', 'Hervidor', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_CAFETIERE', 'Cafetière (avec filtre)', 'Filter coffee maker', 'Cafetera de filtro', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_FER_A_REPASSER', 'Fer à repasser', 'Iron', 'Plancha', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'ELECTROMENAGER_SOIN_PERSONNEL', 'Équipement de soin personnel (sèche-cheveux, rasoir, tondeuse, lisseur...)', 'Personal care appliance (hairdryer, shaver, trimmer, straightener...)', 'Aparato de cuidado personal (secador, afeitadora, cortapelo, plancha de pelo...)', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'EGP_TELEVISEUR', 'Téléviseur', 'Television set', 'Televisor', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_SMARTPHONE', 'Téléphone portable (smartphone)', 'Mobile phone (smartphone)', 'Teléfono móvil (smartphone)', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_ORDINATEUR_PORTABLE', 'Ordinateur portable', 'Laptop computer', 'Ordenador portátil', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_ORDINATEUR_FIXE', 'Ordinateur fixe', 'Desktop computer', 'Ordenador de sobremesa', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_TABLETTE', 'Tablette', 'Tablet', 'Tableta', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';
INSERT INTO categorie_produit (code, libelle_fr, libelle_en, libelle_es, type_depense_id)
SELECT 'INFORMATIQUE_IMPRIMANTE', 'Imprimante ou multifonction', 'Printer or multifunction device', 'Impresora o multifunción', id FROM type_depense WHERE code = 'EQUIPEMENT_MAISON';

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
                   'PRODUITS_ENTRETIEN_MENAGER', 'PRODUITS_HYGIENE_BEAUTE', 'JOUETS', 'FOURNITURES_SCOLAIRES',
                   'ELECTROMENAGER_REFRIGERATEUR_CONGELATEUR', 'ELECTROMENAGER_LAVE_LINGE',
                   'ELECTROMENAGER_SECHE_LINGE', 'ELECTROMENAGER_LAVE_VAISSELLE', 'ELECTROMENAGER_CUISINIERE',
                   'ELECTROMENAGER_FOUR_MICRO_ONDES', 'ELECTROMENAGER_ASPIRATEUR', 'ELECTROMENAGER_BOUILLOIRE',
                   'ELECTROMENAGER_CAFETIERE', 'ELECTROMENAGER_FER_A_REPASSER', 'ELECTROMENAGER_SOIN_PERSONNEL',
                   'EGP_TELEVISEUR', 'INFORMATIQUE_SMARTPHONE', 'INFORMATIQUE_ORDINATEUR_PORTABLE',
                   'INFORMATIQUE_ORDINATEUR_FIXE', 'INFORMATIQUE_TABLETTE', 'INFORMATIQUE_IMPRIMANTE')
  AND p.code = 'TVA_NORMAL';

-- Rattachement des 17 catégories d'électroménager/informatique fines à
-- leur éco-participation DEEE spécifique (1:1, voir seed_data/fr_seed_lot3.sql
-- pour la définition des ECO_PART_*) — ajouté le 2026-08-02
-- (PROJECT_STATE.md sections 7.8/7.10).
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_REFRIGERATEUR_CONGELATEUR' AND p.code = 'ECO_PART_REFRIGERATEUR_CONGELATEUR';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_LAVE_LINGE' AND p.code = 'ECO_PART_LAVE_LINGE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_SECHE_LINGE' AND p.code = 'ECO_PART_SECHE_LINGE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_LAVE_VAISSELLE' AND p.code = 'ECO_PART_LAVE_VAISSELLE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_CUISINIERE' AND p.code = 'ECO_PART_CUISINIERE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_FOUR_MICRO_ONDES' AND p.code = 'ECO_PART_FOUR_MICRO_ONDES';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_ASPIRATEUR' AND p.code = 'ECO_PART_ASPIRATEUR';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_BOUILLOIRE' AND p.code = 'ECO_PART_BOUILLOIRE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_CAFETIERE' AND p.code = 'ECO_PART_CAFETIERE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_FER_A_REPASSER' AND p.code = 'ECO_PART_FER_A_REPASSER';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'ELECTROMENAGER_SOIN_PERSONNEL' AND p.code = 'ECO_PART_SOIN_PERSONNEL';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'EGP_TELEVISEUR' AND p.code = 'ECO_PART_TELEVISEUR';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'INFORMATIQUE_SMARTPHONE' AND p.code = 'ECO_PART_SMARTPHONE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'INFORMATIQUE_ORDINATEUR_PORTABLE' AND p.code = 'ECO_PART_ORDINATEUR_PORTABLE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'INFORMATIQUE_ORDINATEUR_FIXE' AND p.code = 'ECO_PART_ORDINATEUR_FIXE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'INFORMATIQUE_TABLETTE' AND p.code = 'ECO_PART_TABLETTE';
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p WHERE cp.code = 'INFORMATIQUE_IMPRIMANTE' AND p.code = 'ECO_PART_IMPRIMANTE';

-- Rattachement des 2 taxes soda (voir seed_data/fr_seed_lot3.sql pour leur
-- définition) à BOISSONS_SUCREES — AJOUTÉ le 2026-07-29, fiabilisation
-- section 7.5 de PROJECT_STATE.md. Ce rattachement était volontairement
-- absent jusqu'ici car ces 2 taxes sont de type 'montant_par_unite_a_seuil'
-- : leur calcul a besoin d'une donnée PAR PRODUIT (teneur en sucre ou en
-- édulcorant), pas seulement de la catégorie. fiscal_engine/orchestrator.py
-- sait désormais résoudre cette donnée depuis produit_reference (via
-- ligne_document.produit_reference_id) quand elle est disponible :
--   - TAXE_BOISSONS_SUCRE : calculée automatiquement SI la ligne est liée à
--     un produit_reference avec teneur_sucre_100g renseigné (typiquement
--     via l'import Open Food Facts). Sinon, ce prélèvement précis est
--     silencieusement absent du résultat pour cette ligne (pas d'erreur,
--     pas de montant inventé) — les autres prélèvements de la ligne (TVA)
--     sont calculés normalement.
--   - TAXE_BOISSONS_EDULCORANT : rattachée ici pour la cohérence
--     architecturale et pour être prête si une source de données fournit un
--     jour la concentration en mg/L, MAIS N'EST JAMAIS CALCULÉE
--     AUTOMATIQUEMENT aujourd'hui : OFF ne fournit que la PRÉSENCE d'un
--     édulcorant (contient_edulcorants), pas sa concentration, qui est
--     pourtant nécessaire pour choisir la bonne tranche du barème (seuil à
--     120mg/L). Voir fiscal_engine/orchestrator.py::_resoudre_valeur_seuil_produit.
INSERT INTO categorie_prelevement (categorie_produit_id, prelevement_id)
SELECT cp.id, p.id FROM categorie_produit cp, prelevement p
WHERE cp.code = 'BOISSONS_SUCREES' AND p.code IN ('TAXE_BOISSONS_SUCRE', 'TAXE_BOISSONS_EDULCORANT');

-- =========================================================================
-- Fin du mapping produits par catégories
-- =========================================================================
