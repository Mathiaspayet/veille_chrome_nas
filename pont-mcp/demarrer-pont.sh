#!/bin/bash
# =====================================================================
#  Démarrage du pont MCP, avec auto-réparation.
#
#  Le pont partage le réseau du conteneur chrome. Si ce conteneur est
#  redémarré seul (bouton « Redémarrer » de Container Manager…), le pont
#  reste branché sur l'ANCIEN réseau et ne voit plus Chrome. On le
#  détecte en ne voyant plus la prise 9222 pendant 2 minutes : le pont
#  s'arrête alors, et Docker le relance aussitôt, rebranché sur le réseau
#  actuel de Chrome. (Le délai laisse au veilleur de Chrome le temps de
#  relancer un Chrome simplement fermé.)
# =====================================================================

node node_modules/@playwright/mcp/cli.js "$@" &
PONT=$!

# Arrêt propre quand Docker arrête le conteneur.
trap 'kill "$PONT" 2>/dev/null; wait "$PONT"; exit 0' TERM INT

perdu=0
while kill -0 "$PONT" 2>/dev/null; do
  sleep 20 & wait $!
  if (exec 3<>/dev/tcp/127.0.0.1/9222) 2>/dev/null; then
    perdu=0
  else
    perdu=$((perdu + 20))
    if [ "$perdu" -ge 120 ]; then
      echo "⚠️ Chrome injoignable depuis 2 minutes : le pont redémarre pour se rebrancher."
      kill "$PONT" 2>/dev/null
      wait "$PONT"
      exit 1
    fi
  fi
done

# Le pont s'est arrêté de lui-même : on transmet son code de sortie.
wait "$PONT"
exit $?
