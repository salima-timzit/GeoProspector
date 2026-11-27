FROM python:3.14-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Bibliothèques géographiques nécessaires à GeoDjango (GDAL, GEOS, PROJ)
RUN apt-get update \
    && apt-get install -y --no-install-recommends binutils gdal-bin libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Seules les dépendances sont dans l'image : le code est monté en volume (cf. docker-compose)
COPY requirements.txt .
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
