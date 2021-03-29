#!/usr/bin/env python3

# RDS-vaaratiedotteiden vastaanottaja Raspberrylle
# RELEPINNI ohjaa vahvistimen päälle kun vaaratiedote tulee.
# PIIPPARIPINNI soittaa lyhyesti summeria (varmistus jos vahvistin ei toimikaan niin saa silti jonkinlaisen signaalin)
#
# Vastaanotto tapahtuu millä tahansa rtl_fm:n tukemalla DVB-tikulla ja RDS-signaali tulkitaan ohjelmalla https://github.com/windytan/redsea
# rtl_fm --> redsea --> [!mute] --> aplay
# Tämä koodi on pelkkä testiversio ja edellyttäisi lähinnä kirjoittamista kokonaan uusiksi selkeyden kannalta :D
#
# Kun vaaratiedote tai liikennetiedote ei ole menossa, ei kirjoiteta aplaylle ollenkaan, niin äänikortilla voi tehdä muutakin.


import threading,subprocess, time, json
import RPi.GPIO as GPIO
from datetime import datetime

RELEPINNI=23 #Tässä pinnissä on vahvistinta ohjaava rele
PIIPPARIPINNI=25 #Tässä pinnissä on summeri
VARMISTUSKERRAT=5 #Sama PTY-koodi pitää saada näin monta kertaa peräkkäin jotta se tulkitaan muuttuneeksi (sulkee pois huonossa kentässä häiriön mahdollisuudet)
halyttavat=("Alarm", "Alarm test") #nämä pty:t pistää kaiuttimen päälle (ks github.com/windytan/redsea/blob/master/src/tables.cc )

lhalyttavat = [x.lower() for x in halyttavat]
onkoRelePaalla=None
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELEPINNI, GPIO.OUT) 
GPIO.setup(PIIPPARIPINNI, GPIO.OUT)
LIIKENNE=False #reagoi TA liikennetiedotteisiin myös?
BUFSIZE=128
aja=True #Prosessien lopettaminen liipaisemalla Falseksi !TODO

tulosta=True
rtlkomento="rtl_fm -d 114 -M fm -l 0 -A std -p 0 -s 171k -g 20 -F 9 -f 96.0M".split(" ")
playkomento="aplay -M -r 171000 -f S16_LE".split(" ")
#playkomento="play -r 171k -t raw -e s -b 16 -c 1 -V1 -".split(" ")
redseapros=None
playpros=None
mute=False

def lokita(*sanoma):
    now = datetime.now()
    dt_string = now.strftime("%Y%m%d %H:%M:%S")
    ssanoma=""
    for s in sanoma:
        ssanoma+=str(s)+" "
    ssanoma+="\n"
    with open ("/tmp/redsealoki.txt", "a") as f:
        f.write(dt_string + " " + ssanoma)


def relepaalle(): # ja unmute
    global onkoRelePaalla, mute, RELEPINNI, PIIPPARIPINNI
    if  onkoRelePaalla != True:
        onkoRelePaalla=True
        lokita("*Rele päälle")
        mute=False
        GPIO.output(PIIPPARIPINNI, GPIO.HIGH)
        GPIO.output(RELEPINNI, GPIO.HIGH)
        time.sleep(0.7)
        GPIO.output(PIIPPARIPINNI, GPIO.LOW)
    else:
        lokita("*rele on jo päällä")


def relepois(): # ja mute
    global onkoRelePaalla, mute
    if onkoRelePaalla == True or onkoRelePaalla == None:
        onkoRelePaalla=False
        lokita("*Rele pois")
        mute=True
        GPIO.output(RELEPINNI, GPIO.LOW)
    else:
        lokita("*rele on jo pois")

def rtlLooppi(): #lukee DVB-tikulta dataa
    global proc, redseapros, mute, playpros, tulosta, aja 
    k=0
    while aja:
        proc = subprocess.Popen(rtlkomento,stdout=subprocess.PIPE)
        while aja:
            line = proc.stdout.read(BUFSIZE)
            if not aja:
                break
            #lokita(line)
            if redseapros is not None:
                #lokita("writetoted")
                redseapros.stdin.write(line)
            if playpros is not None and not mute:
                if tulosta:
                    lokita(len(line),k)
                    tulosta=False
                playpros.stdin.write(line)
            k+=1
    proc.terminate()
    lokita("end rtllooppi")


def redsealooppi():
    global redseapros, aja
    global proc, redseapros, mute, playpros, tulosta
    nytPty="" #tällä lukukierroksella saatu pty
    viimPty="" #edellisellä lukukierroksella saatu pty
    voimassaPty="None" #rekisteröimämme pty
    saatuPty=0 #sama pty saatu näin monta kertaa
    saatuTa=0 #sama TA saatu näin monta kertaa
    voimassaTa=-1
    redseapros = subprocess.Popen("redsea",stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    while aja:
        line = redseapros.stdout.readline()
        if not line:
            break
        if "prog_type" in line.decode():
            rjson=json.loads(line.decode())
            nytPty=rjson.get("prog_type").lower()
            nytTa=rjson.get("ta")
            #lokita(nytTa)
            if nytTa is not None:
                if nytTa != voimassaTa:
                    saatuTa+=1
                    lokita("ta muutos", nytTa,voimassaTa,saatuTa)
                    #lokita(rjson)
                    if saatuTa>=VARMISTUSKERRAT:
                        lokita("TA muuttui", nytTa)
                        voimassaTa=nytTa
                        saatuTa=0
                        if LIIKENNE:
                            if voimassaTa:
                                lokita("liikennetiedote alkoi, rele päälle")
                                relepaalle()
                            else:
                                lokita("liikennetiedote päättyi, rele pois")
                                relepois()
                else:
                    saatuTa=0

                #lokita(pty)
        if nytPty == viimPty and nytPty != voimassaPty:
            saatuPty+=1
            lokita("ptymuutos", nytPty, saatuPty,"/",VARMISTUSKERRAT)
            if saatuPty>=VARMISTUSKERRAT:
                voimassaPty=nytPty
                lokita("PTY vaihtui, uusi: "+voimassaPty, saatuPty)
                saatuPty=0
                if nytPty.lower() in lhalyttavat:
                    lokita("rele päälle")
                    relepaalle()
                else:
                    lokita("rele pois")
                    relepois()
        else:
            #lokita("virhe: "+nytPty)
            viimPty=nytPty
            saatuPty=0
        #lokita(line)
    lokita("end redsea")
    redseapros.terminate()


def playLooppi():
    global playpros, aja
    playpros = subprocess.Popen(playkomento,stdin=subprocess.PIPE)
    while aja:
        time.sleep(1)
    lokita("end play")
    playpros.terminate()

if __name__ == "__main__":
    r=threading.Thread(target=rtlLooppi)
    r.start()
    p=threading.Thread(target=playLooppi)
    p.start()
    rs=threading.Thread(target=redsealooppi)
    rs.start()
    while aja:
        time.sleep(1)
    redseapros.terminate()
    k.join()
    r.join()
    p.join()
    rs.join()
    lokita("end main")

