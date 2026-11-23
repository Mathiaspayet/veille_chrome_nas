#!/usr/bin/with-contenv bash
# =====================================================================
#  Veilleur de Chrome : si Chrome est fermé (croix de la fenêtre,
#  plantage…), il le relance tout seul en moins d'une minute, avec sa
#  « prise » de pilotage (port 9222) pour le pont MCP.
#
#  Ce fichier est lancé en permanence par le conteneur chrome-nas (c'est
#  un « service personnalisé » de l'image linuxserver, déposé dans
#  /custom-services.d). Ses messages apparaissent dans le journal du
#  conteneur : Container Manager → chrome-nas → Journal.
#
#  Ne pas modifier sur le NAS : il est remplacé par la tâche « Mettre à
#  jour le projet », et doit appartenir à root (chrome-nas.sh s'en charge).
# =====================================================================

dire() { echo "[veilleur-chrome] $(date '+%d/%m/%Y %H:%M:%S') $*"; }

# Réglages de la session du Chrome en marche, mémorisés pour pouvoir le
# relancer à l'identique (même écran, même bureau).
MEMOIRE=/tmp/veilleur-chrome.reglages

# Numéro du processus principal de Chrome (vide s'il est fermé).
chrome_principal() { pgrep -o -f '^/usr/lib/chromium/chromium' || true; }

# Remplit le tableau « reglages » pour relancer Chrome DANS le bureau.
preparer_reglages() {
  reglages=()
  local variable
  if [ -s "$MEMOIRE" ]; then
    # Cas habituel : les réglages exacts du Chrome lancé par le bureau.
    while IFS= read -r -d '' variable; do reglages+=("$variable"); done < "$MEMOIRE"
    return 0
  fi
  # Secours (Chrome fermé avant d'avoir été mémorisé) : on part des
  # réglages du gestionnaire de fenêtres (labwc)… mais labwc s'affiche
  # lui-même sur l'écran de l'affichage à distance, qui montre tout en
  # plein écran : il faut prendre l'écran que labwc offre à SES fenêtres.
  local session ecran_parent x_parent runtime ecran x
  session="$(pgrep -o -x labwc || true)"
  [ -n "$session" ] || return 1
  while IFS= read -r -d '' variable; do
    case "$variable" in
      WAYLAND_DISPLAY=*) ecran_parent="${variable#*=}" ;;
      DISPLAY=*) x_parent="${variable#*=}" ;;
      *) reglages+=("$variable") ;;
    esac
    case "$variable" in XDG_RUNTIME_DIR=*) runtime="${variable#*=}" ;; esac
  done < <(s6-setuidgid abc cat "/proc/$session/environ" 2>/dev/null)
  ecran="$(ls -1 "${runtime:-/config/.XDG}" 2>/dev/null | grep -E '^wayland-[0-9]+$' | grep -vx "${ecran_parent:-}" | head -n 1)"
  x="$(ls -1 /tmp/.X11-unix 2>/dev/null | sed -n 's/^X\([0-9]*\)$/:\1/p' | grep -vx "${x_parent:-}" | head -n 1)"
  [ -n "$ecran" ] || return 1
  reglages+=("WAYLAND_DISPLAY=$ecran" "LABWC_PID=$session" "XDG_CURRENT_DESKTOP=labwc:wlroots")
  [ -n "$x" ] && reglages+=("DISPLAY=$x")
  return 0
}

# Laisse le temps au bureau et à Chrome de démarrer avec le conteneur.
sleep 90
dire "en service : je vérifie toutes les 20 secondes que Chrome est ouvert."

while true; do
  principal="$(chrome_principal)"
  if [ -n "$principal" ]; then
    # Chrome tourne : on mémorise (ou rafraîchit) ses réglages.
    if s6-setuidgid abc cat "/proc/$principal/environ" > "$MEMOIRE.tmp" 2>/dev/null && [ -s "$MEMOIRE.tmp" ]; then
      chmod 600 "$MEMOIRE.tmp" && mv -f "$MEMOIRE.tmp" "$MEMOIRE"
    fi
  elif ! preparer_reglages; then
    dire "Chrome est fermé, mais le bureau n'est pas encore prêt : j'attends."
  else
    dire "Chrome était fermé : je le relance."
    # Même lancement que le menu du bureau (« Chromium »), avec
    # l'utilisateur du bureau ; les options (port 9222, français)
    # viennent de /etc/chromium.d.
    s6-setuidgid abc env -i "${reglages[@]}" setsid /usr/bin/wrapped-chromium > /dev/null 2>&1 &
    # Laisse à Chrome le temps de démarrer avant de revérifier.
    sleep 40
    if [ -n "$(chrome_principal)" ]; then
      dire "Chrome est relancé."
    else
      dire "Chrome n'a pas redémarré : nouvel essai dans une minute."
      sleep 20
    fi
  fi
  sleep 20
done
