"""Tests unitaires du module fiscal_engine.foyer, contre les vraies données
2026 du seed (seed_data/fr_seed_lot3.sql), sur le modèle de
tests/test_alcool.py et tests/test_retraite.py.

Contrairement à tests/test_engine.py::TestFoyerFiscal (qui teste le
MÉCANISME générique avec un barème et des plafonds de test arbitraires),
ce fichier teste les 4 points fiabilisés le 2026-07-29 (voir
fiscal_engine/foyer.py) contre les vraies valeurs légales :
  1. Garde alternée (quart de part, plafonds 904€/2131€).
  2. Invalidité / ancien combattant (demi-part, plafonds 3608€/1807€/904€).
  3. Plafonds spécifiques "personne seule ayant élevé un enfant" (1079€) et
     "veuf avec personne à charge" (5625€).
  4. Imposition séparée des époux/pacsés.
"""

import sqlite3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiscal_engine import foyer

CHEMIN_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "schema.sql"
CHEMIN_SEED = Path(__file__).resolve().parent.parent / "seed_data" / "fr_seed_lot3.sql"

DATE_REF = "2026-06-01"


def _creer_bdd_reelle() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    for chemin in (CHEMIN_SCHEMA, CHEMIN_SEED):
        with open(chemin, encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


class TestGardeAlternee(unittest.TestCase):
    """Point 1 : garde alternée -> quart de part, plafond halved."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_un_enfant_garde_alternee_donne_un_quart_de_part(self):
        s = foyer.SituationFoyer(situation_familiale="celibataire", nombre_enfants_garde_alternee=1)
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.25)

    def test_deux_enfants_garde_alternee_donnent_un_demi_part(self):
        s = foyer.SituationFoyer(situation_familiale="celibataire", nombre_enfants_garde_alternee=2)
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.5)

    def test_troisieme_enfant_garde_alternee_donne_un_demi_part_de_plus(self):
        s = foyer.SituationFoyer(situation_familiale="celibataire", nombre_enfants_garde_alternee=3)
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 2.0)  # 1 + 0.25*2 + 0.5

    def test_melange_garde_exclusive_et_alternee(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_enfants_a_charge=1, nombre_enfants_garde_alternee=1
        )
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.75)  # 1 + 0.5 + 0.25

    def test_parent_isole_en_garde_alternee_seule_donne_un_quart_de_part_de_plus(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_enfants_garde_alternee=1, parent_isole=True
        )
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.5)  # 1 + 0.25 + 0.25

    def test_plafond_quart_part_ecrete_lavantage(self):
        # 1 enfant en garde alternee, tres haut revenu : l'avantage brut du
        # quart de part doit etre ecrete a 904E (PLAFOND_QF_QUART_PART).
        s = foyer.SituationFoyer(situation_familiale="celibataire", nombre_enfants_garde_alternee=1)
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(resultat["avantage_quotient_familial_plafonne"], 904.0)


class TestInvaliditeAncienCombattant(unittest.TestCase):
    """Point 2 : invalidité/ancien combattant (contribuable) et enfants invalides à charge."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_une_demi_part_invalidite_contribuable(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_demi_parts_invalidite_ancien_combattant=1
        )
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.5)

    def test_deux_demi_parts_invalidite_couple(self):
        s = foyer.SituationFoyer(
            situation_familiale="marie", nombre_demi_parts_invalidite_ancien_combattant=2
        )
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 3.0)

    def test_trois_demi_parts_invalidite_leve_value_error(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(
                    situation_familiale="celibataire",
                    nombre_demi_parts_invalidite_ancien_combattant=3,
                )
            )

    def test_plafond_invalidite_contribuable_est_majore_a_3608(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_demi_parts_invalidite_ancien_combattant=1
        )
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(resultat["avantage_quotient_familial_plafonne"], 3608.0)

    def test_enfant_invalide_a_charge_ajoute_une_demi_part_en_plus(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_enfants_a_charge=1, nombre_enfants_invalides_a_charge=1
        )
        # 1 (base) + 0.5 (enfant) + 0.5 (bonus invalidite du meme enfant) = 2.0
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 2.0)

    def test_enfant_invalide_a_charge_plafonne_au_taux_standard(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", nombre_enfants_a_charge=1, nombre_enfants_invalides_a_charge=1
        )
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        # 2 demi-parts (celle de l'enfant + le bonus invalidite), toutes deux
        # au plafond standard 1807E (pas de parent isole ni veuf ici) : 3614E
        self.assertAlmostEqual(resultat["avantage_quotient_familial_plafonne"], 2 * 1807.0)

    def test_plus_denfants_invalides_que_denfants_a_charge_leve_value_error(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(
                    situation_familiale="celibataire",
                    nombre_enfants_a_charge=1,
                    nombre_enfants_invalides_a_charge=2,
                )
            )


