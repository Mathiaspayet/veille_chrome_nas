"""Tests du portier. Lancement : pytest -q portier/test_portier.py

Un faux « pont » remplace Playwright MCP : il renvoie une liste d'outils
contenant l'outil dangereux, pour vérifier que le portier le retire.
"""

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

import portier

UTILISATEUR, MOT_DE_PASSE = "moi", "Tartine-Velo-Nuage-42"
RETOUR = "https://claude.ai/api/mcp/auth_callback"
OUTILS = [{"name": "browser_navigate"}, {"name": "browser_run_code_unsafe"}, {"name": "browser_click"}]

recu_par_le_pont = []


async def faux_pont(request):
    corps = await request.body()
    recu_par_le_pont.append({"corps": corps, "entetes": dict(request.headers)})
    if request.method != "POST":
        return Response("", status_code=405)
    message = json.loads(corps)
    entetes = {"mcp-session-id": "session-1"}
    if message.get("method") == "tools/list":
        resultat = {"jsonrpc": "2.0", "id": message["id"], "result": {"tools": OUTILS}}
        if message.get("params", {}).get("format") == "sse":
            return Response(f"event: message\ndata: {json.dumps(resultat)}\n\n",
                            media_type="text/event-stream", headers=entetes)
        return JSONResponse(resultat, headers=entetes)
    return JSONResponse({"jsonrpc": "2.0", "id": message.get("id"), "result": {"recu": message.get("method")}},
                        headers=entetes)


PONT = Starlette(routes=[Route("/mcp", faux_pont, methods=["GET", "POST", "DELETE"])])


@pytest.fixture
def client(tmp_path):
    recu_par_le_pont.clear()
    app = portier.creer_app(UTILISATEUR, MOT_DE_PASSE, str(tmp_path / "base.sqlite3"), "http://pont/mcp",
                            transport=httpx.ASGITransport(app=PONT), http_local=True, attente_echec=0)
    with TestClient(app, base_url="http://nas.test") as c:
        yield c


def pkce():
    verificateur = secrets.token_urlsafe(48)
    defi = base64.urlsafe_b64encode(hashlib.sha256(verificateur.encode()).digest()).rstrip(b"=").decode()
    return verificateur, defi


def enregistrer(client):
    r = client.post("/oauth/enregistrer/", json={"client_name": "Claude", "redirect_uris": [RETOUR]})
    assert r.status_code == 201
    return r.json()["client_id"]


def parametres(client_id, defi):
    return {"client_id": client_id, "redirect_uri": RETOUR, "response_type": "code", "state": "etat42",
            "code_challenge": defi, "code_challenge_method": "S256", "scope": "chrome"}


def obtenir_jetons(client):
    client_id = enregistrer(client)
    verificateur, defi = pkce()
    r = client.post("/oauth/autoriser/", data={**parametres(client_id, defi), "decision": "autoriser",
                                                "identifiant": UTILISATEUR, "mot_de_passe": MOT_DE_PASSE},
                    follow_redirects=False)
    assert r.status_code == 303
    retour = parse_qs(urlsplit(r.headers["location"]).query)
    assert retour["state"] == ["etat42"]
    r = client.post("/oauth/jeton/", data={"grant_type": "authorization_code", "code": retour["code"][0],
                                           "client_id": client_id, "redirect_uri": RETOUR,
                                           "code_verifier": verificateur})
    assert r.status_code == 200, r.text
    return client_id, r.json()


def appel(client, jeton, message, **entetes):
    return client.post("/mcp", json=message, headers={
        "Authorization": f"Bearer {jeton}", "Accept": "application/json, text/event-stream", **entetes})


# --------------------------------------------------------------------------- découverte et enregistrement

def test_metadonnees(client):
    r = client.get("/.well-known/oauth-protected-resource/mcp", headers={"Host": "mcp-chrome.exemple.fr"})
    assert r.json()["resource"] == "http://mcp-chrome.exemple.fr/mcp"
    r = client.get("/.well-known/oauth-authorization-server")
    assert r.json()["code_challenge_methods_supported"] == ["S256"]


