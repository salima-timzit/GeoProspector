import io
import json
from unittest.mock import patch
from urllib.error import URLError

from rest_framework.test import APITestCase

from .geocodage import departement
from .models import Dept, Region


def reponse_ign(features):
    return io.BytesIO(json.dumps({"type": "FeatureCollection", "features": features}).encode())


def feature(label, lon, lat, context, citycode):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"label": label, "context": context, "citycode": citycode, "score": 0.97},
    }


class GeocodageTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id_region="27", libelle="Bourgogne-Franche-Comté")
        Dept.objects.create(id_dept="21", region_id="27", libelle="Côte-d'Or")

    @patch("bpe.geocodage.urlopen")
    def test_adresse_dans_la_zone(self, urlopen):
        urlopen.return_value.__enter__.return_value = reponse_ign([
            feature("1 Rue de la Liberté 21000 Dijon", 5.0386, 47.3217, "21, Côte-d'Or, Bourgogne-Franche-Comté", "21231")
        ])
        r = self.client.get("/api/geocodage/", {"q": "1 rue de la liberté dijon"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["dans_zone"])
        self.assertIsNone(data["message"])
        self.assertEqual((data["lon"], data["lat"], data["dept"]), (5.0386, 47.3217, "21"))

    @patch("bpe.geocodage.urlopen")
    def test_adresse_hors_zone(self, urlopen):
        urlopen.return_value.__enter__.return_value = reponse_ign([
            feature("10 Rue de Rivoli 75004 Paris", 2.3561, 48.8555, "75, Paris, Île-de-France", "75104")
        ])
        data = self.client.get("/api/geocodage/", {"q": "10 rue de rivoli paris"}).json()
        self.assertFalse(data["dans_zone"])
        self.assertIn("hors zone", data["message"])
        self.assertIn("Bourgogne-Franche-Comté", data["message"])

    @patch("bpe.geocodage.urlopen")
    def test_adresse_introuvable(self, urlopen):
        urlopen.return_value.__enter__.return_value = reponse_ign([])
        self.assertEqual(self.client.get("/api/geocodage/", {"q": "zzzzzz"}).status_code, 404)

    @patch("bpe.geocodage.urlopen", side_effect=URLError("timeout"))
    def test_service_indisponible(self, _):
        self.assertEqual(self.client.get("/api/geocodage/", {"q": "1 rue x dijon"}).status_code, 502)

    def test_requete_trop_courte(self):
        self.assertEqual(self.client.get("/api/geocodage/", {"q": "a"}).status_code, 400)

    def test_departement_sans_context(self):
        self.assertEqual(departement({"citycode": "21231"}), "21")
        self.assertEqual(departement({"citycode": "97411"}), "974")
        self.assertEqual(departement({"context": "2A, Corse-du-Sud, Corse"}), "2A")


class RechercheEquipementsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        import uuid  # noqa: F401
        from django.contrib.gis.geos import Point

        from .models import Bpe, Domaine1, Domaine2, Domaine3

        Region.objects.create(id_region="27", libelle="Bourgogne-Franche-Comté")
        d21 = Dept.objects.create(id_dept="21", region_id="27", libelle="Côte-d'Or")
        Domaine1.objects.create(code="B", libelle="Commerces")
        Domaine2.objects.create(code="B2", domaine1_id="B", libelle="Alimentaire")
        Domaine3.objects.create(code="B207", domaine2_id="B2", libelle="Boulangerie")
        for nom, ville, geom in [
            ("Boulangerie Pâtisserie du Centre", "Dijon", Point(5.04, 47.32, srid=4326)),
            ("BOULANGERIE MARTIN", "Beaune", Point(4.84, 47.02, srid=4326)),
            ("Boulangerie sans coordonnées", "Dijon", None),
            ("Boucherie", "Dijon", Point(5.05, 47.33, srid=4326)),
        ]:
            Bpe.objects.create(nom=nom, domaine3_id="B207", ville=ville, codepostal="21000", dept=d21, geom=geom)

    def test_recherche_insensible_casse_et_accents(self):
        data = self.client.get("/api/equipements/recherche/", {"q": "patisserie"}).json()
        self.assertEqual([d["nom"] for d in data], ["Boulangerie Pâtisserie du Centre"])
        self.assertEqual((data[0]["lon"], data[0]["lat"]), (5.04, 47.32))

    def test_recherche_exclut_sans_coordonnees(self):
        noms = {d["nom"] for d in self.client.get("/api/equipements/recherche/", {"q": "boulangerie"}).json()}
        self.assertEqual(noms, {"Boulangerie Pâtisserie du Centre", "BOULANGERIE MARTIN"})

    def test_recherche_filtre_ville(self):
        data = self.client.get("/api/equipements/recherche/", {"q": "boulangerie", "ville": "Beaune"}).json()
        self.assertEqual([d["nom"] for d in data], ["BOULANGERIE MARTIN"])

    def test_recherche_trop_courte(self):
        self.assertEqual(self.client.get("/api/equipements/recherche/", {"q": "bo"}).status_code, 400)
