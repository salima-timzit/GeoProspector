from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from bpe.models import Domaine1, Domaine2, Domaine3

from .models import Implantation

URL = "/api/implantations/"
PAYLOAD = {"lon": 5.0415, "lat": 47.322, "domaine3_code": "B207", "titre": "Local Liberté",
           "annotations": "Passage", "commentaire": "Loyer ?"}


class ImplantationApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        Domaine1.objects.create(code="B", libelle="Commerces")
        Domaine2.objects.create(code="B2", domaine1_id="B", libelle="Alimentaire")
        Domaine3.objects.create(code="B207", domaine2_id="B2", libelle="Boulangerie")
        User.objects.create_user("alice", password="motdepasse-alice")
        User.objects.create_user("bob", password="motdepasse-bob")

    def login(self, username):
        """Passe par la vraie route JWT, comme le front."""
        self.client.credentials()
        resp = self.client.post("/api/auth/login/", {"username": username, "password": f"motdepasse-{username}"})
        self.assertEqual(resp.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    def create(self, **overrides):
        resp = self.client.post(URL, {**PAYLOAD, **overrides}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.json()

    def test_auth_obligatoire(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.assertEqual(self.client.post(URL, PAYLOAD, format="json").status_code, 401)

    def test_creer_et_lister(self):
        self.login("alice")
        feat = self.create()
        self.assertEqual(feat["type"], "Feature")
        self.assertEqual(feat["geometry"], {"type": "Point", "coordinates": [5.0415, 47.322]})
        self.assertEqual(feat["properties"]["domaine3_code"], "B207")
        self.assertEqual(feat["properties"]["domaine3_libelle"], "Boulangerie")
        impl = Implantation.objects.get(pk=feat["properties"]["id"])
        self.assertEqual(impl.user.username, "alice")

        data = self.client.get(URL).json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        detail = self.client.get(f"{URL}{impl.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["properties"]["titre"], "Local Liberté")

    def test_creer_sans_domaine(self):
        self.login("alice")
        feat = self.create(domaine3_code=None)
        self.assertIsNone(feat["properties"]["domaine3_code"])

    def test_validation(self):
        self.login("alice")
        cas = [
            {"lon": 200},                      # longitude hors limites
            {"lat": "abc"},                    # latitude non numérique
            {"domaine3_code": "Z999"},         # domaine inexistant
            {"titre": ""},                     # titre obligatoire
        ]
        for override in cas:
            with self.subTest(override=override):
                resp = self.client.post(URL, {**PAYLOAD, **override}, format="json")
                self.assertEqual(resp.status_code, 400)
        sans_lat = {k: v for k, v in PAYLOAD.items() if k != "lat"}
        self.assertEqual(self.client.post(URL, sans_lat, format="json").status_code, 400)

    def test_modifier_partiellement(self):
        self.login("alice")
        pk = self.create()["properties"]["id"]
        resp = self.client.patch(f"{URL}{pk}/", {"commentaire": "Signé !", "lat": 47.5}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        props = resp.json()["properties"]
        self.assertEqual(props["commentaire"], "Signé !")
        self.assertEqual(props["titre"], "Local Liberté")
        self.assertEqual(resp.json()["geometry"]["coordinates"], [5.0415, 47.5])

    def test_supprimer(self):
        self.login("alice")
        pk = self.create()["properties"]["id"]
        self.assertEqual(self.client.delete(f"{URL}{pk}/").status_code, 204)
        self.assertFalse(Implantation.objects.filter(pk=pk).exists())

    def test_put_non_expose(self):
        self.login("alice")
        pk = self.create()["properties"]["id"]
        self.assertEqual(self.client.put(f"{URL}{pk}/", PAYLOAD, format="json").status_code, 405)

    def test_confidentialite_deux_comptes(self):
        self.login("alice")
        pk = self.create(titre="Secret d'Alice")["properties"]["id"]

        self.login("bob")
        self.assertEqual(self.client.get(URL).json()["features"], [])
        self.assertEqual(self.client.get(f"{URL}{pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"{URL}{pk}/", {"titre": "piraté"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"{URL}{pk}/").status_code, 404)
        self.create(titre="Point de Bob")

        self.login("alice")
        features = self.client.get(URL).json()["features"]
        self.assertEqual([f["properties"]["titre"] for f in features], ["Secret d'Alice"])

    def test_id_inexistant(self):
        self.login("alice")
        self.assertEqual(self.client.get(f"{URL}999999/").status_code, 404)
