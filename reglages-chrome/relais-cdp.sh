#!/usr/bin/with-contenv bash
# =====================================================================
#  Relais de la prise de pilotage de Chrome.
#
#  Chrome n'ouvre sa prise de pilotage (port 9222) qu'à l'intérieur de
#  son conteneur. Ce relais la rend accessible, sur le port 9223, aux
#  autres conteneurs du projet (le pont MCP), par le réseau Docker du
#  projet. Rien n'est ouvert vers ton réseau ni vers Internet : le port
#  9223 n'est pas publié.
#
#  Grâce à lui, le pont n'a plus besoin de partager le réseau de Chrome :
#  chaque conteneur démarre seul, dans n'importe quel ordre (redémarrage
#  du NAS, de Chrome seul, mise à jour par Watchtower).
#
#  Service personnalisé de l'image linuxserver (/custom-services.d) : il
#  doit appartenir à root (chrome-nas.sh s'en charge). Il tourne avec
#  l'utilisateur du bureau (abc), pas en root.
# =====================================================================

exec s6-setuidgid abc python3 -u - <<'PYTHON'
import asyncio


async def tuyau(lecteur, ecrivain):
    """Recopie tout ce qui arrive d'un côté vers l'autre."""
    try:
        while True:
            donnees = await lecteur.read(65536)
            if not donnees:
                break
            ecrivain.write(donnees)
            await ecrivain.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            ecrivain.close()
        except Exception:
            pass


async def nouveau_client(lecteur_client, ecrivain_client):
    try:
        lecteur_chrome, ecrivain_chrome = await asyncio.open_connection("127.0.0.1", 9222)
    except OSError:
        # Chrome est fermé (le veilleur va le relancer) : on raccroche.
        ecrivain_client.close()
        return
    await asyncio.gather(tuyau(lecteur_client, ecrivain_chrome), tuyau(lecteur_chrome, ecrivain_client))


async def principal():
    serveur = await asyncio.start_server(nouveau_client, "0.0.0.0", 9223)
    print("[relais-cdp] en service : port 9223 (réseau du projet) -> prise de Chrome 9222", flush=True)
    async with serveur:
        await serveur.serve_forever()


asyncio.run(principal())
PYTHON
