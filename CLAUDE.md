# Notes pour Claude Code

## Contexte
- Projet de Mathias : un Chromium allumé en permanence sur son NAS (conteneur
  `linuxserver/chromium`), piloté par Claude via un connecteur MCP (pont
  Playwright MCP + portier OAuth, voir plus bas) par le protocole CDP
  (port 9222). Le « robot » (scripts Python/Playwright) a été retiré le
  23/11/2026 à la demande de Mathias : tout passe par le pont MCP.
- NAS : Synology **DS1522+** (AMD Ryzen R1600, x86-64, 2 cœurs, 8 Go),
  **DSM 7.4**. Mathias n'utilise **pas SSH** : toutes les commandes passent
  par le **Planificateur de tâches** (utilisateur root), qui appelle
  `chrome-nas.sh` (actions : `demarrer`, `arreter`, `mettre-a-jour`).
  Le projet est dans `/volume1/docker/veille_chrome_nas`.
- Sur le même NAS tournent d'autres projets de Mathias (gestion-locative,
  immo, menus-famille, suivi-prix-essence). Un seul **Watchtower** (installé
  avec gestion-locative) met à jour tous les conteneurs portant l'étiquette
  `com.centurylinklabs.watchtower.scope=gestion-locative`. Les 3
  conteneurs (chrome, pont-mcp, portier) la portent. Ne pas ajouter de
  second Watchtower ni de tâche de mise à jour planifiée.
- Mathias publie ses applications par le proxy inversé de DSM
  (`*.bignasmathias.synology.me`). Pour Chrome : destination **HTTPS**
  localhost:3001, en-têtes **WebSocket**, et profil de contrôle d'accès
  **réseau local uniquement** (un navigateur connecté à ses comptes ne doit
  pas être joignable depuis Internet ; accès extérieur = VPN).
- Ports déjà pris sur le NAS par ces projets : 8000, 8010, 8020, 8080,
  8081, 8095, 8100. Ce projet utilise 3001 (Chrome) et 8930 (portier,
  publié sur 127.0.0.1 seulement).
- **Pont MCP** (pour que Claude pilote Chrome via un connecteur claude.ai) :
  conteneur `pont-mcp` (Playwright MCP, version fixée dans
  pont-mcp/package-lock.json, écoute 127.0.0.1:8931, `--cdp-endpoint`) et
  conteneur `portier` (portier/portier.py : OAuth 2.1 + DCR + PKCE copié de
  menus-famille, mot de passe = celui de reglages.env, verrouillage 15 min
  après 5 échecs, outil `browser_run_code_unsafe` retiré de tools/list et
  bloqué dans tools/call). Proxy inversé DSM : `mcp-chrome.…synology.me` →
  HTTP 127.0.0.1:8930, sans profil d'accès (Claude vient d'Internet).
  Tests : `pytest portier/test_portier.py`.
- **Images fabriquées par GitHub** (.github/workflows/images.yml) : à
  chaque push sur `main` (et chaque lundi), tests du portier puis
  fabrication et publication de `ghcr.io/mathiaspayet/veille_chrome_nas-
  {pont-mcp,portier}:latest`. Ces paquets GHCR sont PUBLICS d'office
  (dépôt public ; vérifié le 23/11/2026 par un jeton anonyme). Le NAS ne
  fabrique plus rien : `demarrer` fait `pull` + `up`. Le paquet
  `veille_chrome_nas-robot` (ancien) peut être supprimé sur GitHub ;
  `demarrer` supprime son image et l'ancien dossier `robot/` du NAS.
- Pont et portier partagent le réseau de chrome et portent l'étiquette de
  portée : Watchtower installe leurs nouvelles images. Vérifié avec
  containrrr/watchtower 1.7.1 : quand Chrome est mis à jour, Watchtower les
  arrête puis les recrée rebranchés sur le nouveau Chrome, et les jetons
  (SQLite dans donnees/portier) restent valables.
- `chrome-nas.sh mettre-a-jour` demande à l'API GitHub le numéro (SHA) du
  dernier commit de `main`, télécharge l'archive de CE numéro (l'archive
  « par nom de branche » est mise en cache quelques minutes par GitHub :
  constaté), remplace les fichiers (jamais reglages.env ni donnees/), puis
  relance `demarrer` avec la nouvelle version du script. Les fichiers
  supprimés du dépôt restent sur le NAS. Test d'une branche :
  `BRANCHE_PROJET=nom-de-branche`. La tâche DSM « Mettre à jour le
  projet » fait `cd` dans le dossier, y télécharge chrome-nas.sh
  (raw.githubusercontent.com, en cache ~5 min : peut être l'ancienne
  version, ce qui ne gêne pas) puis lance `mettre-a-jour` : elle marche
  aussi sur un dossier vide (installation neuve, sans ZIP).
- Mathias débute en code : toujours répondre **en français**, de façon
  **didactique** (expliquer les termes techniques simplement). Les commentaires
  du code et les messages affichés par les scripts sont en français.

## Règles du projet
- Ne jamais écrire de mot de passe ni d'identifiant de site dans le dépôt.
  L'utilisateur se connecte lui-même dans le Chrome du NAS ; les scripts
  réutilisent ses cookies. `reglages.env` et `donnees/` sont dans `.gitignore`.
- Un script ne valide jamais un paiement ni une commande : il prépare, et
  l'humain valide.
- Le port 9222 ne doit jamais être publié : le pont y accède en partageant
  le réseau du conteneur chrome (`network_mode: "service:chrome"`).
- Tout passe par `chrome-nas.sh` : il lit `reglages.env` (copie nettoyée des
  fins de ligne Windows, passée avec `--env-file`), détecte PUID/PGID à partir
  du propriétaire du dossier et écrit dans `donnees/journal.txt`. Toute
  nouvelle fonction doit rester utilisable depuis le Planificateur de tâches
  (sans terminal interactif).

## Pièges déjà rencontrés (et réglés)
- Les options de Chrome passent par `/etc/chromium.d/` (fichier
  `reglages-chrome/options-chrome.sh`) plutôt que par `CHROME_CLI`, pour que
  la prise 9222 existe aussi quand Chrome est relancé depuis le menu du bureau.
- `DISABLE_IPV6=true` est nécessaire sur les hôtes sans IPv6 : sinon, nginx
  ne démarre pas et la page d'accès (port 3001) ne répond pas.
- Le Docker de Synology ne crée PAS les dossiers manquants d'un montage
  (« Bind mount failed: ... does not exist ») : `chrome-nas.sh` crée
  `donnees/chrome` et `donnees/portier` avant de lancer Docker. Tout
  nouveau dossier monté doit être créé de la même façon.
- L'Éditeur de texte de DSM affiche mal les emojis récents (au-delà de
  U+FFFF, ex. 📸) dans `journal.txt`. Dans les messages des scripts,
  n'utiliser que ✅ ❌ ⚠️ (qui s'affichent bien) ou du texte simple.
- Test de bout en bout : créer `reglages.env`, puis `bash chrome-nas.sh
  demarrer`, puis le parcours OAuth + appels MCP à travers le portier
  (127.0.0.1:8930) : enregistrement, autorisation, jeton, initialize,
  tools/list, browser_navigate.
