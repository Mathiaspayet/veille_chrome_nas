# Chrome sur le NAS, piloté par un robot

Ce projet installe sur le NAS un **navigateur Chrome allumé en permanence**
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
> l'intérieur du NAS grâce au logiciel **Docker** (sur Synology, il s'appelle
> **Container Manager**). Il contient tout ce dont le programme a besoin,
> donc il n'y a rien à installer à la main.
>
> **Sans SSH :** toutes les commandes passent par le **Planificateur de
> tâches** du Synology. Il exécute le script `chrome-nas.sh`, la
> « télécommande » du projet, qui note tout ce qu'il fait dans
> `donnees/journal.txt`.

---

## Mode opératoire (Synology DSM 7, sans SSH)

Préparé pour un **DS1522+** (AMD Ryzen, 8 Go de RAM, DSM 7.4) : tout est
compatible. Compte environ **30 minutes**. Les noms des menus peuvent varier
légèrement selon la version de DSM.

### Étape 1 : installer 2 paquets

1. Ouvre le **Centre de paquets**.
2. Cherche **Container Manager**, puis clique sur **Installer**. C'est lui qui fait
   tourner les conteneurs.
3. Cherche **Éditeur de texte**, puis clique sur **Installer**. Il permet d'ouvrir et
   de modifier les fichiers texte directement sur le NAS.
4. Ouvre **File Station** et vérifie qu'il existe un dossier partagé
   **`docker`**. S'il n'y est pas : **Panneau de configuration → Dossier
   partagé → Créer**, puis nom : `docker`, et valide avec les options proposées par défaut.

### Étape 2 : télécharger le projet

Sur la page GitHub du projet, **choisis la branche** qui contient la version à
installer (menu déroulant en haut à gauche), puis clique sur **Code → Download
ZIP**. Garde le fichier `.zip` tel quel, sans le décompresser.

### Étape 3 : déposer le projet sur le NAS

1. Dans **File Station**, ouvre le dossier **`docker`**.
2. Clique sur **Charger**, puis choisis le fichier `.zip` téléchargé.
3. Fais un clic droit sur le `.zip` → **Extraire** → **Extraire ici**.
4. Un dossier `veille_chrome_nas-…` apparaît. Fais un clic droit dessus →
   **Renommer**, puis tape exactement : **`veille_chrome_nas`**.
5. Tu peux supprimer le `.zip`.
6. **Vérifie l'emplacement** : clic droit sur `veille_chrome_nas` →
   **Propriétés**. L'emplacement doit être **`/volume1/docker/veille_chrome_nas`**.
   S'il est différent (par exemple `/volume2/...`), note-le et utilise-le
   à la place de `/volume1/docker/veille_chrome_nas` dans les tâches
   des étapes 5 et 8.

### Étape 4 : écrire tes réglages

1. Dans le dossier `veille_chrome_nas`, fais un clic droit sur
   **`reglages-exemple.env`** → **Renommer**, puis tape exactement : **`reglages.env`**.
2. Clic droit sur `reglages.env` → **Ouvrir avec Éditeur de texte**.
3. Remplace :
   - `moi` par l'identifiant de ton choix ;
   - `remplace-moi-par-un-long-mot-de-passe` par un **vrai mot de passe**, avec
     **au moins 12 caractères**, uniquement des lettres sans accents, des
     chiffres, `-` ou `_`. Exemple de forme : `Tartine-Velo-Nuage-42`.
4. Enregistre (**Fichier → Enregistrer**) et ferme.

> Cet identifiant et ce mot de passe protègent **l'accès à ton Chrome**. Ce
> ne sont **pas** tes identifiants Leclerc ou autres. Note-les quelque part.

### Étape 5 : créer la tâche « Démarrer »

