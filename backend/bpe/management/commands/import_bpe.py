"""ETL : parquet BPE (plat) -> modèle relationnel PostGIS.

    python manage.py import_bpe                       # région et fichier depuis .env
    python manage.py import_bpe --file /data/bpe25.parquet --region 27

1. Extraction  : lecture du parquet dans un DataFrame pandas
2. Filtrage    : uniquement la région demandée
3. Restructuration : domaines (3 niveaux), régions, départements, équipements
4. Chargement  : bulk_create dans l'ordre des clés étrangères

La commande est rejouable : les tables de référence sont mises à jour (upsert)
et les équipements sont remplacés. Les implantations des utilisateurs ne sont pas touchées.
"""
import math
import time
import uuid
import zipfile
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from bpe.models import Bpe, Dept, Domaine1, Domaine2, Domaine3, Region

COLUMNS = [
    "_id", "nom", "adresse", "codepostal", "ville", "dept", "region",
    "domaine1_code", "domaine1_libelle",
    "domaine2_code", "domaine2_libelle",
    "domaine3_code", "domaine3_libelle",
    "SIRET", "lon", "lat",
]

# Le parquet ne contient pas les libellés des régions / départements
REGIONS = {
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "52": "Pays de la Loire",
    "53": "Bretagne",
}
DEPTS = {
    "21": "Côte-d'Or", "25": "Doubs", "39": "Jura", "58": "Nièvre",
    "70": "Haute-Saône", "71": "Saône-et-Loire", "89": "Yonne", "90": "Territoire de Belfort",
}


def txt(value, width=None):
    """Valeur pandas -> chaîne propre ('' si vide). Gère les codes lus comme des floats."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            value = int(value)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    if width and s.isdigit():
        s = s.zfill(width)
    return s


class Command(BaseCommand):
    help = "Importe les équipements BPE d'une région depuis le fichier parquet."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=settings.BPE_PARQUET, help="Chemin du .parquet (ou du .zip)")
        parser.add_argument("--region", default=settings.BPE_REGION, help="Code région INSEE (27 = BFC)")
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **opts):
        start = time.monotonic()
        region = txt(opts["region"], 2)
        path = self.resolve_file(Path(opts["file"]))

        # 1. Extraction
        self.stdout.write(f"Lecture de {path} …")
        df = pd.read_parquet(path, columns=COLUMNS).rename(columns={"_id": "uid"})
        self.stdout.write(f"  {len(df):,} lignes au total")

        # 2. Filtrage sur la région
        df = df[df["region"].map(lambda v: txt(v, 2)) == region]
        if df.empty:
            raise CommandError(f"Aucun équipement pour la région {region}.")
        self.stdout.write(f"  {len(df):,} lignes pour la région {region}")

        # 3. Restructuration
        d1 = self.unique(df, "domaine1_code", "domaine1_libelle")
        d2 = self.unique(df, "domaine2_code", "domaine2_libelle", "domaine1_code")
        d3 = self.unique(df, "domaine3_code", "domaine3_libelle", "domaine2_code")
        depts = sorted({txt(v, 2) for v in df["dept"]} - {""})

        # 4. Chargement (dans l'ordre des FK)
        with transaction.atomic():
            Region.objects.bulk_create(
                [Region(id_region=region, libelle=REGIONS.get(region, f"Région {region}"))],
                update_conflicts=True, unique_fields=["id_region"], update_fields=["libelle"],
            )
            Dept.objects.bulk_create(
                [Dept(id_dept=d, region_id=region, libelle=DEPTS.get(d, f"Département {d}")) for d in depts],
                update_conflicts=True, unique_fields=["id_dept"], update_fields=["libelle", "region"],
            )
            Domaine1.objects.bulk_create(
                [Domaine1(code=c, libelle=l) for c, l in d1],
                update_conflicts=True, unique_fields=["code"], update_fields=["libelle"],
            )
            Domaine2.objects.bulk_create(
                [Domaine2(code=c, libelle=l, domaine1_id=p) for c, l, p in d2],
                update_conflicts=True, unique_fields=["code"], update_fields=["libelle", "domaine1"],
            )
            Domaine3.objects.bulk_create(
                [Domaine3(code=c, libelle=l, domaine2_id=p) for c, l, p in d3],
                update_conflicts=True, unique_fields=["code"], update_fields=["libelle", "domaine2"],
            )
            self.stdout.write(
                f"  Référentiels : {len(d1)} domaine1, {len(d2)} domaine2, {len(d3)} domaine3, {len(depts)} depts"
            )

            # Les équipements de la région sont remplacés
            deleted, _ = Bpe.objects.filter(dept__region_id=region).delete()
            if deleted:
                self.stdout.write(f"  {deleted:,} anciens équipements supprimés")

            objs, skipped = [], 0
            for row in df.itertuples(index=False):
                code3, dept = txt(row.domaine3_code), txt(row.dept, 2)
                if not code3 or not dept:
                    skipped += 1
                    continue
                lon, lat = row.lon, row.lat
                geom = None
                if not (pd.isna(lon) or pd.isna(lat)):
                    geom = Point(float(lon), float(lat), srid=4326)
                objs.append(Bpe(
                    id=self.as_uuid(row.uid),
                    domaine3_id=code3,
                    nom=txt(row.nom)[:255],
                    adresse=txt(row.adresse)[:255],
                    codepostal=txt(row.codepostal, 5)[:5],
                    ville=txt(row.ville)[:255],
                    dept_id=dept,
                    siret=txt(row.SIRET, 14)[:14],
                    geom=geom,
                ))
            Bpe.objects.bulk_create(objs, batch_size=opts["batch_size"])

        with connection.cursor() as cur:
            cur.execute("ANALYZE bpe")

        no_geom = sum(1 for o in objs if o.geom is None)
        self.stdout.write(self.style.SUCCESS(
            f"{len(objs):,} équipements importés ({no_geom:,} sans coordonnées, "
            f"{skipped:,} ignorés) en {time.monotonic() - start:.1f} s"
        ))

    @staticmethod
    def unique(df, code_col, libelle_col, parent_col=None):
        cols = [code_col, libelle_col] + ([parent_col] if parent_col else [])
        rows = {}
        for values in df[cols].drop_duplicates().itertuples(index=False):
            values = tuple(txt(v) for v in values)
            if values[0]:
                rows.setdefault(values[0], values)
        return sorted(rows.values())

    @staticmethod
    def as_uuid(value):
        try:
            return uuid.UUID(txt(value))
        except ValueError:
            return uuid.uuid4()

    def resolve_file(self, path):
        """Accepte le .parquet ou le .zip téléchargé (extrait à côté au besoin)."""
        if not path.exists() and path.with_suffix(".parquet.zip").exists():
            path = path.with_suffix(".parquet.zip")
        if not path.exists():
            raise CommandError(
                f"Fichier introuvable : {path}\n"
                "Téléchargez https://data.atontour.info/bpe25.parquet.zip dans le dossier data/ (voir README)."
            )
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                name = next(n for n in zf.namelist() if n.endswith(".parquet"))
                target = path.parent / Path(name).name
                if not target.exists():
                    self.stdout.write(f"Extraction de {name} …")
                    zf.extract(name, path.parent)
                    extracted = path.parent / name
                    if extracted != target:
                        extracted.rename(target)
            path = target
        return path
