# Chrome sur le NAS, piloté par Claude

Ce projet installe sur le NAS un **navigateur Chrome allumé en permanence**,
que **Claude** peut piloter grâce à un connecteur (le « pont MCP »).

- **Toi**, tu ouvres ce Chrome depuis ton PC, dans un simple onglet, et tu te
  connectes **une seule fois** à tes sites. Le NAS garde tes connexions,
  même après un redémarrage.
- **Claude** (dans une discussion, dans Cowork ou dans une tâche planifiée)
  utilise ensuite ce même Chrome, déjà connecté : il ouvre des pages, les
  lit, clique, remplit des formulaires… **Le paiement reste toujours ton
  travail.**

```
 Ton PC ── https://chrome.… ──────────────────────────────► ┌──── NAS ────┐
                                                            │  chrome-nas │──► sites web
 Claude ── https://mcp-chrome.… ──► portier-mcp ──► pont-mcp ─► (prise 9222)│
                                                            └─────────────┘
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

### Étape 1 : vérifier les prérequis

Tes autres projets (gestion-locative, immo, menus-famille…) tournent déjà
sur le NAS : **Container Manager**, le dossier partagé **`docker`** et
**Watchtower** sont donc en place. Il reste deux vérifications :

1. **Centre de paquets** : vérifie que **Éditeur de texte** est installé.
   Sinon, cherche-le et clique sur **Installer**. Il permet d'ouvrir et de
   modifier les fichiers texte directement sur le NAS.
2. **Container Manager → Conteneur** : la ligne **`watchtower`** doit être
   **en cours d'exécution**. C'est lui qui mettra Chrome à jour tout seul,
   comme tes autres applications.

### Étape 2 : créer le dossier du projet

1. Dans **File Station**, ouvre le dossier **`docker`**.
2. **Créer → Créer un dossier**, nom : **`veille_chrome_nas`** (exactement).
3. **Vérifie l'emplacement** : clic droit sur `veille_chrome_nas` →
   **Propriétés**. L'emplacement doit être **`/volume1/docker/veille_chrome_nas`**.
   S'il est différent (par exemple `/volume2/...`), utilise-le à la place de
   `/volume1/docker/veille_chrome_nas` dans toutes les tâches.

### Étape 3 : créer la tâche « Mettre à jour le projet »

Cette tâche télécharge les fichiers du projet depuis GitHub, sans ZIP à
extraire. Tu la garderas : c'est ton bouton de mise à jour.

1. **Panneau de configuration → Planificateur de tâches**.
2. **Créer → Tâche planifiée → Script défini par l'utilisateur**.
3. Onglet **Général** :
   - Tâche : **`Chrome NAS – Mettre à jour le projet`**
   - Utilisateur : **`root`** (Docker exige les droits d'administrateur)
   - **Activé** : coché
4. Onglet **Programmer** : **Exécuter à la date suivante**, avec la date du
   jour, et **Ne pas répéter**. Cette tâche se lance à la main.
5. Onglet **Paramètres de tâche**, dans la case **Script défini par
   l'utilisateur**, colle exactement cette ligne (elle est longue, c'est
   normal) :

   ```bash
   cd /volume1/docker/veille_chrome_nas && curl -fsSL https://raw.githubusercontent.com/Mathiaspayet/veille_chrome_nas/main/chrome-nas.sh -o chrome-nas.sh.nouveau && mv -f chrome-nas.sh.nouveau chrome-nas.sh && bash chrome-nas.sh mettre-a-jour
   ```

   Elle se place dans le dossier du projet, y télécharge la dernière
   version de la « télécommande » `chrome-nas.sh`, puis la lance pour
   télécharger le reste du projet, sans jamais toucher à tes réglages
   (`reglages.env`) ni à tes données (`donnees/`).
6. **OK**. DSM avertit que la tâche tourne en `root` : confirme (DSM peut
   te demander ton mot de passe DSM).
7. **Lance-la** : sélectionne la tâche, clique sur **Exécuter**, puis confirme.

Le dossier `veille_chrome_nas` se remplit. À ce stade, `donnees/journal.txt`
se termine par `❌ Le fichier reglages.env est introuvable` : **c'est
normal**, on le crée à l'étape suivante.

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
4. Onglet **Programmer** : **Exécuter à la date suivante**, avec la date du jour,
   et **Ne pas répéter**. Cette tâche se lance à la main : les mises à
   jour de Chrome, c'est ton Watchtower qui s'en charge (voir « Au
   quotidien »).
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

La première fois, la tâche télécharge Chrome et les images du projet
(environ 2 Go). **Compte 5 à 10 minutes.**

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

**C'est terminé : Chrome est en place.** 🎉 Pour que Claude puisse le
piloter, suis la section « Piloter Chrome depuis Claude : le pont MCP »
plus bas.

---

## Au quotidien

| Je veux… | Comment |
|---|---|
| Utiliser Chrome | `https://IP-DU-NAS:3001` depuis un PC de la maison |
| Redémarrer Chrome | **Container Manager → Conteneur → `chrome-nas` → Action → Redémarrer** |
| Rouvrir Chrome si j'ai fermé sa fenêtre | Clic droit sur le fond du bureau → **Chromium**, ou redémarre le conteneur |
| Mettre à jour Chrome, le pont et le portier | Rien à faire : ton Watchtower (portée `gestion-locative`) vérifie toutes les 5 minutes et installe les nouvelles versions. Celles du pont et du portier sont fabriquées par GitHub à chaque modification du projet. |
| Mettre à jour les fichiers du projet (réglages de Chrome, télécommande…) | Rarement utile : **Exécuter** la tâche « Mettre à jour le projet » |
| Changer le mot de passe d'accès | Modifie `reglages.env`, puis **Exécuter** la tâche « Démarrer » |
| Arrêter Chrome et le pont (libérer la mémoire) | Crée une tâche avec `bash /volume1/docker/veille_chrome_nas/chrome-nas.sh arreter` |
| Savoir ce qui s'est passé | Ouvre `donnees/journal.txt` avec l'Éditeur de texte |

