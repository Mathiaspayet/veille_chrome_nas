# Recette de fabrication du conteneur « robot ».
# Il contient seulement Python et la bibliothèque Playwright, qui sait
# piloter un navigateur. Pas besoin d'installer un navigateur ici :
# le robot se branche sur le Chrome du conteneur « chrome ».

FROM python:3.13-slim

WORKDIR /app

# Petite bibliothèque système dont Playwright a besoin pour démarrer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/

# Adresse de la « prise » de pilotage de Chrome (voir docker-compose.yml).
ENV CDP_URL=http://127.0.0.1:9222
# Affiche les messages tout de suite, sans attendre la fin du script.
ENV PYTHONUNBUFFERED=1

# Par défaut, le robot lance le script de test.
# Pour un autre script : docker compose run --rm robot scripts/autre.py
ENTRYPOINT ["python"]
CMD ["scripts/test_connexion.py"]
