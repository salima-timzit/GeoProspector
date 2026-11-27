"""Endpoints publics de la carte.

Contrat validé en équipe :
    GET /api/domaines/                       -> arbre domaine1 > domaine2 > domaine3
    GET /api/villes/?search=dij              -> [{nom, codepostal, id_dept}]
    GET /api/equipements/?bbox=minLon,minLat,maxLon,maxLat&domaines=A1,B201&villes=Dijon
                                             -> GeoJSON FeatureCollection
    GET /api/equipements/<uuid>/             -> fiche complète
    GET /api/equipements/recherche/?q=boulang -> [{id, nom, ville, lon, lat, …}] (20 max)
    GET /api/geocodage/?q=1 rue X Dijon      -> {label, lon, lat, dept, dans_zone, message}
"""
from django.urls import path

from . import views

urlpatterns = [
    path("domaines/", views.DomainesView.as_view(), name="domaines"),
    path("villes/", views.VillesView.as_view(), name="villes"),
    path("equipements/", views.EquipementsView.as_view(), name="equipements"),
    path("equipements/recherche/", views.RechercheEquipementsView.as_view(), name="equipements-recherche"),
    path("equipements/<uuid:pk>/", views.EquipementDetailView.as_view(), name="equipement-detail"),
    path("geocodage/", views.GeocodageView.as_view(), name="geocodage"),
]
