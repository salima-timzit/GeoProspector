"""Endpoints publics de la carte.

Contrat validé en équipe :
    GET /api/domaines/                       -> arbre domaine1 > domaine2 > domaine3
    GET /api/villes/?search=dij              -> [{nom, codepostal, id_dept}]
    GET /api/equipements/?bbox=minLon,minLat,maxLon,maxLat&domaines=A1,B201&villes=Dijon
                                             -> GeoJSON FeatureCollection
    GET /api/equipements/<uuid>/             -> fiche complète
"""
from django.urls import path

from . import views

urlpatterns = [
    path("domaines/", views.DomainesView.as_view(), name="domaines"),
    path("villes/", views.VillesView.as_view(), name="villes"),
    path("equipements/", views.EquipementsView.as_view(), name="equipements"),
    path("equipements/<uuid:pk>/", views.EquipementDetailView.as_view(), name="equipement-detail"),
]