1. **Panneau de configuration → Planificateur de tâches**.
2. **Créer → Tâche planifiée → Script défini par l'utilisateur**.
3. Onglet **Général** :
   - Tâche : **`Chrome NAS – Démarrer`**
   - Utilisateur : **`root`** (Docker exige les droits d'administrateur)
   - **Activé** : coché
4. Onglet **Programmer** : cette tâche installe aussi les **mises à jour
   de sécurité** de Chrome. On la fait donc tourner une fois par semaine,
   la nuit :
   - Exécuter aux jours suivants : **Lundi**
   - Heure de première exécution : **04:00**, une seule fois dans la journée
5. Onglet **Paramètres de tâche**, dans la case **Script défini par
   l'utilisateur**, colle exactement cette ligne :

   ```bash
   bash /volume1/docker/veille_chrome_nas/chrome-nas.sh demarrer
   ```

   *(Facultatif : coche « Envoyer les détails de l'exécution par e-mail »,
   option « uniquement en cas d'arrêt anormal », si les notifications par
   e-mail de DSM sont configurées.)*
6. **OK**. DSM avertit que la tâche tourne en `root` : confirme (DSM peut
   te demander ton mot de passe DSM).
7. **Lance-la tout de suite** : sélectionne la tâche, clique sur **Exécuter**,
   puis confirme.

La première fois, la tâche télécharge Chrome (environ 1,5 Go) et prépare le robot.
**Compte 5 à 10 minutes.**

### Étape 6 : vérifier que Chrome tourne

1. Dans **File Station**, ouvre `docker/veille_chrome_nas/donnees`, fais un
   clic droit sur **`journal.txt`** → **Ouvrir avec Éditeur de texte**.
2. La dernière ligne doit être :
   `✅ Chrome tourne. Ouvre https://IP-DU-NAS:3001 depuis ton PC.`
   - Une ligne commençant par ❌ explique le problème (voir **Dépannage**).
   - S'il n'y a pas encore de ligne ✅ ni ❌, la tâche travaille encore :
     ferme le journal, attends quelques minutes, rouvre-le.
3. Autre vérification possible : **Container Manager → Conteneur**. La ligne
   **`chrome-nas`** doit être **en cours d'exécution**.

### Étape 7 : ouvrir Chrome depuis ton PC

1. Trouve l'adresse IP du NAS. C'est celle que tu tapes pour ouvrir DSM
   (par exemple `192.168.1.20`), ou dans **Panneau de configuration →
   Réseau → Interface réseau**.
2. Dans ton navigateur habituel, va sur **`https://IP-DU-NAS:3001`**, par
   exemple `https://192.168.1.20:3001`. N'oublie pas le **`https://`**.
3. L'avertissement « Votre connexion n'est pas privée » est **normal** : le
   NAS utilise un certificat « fait maison », sans danger sur ton réseau
   local. Clique sur **Paramètres avancés** → **Continuer vers le site**.
   Sur Firefox : **Avancé** → **Accepter le risque et poursuivre**.
4. Une fenêtre de connexion s'ouvre : saisis l'identifiant et le mot de passe
   de `reglages.env`.
5. Tu vois un Chrome, en français, **qui tourne sur le NAS**. Va sur tes sites
   et connecte-toi, par exemple sur Leclerc Drive. Coche « Rester connecté »
   quand le site le propose.

> La petite barre colorée sur le bord gauche ouvre le menu de la page
> d'accès : plein écran, presse-papiers, etc.

### Étape 8 : créer la tâche « Test robot »

1. **Planificateur de tâches → Créer → Tâche planifiée → Script défini par
   l'utilisateur**.
2. Onglet **Général** : tâche **`Chrome NAS – Test robot`**, utilisateur
   **`root`**.
3. Onglet **Programmer** : **Exécuter à la date suivante**, avec la date du jour,
   et **Ne pas répéter**. Cette tâche se lance à la main.
4. Onglet **Paramètres de tâche**, colle :

   ```bash
   bash /volume1/docker/veille_chrome_nas/chrome-nas.sh robot test_connexion.py
   ```

5. **OK**, puis sélectionne la tâche → **Exécuter**.

Pendant le test, si Chrome est ouvert sur ton PC (étape 7), tu vois un onglet
s'ouvrir sur `example.com`, puis se refermer. Ensuite :

- dans **`donnees/journal.txt`**, tu dois lire `✅ Robot terminé sans erreur.` ;
- dans **`donnees/captures`**, une capture d'écran de la page est apparue :
  double-clique dessus pour la voir.

**C'est terminé : Chrome et le robot sont en place.** 🎉

---

## Au quotidien

| Je veux… | Comment |
|---|---|
| Utiliser Chrome | `https://IP-DU-NAS:3001` depuis un PC de la maison |
| Redémarrer Chrome | **Container Manager → Conteneur → `chrome-nas` → Action → Redémarrer** |
| Rouvrir Chrome si j'ai fermé sa fenêtre | Clic droit sur le fond du bureau → **Chromium**, ou redémarre le conteneur |
| Mettre à jour | Rien à faire : la tâche « Démarrer » le fait chaque lundi à 4 h |
| Changer le mot de passe d'accès | Modifie `reglages.env`, puis **Exécuter** la tâche « Démarrer » |
| Arrêter Chrome (libérer la mémoire) | Crée une tâche avec `bash /volume1/docker/veille_chrome_nas/chrome-nas.sh arreter` |
| Savoir ce qui s'est passé | Ouvre `donnees/journal.txt` avec l'Éditeur de texte |

- Après un redémarrage, Chrome affiche parfois **« Restaurer les pages ? »** :
  c'est normal, tu peux cliquer sur **Restaurer** ou fermer la bulle. Tes
  connexions sont conservées.
- Après un redémarrage du NAS, Chrome se relance tout seul.

---

## Sécurité : les règles à respecter

- **N'ouvre jamais le port 3001 sur Internet** (pas de « redirection de port »
  sur ta box). Ce Chrome est connecté à tes comptes : il doit rester sur ton
  réseau local. Pour y accéder de l'extérieur plus tard, on passera par un
  VPN.