- Après un redémarrage, Chrome affiche parfois **« Restaurer les pages ? »** :
  c'est normal, tu peux cliquer sur **Restaurer** ou fermer la bulle. Tes
  connexions sont conservées.
- Après un redémarrage du NAS, Chrome se relance tout seul.
- Quand Watchtower installe une nouvelle version de Chrome (souvent une
  fois par semaine), Chrome redémarre en quelques secondes. Tes connexions
  sont conservées. Si Claude travaillait dans Chrome à ce moment-là, il
  perd la page en cours : redemande-lui simplement.

---

## Option : une adresse du type `https://chrome.….synology.me`

Comme pour tes autres applications, tu peux ouvrir Chrome par un nom de
domaine grâce au **proxy inversé** de DSM. Un proxy inversé est un
« aiguilleur » : il reçoit la visite sur le nom de domaine et la transmet
au bon conteneur. Trois réglages sont **indispensables** pour ce
conteneur-là :

1. **Destination en HTTPS.** Dans **Panneau de configuration → Portail de
   connexion → Avancé → Proxy inversé**, ouvre ta règle (**Modifier**) et
   règle la partie **Destination** ainsi :
   - Protocole : **HTTPS**, et non HTTP (sinon : « 400 Bad Request – The
     plain HTTP request was sent to HTTPS port ») ;
   - Nom d'hôte : **`localhost`** ;
   - Port : **`3001`**.
2. **WebSocket.** Dans l'onglet **En-tête personnalisé**, clique sur
   **Créer → WebSocket**. Sans ces en-têtes, la page s'ouvre mais l'image
   de Chrome ne s'affiche pas : c'est un flux vidéo en continu, qui passe
   par une connexion de type « WebSocket ».
3. **Réseau local uniquement** (sécurité, voir plus bas) :
   - **Portail de connexion → Avancé → Profil de contrôle d'accès →
     Créer**. Nom : `Réseau local uniquement`. Ajoute une règle
     **Autoriser** pour ton réseau, par exemple l'adresse `192.168.1.0`
     avec le masque `255.255.255.0` si l'adresse IP de ton NAS commence par
     `192.168.1.` (adapte si elle commence autrement). Ajoute ensuite une
     règle **Refuser** pour **Tout**.
   - Dans ta règle de proxy inversé, onglet **Général**, choisis ce profil
     dans **Profil de contrôle d'accès**.

