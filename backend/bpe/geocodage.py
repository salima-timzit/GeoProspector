"""Géocodage d'une adresse postale via l'API Géoplateforme de l'IGN (Base Adresse Nationale).

Documentation : https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage
L'ancienne URL api-adresse.data.gouv.fr a été décommissionnée fin janvier 2026.
"""
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GEOCODAGE_URL = "https://data.geopf.fr/geocodage/search"
TIMEOUT_S = 5


class GeocodageIndisponible(Exception):
    """Le service de l'IGN n'a pas répondu correctement."""


def rechercher_adresse(q):
    """Renvoie la meilleure correspondance {label, lon, lat, dept, score} ou None."""
    url = f"{GEOCODAGE_URL}?{urlencode({'q': q, 'limit': 1, 'index': 'address'})}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "GeoProspector/1.0"})
    try:
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.load(resp)
    except (URLError, TimeoutError, ValueError) as exc:
        raise GeocodageIndisponible(str(exc)) from exc

    features = data.get("features") or []
    if not features:
        return None
    f = features[0]
    props = f.get("properties", {})
    lon, lat = f["geometry"]["coordinates"][:2]
    return {
        "label": props.get("label", q),
        "lon": lon,
        "lat": lat,
        "dept": departement(props),
        "score": props.get("score"),
    }


def departement(props):
    """Code département à partir du 'context' ('21, Côte-d'Or, Bourgogne-…') ou du code INSEE."""
    context = props.get("context") or ""
    code = context.split(",")[0].strip()
    if code:
        return code
    citycode = props.get("citycode") or ""
    return citycode[:3] if citycode.startswith("97") else citycode[:2]
