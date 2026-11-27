"""Référentiel BPE, normalisé à partir du fichier parquet plat.

    domaine1 (A)  <- domaine2 (A1)  <- domaine3 (A101)  <- bpe
    regions (27)  <- depts (21)                          <- bpe
"""
import uuid

from django.contrib.gis.db import models


class Domaine1(models.Model):
    code = models.CharField(max_length=1, primary_key=True)
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = "domaine1"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.libelle}"


class Domaine2(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    domaine1 = models.ForeignKey(
        Domaine1, on_delete=models.PROTECT, db_column="domaine1_code", related_name="enfants"
    )
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = "domaine2"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.libelle}"


class Domaine3(models.Model):
    code = models.CharField(max_length=4, primary_key=True)
    domaine2 = models.ForeignKey(
        Domaine2, on_delete=models.PROTECT, db_column="domaine2_code", related_name="enfants"
    )
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = "domaine3"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.libelle}"


class Region(models.Model):
    id_region = models.CharField(max_length=3, primary_key=True)
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = "regions"

    def __str__(self):
        return self.libelle


class Dept(models.Model):
    id_dept = models.CharField(max_length=3, primary_key=True)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, db_column="id_region", related_name="depts"
    )
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = "depts"
        ordering = ["id_dept"]

    def __str__(self):
        return f"{self.id_dept} – {self.libelle}"


class Bpe(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_column="_id")
    domaine3 = models.ForeignKey(
        Domaine3, on_delete=models.PROTECT, db_column="domaine3_code", related_name="equipements"
    )
    nom = models.CharField(max_length=255, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    codepostal = models.CharField(max_length=5, blank=True)
    ville = models.CharField(max_length=255, blank=True, db_index=True)
    dept = models.ForeignKey(
        Dept, on_delete=models.PROTECT, db_column="id_dept", related_name="equipements"
    )
    siret = models.CharField(max_length=14, blank=True, db_column="SIRET")
    # PointField crée automatiquement un index spatial GiST
    geom = models.PointField(srid=4326, null=True, blank=True)

    class Meta:
        db_table = "bpe"
        verbose_name = "équipement BPE"
        verbose_name_plural = "équipements BPE"

    def __str__(self):
        return self.nom or str(self.id)
