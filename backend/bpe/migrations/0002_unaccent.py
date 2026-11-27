from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Extension PostgreSQL pour la recherche d'équipements sans tenir compte des accents."""

    dependencies = [("bpe", "0001_initial")]

    operations = [UnaccentExtension()]