**Pourquoi le point 3 ?** Tes autres applications ont leur propre écran de
connexion. Derrière celle-ci, il y a un **navigateur déjà connecté à tes
comptes** (courses, billetterie…), protégé seulement par l'identifiant et
le mot de passe de `reglages.env`. Sans ce profil, n'importe qui sur
Internet qui trouve l'adresse peut tenter sa chance. Et le blocage
automatique de DSM ne protège pas ce mot de passe-là : il ne surveille que
les connexions à DSM lui-même. Avec le profil, le nom de domaine fonctionne
chez toi, mais reste fermé depuis l'extérieur. Pour un accès hors de chez
toi, on passera par un VPN, c'est-à-dire un tunnel privé entre ton
téléphone et ta maison.

---

## Piloter Chrome depuis Claude : le pont MCP

Grâce au **pont MCP**, Claude (dans une discussion, dans Cowork ou dans une
tâche planifiée) peut piloter le Chrome du NAS : ouvrir des pages, les
lire, cliquer, taper du texte. MCP est le langage des connecteurs de
Claude, comme celui de ton appli Menus famille.

```
Claude ──https──► proxy inversé DSM ──► portier ──► pont MCP ──► Chrome du NAS
                  (mcp-chrome.…)        (OAuth)     (Playwright)
```

- Le **pont** (Playwright MCP, de Microsoft) fournit les outils de pilotage.
  Il n'a aucun mot de passe : il n'est joignable que par le portier.
- Le **portier** est la porte d'entrée sécurisée, sur le modèle de Menus
  famille. Pour autoriser Claude, il faut saisir l'identifiant et le mot de
  passe de `reglages.env`. Il se verrouille 15 minutes après 5 essais ratés
  et bloque l'outil dangereux du pont (exécution de code arbitraire).
- Leurs images sont **fabriquées par GitHub** à chaque modification du
  projet. Ton Watchtower installe les nouvelles versions tout seul ; après
  une mise à jour de Chrome, il les rebranche aussi, et Claude reste
  autorisé.

### 1. Les images du projet (rien à faire, normalement)

GitHub fabrique deux images : le pont et le portier. Comme le
dépôt est public, elles sont **publiques d'office** : le NAS les télécharge
sans mot de passe (vérifié à leur première publication). Elles ne
contiennent que le code du projet : tes réglages et tes données restent sur
le NAS.

Si un jour le journal affiche `❌ Impossible de télécharger « pont-mcp »`
alors qu'Internet fonctionne, vérifie leur visibilité sur
<https://github.com/Mathiaspayet?tab=packages> : pour chaque image
(`veille_chrome_nas-pont-mcp` et `veille_chrome_nas-portier`), **Package settings** →
**Danger Zone** → **Change visibility** → **Public**.

### 2. Installer la nouvelle version sur le NAS

**Exécute** la tâche « Chrome NAS – Mettre à jour le projet ». Si tu ne
l'as pas encore, crée-la comme à l'étape 3 du mode opératoire, avec la
ligne :

```bash
cd /volume1/docker/veille_chrome_nas && curl -fsSL https://raw.githubusercontent.com/Mathiaspayet/veille_chrome_nas/main/chrome-nas.sh -o chrome-nas.sh.nouveau && mv -f chrome-nas.sh.nouveau chrome-nas.sh && bash chrome-nas.sh mettre-a-jour
```

La fin du journal doit afficher `✅ Pont MCP et portier démarrés…`.

### 3. Créer l'adresse du pont (proxy inversé)

**Panneau de configuration → Portail de connexion → Avancé → Proxy inversé
→ Créer** :

| Réglage | Valeur |
|---|---|
| Nom du proxy inversé | `mcp-chrome` |
| Source – Protocole | **HTTPS** |
| Source – Nom d'hôte | `mcp-chrome.bignasmathias.synology.me` |
| Source – Port | `443` |
| Destination – Protocole | **HTTP** (attention : différent de la règle de Chrome) |
| Destination – Nom d'hôte | **`127.0.0.1`** |
| Destination – Port | **`8930`** |

