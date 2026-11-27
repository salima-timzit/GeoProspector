"""Endpoints publics de la carte (lecture seule, sans authentification).

Le filtrage est fait en base (PostGIS) : seuls les équipements demandés sont lus.
"""
from django.contrib.gis.geos import Polygon
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from .geocodage import GeocodageIndisponible, rechercher_adresse
from .models import Bpe, Dept, Domaine1

VILLES_SEARCH_LIMIT = 20
# Niveau de domaine déduit de la longueur du code : A -> 1, A1 -> 2, A101 -> 3
DOMAINE_FILTERS = {1: "domaine3__domaine2__domaine1_id", 2: "domaine3__domaine2_id", 4: "domaine3_id"}

ERREUR_400 = OpenApiResponse(
    description="Paramètre invalide",
    examples=[OpenApiExample("Erreur", value={"detail": "bbox doit contenir 4 nombres : minLon,minLat,maxLon,maxLat."})],
)


def split_param(request, name):
    """'A1, B201,' -> ['A1', 'B201']"""
    raw = request.query_params.get(name, "")
    return [v.strip() for v in raw.split(",") if v.strip()]


def parse_bbox(raw):
    """'minLon,minLat,maxLon,maxLat' -> Polygon (SRID 4326). Lève ValidationError si invalide."""
    parts = raw.split(",")
    try:
        if len(parts) != 4:
            raise ValueError
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise ValidationError({"detail": "bbox doit contenir 4 nombres : minLon,minLat,maxLon,maxLat."})
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValidationError(
            {"detail": "bbox invalide : il faut minLon < maxLon, minLat < maxLat, longitudes dans [-180, 180] et latitudes dans [-90, 90]."}
        )
    return Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))


class DomainesView(APIView):
    """Arbre complet des domaines BPE : domaine1 > domaine2 > domaine3."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        summary="Arbre des domaines (3 niveaux)",
        responses={200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            examples=[OpenApiExample("Arbre", value=[{
                "code": "A", "libelle": "Services pour les particuliers",
                "enfants": [{"code": "A1", "libelle": "Services publics",
                             "enfants": [{"code": "A101", "libelle": "Police"}]}],
            }])],
        )},
    )
    def get(self, request):
        data = [
            {
                "code": d1.code,
                "libelle": d1.libelle,
                "enfants": [
                    {
                        "code": d2.code,
                        "libelle": d2.libelle,
                        "enfants": [{"code": d3.code, "libelle": d3.libelle} for d3 in d2.enfants.all()],
                    }
                    for d2 in d1.enfants.all()
                ],
            }
            for d1 in Domaine1.objects.prefetch_related("enfants__enfants")
        ]
        return Response(data)


class VillesView(APIView):
    """Liste des villes présentes dans la BPE (couples nom / code postal / département)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        summary="Recherche de villes",
        parameters=[OpenApiParameter(
            "search", str, description=f"Texte contenu dans le nom (insensible à la casse). "
                                       f"Avec ce paramètre, {VILLES_SEARCH_LIMIT} résultats maximum ; "
                                       f"sans, toutes les villes sont renvoyées.",
        )],
        responses={200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            examples=[OpenApiExample("Villes", value=[{"nom": "Dijon", "codepostal": "21000", "id_dept": "21"}])],
        )},
    )
    def get(self, request):
        qs = (
            Bpe.objects.exclude(ville="")
            .values("ville", "codepostal", "dept_id")
            .distinct()
            .order_by("ville", "codepostal")
        )
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(ville__icontains=search)[:VILLES_SEARCH_LIMIT]
        return Response([{"nom": v["ville"], "codepostal": v["codepostal"], "id_dept": v["dept_id"]} for v in qs])


