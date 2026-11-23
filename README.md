# Chrome sur le NAS, piloté par un robot

Ce projet installe sur ton NAS un **navigateur Chrome allumé en permanence**
et un **robot** (des petits programmes Python) capable de le piloter.

- **Toi**, tu ouvres ce Chrome depuis ton PC, dans un simple onglet, et tu te
  connectes **une seule fois** à tes sites (Leclerc Drive, etc.). Le NAS garde
  tes connexions, même après un redémarrage.
- **Le robot** utilise ensuite ce même Chrome, déjà connecté, pour faire des
  tâches répétitives à ta place, par exemple remplir un panier.
  **Le paiement reste toujours ton travail.**

```
 Ton PC  ── onglet https://IP-DU-NAS:3001 ──►  ┌────────── NAS ──────────┐
                                               │  conteneur « chrome »   │──► sites web
                                               │        ▲                │
                                               │        │ prise 9222     │
                                               │  conteneur « robot »    │
                                               └─────────────────────────┘
```

> **Un conteneur, c'est quoi ?** Un mini-ordinateur isolé, qui tourne à
> l'intérieur du NAS grâce au logiciel **Docker**. Il contient tout ce dont
> le programme a besoin, donc il n'y a rien à installer à la main.

---

## Ce qu'il te faut

| | |
|---|---|
| Un NAS avec Docker | Synology avec **Container Manager** (DSM 7.2 ou plus), QNAP avec **Container Station**, Unraid, OpenMediaVault… |
| Un processeur 64 bits | Intel/AMD ou ARM 64 bits (les ARM 32 bits ne sont pas pris en charge) |
| De la mémoire | au moins **2 Go de RAM libres** (Chrome est gourmand) |
| De la place | environ **3 Go** sur le disque |

---

## Installation pas à pas

### Étape 1 : préparer le dossier sur ton PC

1. Sur la page GitHub du projet, clique sur **Code** → **Download ZIP**, puis
   décompresse le fichier.
2. Dans le dossier obtenu, fais une **copie** de `.env.exemple` et renomme-la
   exactement `.env` (point au début, sans rien après).
3. Ouvre `.env` avec le Bloc-notes et remplis-le. Tout est expliqué dedans.
   L'essentiel : choisis un **identifiant** et un **long mot de passe**.
   Ils protègent l'accès à TON Chrome. Ce ne sont pas tes identifiants Leclerc.

> ⚠️ **Piège Windows :** le Bloc-notes ajoute parfois `.txt` en enregistrant.
> Dans « Enregistrer sous », choisis le type **Tous les fichiers** et vérifie
> que le nom est bien `.env`, et non `.env.txt`.

### Étape 2 : copier le dossier sur le NAS

Copie tout le dossier sur le NAS, par exemple dans le dossier partagé
`docker` (sur Synology : avec **File Station**, glisser-déposer).
Exemple de résultat : `/volume1/docker/veille_chrome_nas`.

### Étape 3 : démarrer Chrome

**Sur Synology (sans ligne de commande) :**
1. Ouvre **Container Manager** → **Projet** → **Créer**.
2. Nom du projet : `veille-chrome-nas`.
3. Chemin : choisis le dossier `docker/veille_chrome_nas`.
4. Source : **Utiliser le fichier docker-compose.yml existant**.
5. **Suivant** jusqu'à **Terminé**. Le NAS télécharge Chrome (environ
   1,5 Go, ça prend quelques minutes) puis le démarre.

