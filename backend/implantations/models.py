"""Implantations potentielles saisies par les utilisateurs.

Stockées à part du référentiel BPE : un réimport de la BPE ne les touche pas.
"""
from django.conf import settings
from django.contrib.gis.db import models

from bpe.models import Domaine3


class Implantation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="implantations"
    )
    geom = models.PointField(srid=4326)
    domaine3 = models.ForeignKey(
        Domaine3,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="domaine3_code",
        help_text="Type de commerce envisagé (classification BPE)",
    )
    titre = models.CharField(max_length=255)
    annotations = models.TextField(blank=True)
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "implantations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.titre} ({self.user})"
