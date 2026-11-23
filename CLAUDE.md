# Notes pour Claude Code

## Contexte
- Projet de Mathias : un Chromium allumé en permanence sur son NAS (conteneur
  `linuxserver/chromium`), piloté par des scripts Python/Playwright
  (conteneur `robot`) via le protocole CDP (port 9222).
- NAS : Synology **DS1522+** (AMD Ryzen R1600, x86-64, 2 cœurs, 8 Go),
  **DSM 7.4**. Mathias n'utilise **pas SSH** : toutes les commandes passent
  par le **Planificateur de tâches** (utilisateur root), qui appelle
  `chrome-nas.sh` (actions : `demarrer`, `robot NOM.py`, `arreter`).
  Le projet est dans `/volume1/docker/veille_chrome_nas`.
- Sur le même NAS tournent d'autres projets de Mathias (gestion-locative,
  immo, menus-famille, suivi-prix-essence). Un seul **Watchtower** (installé
  avec gestion-locative) met à jour tous les conteneurs portant l'étiquette
  `com.centurylinklabs.watchtower.scope=gestion-locative`. Le conteneur
  chrome la porte ; le robot non (image fabriquée sur le NAS, conteneur
  éphémère). Ne pas ajouter de second Watchtower ni de tâche de mise à
  jour planifiée.
- Ports déjà pris sur le NAS par ces projets : 8000, 8010, 8020, 8080,
  8081, 8095, 8100. Ce projet utilise 3001.
- Mathias débute en code : toujours répondre **en français**, de façon
  **didactique** (expliquer les termes techniques simplement). Les commentaires
  du code et les messages affichés par les scripts sont en français.

## Règles du projet
- Ne jamais écrire de mot de passe ni d'identifiant de site dans le dépôt.
  L'utilisateur se connecte lui-même dans le Chrome du NAS ; les scripts
  réutilisent ses cookies. `reglages.env` et `donnees/` sont dans `.gitignore`.
- Un script ne valide jamais un paiement ni une commande : il prépare, et
  l'humain valide.
- Le port 9222 ne doit jamais être publié : le robot y accède en partageant
  le réseau du conteneur chrome (`network_mode: "service:chrome"`).
- Un script se branche avec `connecter_chrome()` (robot/scripts/outils.py),
  travaille dans un nouvel onglet, le referme, puis appelle
  `navigateur.close()`. Ce close() débranche le script sans fermer Chrome.
- Tout passe par `chrome-nas.sh` : il lit `reglages.env` (copie nettoyée des
  fins de ligne Windows, passée avec `--env-file`), détecte PUID/PGID à partir
  du propriétaire du dossier et écrit dans `donnees/journal.txt`. Toute
  nouvelle fonction doit rester utilisable depuis le Planificateur de tâches
  (sans terminal interactif, d'où `run -T`).

## Pièges déjà rencontrés (et réglés)
- Les options de Chrome passent par `/etc/chromium.d/` (fichier
  `reglages-chrome/options-chrome.sh`) plutôt que par `CHROME_CLI`, pour que
  la prise 9222 existe aussi quand Chrome est relancé depuis le menu du bureau.
- `DISABLE_IPV6=true` est nécessaire sur les hôtes sans IPv6 : sinon, nginx
  ne démarre pas et la page d'accès (port 3001) ne répond pas.
- Le Docker de Synology ne crée PAS les dossiers manquants d'un montage
  (« Bind mount failed: ... does not exist ») : `chrome-nas.sh` crée
  `donnees/chrome` et `donnees/captures` avant de lancer Docker. Tout
  nouveau dossier monté doit être créé de la même façon.
- Le robot a besoin de `libatomic1` (python:3.13-slim), sinon le pilote
  Playwright ne démarre pas.
- Test de bout en bout : créer `reglages.env`, puis
  `bash chrome-nas.sh demarrer` et `bash chrome-nas.sh robot test_connexion.py`.
