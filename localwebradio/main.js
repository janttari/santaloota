#!/usr/bin/env node
const WebServer = require("./lib/WebServer");
const Player = require("./lib/Player");

const web = new WebServer();

const player = new Player({
    musicDir: "/www/musa",
    output: web
});

web.start(7052);

let stopTimer = null;

web.on("firstClient", () => {
    console.log("First listener");
    if (stopTimer) {
        console.log("Cancelling stop timer");
        clearTimeout(stopTimer);
        stopTimer = null;
    }

    player.start();

});

web.on("lastClient", () => {
    console.log("Last listener");
    console.log("Starting 30 second stop timer");
    stopTimer = setTimeout(() => {
        console.log("Stop timer expired");
        stopTimer = null;
        player.stop();
    }, 30000);

});

function shutdown() {
    console.log("Stopping radio...");
    player.stop();
    web.stop();
    process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
