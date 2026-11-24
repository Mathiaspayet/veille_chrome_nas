"""
Portier du pont MCP : la porte d'entrée sécurisée entre Claude et le Chrome
du NAS.

Pourquoi un portier ? Le pont (Playwright MCP) sait piloter Chrome, mais il
n'a AUCUN mot de passe : quiconque l'atteint pilote ton Chrome, connecté à
tes comptes. Le portier se place devant lui et :
  1. exige une connexion OAuth (le même système que l'appli Menus famille) :
     pour autoriser Claude, il faut saisir l'identifiant et le mot de passe
     de reglages.env ;
  2. se verrouille 15 minutes après 5 mots de passe faux ;
  3. bloque les outils dangereux du pont (exécution de code arbitraire) ;
  4. transmet tout le reste au pont, sans rien modifier.

Le parcours, vu de toi :
  1. dans Claude, tu ajoutes le connecteur https://<domaine>/mcp ;
  2. Claude ouvre la page « Autoriser » du portier ;
  3. tu saisis l'identifiant et le mot de passe de reglages.env, puis tu
     cliques sur « Autoriser » : Claude reçoit une clé d'accès (un « jeton »)
     qu'il renouvelle tout seul.

Côté technique, Claude suit la spécification d'autorisation MCP :
  - il lit /.well-known/oauth-protected-resource puis
    /.well-known/oauth-authorization-server ;
  - il s'enregistre tout seul (/oauth/enregistrer/, « Dynamic Client
    Registration ») ;
  - il obtient un code (/oauth/autoriser/, avec PKCE S256) puis des jetons
    (/oauth/jeton/), qu'il renouvelle avant expiration.

Seules les empreintes SHA-256 des codes et jetons sont enregistrées.
"""

import asyncio
import base64
import hashlib
import html
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import (HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response,
                                 StreamingResponse)
from starlette.routing import Route

PORTEE = "chrome"
DUREE_CODE = 10 * 60                  # 10 minutes
DUREE_ACCES = 60 * 60                 # 1 heure
# Renouvelé à chaque utilisation : Claude ne redemande l'autorisation
# qu'après 90 jours sans aucune utilisation.
DUREE_RAFRAICHISSEMENT = 90 * 24 * 3600

# Adresses de retour acceptées : celle des applis Claude (web, ordinateur,
# téléphone) et, pour Claude Code, une adresse locale de l'ordinateur.
HOTES_CLAUDE = {"claude.ai", "claude.com"}
CHEMIN_RETOUR_CLAUDE = "/api/mcp/auth_callback"
HOTES_LOCAUX = {"localhost", "127.0.0.1"}

# Protection contre les essais de mots de passe en rafale.
ESSAIS_MAX = 5
FENETRE_ESSAIS = 15 * 60              # 15 minutes
NB_MAX_CLIENTS = 200

# Outils du pont que Claude ne doit jamais pouvoir utiliser.
OUTILS_BLOQUES = {
    # Exécute n'importe quel code dans le conteneur du pont : sa propre
    # description dit « équivalent à une prise de contrôle à distance ».
    "browser_run_code_unsafe",
}

# En-têtes transmis entre Claude et le pont (tous les autres sont ignorés,
# en particulier « Authorization », qui ne regarde que le portier).
ENTETES_VERS_PONT = ("content-type", "accept", "mcp-session-id", "mcp-protocol-version", "last-event-id")
ENTETES_VERS_CLAUDE = ("content-type", "mcp-session-id", "mcp-protocol-version", "cache-control")


# --------------------------------------------------------------------------- outils

def empreinte(valeur):
    return hashlib.sha256(valeur.encode()).hexdigest()


def _pkce(verificateur):
    condense = hashlib.sha256(verificateur.encode("ascii")).digest()
    return base64.urlsafe_b64encode(condense).rstrip(b"=").decode("ascii")


def _redirection_autorisee(uri):
    try:
        p = urlsplit(uri)
    except ValueError:
        return False
    if p.fragment or not p.hostname:
        return False
    if p.scheme == "https" and p.hostname in HOTES_CLAUDE and p.path == CHEMIN_RETOUR_CLAUDE:
        return True
    return p.scheme == "http" and p.hostname in HOTES_LOCAUX


def _meme_redirection(demandee, enregistree):
    """Comparaison exacte, sauf pour les adresses locales (Claude Code) dont le
    port change à chaque session (RFC 8252, §7.3)."""
    if demandee == enregistree:
        return True
    try:
        a, b = urlsplit(demandee), urlsplit(enregistree)
    except ValueError:
        return False
    return (a.scheme == b.scheme == "http" and a.hostname in HOTES_LOCAUX and a.hostname == b.hostname
            and a.path == b.path and a.query == b.query)


