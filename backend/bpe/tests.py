import uuid

from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from .models import Bpe, Dept, Domaine1, Domaine2, Domaine3, Region


class CarteApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id_region="27", libelle="Bourgogne-Franche-Comté")
        cls.d21 = Dept.objects.create(id_dept="21", region_id="27", libelle="Côte-d'Or")
        cls.d25 = Dept.objects.create(id_dept="25", region_id="27", libelle="Doubs")
        Domaine1.objects.create(code="A", libelle="Services")
        Domaine1.objects.create(code="B", libelle="Commerces")
        Domaine2.objects.create(code="A1", domaine1_id="A", libelle="Services publics")
        Domaine2.objects.create(code="B2", domaine1_id="B", libelle="Alimentaire")
        Domaine3.objects.create(code="A101", domaine2_id="A1", libelle="Police")
        Domaine3.objects.create(code="B207", domaine2_id="B2", libelle="Boulangerie")
        Domaine3.objects.create(code="B208", domaine2_id="B2", libelle="Boucherie")

        def bpe(nom, d3, ville, cp, dept, lon=None, lat=None):
            return Bpe.objects.create(
                nom=nom, domaine3_id=d3, ville=ville, codepostal=cp, dept=dept,
                geom=Point(lon, lat, srid=4326) if lon is not None else None,
            )

        cls.police_dijon = bpe("Commissariat", "A101", "Dijon", "21000", cls.d21, 5.04, 47.32)
        cls.boul_dijon = bpe("Boulangerie Dijon", "B207", "Dijon", "21000", cls.d21, 5.05, 47.33)
        cls.bouch_beaune = bpe("Boucherie Beaune", "B208", "Beaune", "21200", cls.d21, 4.84, 47.02)
        cls.boul_besancon = bpe("Boulangerie Besançon", "B207", "Besançon", "25000", cls.d25, 6.02, 47.24)
        cls.sans_geom = bpe("Sans coordonnées", "B207", "Dijon", "21000", cls.d21)

    def ids(self, resp):
        return {f["properties"]["id"] for f in resp.json()["features"]}

    # --- /api/domaines/ ---------------------------------------------------
    def test_domaines_arbre(self):
        data = self.client.get("/api/domaines/").json()
        self.assertEqual([d["code"] for d in data], ["A", "B"])
        b = data[1]
        self.assertEqual(b["enfants"][0]["code"], "B2")
        self.assertEqual([d["code"] for d in b["enfants"][0]["enfants"]], ["B207", "B208"])

    # --- /api/villes/ -----------------------------------------------------
    def test_villes_liste_distincte(self):
        data = self.client.get("/api/villes/").json()
        self.assertEqual([v["nom"] for v in data], ["Beaune", "Besançon", "Dijon"])
        self.assertEqual(data[2], {"nom": "Dijon", "codepostal": "21000", "id_dept": "21"})

    def test_villes_search_insensible_casse(self):
        data = self.client.get("/api/villes/", {"search": "dij"}).json()
        self.assertEqual([v["nom"] for v in data], ["Dijon"])
        self.assertEqual(self.client.get("/api/villes/", {"search": "zzz"}).json(), [])

    # --- /api/equipements/ ------------------------------------------------
    def test_bbox_obligatoire(self):
        resp = self.client.get("/api/equipements/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())

    def test_bbox_filtre_geojson(self):
        resp = self.client.get("/api/equipements/", {"bbox": "5.0,47.3,5.1,47.4"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(self.ids(resp), {str(self.police_dijon.id), str(self.boul_dijon.id)})
        f = next(f for f in data["features"] if f["properties"]["id"] == str(self.boul_dijon.id))
        self.assertEqual(f["geometry"], {"type": "Point", "coordinates": [5.05, 47.33]})
        self.assertEqual(f["properties"]["domaine3_code"], "B207")
        self.assertEqual(f["properties"]["domaine1_code"], "B")

    def test_bbox_ordre_lon_lat(self):
        # bbox inversée (lat,lon) -> zone vide en Afrique de l'Est : aucun résultat
        resp = self.client.get("/api/equipements/", {"bbox": "47.3,5.0,47.4,5.1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["features"], [])

    def test_bbox_invalide(self):
        for bbox in ["abc", "1,2,3", "1,2,3,4,5", "5.1,47.3,5.0,47.4", "5,47,200,48", "5,a,6,48"]:
            with self.subTest(bbox=bbox):
                self.assertEqual(self.client.get("/api/equipements/", {"bbox": bbox}).status_code, 400)

    def test_filtre_domaines_trois_niveaux(self):
        bbox = "4,46,7,48"
        cas = {
            "A": {self.police_dijon},
            "B2": {self.boul_dijon, self.bouch_beaune, self.boul_besancon},
            "B207": {self.boul_dijon, self.boul_besancon},
            "A101,B208": {self.police_dijon, self.bouch_beaune},
            "b207": {self.boul_dijon, self.boul_besancon},
        }
        for domaines, attendus in cas.items():
            with self.subTest(domaines=domaines):
                resp = self.client.get("/api/equipements/", {"bbox": bbox, "domaines": domaines})
                self.assertEqual(self.ids(resp), {str(e.id) for e in attendus})

    def test_domaine_invalide(self):
        resp = self.client.get("/api/equipements/", {"bbox": "4,46,7,48", "domaines": "ABC"})
        self.assertEqual(resp.status_code, 400)

    def test_filtre_villes_sans_bbox(self):
        resp = self.client.get("/api/equipements/", {"villes": "Dijon,Beaune"})
        self.assertEqual(resp.status_code, 200)
        # l'équipement sans coordonnées est exclu
        self.assertEqual(self.ids(resp), {str(self.police_dijon.id), str(self.boul_dijon.id), str(self.bouch_beaune.id)})

    def test_filtres_combines(self):
        resp = self.client.get("/api/equipements/", {"bbox": "4,46,7,48", "villes": "Dijon", "domaines": "B"})
        self.assertEqual(self.ids(resp), {str(self.boul_dijon.id)})

    def test_token_invalide_ignore_sur_routes_publiques(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expire")
        self.assertEqual(self.client.get("/api/equipements/", {"bbox": "4,46,7,48"}).status_code, 200)

    # --- /api/equipements/<id>/ -------------------------------------------
    def test_fiche_equipement(self):
        data = self.client.get(f"/api/equipements/{self.boul_dijon.id}/").json()
        self.assertEqual(data["nom"], "Boulangerie Dijon")
        self.assertEqual(data["dept"], {"id_dept": "21", "libelle": "Côte-d'Or"})
        self.assertEqual(data["domaine1"]["code"], "B")
        self.assertEqual(data["domaine2"]["code"], "B2")
        self.assertEqual(data["domaine3"], {"code": "B207", "libelle": "Boulangerie"})
        self.assertEqual((data["lon"], data["lat"]), (5.05, 47.33))

    def test_fiche_sans_geom(self):
        data = self.client.get(f"/api/equipements/{self.sans_geom.id}/").json()
        self.assertIsNone(data["lon"])

    def test_fiche_inexistante(self):
        self.assertEqual(self.client.get(f"/api/equipements/{uuid.uuid4()}/").status_code, 404)
        self.assertEqual(self.client.get("/api/equipements/pas-un-uuid/").status_code, 404)
