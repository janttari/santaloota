const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

class Player {
    constructor(options = {}) {
        this.musicDir = options.musicDir ;
        this.output = options.output; // RadioStream.write()
        this.ffmpeg = null;
        this.running = false;
    }


    async start() {
        if (this.running) {
            console.log("Player already running");
            return;
        }

        this.running = true;

        while (this.running) {
            const song = this.randomSong();

            if (!song) {
                console.error("Ei löytynyt kappaleita");
                this.running = false;
                break;
            }

            console.log("Playing:", song);

            await this.play(song);
        }
    }


    stop() {
        if (!this.running) return;
        console.log("Stopping player");
        this.running = false;

        if (this.ffmpeg) {
            console.log("Sending SIGTERM to ffmpeg");
            this.ffmpeg.kill("SIGTERM");
            this.ffmpeg = null;
        }
    }


    randomSong() {
        const files = fs.readdirSync(this.musicDir)
            .filter(file => {
                const ext = path.extname(file).toLowerCase();

                return [
                    ".opus",
                    ".mp3",
                    ".ogg",
                    ".flac",
                    ".wav",
                    ".m4a"
                ].includes(ext);
            });


        if (files.length === 0) {
            return null;
        }


        const file =
            files[Math.floor(Math.random() * files.length)];

        return path.join(this.musicDir, file);
    }


    play(file) {

        return new Promise((resolve, reject) => {

            this.ffmpeg = spawn("ffmpeg", [
                "-hide_banner",
                "-loglevel", "error",
                "-re",
                "-i", file,

                "-c:a", "libmp3lame",
                "-b:a", "128k",

                "-f", "mp3",

                "-"
            ]);





            this.ffmpeg.stdout.on("data", data => {

                if (this.output) {
                    this.output.write(data);
                }

            });


            // this.ffmpeg.stderr.on("data", data => {
            //     // ffmpeg kirjoittaa logit tänne
            //     // console.log(data.toString());
            // });


            this.ffmpeg.on("close", code => {

                this.ffmpeg = null;

                console.log(
                    "Finished:",
                    path.basename(file),
                    "code:",
                    code
                );

                resolve();

            });


            this.ffmpeg.on("error", err => {
                this.ffmpeg = null;
                reject(err);
            });

        });
    }
}


module.exports = Player;