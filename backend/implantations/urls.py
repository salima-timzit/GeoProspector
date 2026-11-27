"""CRUD des implantations – à compléter par la personne B.

Contrat validé en équipe (JWT obligatoire, chaque utilisateur ne voit que ses points) :
    GET    /api/implantations/        -> GeoJSON de mes points
    POST   /api/implantations/        {lon, lat, domaine3_code, titre, annotations, commentaire}
    PATCH  /api/implantations/<id>/
    DELETE /api/implantations/<id>/

Astuce : un ModelViewSet avec permission IsAuthenticated et
get_queryset() -> Implantation.objects.filter(user=self.request.user),
perform_create() -> serializer.save(user=self.request.user).
"""
from django.urls import path  # noqa: F401

urlpatterns = []