- **Pas** d'en-têtes WebSocket et **pas** de profil de contrôle d'accès :
  Claude doit pouvoir joindre cette adresse depuis Internet. C'est le portier
  qui protège.
- Onglet **Paramètres avancés** : si tu y trouves les délais d'expiration
  du proxy, mets celui de **lecture** à **300** secondes (certaines pages
  sont longues à charger).

**Vérification :** ouvre `https://mcp-chrome.bignasmathias.synology.me` dans
ton navigateur. Tu dois voir « Portier du pont MCP – En service ».

### 4. Ajouter le connecteur dans Claude

1. Sur claude.ai : **Paramètres → Connecteurs → Ajouter un connecteur
   personnalisé**, comme pour Menus famille.
2. Nom : `Chrome du NAS`. Adresse :
   **`https://mcp-chrome.bignasmathias.synology.me/mcp`** (avec `/mcp` à la
   fin).
3. Clique sur **Connecter**. La page « Autoriser Claude à piloter le Chrome
   du NAS ? » s'ouvre : saisis l'identifiant et le mot de passe de
   `reglages.env`, puis clique sur **Autoriser**.

### 5. Premier essai

Dans une discussion avec Claude, en activant le connecteur « Chrome du NAS » :

> Avec le connecteur Chrome du NAS, ouvre example.com et dis-moi le titre de la page.

Ouvre `https://chrome.bignasmathias.synology.me` à côté : tu vois Claude
travailler en direct.

### Sécurité du pont

- Claude pourra faire **tout ce que tu peux faire dans ce Chrome**, y compris
  sur les sites où tu es connecté. Garde la règle : **aucune carte bancaire
  enregistrée** dans tes comptes, et c'est toi qui valides les commandes.
- Les pages web peuvent contenir du texte écrit pour tromper une IA.
  Surveille Claude quand il travaille sur des sites que tu ne connais pas.
- Les sites qui refusent les robots (comme Leclerc Drive) refuseront aussi
  Claude : on respecte leur choix.
- **Retirer l'accès à Claude :** supprime le connecteur dans Claude. Pour
  couper **tous** les accès d'un coup : lance la tâche d'arrêt, supprime le
  fichier `donnees/portier/portier.sqlite3`, puis **Exécuter** « Démarrer ».

---

## Sécurité : les règles à respecter

- **N'ouvre jamais ce Chrome sur Internet** : pas de « redirection de port »
  du 3001 sur ta box, et pas de proxy inversé sans le profil « Réseau local
  uniquement » (voir l'option ci-dessus). Ce Chrome est connecté à tes
  comptes : il doit rester sur ton réseau local. Pour y accéder de
  l'extérieur plus tard, on passera par un VPN. (Le pont MCP, lui, est fait
  pour être joignable depuis Internet par Claude : c'est son portier qui le
  protège.)
- Le dossier **`donnees/chrome`** contient tes connexions (cookies). Quiconque
  le récupère peut se faire passer pour toi sur ces sites : ne le partage
  pas. Il n'est jamais envoyé sur GitHub (voir `.gitignore`), tout comme
  `reglages.env`.
- Ce Chrome est réglé pour **ne jamais enregistrer de mot de passe ni de carte
  bancaire** (fichier `reglages-chrome/politiques.json`). Tu restes connecté
  grâce aux cookies, pas grâce à un mot de passe mémorisé.
- **Le paiement, c'est toi.** Claude peut préparer, mais c'est toi qui valides
  les commandes.
- Certains sites marchands détectent les robots ou interdisent
  l'automatisation dans leurs conditions d'utilisation. On testera au cas par
  cas.

---

## Dépannage

Commence toujours par lire la fin de **`donnees/journal.txt`**.