class EquipementsView(APIView):
    """Équipements à afficher sur la carte, au format GeoJSON."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        operation_id="equipements_list",
        summary="Équipements visibles (GeoJSON FeatureCollection)",
        description=(
            "Filtrage fait en base. `bbox` est obligatoire sauf si `villes` est fourni "
            "(on ne renvoie jamais toute la BPE). Les filtres se combinent (ET entre paramètres, "
            "OU entre les valeurs d'un même paramètre). Les équipements sans coordonnées sont exclus."
        ),
        parameters=[
            OpenApiParameter("bbox", str, description="minLon,minLat,maxLon,maxLat (WGS84), ex. `5.0,47.3,5.1,47.4`"),
            OpenApiParameter("domaines", str, description="Codes séparés par des virgules, tous niveaux mélangés : "
                                                          "`A` (niveau 1), `A1` (niveau 2), `A101` (niveau 3). Ex. `A1,B201`"),
            OpenApiParameter("villes", str, description="Noms exacts (tels que renvoyés par /api/villes/) séparés par des virgules. Ex. `Dijon,Beaune`"),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                examples=[OpenApiExample("FeatureCollection", value={
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [5.041, 47.322]},
                        "properties": {"id": "3f2c…", "nom": "Boulangerie X", "ville": "Dijon",
                                       "domaine1_code": "B", "domaine3_code": "B207", "domaine3_libelle": "Boulangerie-pâtisserie"},
                    }],
                })],
            ),
            400: ERREUR_400,
        },
    )
    def get(self, request):
        bbox = request.query_params.get("bbox", "").strip()
        villes = split_param(request, "villes")
        domaines = split_param(request, "domaines")
        if not bbox and not villes:
            raise ValidationError({"detail": "Paramètre bbox obligatoire (ou au moins une ville via villes)."})

        qs = Bpe.objects.filter(geom__isnull=False)
        if bbox:
            # && PostGIS : utilise l'index GiST de bpe.geom
            qs = qs.filter(geom__bboverlaps=parse_bbox(bbox))
        if villes:
            qs = qs.filter(ville__in=villes)
        if domaines:
            q = Q()
            for code in domaines:
                field = DOMAINE_FILTERS.get(len(code))
                if field is None:
                    raise ValidationError({"detail": f"Code de domaine invalide : {code!r} (attendu : A, A1 ou A101)."})
                q |= Q(**{field: code.upper()})
            qs = qs.filter(q)

        rows = qs.values(
            "id", "nom", "ville", "geom", "domaine3_id", "domaine3__libelle", "domaine3__domaine2__domaine1_id"
        )
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(r["geom"].x, 6), round(r["geom"].y, 6)]},
                "properties": {
                    "id": str(r["id"]),
                    "nom": r["nom"],
                    "ville": r["ville"],
                    "domaine1_code": r["domaine3__domaine2__domaine1_id"],
                    "domaine3_code": r["domaine3_id"],
                    "domaine3_libelle": r["domaine3__libelle"],
                },
            }
            for r in rows
        ]
        return Response({"type": "FeatureCollection", "features": features})


class EquipementDetailView(APIView):
    """Fiche complète d'un équipement."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        operation_id="equipements_detail",
        summary="Fiche d'un équipement",
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                examples=[OpenApiExample("Fiche", value={
                    "id": "3f2c…", "nom": "Boulangerie X", "adresse": "1 rue de la Liberté",
                    "codepostal": "21000", "ville": "Dijon", "siret": "12345678900011",
                    "dept": {"id_dept": "21", "libelle": "Côte-d'Or"},
                    "domaine1": {"code": "B", "libelle": "Commerces"},
                    "domaine2": {"code": "B2", "libelle": "Commerces alimentaires"},
                    "domaine3": {"code": "B207", "libelle": "Boulangerie-pâtisserie"},
                    "lon": 5.041, "lat": 47.322,
                })],
            ),
            404: OpenApiResponse(description="Équipement inexistant"),
        },
    )
    def get(self, request, pk):
        e = get_object_or_404(
            Bpe.objects.select_related("dept", "domaine3__domaine2__domaine1"), pk=pk
        )
        d3 = e.domaine3
        d2 = d3.domaine2
        d1 = d2.domaine1
        return Response({
            "id": str(e.id),
            "nom": e.nom,
            "adresse": e.adresse,
            "codepostal": e.codepostal,
            "ville": e.ville,
            "siret": e.siret,
            "dept": {"id_dept": e.dept.id_dept, "libelle": e.dept.libelle},
            "domaine1": {"code": d1.code, "libelle": d1.libelle},
            "domaine2": {"code": d2.code, "libelle": d2.libelle},
            "domaine3": {"code": d3.code, "libelle": d3.libelle},
            "lon": round(e.geom.x, 6) if e.geom else None,
            "lat": round(e.geom.y, 6) if e.geom else None,
        })


RECHERCHE_LIMIT = 20


