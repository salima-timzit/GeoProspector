"""Endpoints publics de la carte – à compléter par la personne B.

Contrat validé en équipe :
    GET /api/domaines/                       -> arbre domaine1 > domaine2 > domaine3
    GET /api/villes/?search=dij              -> [{nom, codepostal, id_dept}]
    GET /api/equipements/?bbox=minLon,minLat,maxLon,maxLat&domaines=A1,B201&villes=Dijon
                                             -> GeoJSON FeatureCollection
    GET /api/equipements/<uuid>/             -> fiche complète

Astuce bbox : Polygon.from_bbox((minx, miny, maxx, maxy)) puis
Bpe.objects.filter(geom__bboverlaps=poly)  (utilise l'index GiST).
"""
from django.urls import path  # noqa: F401

urlpatterns = []