def _avec_parametres(uri, **params):
    p = urlsplit(uri)
    requete = parse_qsl(p.query, keep_blank_values=True) + [(k, v) for k, v in params.items() if v is not None]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(requete), ""))


def _erreur(code, description, statut=400):
    return JSONResponse({"error": code, "error_description": description}, status_code=statut,
                        headers={"Cache-Control": "no-store"})


def filtrer_liste_outils(contenu, type_contenu):
    """Retire les outils bloqués de la réponse à « tools/list », qu'elle
    arrive en JSON simple ou en flux d'événements (text/event-stream)."""
    def nettoyer(message):
        resultat = message.get("result") if isinstance(message, dict) else None
        if isinstance(resultat, dict) and isinstance(resultat.get("tools"), list):
            resultat["tools"] = [o for o in resultat["tools"]
                                 if not (isinstance(o, dict) and o.get("name") in OUTILS_BLOQUES)]
        return message

    try:
        texte = contenu.decode("utf-8")
    except UnicodeDecodeError:
        return contenu
    if "text/event-stream" in type_contenu:
        lignes = []
        for ligne in texte.split("\n"):
            if ligne.startswith("data:"):
                try:
                    ligne = "data: " + json.dumps(nettoyer(json.loads(ligne[5:])), ensure_ascii=False)
                except ValueError:
                    pass
            lignes.append(ligne)
        return "\n".join(lignes).encode("utf-8")
    try:
        return json.dumps(nettoyer(json.loads(texte)), ensure_ascii=False).encode("utf-8")
    except ValueError:
        return contenu


def _appel_bloque(message):
    """Nom de l'outil bloqué demandé par ce message, sinon None."""
    if isinstance(message, dict) and message.get("method") == "tools/call":
        nom = (message.get("params") or {}).get("name")
        if nom in OUTILS_BLOQUES:
            return nom
    return None


# --------------------------------------------------------------------------- registre (SQLite)