class RechercheEquipementsView(APIView):
    """Recherche d'équipements par leur nom (pour les retrouver sur la carte)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        operation_id="equipements_recherche",
        summary="Chercher un équipement par son nom",
        description=f"Texte contenu dans le nom (insensible à la casse et aux accents). {RECHERCHE_LIMIT} résultats maximum, "
                    "équipements sans coordonnées exclus. Filtre optionnel `ville`.",
        parameters=[
            OpenApiParameter("q", str, required=True, description="Au moins 3 caractères, ex. `boulangerie`"),
            OpenApiParameter("ville", str, description="Nom exact de la ville, ex. `Dijon`"),
        ],
        responses={200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            examples=[OpenApiExample("Résultats", value=[{
                "id": "3f2c…", "nom": "Boulangerie X", "ville": "Dijon", "codepostal": "21000",
                "domaine1_code": "B", "domaine3_code": "B207", "domaine3_libelle": "Boulangerie-pâtisserie",
                "lon": 5.041, "lat": 47.322,
            }])],
        ), 400: ERREUR_400},
    )
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            raise ValidationError({"detail": "Saisissez au moins 3 caractères du nom."})
        qs = Bpe.objects.filter(geom__isnull=False, nom__unaccent__icontains=q)
        ville = request.query_params.get("ville", "").strip()
        if ville:
            qs = qs.filter(ville=ville)
        rows = qs.order_by("nom", "ville").values(
            "id", "nom", "ville", "codepostal", "geom", "domaine3_id", "domaine3__libelle",
            "domaine3__domaine2__domaine1_id",
        )[:RECHERCHE_LIMIT]
        return Response([
            {
                "id": str(r["id"]),
                "nom": r["nom"],
                "ville": r["ville"],
                "codepostal": r["codepostal"],
                "domaine1_code": r["domaine3__domaine2__domaine1_id"],
                "domaine3_code": r["domaine3_id"],
                "domaine3_libelle": r["domaine3__libelle"],
                "lon": round(r["geom"].x, 6),
                "lat": round(r["geom"].y, 6),
            }
            for r in rows
        ])


class GeocodageView(APIView):
    """Géolocalise une adresse postale et indique si elle est dans la région couverte."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Carte"],
        summary="Géocoder une adresse postale",
        description=(
            "Interroge l'API Géoplateforme de l'IGN (Base Adresse Nationale) et renvoie la meilleure "
            "correspondance. `dans_zone` vaut `false` si l'adresse est hors de la région importée ; "
            "`message` contient alors le texte à afficher."
        ),
        parameters=[OpenApiParameter("q", str, required=True, description="Adresse saisie, ex. `1 rue de la Liberté Dijon`")],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample("Dans la zone", value={
                        "label": "1 Rue de la Liberté 21000 Dijon", "lon": 5.0386, "lat": 47.3217,
                        "dept": "21", "dans_zone": True, "message": None,
                    }),
                    OpenApiExample("Hors zone", value={
                        "label": "10 Rue de Rivoli 75004 Paris", "lon": 2.3561, "lat": 48.8555,
                        "dept": "75", "dans_zone": False,
                        "message": "Adresse hors zone : 10 Rue de Rivoli 75004 Paris (département 75). "
                                   "GeoProspector couvre uniquement la région Bourgogne-Franche-Comté.",
                    }),
                ],
            ),
            400: OpenApiResponse(description="Paramètre q manquant ou trop court"),
            404: OpenApiResponse(description="Adresse introuvable"),
            502: OpenApiResponse(description="Service de géocodage de l'IGN indisponible"),
        },
    )
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 3:
            raise ValidationError({"detail": "Saisissez une adresse d'au moins 3 caractères."})
        try:
            res = rechercher_adresse(q)
        except GeocodageIndisponible:
            return Response({"detail": "Le service de géocodage de l'IGN est indisponible, réessayez."}, status=502)
        if res is None:
            return Response({"detail": f"Adresse introuvable : « {q} »."}, status=404)

        dans_zone = Dept.objects.filter(id_dept=res["dept"], region_id=settings.BPE_REGION).exists()
        region = Dept.objects.filter(region_id=settings.BPE_REGION).select_related("region").first()
        nom_region = region.region.libelle if region else f"région {settings.BPE_REGION}"
        message = None
        if not dans_zone:
            message = (
                f"Adresse hors zone : {res['label']} (département {res['dept']}). "
                f"GeoProspector couvre uniquement la région {nom_region}."
            )
        return Response({
            "label": res["label"],
            "lon": res["lon"],
            "lat": res["lat"],
            "dept": res["dept"],
            "dans_zone": dans_zone,
            "message": message,
        })