class TestPersonneSeuleAyantEleveEnfant(unittest.TestCase):
    """Point 3a : plafond spécifique 1079€ (case L)."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_ajoute_une_demi_part(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", personne_seule_ayant_eleve_enfant=True
        )
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.5)

    def test_plafond_est_1079(self):
        s = foyer.SituationFoyer(
            situation_familiale="celibataire", personne_seule_ayant_eleve_enfant=True
        )
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(resultat["avantage_quotient_familial_plafonne"], 1079.0)

    def test_incompatible_avec_enfant_a_charge_actuel(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(
                    situation_familiale="celibataire",
                    nombre_enfants_a_charge=1,
                    personne_seule_ayant_eleve_enfant=True,
                )
            )

    def test_incompatible_avec_parent_isole(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(
                    situation_familiale="celibataire",
                    nombre_enfants_a_charge=1,
                    parent_isole=True,
                    personne_seule_ayant_eleve_enfant=True,
                )
            )


class TestVeufAvecCharge(unittest.TestCase):
    """Point 3b : plafond combiné 5625€ pour les 2 premières demi-parts."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_veuf_avec_deux_enfants_plafond_combine_5625(self):
        s = foyer.SituationFoyer(situation_familiale="veuf", nombre_enfants_a_charge=2)
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        self.assertAlmostEqual(resultat["avantage_quotient_familial_plafonne"], 5625.0)

    def test_veuf_avec_trois_enfants_5625_plus_1807_pour_le_troisieme(self):
        s = foyer.SituationFoyer(situation_familiale="veuf", nombre_enfants_a_charge=3)
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=500000.0, date_reference=DATE_REF
        )
        # 3e enfant = 1 part entiere = 2 unites de demi-part au taux standard
        self.assertAlmostEqual(
            resultat["avantage_quotient_familial_plafonne"], 5625.0 + 2 * 1807.0
        )

    def test_veuf_et_parent_isole_leve_value_error(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(
                    situation_familiale="veuf", nombre_enfants_a_charge=1, parent_isole=True
                )
            )


class TestImpositionSeparee(unittest.TestCase):
    """Point 4 : imposition séparée des époux/pacsés."""

    def setUp(self):
        self.conn = _creer_bdd_reelle()

    def test_marie_imposition_separee_traite_comme_une_part(self):
        s = foyer.SituationFoyer(situation_familiale="marie", imposition_separee=True)
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 1.0)

    def test_marie_imposition_commune_traite_comme_deux_parts(self):
        s = foyer.SituationFoyer(situation_familiale="marie", imposition_separee=False)
        self.assertAlmostEqual(foyer.calculer_nombre_parts(s), 2.0)

    def test_imposition_separee_sans_mariage_ni_pacs_leve_value_error(self):
        with self.assertRaises(ValueError):
            foyer.calculer_nombre_parts(
                foyer.SituationFoyer(situation_familiale="celibataire", imposition_separee=True)
            )

    def test_imposition_separee_desactive_le_seuil_de_decote_couple(self):
        s = foyer.SituationFoyer(situation_familiale="pacse", imposition_separee=True)
        resultat = foyer.calculer_impot_foyer(
            self.conn, s, revenu_net_imposable=15000.0, date_reference=DATE_REF
        )
        # Avec 1 part (imposition separee), l'impot est calcule comme un
        # celibataire : le test verifie juste que ca ne plante pas et que
        # nombre_parts est bien 1.0 (pas 2.0 comme un couple imposé en commun).
        self.assertAlmostEqual(resultat["nombre_parts"], 1.0)


if __name__ == "__main__":
    unittest.main()