class Registre:
    """Petite base SQLite : applications enregistrées, codes, jetons et
    essais de mot de passe ratés. Elle survit aux redémarrages, pour que
    Claude n'ait pas à redemander l'autorisation."""

    def __init__(self, chemin):
        self._verrou = threading.Lock()
        self._base = sqlite3.connect(chemin, check_same_thread=False, isolation_level=None)
        self._base.row_factory = sqlite3.Row
        self._base.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY, nom TEXT, redirect_uris TEXT, cree_le REAL);
            CREATE TABLE IF NOT EXISTS codes (
                code_hash TEXT PRIMARY KEY, client_id TEXT, redirect_uri TEXT, challenge TEXT, expire_le REAL);
            CREATE TABLE IF NOT EXISTS jetons (
                id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT,
                acces_hash TEXT UNIQUE, acces_expire_le REAL,
                rafraichissement_hash TEXT UNIQUE, rafraichissement_expire_le REAL,
                utilise_le REAL);
            CREATE TABLE IF NOT EXISTS echecs (horodatage REAL);
        """)

    def requete(self, sql, params=()):
        with self._verrou:
            return self._base.execute(sql, params).fetchall()

    def un(self, sql, params=()):
        lignes = self.requete(sql, params)
        return lignes[0] if lignes else None


# --------------------------------------------------------------------------- pages HTML

STYLE = """
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f4f5f7;color:#1f2328;margin:0;
padding:16px;display:flex;justify-content:center}
main{background:#fff;max-width:420px;width:100%;margin-top:6vh;padding:24px;border-radius:12px;
box-shadow:0 2px 12px rgba(0,0,0,.08)}
h1{font-size:1.3rem;margin:0 0 12px}p{line-height:1.5}
label{display:block;margin:14px 0 4px;font-weight:600}
input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:10px;border:1px solid #c9ccd1;
border-radius:8px;font-size:1rem}
.boutons{display:flex;gap:10px;margin-top:20px}
button{flex:1;padding:11px;border-radius:8px;border:0;font-size:1rem;cursor:pointer}
.oui{background:#1f6feb;color:#fff}.non{background:#e7e9ec;color:#1f2328}
.erreur{background:#ffebe9;color:#a40e26;padding:10px;border-radius:8px}
.note{color:#59636e;font-size:.9rem}
"""

ENTETES_HTML = {
    # La page ne peut pas être affichée dans un cadre d'un autre site
    # (protection contre le « clickjacking »).
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def page(titre, corps, statut=200):
    return HTMLResponse(
        f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(titre)}</title><style>{STYLE}</style></head>'
        f'<body><main>{corps}</main></body></html>',
        status_code=statut, headers=ENTETES_HTML)


def page_autoriser(champs, nom_client, hote, local, message=None, statut=200):
    caches = "".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
                     for k, v in champs.items())
    origine = ("Claude Code, sur un ordinateur" if local
               else f"Claude ({html.escape(hote)})")
    alerte = f'<p class="erreur">{html.escape(message)}</p>' if message else ""
    return page("Autoriser Claude", f"""
        <h1>Autoriser Claude à piloter le Chrome du NAS ?</h1>
        <p><strong>{origine}</strong> demande l'accès au connecteur
        « {html.escape(nom_client or 'Claude')} ».</p>
        <p>Il pourra ouvrir des pages, lire leur contenu, cliquer et taper du texte
        dans le Chrome du NAS, <strong>avec tes connexions aux sites</strong>.</p>
        {alerte}
        <form method="post" action="/oauth/autoriser/">
          {caches}
          <label for="identifiant">Identifiant (celui de reglages.env)</label>
          <input id="identifiant" name="identifiant" type="text" autocomplete="username" autocapitalize="none" required>
          <label for="mot_de_passe">Mot de passe (celui de reglages.env)</label>
          <input id="mot_de_passe" name="mot_de_passe" type="password" autocomplete="current-password" required>
          <div class="boutons">
            <button class="non" type="submit" name="decision" value="refuser" formnovalidate>Refuser</button>
            <button class="oui" type="submit" name="decision" value="autoriser">Autoriser</button>
          </div>
        </form>
        <p class="note">Tu pourras retirer cet accès à tout moment en supprimant le connecteur dans Claude.</p>
    """, statut)


# --------------------------------------------------------------------------- l'application

def creer_app(utilisateur, mot_de_passe, fichier_base, url_pont, transport=None, http_local=False,
              attente_echec=1.0):
    """Construit le portier. « transport » et « http_local » servent aux tests."""
    registre = Registre(fichier_base)
    client_pont = httpx.AsyncClient(
        transport=transport,
        # Lecture sans limite de durée : le pont peut garder un flux ouvert.
        timeout=httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0))

    # ----- adresses

    def url_base(request):
        """https://<domaine> tel que Claude le voit (le proxy inversé de DSM
        fait le HTTPS et transmet le nom de domaine d'origine)."""
        hote = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
        hote = hote.split(",")[0].strip()
        schema = request.url.scheme if http_local else "https"
        return f"{schema}://{hote}"

    def origine_autorisee(request):
        """Protection contre le « DNS rebinding » demandée par la spécification
        MCP : un navigateur ne doit pas pouvoir appeler /mcp depuis un autre
        site. Claude, lui, n'envoie pas d'en-tête Origin."""
        origine = request.headers.get("origin")
        if not origine:
            return True
        return (urlsplit(origine).hostname or "") == (urlsplit(url_base(request)).hostname or "")

    # ----- découverte

    async def metadonnees_ressource(request):
        """RFC 9728 : « pour utiliser /mcp, adressez-vous à ce serveur d'autorisation »."""
        base = url_base(request)
        return JSONResponse({
            "resource": base + "/mcp",
            "authorization_servers": [base],
            "scopes_supported": [PORTEE],
            "bearer_methods_supported": ["header"],
            "resource_name": "Chrome du NAS",
        })

    async def metadonnees_serveur(request):
        """RFC 8414 : adresses des étapes de connexion."""
        base = url_base(request)
        return JSONResponse({
            "issuer": base,
            "authorization_endpoint": base + "/oauth/autoriser/",
            "token_endpoint": base + "/oauth/jeton/",
            "registration_endpoint": base + "/oauth/enregistrer/",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [PORTEE],
        })

    # ----- enregistrement

    async def enregistrer(request):
        """RFC 7591 : Claude s'enregistre tout seul à chaque nouvelle connexion."""
        try:
            data = json.loads(await request.body() or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _erreur("invalid_client_metadata", "Corps JSON illisible.")
        if not isinstance(data, dict):
            return _erreur("invalid_client_metadata", "Un objet JSON est attendu.")
        uris = data.get("redirect_uris")
        if (not isinstance(uris, list) or not uris
                or not all(isinstance(u, str) and _redirection_autorisee(u) for u in uris)):
            return _erreur("invalid_redirect_uri", "Seules les adresses de retour de Claude sont acceptées.")

        maintenant = time.time()
        # Ménage : enregistrements de plus d'un jour qui n'ont mené à aucune connexion.
        registre.requete("DELETE FROM clients WHERE cree_le < ? AND client_id NOT IN "
                         "(SELECT DISTINCT client_id FROM jetons)", (maintenant - 86400,))
        if registre.un("SELECT COUNT(*) AS n FROM clients")["n"] >= NB_MAX_CLIENTS:
            return _erreur("temporarily_unavailable", "Trop d'enregistrements en attente, réessayez demain.", 503)

        client_id = secrets.token_urlsafe(24)
        nom = str(data.get("client_name") or "")[:200]
        registre.requete("INSERT INTO clients VALUES (?, ?, ?, ?)", (client_id, nom, json.dumps(uris), maintenant))
        return JSONResponse({
            "client_id": client_id,
            "client_id_issued_at": int(maintenant),
            "client_name": nom,
            "redirect_uris": uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }, status_code=201)

    # ----- autorisation

    def trop_d_echecs():
        limite = time.time() - FENETRE_ESSAIS
        registre.requete("DELETE FROM echecs WHERE horodatage < ?", (limite,))
        return registre.un("SELECT COUNT(*) AS n FROM echecs")["n"] >= ESSAIS_MAX

    async def autoriser(request):
        """Page « Autoriser Claude ? » (GET), puis décision (POST)."""
        p = dict(request.query_params) if request.method == "GET" else dict(await request.form())
        client = registre.un("SELECT * FROM clients WHERE client_id = ?", (p.get("client_id", ""),))
        redirect_uri = p.get("redirect_uri", "")
        if not client:
            return page("Erreur", "<h1>Application inconnue</h1><p>Retire le connecteur dans Claude, "
                                  "puis ajoute-le à nouveau.</p>", 400)
        if not redirect_uri or not any(_meme_redirection(redirect_uri, u) for u in json.loads(client["redirect_uris"])):
            return page("Erreur", "<h1>Adresse de retour non autorisée</h1>", 400)

        # À partir d'ici, les erreurs sont renvoyées à Claude par l'adresse de retour.
        etat = p.get("state")
        if p.get("response_type") != "code":
            return RedirectResponse(_avec_parametres(redirect_uri, error="unsupported_response_type", state=etat), 302)
        challenge = p.get("code_challenge", "")
        if not 43 <= len(challenge) <= 128 or p.get("code_challenge_method") != "S256":
            return RedirectResponse(_avec_parametres(
                redirect_uri, error="invalid_request", error_description="PKCE (S256) obligatoire.", state=etat), 302)

        champs = {k: p.get(k, "") for k in ("client_id", "redirect_uri", "response_type", "state",
                                             "code_challenge", "code_challenge_method", "scope", "resource")}
        hote = urlsplit(redirect_uri).hostname or ""
        afficher = lambda message=None, statut=200: page_autoriser(  # noqa: E731
            champs, client["nom"], hote, hote in HOTES_LOCAUX, message, statut)

        if request.method == "GET":
            return afficher()

        if p.get("decision") != "autoriser":
            return RedirectResponse(_avec_parametres(redirect_uri, error="access_denied", state=etat), 303)
        if trop_d_echecs():
            return afficher("Trop d'essais ratés : le portier est verrouillé. Réessaie dans 15 minutes.", 429)
        bon_identifiant = secrets.compare_digest(p.get("identifiant", "").encode(), utilisateur.encode())
        bon_mot_de_passe = secrets.compare_digest(p.get("mot_de_passe", "").encode(), mot_de_passe.encode())
        if not (bon_identifiant and bon_mot_de_passe):
            registre.requete("INSERT INTO echecs VALUES (?)", (time.time(),))
            await asyncio.sleep(attente_echec)  # ralentit les essais en rafale
            return afficher("Identifiant ou mot de passe incorrect.", 401)

        code = secrets.token_urlsafe(32)
        registre.requete("DELETE FROM codes WHERE expire_le < ?", (time.time(),))
        registre.requete("INSERT INTO codes VALUES (?, ?, ?, ?, ?)",
                         (empreinte(code), client["client_id"], redirect_uri, challenge, time.time() + DUREE_CODE))
        return RedirectResponse(_avec_parametres(redirect_uri, code=code, state=etat), 303)

    # ----- jetons

    def emettre(jeton_id, client_id):
        """Crée (ou renouvelle, en remplaçant les anciens) un couple de jetons."""
        acces, rafraichissement = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        maintenant = time.time()
        valeurs = (empreinte(acces), maintenant + DUREE_ACCES,
                   empreinte(rafraichissement), maintenant + DUREE_RAFRAICHISSEMENT)
        if jeton_id is None:
            registre.requete("INSERT INTO jetons (client_id, acces_hash, acces_expire_le, rafraichissement_hash, "
                             "rafraichissement_expire_le) VALUES (?, ?, ?, ?, ?)", (client_id, *valeurs))
        else:
            registre.requete("UPDATE jetons SET acces_hash = ?, acces_expire_le = ?, rafraichissement_hash = ?, "
                             "rafraichissement_expire_le = ? WHERE id = ?", (*valeurs, jeton_id))
        return JSONResponse({
            "access_token": acces, "token_type": "Bearer", "expires_in": DUREE_ACCES,
            "refresh_token": rafraichissement, "scope": PORTEE,
        }, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    async def jeton(request):
        """Échange d'un code (première connexion) ou renouvellement des jetons."""
        if request.headers.get("content-type", "").startswith("application/json"):
            try:  # tolérance : la norme demande un formulaire
                p = json.loads(await request.body() or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                return _erreur("invalid_request", "Corps illisible.")
            if not isinstance(p, dict):
                return _erreur("invalid_request", "Corps illisible.")
        else:
            p = dict(await request.form())
        client_id = p.get("client_id", "")
        client = registre.un("SELECT * FROM clients WHERE client_id = ?", (client_id,)) if client_id else None
        if client_id and not client:
            return _erreur("invalid_client", "Application inconnue.", 401)
        maintenant = time.time()
        grant = p.get("grant_type")

        if grant == "authorization_code":
            if not client:
                return _erreur("invalid_request", "client_id manquant.")
            code = registre.un("SELECT * FROM codes WHERE code_hash = ?", (empreinte(p.get("code", "")),))
            if not code or code["client_id"] != client_id:
                return _erreur("invalid_grant", "Code inconnu ou déjà utilisé.")
            registre.requete("DELETE FROM codes WHERE code_hash = ?", (code["code_hash"],))  # usage unique
            verificateur = p.get("code_verifier", "")
            if (code["expire_le"] < maintenant or p.get("redirect_uri", "") != code["redirect_uri"]
                    or not 43 <= len(verificateur) <= 128
                    or not secrets.compare_digest(_pkce(verificateur), code["challenge"])):
                return _erreur("invalid_grant", "Code expiré ou invalide.")
            return emettre(None, client_id)

        if grant == "refresh_token":
            j = registre.un("SELECT * FROM jetons WHERE rafraichissement_hash = ?",
                            (empreinte(p.get("refresh_token", "")),))
            if not j or (client and j["client_id"] != client_id) or j["rafraichissement_expire_le"] < maintenant:
                return _erreur("invalid_grant", "Jeton de renouvellement invalide : reconnecte le connecteur.")
            return emettre(j["id"], j["client_id"])

        return _erreur("unsupported_grant_type", "Types acceptés : authorization_code, refresh_token.")

    # ----- contrôle des appels /mcp

    def jeton_valide(request):
        """(valide, jeton_fourni)."""
        entete = request.headers.get("authorization", "")
        if entete[:7].lower() != "bearer ":
            return False, False
        j = registre.un("SELECT * FROM jetons WHERE acces_hash = ?", (empreinte(entete[7:].strip()),))
        maintenant = time.time()
        if not j or j["acces_expire_le"] < maintenant:
            return False, True
        if not j["utilise_le"] or maintenant - j["utilise_le"] > 300:
            registre.requete("UPDATE jetons SET utilise_le = ? WHERE id = ?", (maintenant, j["id"]))
        return True, True

    def refus(request, jeton_fourni):
        """401 qui indique à Claude où se connecter (et, si le jeton a expiré,
        qu'il doit le renouveler)."""
        entete = (f'Bearer resource_metadata="{url_base(request)}/.well-known/oauth-protected-resource/mcp", '
                  f'scope="{PORTEE}"')
        if jeton_fourni:
            entete += ', error="invalid_token"'
        return JSONResponse({"error": "invalid_token" if jeton_fourni else "unauthorized",
                             "error_description": "Autorisation du portier du NAS nécessaire."},
                            status_code=401, headers={"WWW-Authenticate": entete})

    async def point_mcp(request):
        """Transmet les échanges MCP au pont, après contrôle."""
        if not origine_autorisee(request):
            return JSONResponse({"error": "origine_refusee"}, status_code=403)
        valide, jeton_fourni = jeton_valide(request)
        if not valide:
            return refus(request, jeton_fourni)

        corps = await request.body() if request.method == "POST" else b""
        message = None
        if corps:
            try:
                message = json.loads(corps)
            except (json.JSONDecodeError, UnicodeDecodeError):
                message = None

        bloque = _appel_bloque(message)
        if bloque:
            return JSONResponse({"jsonrpc": "2.0", "id": message.get("id"), "error": {
                "code": -32601,
                "message": f"L'outil « {bloque} » est désactivé par le portier du NAS, car il permet "
                           f"d'exécuter n'importe quel code. Utilise les autres outils du navigateur."}})
        if isinstance(message, list) and any(_appel_bloque(m) for m in message):
            return JSONResponse({"error": "outil_bloque"}, status_code=400)
        a_filtrer = isinstance(message, dict) and message.get("method") == "tools/list"

        entetes = {k: v for k in ENTETES_VERS_PONT if (v := request.headers.get(k))}
        entetes["accept-encoding"] = "identity"  # flux transmis tel quel, sans compression
        requete_pont = client_pont.build_request(request.method, url_pont, headers=entetes, content=corps or None)
        try:
            reponse = await client_pont.send(requete_pont, stream=True)
        except httpx.HTTPError:
            return JSONResponse({"error": "pont_injoignable",
                                 "error_description": "Le pont MCP ne répond pas : Chrome et le pont sont-ils "
                                                      "démarrés sur le NAS ?"}, status_code=502)

        sortie = {k: reponse.headers[k] for k in ENTETES_VERS_CLAUDE if k in reponse.headers}
        # Demande au proxy inversé de DSM de ne pas retenir le flux.
        sortie["X-Accel-Buffering"] = "no"
        if a_filtrer:
            contenu = await reponse.aread()
            await reponse.aclose()
            contenu = filtrer_liste_outils(contenu, reponse.headers.get("content-type", ""))
            return Response(contenu, status_code=reponse.status_code, headers=sortie)
        return StreamingResponse(reponse.aiter_raw(), status_code=reponse.status_code, headers=sortie,
                                 background=BackgroundTask(reponse.aclose))

    # ----- pages simples

    async def accueil(request):
        return page("Portier du pont MCP", "<h1>Portier du pont MCP</h1>"
                    "<p>En service. Dans Claude, ajoute le connecteur avec l'adresse "
                    f"<strong>{html.escape(url_base(request))}/mcp</strong>.</p>")

    async def sante(request):
        return PlainTextResponse("ok")

    routes = [
        Route("/", accueil),
        Route("/sante", sante),
        Route("/mcp", point_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/mcp/", point_mcp, methods=["GET", "POST", "DELETE"]),
        Route("/.well-known/oauth-protected-resource", metadonnees_ressource),
        Route("/.well-known/oauth-protected-resource/mcp", metadonnees_ressource),
        Route("/.well-known/oauth-authorization-server", metadonnees_serveur),
        Route("/oauth/enregistrer/", enregistrer, methods=["POST"]),
        Route("/oauth/autoriser/", autoriser, methods=["GET", "POST"]),
        Route("/oauth/jeton/", jeton, methods=["POST"]),
    ]
    return Starlette(routes=routes)


# --------------------------------------------------------------------------- démarrage

def principal():
    import uvicorn

    utilisateur = os.environ.get("CHROME_UTILISATEUR", "")
    mot_de_passe = os.environ.get("CHROME_MOT_DE_PASSE", "")
    if not utilisateur or len(mot_de_passe) < 12:
        print("❌ CHROME_UTILISATEUR et CHROME_MOT_DE_PASSE (12 caractères minimum) sont obligatoires.",
              file=sys.stderr)
        sys.exit(1)
    dossier = os.environ.get("PORTIER_DOSSIER", "/donnees")
    os.makedirs(dossier, exist_ok=True)
    app = creer_app(
        utilisateur, mot_de_passe,
        fichier_base=os.path.join(dossier, "portier.sqlite3"),
        url_pont=os.environ.get("PONT_MCP_URL", "http://127.0.0.1:8931/mcp"),
    )
    print("✅ Portier du pont MCP en service.", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORTIER_PORT", "8930")),
                proxy_headers=False, server_header=False)


if __name__ == "__main__":
    principal()
