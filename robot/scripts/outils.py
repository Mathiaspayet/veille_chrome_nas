"""Petites fonctions réutilisables par tous les scripts du robot.

Les autres scripts les importent avec, par exemple :
    from outils import connecter_chrome, capture
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Adresse de la « prise » de pilotage de Chrome (définie dans le Dockerfile).
ADRESSE_CHROME = os.environ.get("CDP_URL", "http://127.0.0.1:9222")

# Dossier où ranger les captures d'écran (donnees/captures sur le NAS).
DOSSIER_CAPTURES = Path(os.environ.get("DOSSIER_CAPTURES", "/app/captures"))


def connecter_chrome(playwright):
    """Se branche sur le Chrome du NAS et renvoie (navigateur, contexte).

    Le « contexte », c'est la session Chrome où TU t'es connecté à tes
    sites : une page ouverte dedans profite de tes connexions (cookies).
    """
    try:
        navigateur = playwright.chromium.connect_over_cdp(ADRESSE_CHROME, timeout=15_000)
    except Exception as erreur:
        print(f"❌ Impossible de joindre Chrome à l'adresse {ADRESSE_CHROME}.")
        print("   - Le conteneur « chrome-nas » est-il démarré ? Si oui, attends")
        print("     une minute (Chrome met un peu de temps à se lancer).")
        print("   - La fenêtre Chrome a-t-elle été fermée ? Rouvre-la : clic droit")
        print("     sur le fond du bureau puis « Chromium », ou redémarre le conteneur.")
        print(f"   Détail technique : {erreur}")
        sys.exit(1)

    if not navigateur.contexts:
        print("❌ Chrome répond, mais aucune fenêtre n'est ouverte.")
        print("   Redémarre le conteneur « chrome-nas », puis réessaie.")
        sys.exit(1)

    return navigateur, navigateur.contexts[0]


def capture(page, nom):
    """Prend une capture d'écran de la page et renvoie le chemin du fichier."""
    DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chemin = DOSSIER_CAPTURES / f"{horodatage}_{nom}.png"
    page.screenshot(path=str(chemin))
    _donner_au_proprietaire(DOSSIER_CAPTURES, chemin)
    return chemin


def _donner_au_proprietaire(*chemins):
    """Le robot travaille en « root » (super-utilisateur). Sans ce petit
    réglage, tu ne pourrais pas supprimer ses captures depuis le NAS :
    on les attribue donc à ton utilisateur (PUID/PGID, trouvés par chrome-nas.sh)."""
    puid, pgid = os.environ.get("PUID"), os.environ.get("PGID")
    if not (puid and pgid):
        return
    for chemin in chemins:
        try:
            os.chown(chemin, int(puid), int(pgid))
        except (OSError, ValueError):
            pass  # pas grave : la capture est quand même enregistrée
