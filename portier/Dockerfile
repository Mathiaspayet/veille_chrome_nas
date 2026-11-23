# Recette de fabrication du conteneur « portier ».
# C'est la porte d'entrée sécurisée du pont MCP : connexion OAuth (comme
# l'appli Menus famille), verrouillage après 5 essais ratés, et blocage des
# outils dangereux. Détails dans portier.py.

FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check -r requirements.txt

COPY portier.py .

# Affiche les messages tout de suite, sans attendre.
ENV PYTHONUNBUFFERED=1

CMD ["python", "portier.py"]
