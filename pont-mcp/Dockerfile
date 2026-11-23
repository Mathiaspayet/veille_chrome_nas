# Recette de fabrication du conteneur « pont MCP ».
# Il contient Playwright MCP (de Microsoft) : un serveur MCP qui donne à
# Claude des outils pour piloter un navigateur (ouvrir une page, lire,
# cliquer, taper…). Il ne contient PAS de navigateur : il se branche sur le
# Chrome du conteneur « chrome », par la prise 9222.
#
# Le pont n'a aucun mot de passe : il n'écoute que sur 127.0.0.1, et seul le
# « portier » (qui exige l'autorisation OAuth) peut lui parler.

FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json ./
# Version exacte de Playwright MCP, fixée dans package-lock.json.
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force

# Script de démarrage avec auto-réparation (voir demarrer-pont.sh).
COPY --chmod=755 demarrer-pont.sh ./

# Le pont tourne avec un utilisateur ordinaire, pas en « root ».
USER node

# Options du pont :
#  --cdp-endpoint : se brancher sur le Chrome existant (avec tes connexions) ;
#  --port / --host : écouter sur 127.0.0.1:8931, pour le portier seulement ;
#  --ignore-roots : ne pas demander de dossier de travail à Claude ;
#  --no-webmcp : ne pas exposer à Claude des outils fournis par les pages web
#    elles-mêmes (une page piégée pourrait en profiter) ;
#  --output-dir : fichiers temporaires (captures, instantanés) dans /tmp.
ENTRYPOINT ["./demarrer-pont.sh"]
CMD ["--cdp-endpoint", "http://127.0.0.1:9222", \
     "--port", "8931", "--host", "127.0.0.1", \
     "--ignore-roots", "--no-webmcp", \
     "--output-dir", "/tmp/pont-mcp"]
