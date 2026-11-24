# Recette de fabrication du conteneur « pont MCP ».
# Il contient Playwright MCP (de Microsoft) : un serveur MCP qui donne à
# Claude des outils pour piloter un navigateur (ouvrir une page, lire,
# cliquer, taper…). Il ne contient PAS de navigateur : il se branche sur le
# Chrome du conteneur « chrome », par sa prise de pilotage (via le relais
# CDP, voir relais-cdp.js).
#
# Le pont n'a aucun mot de passe : il n'est joignable que sur le réseau
# Docker du projet (rien n'est publié vers le NAS ou Internet), et seul le
# « portier » (qui exige l'autorisation OAuth) lui parle.

FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json ./
# Version exacte de Playwright MCP, fixée dans package-lock.json.
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force

# Script de démarrage et relais CDP.
COPY --chmod=755 demarrer-pont.sh ./
COPY relais-cdp.js ./

# Le pont tourne avec un utilisateur ordinaire, pas en « root ».
USER node

# Options du pont :
#  --cdp-endpoint : se brancher sur Chrome (relais local 127.0.0.1:9222) ;
#  --port / --host : écouter sur le port 8931 du réseau du projet ;
#  --allowed-hosts : noms (avec le port) sous lesquels le portier peut
#    l'appeler ;
#  --ignore-roots : ne pas demander de dossier de travail à Claude ;
#  --no-webmcp : ne pas exposer à Claude des outils fournis par les pages web
#    elles-mêmes (une page piégée pourrait en profiter) ;
#  --output-dir : fichiers temporaires (captures, instantanés) dans /tmp.
ENTRYPOINT ["./demarrer-pont.sh"]
CMD ["--cdp-endpoint", "http://127.0.0.1:9222", \
     "--port", "8931", "--host", "0.0.0.0", \
     "--allowed-hosts", "pont-mcp:8931,localhost:8931,127.0.0.1:8931", \
     "--ignore-roots", "--no-webmcp", \
     "--output-dir", "/tmp/pont-mcp"]