**Sur les autres NAS (ligne de commande, voir l'étape 5 pour se connecter) :**

```bash
cd /volume1/docker/veille_chrome_nas
```

```bash
sudo docker compose up -d
```

### Étape 4 : ouvrir Chrome depuis ton PC

1. Dans ton navigateur habituel, va sur **`https://IP-DU-NAS:3001`**
   (remplace `IP-DU-NAS` par l'adresse de ton NAS, par exemple `192.168.1.20`).
   Sur Synology, tu la trouves dans **Panneau de configuration → Réseau**.
2. Un avertissement « connexion non privée » s'affiche : **c'est normal**.
   Le NAS utilise un certificat « fait maison », sans danger sur ton réseau
   local. Clique sur **Paramètres avancés** → **Continuer vers le site**.
3. Entre l'identifiant et le mot de passe choisis dans `.env`.
4. Tu vois un Chrome, en français, **qui tourne sur le NAS**. Connecte-toi à
   tes sites. Coche « Rester connecté » quand le site le propose.

### Étape 5 : tester le robot

Le robot se lance en **ligne de commande** : on se connecte au NAS à
distance en **SSH**, c'est-à-dire qu'on tape des commandes au NAS depuis
ton PC.

1. Sur Synology : **Panneau de configuration → Terminal & SNMP → Activer le
   service SSH**.
2. Sur ton PC Windows, ouvre **Terminal** (ou PowerShell) et tape (avec
   ton identifiant DSM habituel) :

   ```bash
   ssh ton-identifiant@IP-DU-NAS
   ```

3. Une fois connecté, va dans le dossier du projet et lance le test :

   ```bash
   cd /volume1/docker/veille_chrome_nas
   ```

   ```bash
   sudo docker compose run --rm robot
   ```

La première fois, le NAS fabrique le robot (1 à 2 minutes). Ensuite, tu dois
voir à peu près ceci :

```
✅ Branché sur Chrome 156.0.8078.79
Onglets déjà ouverts :
  - Nouvel onglet → chrome://new-tab-page-third-party/
Ouverture de https://www.example.com ...
Titre de la page : Example Domain
📸 Capture enregistrée : /app/captures/2026-11-23_11-36-21_test.png
Terminé. Chrome est toujours ouvert sur le NAS.
```

Si Chrome est ouvert sur ton PC pendant ce temps, tu vois l'onglet du robot
apparaître puis disparaître. La capture d'écran se trouve dans
`donnees/captures` sur le NAS.

> Si `docker compose` n'est pas reconnu, essaie `docker-compose` (avec un tiret).

---

## Sécurité : les règles à respecter

- **N'ouvre jamais le port 3001 sur Internet** (pas de « redirection de port »
  sur ta box). Ce Chrome est connecté à tes comptes : il doit rester sur ton
  réseau local. Pour y accéder de l'extérieur plus tard, on passera par un
  VPN (Tailscale, par exemple).
- Le dossier **`donnees/chrome`** contient tes connexions (cookies). Quiconque
  le récupère peut se faire passer pour toi sur ces sites. Ne le partage pas.
  Il n'est jamais envoyé sur GitHub (voir `.gitignore`), tout comme `.env`.
- Ce Chrome est réglé pour **ne jamais enregistrer de mot de passe ni de carte
  bancaire** (fichier `reglages-chrome/politiques.json`). Tu restes connecté
  grâce aux cookies, pas grâce à un mot de passe mémorisé.
- **Le paiement, c'est toi.** Le robot peut préparer, mais il ne valide jamais
  une commande.
- Certains sites marchands détectent les robots ou interdisent
  l'automatisation dans leurs conditions d'utilisation. On testera au cas par
  cas.

---

## Bon à savoir

- **Ne ferme pas la dernière fenêtre de Chrome.** Si ça arrive, fais un
  clic droit sur le fond du bureau → **Chromium**, ou redémarre le
  conteneur. Le robot fonctionne dans les deux cas.
- Après un redémarrage, Chrome affiche parfois **« Restaurer les pages ? »** :
  c'est normal, tu peux cliquer sur **Restaurer** ou fermer la bulle. Tes
  connexions sont conservées.
- **Mettre à jour Chrome** (une fois par mois, par exemple) : en ligne de
  commande, dans le dossier du projet :

  ```bash
  sudo docker compose pull && sudo docker compose up -d
  ```

---

## Dépannage

| Problème | Solution |
|---|---|
| `required variable CHROME_UTILISATEUR is missing` | Le fichier `.env` est absent ou mal nommé (`.env.txt`). Revois l'étape 1. |
| La page `https://IP-DU-NAS:3001` ne répond pas | Attends 1 minute après le démarrage. Vérifie l'adresse IP et le `https://` au début. |
| Écran noir, ou Chrome qui plante en boucle | Dans `docker-compose.yml`, enlève les `#` devant les 2 lignes `security_opt` et `- seccomp:unconfined`, puis relance le projet. |
| `Impossible de joindre Chrome` (robot) | Le conteneur `chrome-nas` est-il démarré ? La fenêtre Chrome a-t-elle été fermée ? (voir « Bon à savoir ») |
| Le port 3001 est déjà utilisé | Change `PORT_CHROME` dans `.env` (par exemple 3005) et utilise ce numéro dans l'adresse. |
| Le NAS rame | Chrome consomme beaucoup de mémoire : ferme les onglets inutiles. |

---

## Rôle de chaque fichier

```
veille_chrome_nas/
├── docker-compose.yml        ← décrit les 2 conteneurs (chrome + robot)
├── .env.exemple              ← modèle de réglages personnels, à copier en .env
├── reglages-chrome/
│   ├── options-chrome.sh     ← ouvre la « prise » du robot + Chrome en français
│   └── politiques.json       ← rouvre la session au démarrage, pas de mot de passe ni de CB enregistrés
├── robot/
│   ├── Dockerfile            ← recette de fabrication du robot (Python + Playwright)
│   ├── requirements.txt      ← bibliothèques Python utilisées
│   └── scripts/
│       ├── outils.py         ← fonctions communes (se brancher sur Chrome, capture d'écran)
│       └── test_connexion.py ← le script de test de l'étape 5
└── donnees/                  ← créé au premier démarrage (profil Chrome, captures) — privé
```

## Et ensuite ?

1. Un premier vrai script : par exemple, **remplir le panier Leclerc Drive**
   à partir d'une liste de courses.
2. Le lancer **automatiquement** (par exemple chaque jeudi) avec le
   planificateur de tâches du NAS.