| Message ou problème | Solution |
|---|---|
| Pas de fichier `journal.txt` | La tâche n'a pas trouvé le dossier ou le script : vérifie le chemin collé dans la tâche (étape 2, point 3) et que l'utilisateur est bien `root`. |
| `❌ Le fichier reglages.env est introuvable` | Renomme `reglages-exemple.env` en `reglages.env` (étape 4). |
| `❌ Choisis un vrai mot de passe…` / `❌ … ne doit contenir que…` | Corrige `CHROME_MOT_DE_PASSE` dans `reglages.env`, puis relance la tâche. |
| `❌ Docker est introuvable` | Vérifie que **Container Manager** est installé et démarré (Centre de paquets). |
| Chrome n'est jamais mis à jour | **Container Manager → Conteneur** : `watchtower` doit être en cours d'exécution. |
| `⚠️ Téléchargement impossible` | Le NAS n'avait pas Internet à ce moment-là. Ce n'est pas grave si Chrome tournait déjà ; sinon, relance la tâche plus tard. |
| La page `https://IP-DU-NAS:3001` ne répond pas | Attends 1 minute après le démarrage. Vérifie l'IP et le `https://`. Si le pare-feu DSM est activé (**Panneau de configuration → Sécurité → Pare-feu**), autorise le port **3001** pour ton réseau local. |
| Écran noir, ou Chrome qui plante en boucle | Ouvre `docker-compose.yml` avec l'Éditeur de texte et enlève les `#` devant les 2 lignes `security_opt:` et `- seccomp:unconfined`, puis relance la tâche « Démarrer ». |
| `❌ Action inconnue « robot »` | Le robot a été retiré du projet (on passe par le pont MCP) : supprime la tâche « Chrome NAS – Test robot » du Planificateur. |
| Claude : « Couldn't reach the MCP server » | L'adresse doit commencer par `https://` et finir par `/mcp`. Ouvre-la sans `/mcp` dans un navigateur : tu dois voir « Portier du pont MCP ». Sinon, vérifie la règle de proxy inversé (destination **HTTP**, `127.0.0.1`, `8930`). |
| Page d'autorisation : « Trop d'essais ratés » | Le portier est verrouillé 15 minutes après 5 mots de passe faux. Attends, puis réessaie. |
| Claude : « pont_injoignable » | **Container Manager → Conteneur** : `pont-mcp` et `chrome-nas` doivent être en cours d'exécution. Sinon, **Exécuter** « Démarrer ». |
| `❌ Impossible de télécharger « pont-mcp »` (ou portier) | Internet était peut-être coupé : relance « Démarrer » plus tard. Si ça persiste, vérifie que les images sont publiques (pont MCP, point 1). |
| Le port 3001 est déjà utilisé | Change `PORT_CHROME` dans `reglages.env` (par exemple 3005), relance « Démarrer » et utilise ce numéro dans l'adresse. |

---

## Rôle de chaque fichier

```
veille_chrome_nas/
├── .github/workflows/images.yml ← recette de GitHub : tests, puis fabrication des 2 images
├── chrome-nas.sh             ← la « télécommande » appelée par le Planificateur de tâches
├── reglages-exemple.env      ← modèle de réglages, à renommer en reglages.env
├── docker-compose.yml        ← décrit les 3 conteneurs (chrome, pont-mcp, portier)
├── reglages-chrome/
│   ├── options-chrome.sh     ← ouvre la « prise » du pont MCP + Chrome en français
│   └── politiques.json       ← rouvre la session au démarrage, pas de mot de passe ni de CB enregistrés
├── pont-mcp/
│   ├── Dockerfile            ← recette du pont (Playwright MCP, version fixée)
│   └── package.json …        ← version exacte de Playwright MCP
├── portier/
│   ├── Dockerfile            ← recette du portier
│   ├── portier.py            ← connexion OAuth, verrouillage, filtre des outils
│   ├── test_portier.py       ← tests automatiques du portier
│   └── requirements.txt      ← bibliothèques Python du portier
└── donnees/                  ← créé au premier démarrage — privé
    ├── chrome/               ← ton profil Chrome (connexions)
    ├── portier/              ← autorisations données à Claude (empreintes)
    └── journal.txt           ← tout ce que font les tâches
```

## Et ensuite ?

Demander à Claude des tâches dans le Chrome du NAS, avec le connecteur
« Chrome du NAS », sur des sites qui acceptent l'automatisation : préparer
une liste, surveiller une page, remplir un formulaire répétitif… Une tâche
planifiée de Cowork peut aussi le faire automatiquement, à heure fixe.
