-- =========================================================================
-- Fiscal Tracker — Schéma de base de données (SQLite)
-- Lot 1 — voir docs/architecture.md pour le détail des choix de conception
-- =========================================================================
-- Conventions :
--   - Toutes les dates sont stockées au format ISO 8601 'YYYY-MM-DD' (TEXT)
--   - Les libellés multilingues : colonnes libelle_fr / libelle_en / libelle_es
--   - Les tables portant des règles versionnées ne sont JAMAIS mises à jour
--     en place : on clôt une règle (date_fin) et on en insère une nouvelle.
-- =========================================================================

PRAGMA foreign_keys = ON;

-- -------------------------------------------------------------------------
-- 1. Modules pays — point d'entrée de l'extensibilité géographique
-- -------------------------------------------------------------------------
CREATE TABLE pays (
    code            TEXT PRIMARY KEY,       -- 'FR', 'ES', 'EN'...
    nom             TEXT NOT NULL,
    actif           INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0,1))
);

-- -------------------------------------------------------------------------
-- 2. Typologie des prélèvements (axe de ventilation n°1)
--    Ex : TVA, cotisations sociales, impôt sur le revenu, taxes écologiques
-- -------------------------------------------------------------------------
CREATE TABLE typologie_prelevement (
    id              INTEGER PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,   -- 'TVA', 'COTIS_SOC', 'IMPOT_REVENU', ...
    libelle_fr      TEXT NOT NULL,
    libelle_en      TEXT,
    libelle_es      TEXT
);

-- -------------------------------------------------------------------------
-- 3. Type de dépense (axe de ventilation n°2), hiérarchique
--    Ex : Alimentation > Boissons sucrées ; Salaire ; Énergie ; Logement
-- -------------------------------------------------------------------------
CREATE TABLE type_depense (
    id              INTEGER PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    libelle_fr      TEXT NOT NULL,
    libelle_en      TEXT,
    libelle_es      TEXT,
    parent_id       INTEGER REFERENCES type_depense(id)
);

-- -------------------------------------------------------------------------
-- 4. Prélèvement concret, nommé, rattaché à un pays et une typologie
--    Ex : "TVA taux normal", "TICPE essence", "CSG déductible salaire"
-- -------------------------------------------------------------------------
CREATE TABLE prelevement (
    id                  INTEGER PRIMARY KEY,
    pays_code           TEXT NOT NULL REFERENCES pays(code),
    typologie_id        INTEGER NOT NULL REFERENCES typologie_prelevement(id),
    code                TEXT NOT NULL,          -- unique au sein d'un pays
    libelle_fr          TEXT NOT NULL,
    libelle_en          TEXT,
    libelle_es          TEXT,
    base_calcul_desc    TEXT,                   -- description libre : "TTC", "brut mensuel", ...
    reference_legale    TEXT,                   -- article de loi / BOFiP — traçabilité obligatoire
    UNIQUE (pays_code, code)
);

CREATE INDEX idx_prelevement_pays ON prelevement(pays_code);
CREATE INDEX idx_prelevement_typologie ON prelevement(typologie_id);

