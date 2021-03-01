  #!/usr/bin/env python3

# sudo apt install tesseract-ocr-fin tesseract-ocr
# sudo /usr/bin/python3 -m pip install --upgrade pip
# sudo python3 -m pip install --upgrade pip setuptools wheel
# sudo pip3 install pytesseract
# sudo pip3 install av

import av
import cv2
import numpy
import pytesseract

url = '/home/pulla/ts/2.ts'
input_container = av.open(url)

for packet in input_container.demux():
    if packet.size>0:
        #print(packet.stream.language)
        if packet.pts is not None:
            if packet.stream.type =="video":
                pp=packet.decode()
                for frame in pp:
                    pass

        if packet.stream.type =="subtitle":
            if packet.stream.name == "dvbsub":
                t=packet.decode()
                for tt in t:
                    for h in tt: 
                        # print("yrivi",h.y, "xkoord",h.x) #ylempi rivi voi tulla myöhempään!
                        # print("h", h.planes, h, h.nb_colors, "koko", h.height, h.width) # h.height*h.width) == g.buffer_size
                        for g in h .planes:
                            kuva= numpy.zeros((h.height, h.width, 3), numpy.uint8)
                            img = bytes(g)
                            x=0
                            y=0
                            for i in range(len(img)):
                                pass
                                bit=img[i]
                                if bit >12:
                                    kuva[y,x]=[0,0,0]

                                else:
                                    kuva[y,x]=[255,255,255]
                                x+=1
                                if x==h.width:
                                    x=0
                                    y+=1
                            img_rgb = cv2.cvtColor(kuva, cv2.COLOR_BGR2RGB)
                            kaannos=pytesseract.image_to_string(img_rgb, lang='fin')
                            print(packet.stream.language, packet.stream.id, kaannos.rstrip())
                            # cv2.imshow('img', kuva)
                            # cv2.waitKey(0)
                            
     
