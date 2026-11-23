"""Test : le robot arrive-t-il à piloter le Chrome du NAS ?

Ce que fait ce script :
  1. il se branche sur le Chrome du NAS ;
  2. il affiche la liste des onglets déjà ouverts ;
  3. il ouvre un nouvel onglet sur une page (par défaut https://www.example.com),
     affiche son titre et prend une capture d'écran ;
  4. il referme SON onglet et se débranche, sans fermer Chrome.

Si tu regardes le Chrome du NAS depuis ton PC pendant ce temps,
tu vois l'onglet apparaître puis disparaître.

Lancement : tâche du Planificateur de tâches du Synology, avec la ligne
    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh robot test_connexion.py
Pour tester une autre page, ajoute son adresse à la fin :
    bash /volume1/docker/veille_chrome_nas/chrome-nas.sh robot test_connexion.py https://www.wikipedia.org
"""

import sys

from playwright.sync_api import sync_playwright

from outils import capture, connecter_chrome

# La page à ouvrir : celle donnée après le nom du script, sinon example.com.
ADRESSE_TEST = sys.argv[1] if len(sys.argv) > 1 else "https://www.example.com"

with sync_playwright() as p:
    navigateur, contexte = connecter_chrome(p)
    print(f"✅ Branché sur Chrome {navigateur.version}")

    print("Onglets déjà ouverts :")
    for onglet in contexte.pages:
        print(f"  - {onglet.title() or '(sans titre)'} → {onglet.url}")

    page = contexte.new_page()
    try:
        print(f"Ouverture de {ADRESSE_TEST} ...")
        page.goto(ADRESSE_TEST, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2_000)  # laisse 2 secondes à la page pour s'afficher
        print(f"Titre de la page : {page.title()}")
        print(f"📸 Capture enregistrée : {capture(page, 'test')}")
    except Exception as erreur:
        print(f"❌ La page n'a pas pu être ouverte : {erreur}")
        sys.exit(1)
    finally:
        page.close()  # on ferme seulement l'onglet ouvert par le robot

    # Pour un Chrome « emprunté » comme ici, close() débranche le robot
    # sans fermer Chrome : tes sessions restent ouvertes.
    navigateur.close()

print("Terminé. Chrome est toujours ouvert sur le NAS.")
