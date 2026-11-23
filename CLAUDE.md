# Notes pour Claude Code

## Contexte
- Projet de Mathias : un Chromium allumé en permanence sur son NAS (conteneur
  `linuxserver/chromium`), piloté par des scripts Python/Playwright
  (conteneur `robot`) via le protocole CDP (port 9222).
- Mathias débute en code : toujours répondre **en français**, de façon
  **didactique** (expliquer les termes techniques simplement). Les commentaires
  du code et les messages affichés par les scripts sont en français.

## Règles du projet
- Ne jamais écrire de mot de passe ni d'identifiant de site dans le dépôt.
  L'utilisateur se connecte lui-même dans le Chrome du NAS ; les scripts
  réutilisent ses cookies. `.env` et `donnees/` sont dans `.gitignore`.
- Un script ne valide jamais un paiement ni une commande : il prépare, et
  l'humain valide.
- Le port 9222 ne doit jamais être publié : le robot y accède en partageant
  le réseau du conteneur chrome (`network_mode: "service:chrome"`).
- Un script se branche avec `connecter_chrome()` (robot/scripts/outils.py),
  travaille dans un nouvel onglet, le referme, puis appelle
  `navigateur.close()`. Ce close() débranche le script sans fermer Chrome.

## Pièges déjà rencontrés (et réglés)
- Les options de Chrome passent par `/etc/chromium.d/` (fichier
  `reglages-chrome/options-chrome.sh`) plutôt que par `CHROME_CLI`, pour que
  la prise 9222 existe aussi quand Chrome est relancé depuis le menu du bureau.
- `DISABLE_IPV6=true` est nécessaire sur les hôtes sans IPv6 : sinon, nginx
  ne démarre pas et la page d'accès (port 3001) ne répond pas.
- Le robot a besoin de `libatomic1` (python:3.13-slim), sinon le pilote
  Playwright ne démarre pas.
- Test de bout en bout : `docker compose up -d`, puis
  `docker compose run --rm robot`.
