#!/bin/bash
# =====================================================================
#  Télécommande du projet, appelée par le Planificateur de tâches
#  du Synology (utilisateur root). Elle remplace les commandes
#  qu'on taperait sinon en SSH.
#
#  À écrire dans la case « Script défini par l'utilisateur » :
#    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh demarrer
#    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh robot test_connexion.py
#    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh arreter
#    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh mettre-a-jour
#
#  Les actions :
#    demarrer : télécharge Chrome, le pont MCP, le portier et le robot
#               (les trois derniers sont fabriqués par GitHub), puis
#               démarre le tout. Sans danger : on peut la relancer.
#               Ensuite, les mises à jour sont faites par le Watchtower
#               déjà présent sur le NAS (portée gestion-locative).
#    robot NOM : lance le script NOM du dossier robot/scripts
#               (Chrome doit être démarré).
#    arreter  : arrête Chrome et le pont (pour libérer la mémoire du NAS).
#    mettre-a-jour : télécharge la dernière version des fichiers du
#               projet sur GitHub (sans toucher à reglages.env ni à
#               donnees/), puis enchaîne avec « demarrer ».
#
#  La tâche « Mettre à jour le projet » utilise une ligne plus longue, qui
#  télécharge d'abord la dernière version de ce script lui-même dans le
#  dossier du projet (voir README) : elle marche même sur une installation
#  vide ou ancienne.
#
#  Tout ce qui se passe est noté dans donnees/journal.txt
# =====================================================================

set -u

# --- Préparatifs ------------------------------------------------------

# Le dossier du projet = celui où se trouve ce script (ou celui donné
# par DOSSIER_PROJET, quand le script est lancé depuis un autre endroit).
DOSSIER="${DOSSIER_PROJET:-$(cd "$(dirname "$0")" && pwd)}"
if [ ! -d "$DOSSIER" ]; then
  echo "❌ Le dossier du projet $DOSSIER n'existe pas : crée-le d'abord dans File Station." >&2
  exit 1
fi
cd "$DOSSIER" || exit 1

# Sur Synology, Docker est rangé dans /usr/local/bin.
export PATH="/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin:$PATH"

# Les fichiers créés appartiendront au même utilisateur que le dossier
# du projet (toi), pour que tu puisses les ouvrir et les supprimer.
PUID="$(ls -nd "$DOSSIER" | awk '{print $3}')"
PGID="$(ls -nd "$DOSSIER" | awk '{print $4}')"
export PUID PGID

# Le Docker de Synology refuse de démarrer un conteneur si un dossier
# qu'on lui « prête » n'existe pas encore (« Bind mount failed ») :
# on les crée donc à l'avance, et on te les attribue.
mkdir -p "$DOSSIER/donnees/chrome" "$DOSSIER/donnees/captures" "$DOSSIER/donnees/portier"
chown "$PUID:$PGID" "$DOSSIER/donnees" "$DOSSIER/donnees/chrome" "$DOSSIER/donnees/captures" \
  "$DOSSIER/donnees/portier" 2>/dev/null
JOURNAL="$DOSSIER/donnees/journal.txt"

# Le journal ne garde que les 2000 dernières lignes.
if [ -f "$JOURNAL" ] && [ "$(wc -l < "$JOURNAL")" -gt 2000 ]; then
  tail -n 2000 "$JOURNAL" > "$JOURNAL.tmp" && mv "$JOURNAL.tmp" "$JOURNAL"
fi

# Écrit une ligne datée dans le journal (et à l'écran).
journal() { echo "[$(date '+%d/%m/%Y %H:%M:%S')] $*" | tee -a "$JOURNAL"; }

# Lance une commande et recopie tout ce qu'elle affiche dans le journal.
executer() { "$@" 2>&1 | tee -a "$JOURNAL"; return "${PIPESTATUS[0]}"; }

# Rend au propriétaire du dossier les fichiers créés par ce script.
rendre_les_fichiers() {
  chown "$PUID:$PGID" "$DOSSIER/donnees" "$JOURNAL" 2>/dev/null
  [ -d "$DOSSIER/donnees/captures" ] && chown -R "$PUID:$PGID" "$DOSSIER/donnees/captures" 2>/dev/null
  rm -f "${REGLAGES_PROPRES:-}"
}
trap rendre_les_fichiers EXIT

# Trouve la commande « docker compose » (ou l'ancienne « docker-compose »).
if docker compose version > /dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose > /dev/null 2>&1; then
  DC=(docker-compose)
else
  journal "❌ Docker est introuvable. Installe le paquet « Container Manager » (étape 1 du guide)."
  exit 1
fi

# --- Vérification de reglages.env -------------------------------------

