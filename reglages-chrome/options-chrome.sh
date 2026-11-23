# Options de démarrage ajoutées à Chrome à CHAQUE lancement,
# y compris quand tu le relances depuis le menu du bureau.
# (Ce fichier est lu par Chromium au démarrage : ne pas le renommer.)
#
#  --remote-debugging-port=9222 : la « prise » sur laquelle le robot se
#    branche. Elle n'est joignable que depuis l'intérieur du conteneur
#    (et du robot qui partage son réseau), jamais depuis ton réseau.
#  --lang=fr-FR : menus et sites en français.

export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --remote-debugging-port=9222 --lang=fr-FR"
