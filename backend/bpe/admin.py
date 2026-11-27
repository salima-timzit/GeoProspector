from django.contrib.gis import admin

from .models import Bpe, Dept, Domaine1, Domaine2, Domaine3, Region

admin.site.register([Domaine1, Domaine2, Domaine3, Region, Dept])


@admin.register(Bpe)
class BpeAdmin(admin.GISModelAdmin):
    list_display = ("nom", "domaine3", "ville", "dept")
    list_filter = ("dept", "domaine3__domaine2__domaine1")
    search_fields = ("nom", "ville", "siret")
    list_select_related = ("domaine3", "dept")
