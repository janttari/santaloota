package streamreader

import (
	"fmt"
	"os/exec"
	"sync"
)

type Asiakas struct {
	SelainID string
	MsgChan  chan []byte
}

var (
	kanavat = map[string][]Asiakas{}
	mutex   sync.RWMutex
)

func PlayStream(
	ch string,
	url string,
	volume int,
	webID string,
) chan []byte {

	c := make(chan []byte, 512)

	mutex.Lock()

	if _, ok := kanavat[ch]; !ok {
		kanavat[ch] = []Asiakas{}
		go ffprosessi(ch, url, volume)
	}

	kanavat[ch] = append(kanavat[ch], Asiakas{
		SelainID: webID,
		MsgChan:  c,
	})

	mutex.Unlock()

	return c
}

func RemoveClient(ch string, webID string) {

	mutex.Lock()
	defer mutex.Unlock()

	clients := kanavat[ch]

	newClients := make([]Asiakas, 0, len(clients))

	for _, c := range clients {
		if c.SelainID != webID {
			newClients = append(newClients, c)
		}
	}

	kanavat[ch] = newClients

	fmt.Println("client removed:", webID, "left:", len(newClients))

	if len(newClients) == 0 {
		fmt.Println("channel empty -> stop:", ch)
		delete(kanavat, ch)
	}
}

func ffprosessi(ch, url string, volume int) {

	fmt.Println("ffmpeg started:", ch)
	fmt.Println("ffmpeg volume input:", volume)

	if volume < 0 {
		volume = 0
	}
	if volume > 300 {
		volume = 300
	}

	ffVolume := float64(volume) / 100.0
	volumeFilter := fmt.Sprintf("volume=%.2f", ffVolume)

	cmd := exec.Command(
		"ffmpeg",
		"-i", url,
		"-af", volumeFilter,
		"-codec:a", "libmp3lame",
		"-ac", "2",
		"-ar", "44100",
		"-b:a", "128k",
		"-write_xing", "0",
		"-id3v2_version", "0",
		"-f", "mp3",
		"-",
	)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		fmt.Println("ffmpeg pipe error:", err)
		return
	}

	err = cmd.Start()
	if err != nil {
		fmt.Println("ffmpeg start error:", err)
		return
	}

	defer cmd.Process.Kill()

	buf := make([]byte, 4096)

	for {

		mutex.RLock()

		if len(kanavat[ch]) == 0 {
			mutex.RUnlock()
			fmt.Println("no clients -> stop ffmpeg:", ch)
			return
		}

		clients := append([]Asiakas(nil), kanavat[ch]...)
		mutex.RUnlock()

		n, err := stdout.Read(buf)
		if err != nil {
			fmt.Println("ffmpeg ended:", err)
			return
		}

		if n > 0 {
			chunk := append([]byte(nil), buf[:n]...)

			for _, c := range clients {
				select {
				case c.MsgChan <- chunk:
				default:
					go removeSlowClient(ch, c.SelainID)
				}
			}
		}
	}
}

func removeSlowClient(ch, id string) {

	mutex.Lock()
	defer mutex.Unlock()

	clients := kanavat[ch]

	newClients := make([]Asiakas, 0, len(clients))

	for _, c := range clients {
		if c.SelainID != id {
			newClients = append(newClients, c)
		}
	}

	kanavat[ch] = newClients

	fmt.Println("removed slow client:", id, "remaining:", len(newClients))

	if len(newClients) == 0 {
		fmt.Println("channel empty:", ch)
		delete(kanavat, ch)
	}
}