// =====================================================================
//  Relais côté pont : rend la prise de pilotage de Chrome disponible
//  « ici », sur 127.0.0.1:9222, en la faisant venir du conteneur chrome
//  (relais du port 9223, par le réseau Docker du projet).
//
//  Pourquoi passer par 127.0.0.1:9222 ? Chrome n'accepte d'être piloté
//  que par une adresse locale : vu de Chrome, la demande vient bien de
//  « 127.0.0.1:9222 ». Et l'adresse de Chrome est retrouvée à CHAQUE
//  connexion : si Chrome est redémarré ou recréé, le relais le suit.
//
//  Ancienne installation (pont dans le réseau de Chrome) : le port 9222
//  est déjà celui de Chrome, le relais est inutile et s'efface.
// =====================================================================

const net = require("net");

const HOTE_CHROME = process.env.CHROME_HOTE || "chrome";
const PORT_RELAIS_CHROME = Number(process.env.CHROME_PORT_RELAIS || 9223);

const serveur = net.createServer((client) => {
  const chrome = net.connect(PORT_RELAIS_CHROME, HOTE_CHROME);
  client.pipe(chrome).pipe(client);
  const fermer = () => {
    client.destroy();
    chrome.destroy();
  };
  client.on("error", fermer);
  chrome.on("error", fermer);
  client.on("close", fermer);
  chrome.on("close", fermer);
});

serveur.on("error", (erreur) => {
  if (erreur.code === "EADDRINUSE") {
    console.log("Relais CDP inutile : Chrome est déjà sur ce réseau (ancienne installation).");
    process.exit(0);
  }
  console.error("❌ Relais CDP :", erreur.message);
  process.exit(1);
});

serveur.listen(9222, "127.0.0.1", () => {
  console.log(`✅ Relais CDP en service : 127.0.0.1:9222 -> ${HOTE_CHROME}:${PORT_RELAIS_CHROME}`);
});
