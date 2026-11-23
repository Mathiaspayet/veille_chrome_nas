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
#
#  Les actions :
#    demarrer : installe (ou rafraîchit) Chrome, le démarre et prépare
#               le robot. Sans danger : on peut la relancer.
#               Ensuite, les mises à jour de Chrome sont faites par le
#               Watchtower déjà présent sur le NAS (portée gestion-locative).
#    robot NOM : lance le script NOM du dossier robot/scripts
#               (Chrome doit être démarré).
#    arreter  : arrête Chrome (pour libérer la mémoire du NAS).
#
#  Tout ce qui se passe est noté dans donnees/journal.txt
# =====================================================================

set -u

# --- Préparatifs ------------------------------------------------------

# Le dossier du projet = celui où se trouve ce script.
DOSSIER="$(cd "$(dirname "$0")" && pwd)" || exit 1
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
mkdir -p "$DOSSIER/donnees/chrome" "$DOSSIER/donnees/captures"
chown "$PUID:$PGID" "$DOSSIER/donnees" "$DOSSIER/donnees/chrome" "$DOSSIER/donnees/captures" 2>/dev/null
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

# Raccourci : docker compose avec nos réglages.
compose() { executer "${DC[@]}" --env-file "$REGLAGES_PROPRES" "$@"; }

# Numéro interne (identifiant) d'une image Docker, vide si absente.
id_image() { docker image inspect -f '{{.Id}}' "$1" 2>/dev/null; }

# --- Les actions -------------------------------------------------------

demarrer() {
  verifier_reglages
  local image_chrome="lscr.io/linuxserver/chromium:latest"
  local image_robot="veille_chrome_nas-robot"
  local ancien_chrome ancien_robot
  ancien_chrome="$(id_image "$image_chrome")"
  ancien_robot="$(id_image "$image_robot")"

  journal "Téléchargement de la dernière version de Chrome (la 1re fois : environ 1,5 Go, patience)…"
  if ! compose pull --quiet chrome; then
    journal "⚠️ Téléchargement impossible (pas d'Internet ?). On garde la version déjà présente."
  fi

  journal "Démarrage de Chrome…"
  if ! compose up -d --remove-orphans chrome; then
    journal "❌ Chrome n'a pas pu démarrer. Les messages ci-dessus donnent la raison."
    exit 1
  fi

  journal "Préparation du robot…"
  if ! compose --profile robot build --pull robot; then
    if [ -n "$(id_image "$image_robot")" ]; then
      journal "⚠️ Mise à jour du robot impossible. On garde la version déjà présente."
    else
      journal "❌ Le robot n'a pas pu être préparé. Les messages ci-dessus donnent la raison."
      exit 1
    fi
  fi

  # Supprime les anciennes versions remplacées, pour ne pas remplir le disque.
  local nouveau
  nouveau="$(id_image "$image_chrome")"
  if [ -n "$ancien_chrome" ] && [ "$ancien_chrome" != "$nouveau" ]; then
    docker image rm "$ancien_chrome" > /dev/null 2>&1 && journal "Ancienne version de Chrome supprimée."
  fi
  nouveau="$(id_image "$image_robot")"
  if [ -n "$ancien_robot" ] && [ "$ancien_robot" != "$nouveau" ]; then
    docker image rm "$ancien_robot" > /dev/null 2>&1 && journal "Ancienne version du robot supprimée."
  fi

  local port
  port="$(sed -n 's/^PORT_CHROME=//p' "$REGLAGES_PROPRES" | tail -n 1)"
  journal "✅ Chrome tourne. Ouvre https://IP-DU-NAS:${port:-3001} depuis ton PC."
}

robot() {
  local nom="${1:-}"
  if [ -z "$nom" ]; then
    journal "❌ Indique le script à lancer, par exemple : chrome-nas.sh robot test_connexion.py"
    exit 1
  fi
  shift
  if [ ! -f "robot/scripts/$nom" ]; then
    journal "❌ Le script robot/scripts/$nom n'existe pas. Scripts disponibles :"
    journal "   $(cd robot/scripts && ls -- *.py | grep -v '^outils.py$' | tr '\n' ' ')"
    exit 1
  fi
  verifier_reglages
  if [ "$(docker inspect -f '{{.State.Running}}' chrome-nas 2>/dev/null)" != "true" ]; then
    journal "❌ Chrome n'est pas démarré. Lance d'abord la tâche « Chrome NAS – Démarrer »."
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
  journal "Arrêt de Chrome…"
  compose down && journal "✅ Chrome est arrêté. Tes connexions restent enregistrées pour la prochaine fois."
}

# --- Aiguillage ---------------------------------------------------------

ACTION="${1:-}"
[ $# -gt 0 ] && shift
journal "===== Tâche : ${ACTION:-(aucune)} $* ====="
case "$ACTION" in
  demarrer) demarrer ;;
  robot)    robot "$@" ;;
  arreter)  arreter ;;
  *)
    journal "❌ Action inconnue « $ACTION ». Choix possibles : demarrer, robot NOM_DU_SCRIPT, arreter."
    exit 1
    ;;
esac