def test_nom_de_domaine_transmis_par_le_proxy(client):
    r = client.get("/.well-known/oauth-protected-resource", headers={"X-Forwarded-Host": "mcp-chrome.exemple.fr"})
    assert r.json()["authorization_servers"] == ["http://mcp-chrome.exemple.fr"]


def test_https_force_hors_tests(tmp_path):
    app = portier.creer_app(UTILISATEUR, MOT_DE_PASSE, str(tmp_path / "b.sqlite3"), "http://pont/mcp")
    with TestClient(app) as c:
        r = c.get("/.well-known/oauth-protected-resource", headers={"Host": "mcp-chrome.exemple.fr"})
        assert r.json()["resource"] == "https://mcp-chrome.exemple.fr/mcp"


def test_enregistrement_refuse_une_adresse_de_retour_etrangere(client):
    r = client.post("/oauth/enregistrer/", json={"redirect_uris": ["https://pirate.example/api/mcp/auth_callback"]})
    assert r.status_code == 400


# --------------------------------------------------------------------------- page d'autorisation

def test_page_autoriser_affiche_le_formulaire(client):
    client_id = enregistrer(client)
    r = client.get("/oauth/autoriser/", params=parametres(client_id, pkce()[1]))
    assert r.status_code == 200
    assert "Autoriser Claude à piloter le Chrome du NAS" in r.text
    assert r.headers["x-frame-options"] == "DENY"


def test_mauvais_mot_de_passe_refuse(client):
    client_id = enregistrer(client)
    r = client.post("/oauth/autoriser/", data={**parametres(client_id, pkce()[1]), "decision": "autoriser",
                                                "identifiant": UTILISATEUR, "mot_de_passe": "faux-mot-de-passe"},
                    follow_redirects=False)
    assert r.status_code == 401
    assert "incorrect" in r.text


def test_verrouillage_apres_cinq_essais(client):
    client_id = enregistrer(client)
    params = {**parametres(client_id, pkce()[1]), "decision": "autoriser", "identifiant": UTILISATEUR}
    for _ in range(5):
        client.post("/oauth/autoriser/", data={**params, "mot_de_passe": "mauvais"}, follow_redirects=False)
    # Même le bon mot de passe est refusé pendant le verrouillage.
    r = client.post("/oauth/autoriser/", data={**params, "mot_de_passe": MOT_DE_PASSE}, follow_redirects=False)
    assert r.status_code == 429
    assert "verrouillé" in r.text


def test_refuser_renvoie_access_denied(client):
    client_id = enregistrer(client)
    r = client.post("/oauth/autoriser/", data={**parametres(client_id, pkce()[1]), "decision": "refuser"},
                    follow_redirects=False)
    assert "error=access_denied" in r.headers["location"]


def test_pkce_obligatoire(client):
    client_id = enregistrer(client)
    params = parametres(client_id, "trop-court")
    r = client.get("/oauth/autoriser/", params=params, follow_redirects=False)
    assert r.status_code == 302 and "error=invalid_request" in r.headers["location"]


def test_mauvais_verificateur_pkce(client):
    client_id = enregistrer(client)
    _, defi = pkce()
    r = client.post("/oauth/autoriser/", data={**parametres(client_id, defi), "decision": "autoriser",
                                                "identifiant": UTILISATEUR, "mot_de_passe": MOT_DE_PASSE},
                    follow_redirects=False)
    code = parse_qs(urlsplit(r.headers["location"]).query)["code"][0]
    r = client.post("/oauth/jeton/", data={"grant_type": "authorization_code", "code": code, "client_id": client_id,
                                           "redirect_uri": RETOUR, "code_verifier": secrets.token_urlsafe(48)})
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


# --------------------------------------------------------------------------- jetons

