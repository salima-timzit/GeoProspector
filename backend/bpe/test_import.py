"""Tests de la commande d'import : python manage.py import_bpe

Un petit fichier parquet est fabriqué pour chaque test, avec les mêmes colonnes
que le vrai fichier BPE et les mêmes défauts (codes lus comme des nombres,
coordonnées manquantes, lignes d'autres régions).
"""
import io
import tempfile
import uuid
from pathlib import Path

import pandas as pd
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from implantations.models import Implantation

from .models import Bpe, Dept, Domaine1, Domaine2, Domaine3, Region

ID_DIJON = str(uuid.uuid4())


def ligne(nom, dept, region, d3, lon=5.04, lat=47.32, codepostal=21000.0, _id=None):
    d1, d2 = d3[0], d3[:2]
    return {
        "_id": _id or str(uuid.uuid4()), "nom": nom, "adresse": "1 rue de la Liberté",
        "codepostal": codepostal, "ville": "Dijon", "dept": dept, "region": region,
        "domaine1_code": d1, "domaine1_libelle": f"Domaine {d1}",
        "domaine2_code": d2, "domaine2_libelle": f"Sous-domaine {d2}",
        "domaine3_code": d3, "domaine3_libelle": f"Type {d3}",
        "SIRET": None, "lon": lon, "lat": lat,
    }


LIGNES = [
    ligne("Boulangerie", "21", "27", "B207", _id=ID_DIJON),
    ligne("Boucherie", "21", "27", "B208"),
    ligne("Commissariat", "25", "27", "A101", lon=6.02, lat=47.24, codepostal=25000.0),
    ligne("Sans coordonnées", "21", "27", "B207", lon=None, lat=None),
    ligne("Mairie de Paris", "75", "11", "A101", lon=2.35, lat=48.85, codepostal=75001.0),  # autre région
]


class ImportBpeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fichier = Path(self.tmp.name) / "bpe_test.parquet"
        pd.DataFrame(LIGNES).to_parquet(self.fichier)

    def tearDown(self):
        self.tmp.cleanup()

    def importer(self, region="27"):
        call_command("import_bpe", file=str(self.fichier), region=region, stdout=io.StringIO())

    def test_garde_seulement_la_region(self):
        self.importer()
        self.assertEqual(Bpe.objects.count(), 4)
        self.assertFalse(Bpe.objects.filter(nom="Mairie de Paris").exists())

    def test_normalise_les_domaines_sur_3_niveaux(self):
        self.importer()
        self.assertEqual(Domaine1.objects.count(), 2)  # A, B
        self.assertEqual(Domaine2.objects.count(), 2)  # A1, B2
        self.assertEqual(Domaine3.objects.count(), 3)  # A101, B207, B208
        b207 = Domaine3.objects.get(code="B207")
        self.assertEqual((b207.domaine2_id, b207.domaine2.domaine1_id), ("B2", "B"))

    def test_cree_region_et_departements(self):
        self.importer()
        self.assertEqual(Region.objects.get().libelle, "Bourgogne-Franche-Comté")
        self.assertEqual(
            list(Dept.objects.values_list("id_dept", "libelle")),
            [("21", "Côte-d'Or"), ("25", "Doubs")],
        )

    def test_nettoie_les_valeurs(self):
        self.importer()
        e = Bpe.objects.get(id=ID_DIJON)
        self.assertEqual(e.codepostal, "21000")  # 21000.0 (float) -> "21000"
        self.assertEqual(e.siret, "")  # None -> ""
        self.assertEqual((e.geom.x, e.geom.y), (5.04, 47.32))
        self.assertEqual(e.geom.srid, 4326)

    def test_garde_les_equipements_sans_coordonnees(self):
        self.importer()
        e = Bpe.objects.get(nom="Sans coordonnées")
        self.assertIsNone(e.geom)

    def test_rejouable_sans_doublons_ni_perte_des_implantations(self):
        self.importer()
        user = User.objects.create_user("salima", password="motdepasse123")
        Implantation.objects.create(user=user, titre="Local", geom=Point(5.0, 47.3, srid=4326), domaine3_id="B207")

        self.importer()  # deuxième import

        self.assertEqual(Bpe.objects.count(), 4)
        self.assertEqual(Domaine3.objects.count(), 3)
        self.assertEqual(Implantation.objects.get().domaine3_id, "B207")

    def test_region_sans_equipement(self):
        with self.assertRaises(CommandError):
            self.importer(region="53")

    def test_fichier_introuvable(self):
        with self.assertRaises(CommandError):
            call_command("import_bpe", file="/nulle/part/bpe.parquet", region="27")
