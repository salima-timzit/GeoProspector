"""CRUD des implantations.

Contrat validé en équipe (JWT obligatoire, chaque utilisateur ne voit que ses points) :
    GET    /api/implantations/        -> GeoJSON de mes points
    POST   /api/implantations/        {lon, lat, domaine3_code, titre, annotations, commentaire}
    GET    /api/implantations/<id>/   -> Feature GeoJSON
    PATCH  /api/implantations/<id>/
    DELETE /api/implantations/<id>/
"""
from rest_framework.routers import SimpleRouter

from .views import ImplantationViewSet

router = SimpleRouter()
router.register("implantations", ImplantationViewSet, basename="implantation")

urlpatterns = router.urls
