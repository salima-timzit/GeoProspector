from django.contrib.gis.geos import Point
from rest_framework import serializers

from bpe.models import Domaine3

from .models import Implantation


class ImplantationSerializer(serializers.ModelSerializer):
    """Entrée : {lon, lat, domaine3_code, titre, annotations, commentaire}.
    Sortie : une Feature GeoJSON (géométrie Point + propriétés)."""

    lon = serializers.FloatField(write_only=True, min_value=-180, max_value=180)
    lat = serializers.FloatField(write_only=True, min_value=-90, max_value=90)
    domaine3_code = serializers.PrimaryKeyRelatedField(
        source="domaine3", queryset=Domaine3.objects.all(), allow_null=True, required=False,
        help_text="Code domaine3 BPE du commerce envisagé (ex. B207), ou null",
    )

    class Meta:
        model = Implantation
        fields = ("id", "lon", "lat", "domaine3_code", "titre", "annotations", "commentaire", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        lon, lat = attrs.pop("lon", None), attrs.pop("lat", None)
        if self.instance is None or lon is not None or lat is not None:
            # Création : lon et lat obligatoires. Modification : on peut n'en changer qu'un.
            if self.instance is not None:
                lon = self.instance.geom.x if lon is None else lon
                lat = self.instance.geom.y if lat is None else lat
            attrs["geom"] = Point(lon, lat, srid=4326)
        return attrs

    def to_representation(self, obj):
        d3 = obj.domaine3
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [obj.geom.x, obj.geom.y]},
            "properties": {
                "id": obj.id,
                "titre": obj.titre,
                "domaine3_code": d3.code if d3 else None,
                "domaine3_libelle": d3.libelle if d3 else None,
                "annotations": obj.annotations,
                "commentaire": obj.commentaire,
                "created_at": serializers.DateTimeField().to_representation(obj.created_at),
                "updated_at": serializers.DateTimeField().to_representation(obj.updated_at),
            },
        }
