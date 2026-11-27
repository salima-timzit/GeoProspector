from django.contrib.gis import admin

from .models import Implantation


@admin.register(Implantation)
class ImplantationAdmin(admin.GISModelAdmin):
    list_display = ("titre", "user", "domaine3", "created_at")
    list_filter = ("user",)