- Le dossier **`donnees/chrome`** contient tes connexions (cookies). Quiconque
  le récupère peut se faire passer pour toi sur ces sites : ne le partage
  pas. Il n'est jamais envoyé sur GitHub (voir `.gitignore`), tout comme
  `reglages.env`.
- Ce Chrome est réglé pour **ne jamais enregistrer de mot de passe ni de carte
  bancaire** (fichier `reglages-chrome/politiques.json`). Tu restes connecté
  grâce aux cookies, pas grâce à un mot de passe mémorisé.
- **Le paiement, c'est toi.** Le robot peut préparer, mais il ne valide jamais
  une commande.
- Certains sites marchands détectent les robots ou interdisent
  l'automatisation dans leurs conditions d'utilisation. On testera au cas par
  cas.

---

## Dépannage

Commence toujours par lire la fin de **`donnees/journal.txt`**.

| Message ou problème | Solution |
|---|---|
| Pas de fichier `journal.txt` | La tâche n'a pas trouvé le script : vérifie le chemin collé dans la tâche (étape 3, point 6) et que l'utilisateur est bien `root`. |
| `❌ Le fichier reglages.env est introuvable` | Renomme `reglages-exemple.env` en `reglages.env` (étape 4). |
| `❌ Choisis un vrai mot de passe…` / `❌ … ne doit contenir que…` | Corrige `CHROME_MOT_DE_PASSE` dans `reglages.env`, puis relance la tâche. |
| `❌ Docker est introuvable` | Installe **Container Manager** (étape 1). |
| `⚠️ Téléchargement impossible` | Le NAS n'avait pas Internet à ce moment-là. Ce n'est pas grave si Chrome tournait déjà ; sinon, relance la tâche plus tard. |
| La page `https://IP-DU-NAS:3001` ne répond pas | Attends 1 minute après le démarrage. Vérifie l'IP et le `https://`. Si le pare-feu DSM est activé (**Panneau de configuration → Sécurité → Pare-feu**), autorise le port **3001** pour ton réseau local. |
| Écran noir, ou Chrome qui plante en boucle | Ouvre `docker-compose.yml` avec l'Éditeur de texte et enlève les `#` devant les 2 lignes `security_opt:` et `- seccomp:unconfined`, puis relance la tâche « Démarrer ». |
| `❌ Chrome n'est pas démarré` (robot) | Lance la tâche « Démarrer ». |
| `Impossible de joindre Chrome` (robot) | La fenêtre Chrome a peut-être été fermée : voir « Au quotidien ». |
| Le port 3001 est déjà utilisé | Change `PORT_CHROME` dans `reglages.env` (par exemple 3005), relance « Démarrer » et utilise ce numéro dans l'adresse. |

---

## Rôle de chaque fichier

```
veille_chrome_nas/
├── chrome-nas.sh             ← la « télécommande » appelée par le Planificateur de tâches
├── reglages-exemple.env      ← modèle de réglages, à renommer en reglages.env
├── docker-compose.yml        ← décrit les 2 conteneurs (chrome + robot)
├── reglages-chrome/
│   ├── options-chrome.sh     ← ouvre la « prise » du robot + Chrome en français
│   └── politiques.json       ← rouvre la session au démarrage, pas de mot de passe ni de CB enregistrés
├── robot/
│   ├── Dockerfile            ← recette de fabrication du robot (Python + Playwright)
│   ├── requirements.txt      ← bibliothèques Python utilisées
│   └── scripts/
│       ├── outils.py         ← fonctions communes (se brancher sur Chrome, capture d'écran)
│       └── test_connexion.py ← le script de test de l'étape 8
└── donnees/                  ← créé au premier démarrage — privé
    ├── chrome/               ← ton profil Chrome (connexions)
    ├── captures/             ← captures d'écran du robot
    └── journal.txt           ← tout ce que font les tâches
```

## Et ensuite ?

1. Un premier vrai script : par exemple, **remplir le panier Leclerc Drive**
   à partir d'une liste de courses.
2. Le lancer **automatiquement** (par exemple chaque jeudi) avec une
   nouvelle tâche du Planificateur :
   `bash /volume1/docker/veille_chrome_nas/chrome-nas.sh robot NOM_DU_SCRIPT.py`
