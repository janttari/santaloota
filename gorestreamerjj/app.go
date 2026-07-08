package main

/*
KÄYTTÖ:

vlc 'http://192.168.0.19:9090/stream?rix'


custom stream:
vlc 'http://192.168.0.19:9090/url?url=https://st.downtime.fi/sun.mp3&vol=20'


*/
import (
	"fmt"
	"gorestreamerjj/streamreader"
	"net/http"
)

type Stream struct {
	URL    string
	Volume int
}

var streamDict = map[string]Stream{
	"voima": {
		URL:    "https://cast2.radiovoima.fi/voima.mp3",
		Volume: 100,
	},
	"vaasa": {
		URL:    "https://stream.protonbroadcast.com:8443/radiovaasa.mp3",
		Volume: 100,
	},
	"rix": {
		URL:    "https://fm01-ice.stream.khz.se/fm01_mp3",
		Volume: 90,
	},
	"ylelahti": {
		URL:    "https://yleradiolive.akamaized.net/hls/live/2027710/in-YleLahti/master.m3u8",
		Volume: 100,
	},
	"finska": {
		URL:    "https://live1.sr.se/finska-mp3-96",
		Volume: 100,
	},
}

func main() {
	http.HandleFunc("/stream", handleStream)
	http.HandleFunc("/url", handleURLStream)

	fmt.Println("Serveri käynnissä portissa :9090")

	err := http.ListenAndServe(":9090", nil)
	if err != nil {
		fmt.Println("server error:", err)
	}
}

func handleStream(w http.ResponseWriter, r *http.Request) {

	chName := r.URL.RawQuery

	if chName == "" {
		for k := range streamDict {
			chName = k
			break
		}
	}

	stream, ok := streamDict[chName]
	if !ok {
		http.Error(w, "Kanavaa ei löydy", 404)
		return
	}

	webID := fmt.Sprintf("%p", r)

	msgch := streamreader.PlayStream(
		chName,
		stream.URL,
		stream.Volume,
		webID,
	)

	defer streamreader.RemoveClient(chName, webID)

	streamResponse(w, r, msgch)
}

func handleURLStream(w http.ResponseWriter, r *http.Request) {

	url := r.URL.Query().Get("url")
	if url == "" {
		http.Error(w, "url missing", 400)
		return
	}

	volStr := r.URL.Query().Get("vol")
	volume := 100

	if volStr != "" {
		fmt.Sscanf(volStr, "%d", &volume)
	}

	// 🔥 TÄMÄ PYYTÄMÄSI MUUTOS
	chName := "custom-" + url

	webID := fmt.Sprintf("%p", r)

	msgch := streamreader.PlayStream(
		chName,
		url,
		volume,
		webID,
	)

	defer streamreader.RemoveClient(chName, webID)

	streamResponse(w, r, msgch)
}

func streamResponse(w http.ResponseWriter, r *http.Request, msgch chan []byte) {

	w.Header().Set("Content-Type", "audio/mpeg")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "no streaming support", 500)
		return
	}

	ctx := r.Context()

	for {
		select {

		case <-ctx.Done():
			return

		case data := <-msgch:
			_, err := w.Write(data)
			if err != nil {
				return
			}
			flusher.Flush()
		}
	}
}