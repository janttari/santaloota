#!/usr/bin/env python3

import subprocess
import threading
import time
import json
import datetime
import signal
import paho.mqtt.client as mqtt

# ================= CONFIG =================

broker = "127.0.0.1"
port = 1883
topic = "nitro/red31/pty"
client_id = "pypaho"

HALYTTAVAT = ["Alarm", "Alarm test"] #, "News"]
MUTESTATUS = True

# ================= STATE =================

running = True

nyt_pty = None
muuttuva_pty = []
pty_lock = threading.Lock()

aplay = None
aplay_lock = threading.Lock()

mqtt_connected = False
mqtt_lock = threading.Lock()
mqtt_queue = []
mqtt_ready = threading.Event()

# ================= MQTT =================

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)


def on_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connected
    with mqtt_lock:
        mqtt_connected = True

    print("[MQTT] connected")
    mqtt_ready.set()   # <-- replaces sleep


def on_disconnect(client, userdata, reason_code, properties=None):
    global mqtt_connected
    with mqtt_lock:
        mqtt_connected = False

    print("[MQTT] disconnected")
    mqtt_ready.clear()


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.reconnect_delay_set(min_delay=1, max_delay=30)

client.connect_async(broker, port, 60)
client.loop_start()

# wait for broker (instead of time.sleep)
print("[MQTT] waiting for broker...")
mqtt_ready.wait(timeout=15)

if mqtt_ready.is_set():
    print("[MQTT] ready")
else:
    print("[MQTT] WARNING: broker not ready (continuing anyway)")

# ================= MQTT SAFE PUBLISH =================

def mqtt_publish(msg):
    with mqtt_lock:
        if mqtt_connected:
            try:
                client.publish(topic, msg)

                while mqtt_queue:
                    client.publish(topic, mqtt_queue.pop(0))

            except Exception as e:
                print("[MQTT] publish error:", e)
        else:
            mqtt_queue.append(msg)

# ================= SYSTEMD SHUTDOWN =================

def shutdown(signum=None, frame=None):
    global running
    print("[SYS] shutdown")

    running = False

    for p in [redsea, rtl_fm, aplay]:
        try:
            if p:
                p.terminate()
        except:
            pass

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# ================= APLAY CONTROL =================

def start_aplay():
    global aplay
    with aplay_lock:
        if aplay is None:
            print("[APLAY] start")
            aplay = subprocess.Popen(
                ["aplay", "-t", "raw", "-r", "171000", "-c", "1", "-f", "S16_LE"],
                stdin=subprocess.PIPE
            )


def stop_aplay():
    global aplay
    with aplay_lock:
        if aplay:
            print("[APLAY] stop")
            try:
                if aplay.stdin:
                    aplay.stdin.close()
                aplay.terminate()
            except:
                pass
            aplay = None

# ================= RDS READER =================

def rds_reader(stream):
    global nyt_pty, muuttuva_pty, MUTESTATUS

    buffer = ""

    with stream:
        while running:
            chunk = stream.read(1024)
            if not chunk:
                break

            buffer += chunk.decode(errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                try:
                    j = json.loads(line)
                except:
                    continue

                pty = j.get("prog_type")
                if not pty:
                    continue

                with pty_lock:
                    if pty != nyt_pty:
                        muuttuva_pty.append(pty)

                        if not all(v == pty for v in muuttuva_pty):
                            muuttuva_pty = []

                        elif len(muuttuva_pty) > 10:
                            nyt_pty = pty
                            muuttuva_pty = []

                            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            msg = f"{now} {pty}"

                            print("[PTY]", msg)
                            mqtt_publish(msg)

                            # AUDIO LOGIC
                            if nyt_pty in HALYTTAVAT:
                                if MUTESTATUS:
                                    MUTESTATUS = False
                                    start_aplay()
                            else:
                                if not MUTESTATUS:
                                    MUTESTATUS = True
                                    stop_aplay()

# ================= AUDIO PIPE =================

def audio_pipe():
    with redsea.stdout:
        while running:
            data = redsea.stdout.read(4096)
            if not data:
                break

            with aplay_lock:
                if aplay:
                    try:
                        aplay.stdin.write(data)
                        aplay.stdin.flush()
                    except:
                        pass

# ================= START SDR =================

#time.sleep(30)  # systemd boot safety delay

rtl_fm = subprocess.Popen(
    ["rtl_fm", "-f", "97.9M", "-s", "171k", "-"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=False
)

redsea = subprocess.Popen(
    ["redsea", "-r", "171k", "-e"],
    stdin=rtl_fm.stdout,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=False,
    bufsize=0
)

rtl_fm.stdout.close()

# ================= THREADS =================

threading.Thread(target=rds_reader, args=(redsea.stderr,), daemon=True).start()
threading.Thread(target=audio_pipe, daemon=True).start()

# ================= MAIN LOOP =================

try:
    while running:
        if redsea.poll() is not None:
            break
        if rtl_fm.poll() is not None:
            break
        time.sleep(0.5)

finally:
    shutdown()
    client.loop_stop()