def test_renouvellement_des_jetons(client):
    client_id, jetons = obtenir_jetons(client)
    r = client.post("/oauth/jeton/", data={"grant_type": "refresh_token", "refresh_token": jetons["refresh_token"],
                                           "client_id": client_id})
    assert r.status_code == 200
    nouveaux = r.json()
    # L'ancien jeton d'accès ne marche plus, le nouveau oui.
    assert appel(client, jetons["access_token"], {"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 401
    assert appel(client, nouveaux["access_token"], {"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 200
    # L'ancien jeton de renouvellement est usé.
    r = client.post("/oauth/jeton/", data={"grant_type": "refresh_token", "refresh_token": jetons["refresh_token"]})
    assert r.status_code == 400


def test_les_jetons_survivent_a_un_redemarrage(tmp_path):
    base = str(tmp_path / "base.sqlite3")
    transport = httpx.ASGITransport(app=PONT)
    app = portier.creer_app(UTILISATEUR, MOT_DE_PASSE, base, "http://pont/mcp", transport=transport,
                            http_local=True, attente_echec=0)
    with TestClient(app) as c:
        _, jetons = obtenir_jetons(c)
    app2 = portier.creer_app(UTILISATEUR, MOT_DE_PASSE, base, "http://pont/mcp", transport=transport,
                             http_local=True, attente_echec=0)
    with TestClient(app2) as c:
        assert appel(c, jetons["access_token"], {"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 200


# --------------------------------------------------------------------------- passage vers le pont

def test_sans_jeton_401_avec_indication(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 401
    assert "resource_metadata=" in r.headers["www-authenticate"]
    assert recu_par_le_pont == []


def test_faux_jeton_refuse(client):
    r = appel(client, "nimporte-quoi", {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 401 and 'error="invalid_token"' in r.headers["www-authenticate"]


def test_transmission_au_pont(client):
    _, jetons = obtenir_jetons(client)
    r = appel(client, jetons["access_token"], {"jsonrpc": "2.0", "id": 7, "method": "initialize"},
              **{"Mcp-Protocol-Version": "2025-06-18"})
    assert r.status_code == 200 and r.json()["result"]["recu"] == "initialize"
    assert r.headers["mcp-session-id"] == "session-1"
    assert r.headers["x-accel-buffering"] == "no"
    recu = recu_par_le_pont[-1]["entetes"]
    assert "authorization" not in recu            # le jeton ne sort pas du portier
    assert recu["mcp-protocol-version"] == "2025-06-18"


@pytest.mark.parametrize("format_", ["json", "sse"])
def test_outil_dangereux_retire_de_la_liste(client, format_):
    _, jetons = obtenir_jetons(client)
    r = appel(client, jetons["access_token"],
              {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"format": format_}})
    assert r.status_code == 200
    texte = r.text
    assert "browser_navigate" in texte and "browser_click" in texte
    assert "browser_run_code_unsafe" not in texte


def test_outil_dangereux_bloque(client):
    _, jetons = obtenir_jetons(client)
    avant = len(recu_par_le_pont)
    r = appel(client, jetons["access_token"], {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                               "params": {"name": "browser_run_code_unsafe", "arguments": {}}})
    assert r.json()["error"]["code"] == -32601
    assert len(recu_par_le_pont) == avant          # rien n'est parti vers le pont


def test_origine_etrangere_refusee(client):
    _, jetons = obtenir_jetons(client)
    r = appel(client, jetons["access_token"], {"jsonrpc": "2.0", "id": 1, "method": "ping"},
              Origin="https://pirate.example")
    assert r.status_code == 403


def test_pont_injoignable(tmp_path):
    app = portier.creer_app(UTILISATEUR, MOT_DE_PASSE, str(tmp_path / "b.sqlite3"), "http://127.0.0.1:9/mcp",
                            http_local=True, attente_echec=0)
    with TestClient(app) as c:
        _, jetons = obtenir_jetons(c)
        r = appel(c, jetons["access_token"], {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r.status_code == 502 and r.json()["error"] == "pont_injoignable"
