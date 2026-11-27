from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .models import Implantation
from .serializers import ImplantationSerializer

EXEMPLE_FEATURE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [5.0415, 47.3220]},
    "properties": {
        "id": 1, "titre": "Local rue de la Liberté", "domaine3_code": "B207",
        "domaine3_libelle": "Boulangerie-pâtisserie", "annotations": "Passage important",
        "commentaire": "Loyer à négocier",
        "created_at": "2026-11-27T10:00:00+01:00", "updated_at": "2026-11-27T10:00:00+01:00",
    },
}
ID_PARAM = [OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH)]
EXEMPLE_ENTREE = OpenApiExample(
    "Nouvelle implantation", request_only=True,
    value={"lon": 5.0415, "lat": 47.322, "domaine3_code": "B207", "titre": "Local rue de la Liberté",
           "annotations": "Passage important", "commentaire": "Loyer à négocier"},
)


@extend_schema_view(
    list=extend_schema(summary="Mes implantations (GeoJSON FeatureCollection)",
                       examples=[OpenApiExample("Liste", response_only=True,
                                                value={"type": "FeatureCollection", "features": [EXEMPLE_FEATURE]})]),
    create=extend_schema(summary="Créer une implantation", examples=[EXEMPLE_ENTREE]),
    retrieve=extend_schema(summary="Détail d'une de mes implantations", parameters=ID_PARAM),
    partial_update=extend_schema(summary="Modifier une de mes implantations (champs partiels)", parameters=ID_PARAM),
    destroy=extend_schema(summary="Supprimer une de mes implantations", parameters=ID_PARAM),
)
@extend_schema(tags=["Implantations"])
class ImplantationViewSet(viewsets.ModelViewSet):
    """CRUD des implantations de l'utilisateur connecté (JWT obligatoire).

    Chaque utilisateur ne voit que ses propres points : ceux des autres renvoient 404.
    """

    serializer_class = ImplantationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Implantation.objects.filter(user=self.request.user).select_related("domaine3")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def list(self, request, *args, **kwargs):
        features = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"type": "FeatureCollection", "features": features})
