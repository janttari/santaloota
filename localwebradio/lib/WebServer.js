const express = require("express");
const http = require("http");
const EventEmitter = require("events");

class WebServer extends EventEmitter {

    constructor() {
        super();

        this.clients = new Map();
        this.nextId = 1;

        const app = express();

        app.use(express.static("www"));

        app.get("/stream", (req, res) => {

            const id = this.nextId++;
            const ip = req.socket.remoteAddress;
            const ua = req.headers["user-agent"] || "-";

            //
            // TCP-asetukset
            //
            req.socket.setNoDelay(true);
            req.socket.setKeepAlive(true);

            //
            // Jos samasta IP:stä on jo yhteys,
            // suljetaan vanha.
            //
            for (const [oldId, client] of this.clients) {

                if (client.ip === ip) {

                    console.log(`Replacing client ${oldId} -> ${id}`);

                    try {
                        client.res.destroy();
                    } catch {}

                    this.clients.delete(oldId);
                }
            }

            console.log(`CONNECT ${id} ${ip} ${ua}`);

            res.writeHead(200, {
                "Content-Type": "audio/mpeg",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            });

            // Lähetä HTTP-headerit heti
            res.flushHeaders();

            this.clients.set(id, {
                id,
                ip,
                ua,
                res
            });

            console.log("Listeners:", this.clients.size);

            if (this.clients.size === 1) {
                this.emit("firstClient");
            }

            const disconnect = () => {

                if (!this.clients.has(id))
                    return;

                console.log(`DISCONNECT ${id}`);

                this.clients.delete(id);

                console.log("Listeners:", this.clients.size);

                if (this.clients.size === 0) {
                    this.emit("lastClient");
                }
            };

            res.on("close", disconnect);
            req.on("aborted", disconnect);

        });

        this.server = http.createServer(app);

        //
        // Siivotaan mahdolliset kuolleet yhteydet
        //
        setInterval(() => {

            for (const [id, client] of this.clients) {

                if (client.res.destroyed) {

                    console.log(`Removing dead client ${id}`);

                    this.clients.delete(id);

                }

            }

        }, 30000);
    }

    start(port = 8080) {

        this.server.listen(port, () => {
            console.log(`HTTP listening on ${port}`);
        });

    }

    write(buffer) {

        for (const [id, client] of this.clients) {

            if (client.res.destroyed) {
                this.clients.delete(id);
                continue;
            }

            try {

                client.res.write(buffer);

            } catch (err) {

                console.log(`Write failed for client ${id}`);

                try {
                    client.res.destroy();
                } catch {}

                this.clients.delete(id);

            }

        }

    }

    stop() {

        for (const [, client] of this.clients) {

            try {
                client.res.end();
            } catch {}

        }

        this.clients.clear();

        this.server.close();

    }

}

module.exports = WebServer;