verifier_reglages() {
  if [ ! -f reglages.env ]; then
    journal "❌ Le fichier reglages.env est introuvable dans $DOSSIER."
    journal "   Renomme reglages-exemple.env en reglages.env et remplis-le (étape 4 du guide)."
    exit 1
  fi
  # Copie « nettoyée » des réglages (retours à la ligne façon Windows
  # enlevés), lue par Docker puis effacée à la fin.
  REGLAGES_PROPRES="$(mktemp)"
  tr -d '\r' < reglages.env > "$REGLAGES_PROPRES"

  local util mdp
  util="$(sed -n 's/^CHROME_UTILISATEUR=//p' "$REGLAGES_PROPRES" | tail -n 1)"
  mdp="$(sed -n 's/^CHROME_MOT_DE_PASSE=//p' "$REGLAGES_PROPRES" | tail -n 1)"
  if [ -z "$util" ]; then
    journal "❌ CHROME_UTILISATEUR est vide dans reglages.env."
    exit 1
  fi
  if [[ "$mdp" == *remplace-moi* ]] || [ "${#mdp}" -lt 12 ]; then
    journal "❌ Choisis un vrai mot de passe (au moins 12 caractères) pour CHROME_MOT_DE_PASSE dans reglages.env."
    exit 1
  fi
  if [[ ! "$mdp" =~ ^[A-Za-z0-9_-]+$ ]]; then
    journal "❌ Le mot de passe de reglages.env ne doit contenir que des lettres sans accents, des chiffres, - ou _."
    exit 1
  fi
}

# Les images utilisées : celle de Chrome (linuxserver), et les trois
# fabriquées par GitHub pour ce projet.
declare -A IMAGES=(
  [chrome]="lscr.io/linuxserver/chromium:latest"
  [robot]="ghcr.io/mathiaspayet/veille_chrome_nas-robot:latest"
  [pont-mcp]="ghcr.io/mathiaspayet/veille_chrome_nas-pont-mcp:latest"
  [portier]="ghcr.io/mathiaspayet/veille_chrome_nas-portier:latest"
)

# Raccourci : docker compose avec nos réglages.
compose() { executer "${DC[@]}" --env-file "$REGLAGES_PROPRES" "$@"; }

# Numéro interne (identifiant) d'une image Docker, vide si absente.
id_image() { docker image inspect -f '{{.Id}}' "$1" 2>/dev/null; }

# --- Les actions -------------------------------------------------------

demarrer() {
  verifier_reglages
  local -A anciennes
  local nom
  for nom in "${!IMAGES[@]}"; do anciennes[$nom]="$(id_image "${IMAGES[$nom]}")"; done

  journal "Téléchargement des dernières versions de Chrome, du pont MCP, du portier et du robot"
  journal "(la 1re fois : environ 2 Go, patience)…"
  if ! compose --profile robot pull --quiet; then
    for nom in "${!IMAGES[@]}"; do
      if [ -z "$(id_image "${IMAGES[$nom]}")" ]; then
        journal "❌ Impossible de télécharger « $nom » (${IMAGES[$nom]})."
        journal "   Pas d'Internet ? Ou, si c'est la première fois : les images du projet sont-elles"
        journal "   bien « publiques » sur GitHub ? (voir le guide, section pont MCP)"
        exit 1
      fi
    done
    journal "⚠️ Téléchargement impossible pour l'instant. On garde les versions déjà présentes."
  fi

  journal "Démarrage de Chrome, du pont MCP et du portier…"
  if ! compose up -d --remove-orphans; then
    journal "❌ Le démarrage a échoué. Les messages ci-dessus donnent la raison."
    exit 1
  fi

  # Supprime les anciennes versions remplacées, pour ne pas remplir le disque.
  for nom in "${!IMAGES[@]}"; do
    if [ -n "${anciennes[$nom]}" ] && [ "${anciennes[$nom]}" != "$(id_image "${IMAGES[$nom]}")" ]; then
      docker image rm "${anciennes[$nom]}" > /dev/null 2>&1 && journal "Ancienne version de « $nom » supprimée."
    fi
  done

  local port
  port="$(sed -n 's/^PORT_CHROME=//p' "$REGLAGES_PROPRES" | tail -n 1)"
  journal "✅ Chrome tourne. Ouvre https://IP-DU-NAS:${port:-3001} depuis ton PC."
  journal "✅ Pont MCP et portier démarrés (voir le guide pour les relier à Claude)."
}