-- -------------------------------------------------------------------------
-- 5. Règles de calcul, VERSIONNÉES DANS LE TEMPS
--    Une ligne = une version d'un taux/barème, valable sur une période donnée
-- -------------------------------------------------------------------------
CREATE TABLE regle_prelevement (
    id                  INTEGER PRIMARY KEY,
    prelevement_id      INTEGER NOT NULL REFERENCES prelevement(id),
    date_debut          TEXT NOT NULL,          -- date d'entrée en vigueur (incluse)
    date_fin            TEXT,                   -- date de fin (incluse) ; NULL = toujours en vigueur
    type_regle          TEXT NOT NULL CHECK (type_regle IN
                            ('taux_fixe', 'montant_fixe', 'bareme_progressif', 'formule')),
    taux                REAL,                   -- pour type_regle = 'taux_fixe' (ex : 0.20 pour 20%)
    montant_fixe        REAL,                   -- pour type_regle = 'montant_fixe'
    formule             TEXT,                   -- pour type_regle = 'formule' (interprétée par le moteur applicatif)
    source_reference    TEXT NOT NULL,          -- lien ou référence légale précise de CETTE version du taux
    commentaire         TEXT,

    -- Un même prélèvement ne doit jamais avoir deux règles avec des périodes
    -- qui se chevauchent : ce contrôle sera fait côté applicatif à l'insertion
    -- (SQLite ne permet pas nativement une contrainte d'exclusion de plage).
    CHECK (date_fin IS NULL OR date_fin >= date_debut)
);

CREATE INDEX idx_regle_prelevement_prelevement ON regle_prelevement(prelevement_id);
CREATE INDEX idx_regle_prelevement_dates ON regle_prelevement(date_debut, date_fin);

-- -------------------------------------------------------------------------
-- 6. Tranches de barème progressif (ex : barème IR)
-- -------------------------------------------------------------------------
CREATE TABLE tranche_bareme (
    id              INTEGER PRIMARY KEY,
    regle_id        INTEGER NOT NULL REFERENCES regle_prelevement(id),
    borne_min       REAL NOT NULL,
    borne_max       REAL,                       -- NULL = pas de plafond (dernière tranche)
    taux            REAL NOT NULL,
    UNIQUE (regle_id, borne_min)
);

CREATE INDEX idx_tranche_bareme_regle ON tranche_bareme(regle_id);

-- -------------------------------------------------------------------------
-- 7. Catégorie produit — taxonomie FISCALE simplifiée (pas nutritionnelle)
--    Hiérarchique, reliée à un type_depense pour la ventilation
-- -------------------------------------------------------------------------
CREATE TABLE categorie_produit (
    id                  INTEGER PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    libelle_fr          TEXT NOT NULL,
    libelle_en          TEXT,
    libelle_es          TEXT,
    parent_id           INTEGER REFERENCES categorie_produit(id),
    type_depense_id     INTEGER REFERENCES type_depense(id)
);

CREATE INDEX idx_categorie_produit_parent ON categorie_produit(parent_id);
CREATE INDEX idx_categorie_produit_type_depense ON categorie_produit(type_depense_id);

-- -------------------------------------------------------------------------
-- 8. Mapping catégorie produit <-> prélèvements applicables
--    (une catégorie peut avoir plusieurs prélèvements : ex carburant = TVA + TICPE)
-- -------------------------------------------------------------------------
CREATE TABLE categorie_prelevement (
    id                      INTEGER PRIMARY KEY,
    categorie_produit_id    INTEGER NOT NULL REFERENCES categorie_produit(id),
    prelevement_id          INTEGER NOT NULL REFERENCES prelevement(id),
    UNIQUE (categorie_produit_id, prelevement_id)
);

CREATE INDEX idx_categorie_prelevement_categorie ON categorie_prelevement(categorie_produit_id);
CREATE INDEX idx_categorie_prelevement_prelevement ON categorie_prelevement(prelevement_id);

-- -------------------------------------------------------------------------
-- 9. Cache local des produits référencés (Open Food Facts / Open Products Facts)
--    Alimenté par import batch (dump téléchargé), jamais par appel réseau live
-- -------------------------------------------------------------------------
CREATE TABLE produit_reference (
    id                      INTEGER PRIMARY KEY,
    code_barre              TEXT UNIQUE,
    nom                     TEXT,
    source                  TEXT CHECK (source IN ('OFF', 'OPF', 'manuel')),
    categorie_produit_id    INTEGER REFERENCES categorie_produit(id)
);

CREATE INDEX idx_produit_reference_categorie ON produit_reference(categorie_produit_id);

-- -------------------------------------------------------------------------
-- 10. Document importé (ticket de caisse, facture, fiche de paie, avis d'imposition)
-- -------------------------------------------------------------------------
CREATE TABLE document (
    id                  INTEGER PRIMARY KEY,
    type_document       TEXT NOT NULL CHECK (type_document IN
                            ('ticket_caisse', 'facture', 'fiche_paie', 'avis_imposition', 'autre')),
    date_document       TEXT,                   -- date du document lui-même (pas de l'import)
    fichier_source      TEXT,                   -- chemin local du scan/photo d'origine
    texte_ocr_brut      TEXT,                   -- sortie OCR complète, conservée pour audit/correction
    statut              TEXT NOT NULL DEFAULT 'a_valider' CHECK (statut IN
                            ('a_valider', 'valide', 'erreur')),
    date_import         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_document_type ON document(type_document);
CREATE INDEX idx_document_date ON document(date_document);

-- -------------------------------------------------------------------------
-- 11. Ligne de document (article de ticket, ligne de facture, ligne de paie...)
-- -------------------------------------------------------------------------
CREATE TABLE ligne_document (
    id                      INTEGER PRIMARY KEY,
    document_id             INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    libelle_brut             TEXT NOT NULL,      -- texte OCR brut de la ligne, non modifié
    montant                 REAL NOT NULL,       -- montant de la ligne (TTC pour achat, montant pour cotisation)
    quantite                REAL NOT NULL DEFAULT 1,
    categorie_produit_id     INTEGER REFERENCES categorie_produit(id),   -- pour les achats
    prelevement_id           INTEGER REFERENCES prelevement(id),         -- si déjà nommé explicitement (ex : fiche de paie)
    produit_reference_id     INTEGER REFERENCES produit_reference(id)    -- si identifié via code-barres / OFF
);

CREATE INDEX idx_ligne_document_document ON ligne_document(document_id);
CREATE INDEX idx_ligne_document_categorie ON ligne_document(categorie_produit_id);

-- -------------------------------------------------------------------------
-- 12. Résultat du calcul : prélèvement(s) calculé(s) pour une ligne donnée
--     C'est cette table qui alimente les totaux et ventilations finales.
-- -------------------------------------------------------------------------
CREATE TABLE prelevement_calcule (
    id                  INTEGER PRIMARY KEY,
    ligne_document_id    INTEGER NOT NULL REFERENCES ligne_document(id) ON DELETE CASCADE,
    prelevement_id       INTEGER NOT NULL REFERENCES prelevement(id),
    regle_id             INTEGER REFERENCES regle_prelevement(id),  -- règle exacte appliquée (traçabilité)
    montant_calcule      REAL NOT NULL,
    base_calcul          REAL,                  -- montant sur lequel le taux a été appliqué
    taux_applique        REAL
);

CREATE INDEX idx_prelevement_calcule_ligne ON prelevement_calcule(ligne_document_id);
CREATE INDEX idx_prelevement_calcule_prelevement ON prelevement_calcule(prelevement_id);

-- =========================================================================
-- Fin du schéma — Lot 1
-- Prochaine étape (Lot 2) : moteur applicatif Python interrogeant ce schéma
-- =========================================================================
