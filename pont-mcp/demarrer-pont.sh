#!/bin/bash
# =====================================================================
#  Démarrage du pont MCP.
#
#  1. On regarde comment joindre Chrome :
#     - nouveau plan (conteneurs indépendants) : par le relais du
#       conteneur chrome (chrome:9223). On démarre alors notre propre
#       relais (relais-cdp.js), qui rend la prise de Chrome disponible ici,
#       sur 127.0.0.1:9222 ;
#     - ancien plan (pont dans le réseau de Chrome) : la prise de Chrome
#       est directement là, sur 127.0.0.1:9222. Pas de relais : surtout ne
#       pas lui prendre son port.
#  2. Playwright MCP se branche sur 127.0.0.1:9222 et sert les outils de
#     Claude sur le port 8931, pour le portier.
#
#  Si Playwright MCP s'arrête, le conteneur s'arrête aussi, et Docker le
#  relance (restart: unless-stopped).
# =====================================================================

ouvert() { (exec 3<>"/dev/tcp/$1/$2") 2> /dev/null; }

# On attend (2 minutes au plus) que Chrome soit joignable d'une des deux façons.
mode=""
for _ in $(seq 1 60); do
  if ouvert 127.0.0.1 9222; then mode="direct"; break; fi
  if ouvert "${CHROME_HOTE:-chrome}" "${CHROME_PORT_RELAIS:-9223}"; then mode="relais"; break; fi
  sleep 2
done
# Rien trouvé : on suppose le nouveau plan (le relais suivra Chrome quand il arrivera).
mode="${mode:-relais}"

RELAIS=""
if [ "$mode" = "relais" ]; then
  node relais-cdp.js &
  RELAIS=$!
else
  echo "Chrome est dans le même réseau que le pont (ancien plan) : connexion directe, sans relais."
fi

node node_modules/@playwright/mcp/cli.js "$@" &
PONT=$!

# Arrêt propre quand Docker arrête le conteneur.
trap 'kill "$PONT" $RELAIS 2>/dev/null; wait; exit 0' TERM INT

wait "$PONT"
code=$?
[ -n "$RELAIS" ] && kill "$RELAIS" 2>/dev/null
echo "⚠️ Le pont MCP s'est arrêté (code $code) : Docker va le relancer."
exit "${code:-1}"