robot() {
  local nom="${1:-}"
  if [ -z "$nom" ]; then
    journal "❌ Indique le script à lancer, par exemple : chrome-nas.sh robot test_connexion.py"
    exit 1
  fi
  shift
  verifier_reglages
  if [ "$(docker inspect -f '{{.State.Running}}' chrome-nas 2>/dev/null)" != "true" ]; then
    journal "❌ Chrome n'est pas démarré. Lance d'abord la tâche « Chrome NAS – Démarrer »."
    exit 1
  fi
  # Dernière version du robot (ses scripts sont dans son image, fabriquée par GitHub).
  if ! "${DC[@]}" --env-file "$REGLAGES_PROPRES" --profile robot pull --quiet robot > /dev/null 2>&1; then
    if [ -z "$(id_image "${IMAGES[robot]}")" ]; then
      journal "❌ Impossible de télécharger le robot (pas d'Internet ?)."
      exit 1
    fi
    journal "⚠️ Mise à jour du robot impossible pour l'instant. On garde la version déjà présente."
  fi
  if ! docker run --rm --entrypoint test "${IMAGES[robot]}" -f "scripts/$nom"; then
    journal "❌ Le script « $nom » n'existe pas. Scripts disponibles :"
    journal "   $(docker run --rm --entrypoint ls "${IMAGES[robot]}" scripts | grep -v '^outils.py$' | grep '\.py$' | tr '\n' ' ')"
    exit 1
  fi
  journal "Lancement du robot : $nom $*"
  if compose run --rm -T robot "scripts/$nom" "$@"; then
    journal "✅ Robot terminé sans erreur."
  else
    journal "❌ Le robot s'est arrêté sur une erreur (voir les lignes ci-dessus)."
    exit 1
  fi
}

arreter() {
  verifier_reglages
  journal "Arrêt de Chrome et du pont MCP…"
  compose down && journal "✅ Chrome et le pont sont arrêtés. Tes connexions restent enregistrées pour la prochaine fois."
}

mettre_a_jour() {
  local depot="Mathiaspayet/veille_chrome_nas"
  # BRANCHE_PROJET permet de tester une autre branche (sinon : main).
  local branche="${BRANCHE_PROJET:-main}"
  local adresse sha tmp source
  # On demande d'abord à GitHub le numéro exact de la dernière version :
  # l'archive « par nom de branche » peut avoir quelques minutes de retard
  # (cache de GitHub), celle d'un numéro précis jamais.
  sha="$(curl -fsSL --max-time 30 -H 'Accept: application/vnd.github.sha' \
    "https://api.github.com/repos/$depot/commits/$branche" 2>/dev/null)"
  if [[ "$sha" =~ ^[0-9a-f]{40}$ ]]; then
    adresse="https://github.com/$depot/archive/$sha.tar.gz"
  else
    sha=""
    adresse="https://github.com/$depot/archive/refs/heads/$branche.tar.gz"
  fi
  tmp="$(mktemp -d)"
  journal "Téléchargement de la dernière version du projet depuis GitHub (version ${sha:0:7})…"
  if ! curl -fsSL --max-time 300 -o "$tmp/projet.tar.gz" "$adresse"; then
    journal "❌ Téléchargement impossible (pas d'Internet, ou GitHub indisponible). Rien n'a été modifié."
    rm -rf "$tmp"; exit 1
  fi
  mkdir "$tmp/extrait"
  if ! tar -xzf "$tmp/projet.tar.gz" -C "$tmp/extrait"; then
    journal "❌ Archive illisible. Rien n'a été modifié."
    rm -rf "$tmp"; exit 1
  fi
  source="$(find "$tmp/extrait" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [ ! -f "$source/docker-compose.yml" ] || [ ! -f "$source/chrome-nas.sh" ]; then
    journal "❌ Archive incomplète. Rien n'a été modifié."
    rm -rf "$tmp"; exit 1
  fi

  # Copie fichier par fichier. Jamais reglages.env ni donnees/ : tes
  # réglages et tes données restent intacts. Chaque fichier est d'abord
  # copié à côté, puis renommé : ce script peut ainsi se remplacer
  # lui-même pendant qu'il tourne.
  local fichier nb=0
  while IFS= read -r -d '' fichier; do
    fichier="${fichier#./}"
    mkdir -p "$DOSSIER/$(dirname "$fichier")"
    cp "$source/$fichier" "$DOSSIER/$fichier.nouveau" && mv -f "$DOSSIER/$fichier.nouveau" "$DOSSIER/$fichier"
    chown "$PUID:$PGID" "$DOSSIER/$fichier" 2>/dev/null
    nb=$((nb + 1))
  done < <(cd "$source" && find . -type f ! -path './donnees/*' ! -name 'reglages.env' -print0)
  rm -rf "$tmp"
  journal "✅ Projet mis à jour ($nb fichiers, version ${sha:0:7}). Démarrage de la nouvelle version…"

  # On relance la NOUVELLE version du script pour la suite.
  rendre_les_fichiers
  trap - EXIT
  exec bash "$DOSSIER/chrome-nas.sh" demarrer
}

# --- Aiguillage ---------------------------------------------------------

ACTION="${1:-}"
[ $# -gt 0 ] && shift
journal "===== Tâche : ${ACTION:-(aucune)} $* ====="
case "$ACTION" in
  demarrer) demarrer ;;
  robot)    robot "$@" ;;
  arreter)  arreter ;;
  mettre-a-jour) mettre_a_jour ;;
  *)
    journal "❌ Action inconnue « $ACTION ». Choix possibles : demarrer, robot NOM_DU_SCRIPT, arreter, mettre-a-jour."
    exit 1
    ;;
esac
