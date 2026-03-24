package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Config struct {
	Server struct {
		Port           uint16 `json:"port"`
		KeyboardDevice string `json:"keyboard_device"`
		MouseDevice    string `json:"mouse_device"`
	} `json:"server"`
}

var config Config

func getConfigPath() string {
	if envPath := os.Getenv("KVM_CONFIG"); envPath != "" {
		return envPath
	}
	if exePath, err := os.Executable(); err == nil {
		configPath := filepath.Join(filepath.Dir(exePath), "config", "config.json")
		if _, err := os.Stat(configPath); err == nil {
			return configPath
		}
	}
	return "./config/config.json"
}

func loadConfig(path string) error {
	if path == "" {
		path = getConfigPath()
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, &config)
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

type KeyboardEvent struct {
	Modifiers byte   `json:"modifiers"`
	Keys      []byte `json:"keys"`
}

type MouseEvent struct {
	Buttons byte `json:"buttons"`
	X       int8 `json:"x"`
	Y       int8 `json:"y"`
	Wheel   int8 `json:"wheel"`
}

type HIDManager struct {
	kbMu    sync.Mutex
	mouseMu sync.Mutex
	kbFile  *os.File
	mFile   *os.File
}

func NewHIDManager() (*HIDManager, error) {
	kb, err := os.OpenFile(config.Server.KeyboardDevice, os.O_WRONLY|02000, 0666)
	if err != nil {
		return nil, fmt.Errorf("failed to open keyboard: %v", err)
	}
	m, err := os.OpenFile(config.Server.MouseDevice, os.O_WRONLY|02000, 0666)
	if err != nil {
		kb.Close()
		return nil, fmt.Errorf("failed to open mouse: %v", err)
	}
	return &HIDManager{kbFile: kb, mFile: m}, nil
}

func (h *HIDManager) SendKeyReport(event KeyboardEvent) error {
	h.kbMu.Lock()
	defer h.kbMu.Unlock()
	report := make([]byte, 8)
	report[0] = event.Modifiers
	for i := 0; i < len(event.Keys) && i < 6; i++ {
		report[i+2] = event.Keys[i]
	}
	const maxRetries = 3
	for i := 0; i < maxRetries; i++ {
		_, err := h.kbFile.Write(report)
		if err == nil {
			return nil
		}
		if strings.Contains(err.Error(), "EAGAIN") || strings.Contains(err.Error(), "temporarily unavailable") {
			time.Sleep(time.Duration(10*(i+1)) * time.Millisecond)
			continue
		}
		return err
	}
	return nil
}

func (h *HIDManager) SendMouseReport(event MouseEvent) error {
	h.mouseMu.Lock()
	defer h.mouseMu.Unlock()
	report := []byte{event.Buttons, byte(event.X), byte(event.Y), byte(event.Wheel)}
	_, err := h.mFile.Write(report)
	return err
}

func (h *HIDManager) ClearAll() {
	h.SendKeyReport(KeyboardEvent{Modifiers: 0, Keys: []byte{}})
	h.SendMouseReport(MouseEvent{Buttons: 0, X: 0, Y: 0, Wheel: 0})
}

func (h *HIDManager) Close() {
	h.ClearAll()
	h.kbFile.Close()
	h.mFile.Close()
}

type WSHandler struct {
	hid *HIDManager
}

func (w *WSHandler) ServeHTTP(rw http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(rw, r, nil)
	if err != nil {
		log.Printf("WS Upgrade error: %v", err)
		return
	}
	log.Println("New control session established from", r.RemoteAddr)
	defer func() {
		conn.Close()
		log.Println("Connection closed, clearing HID state for:", r.RemoteAddr)
		w.hid.ClearAll()
	}()
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			break
		}
		var generic map[string]interface{}
		if err := json.Unmarshal(message, &generic); err != nil {
			continue
		}
		msgType, _ := generic["type"].(string)
		dataObj, ok := generic["data"]
		if !ok {
			continue
		}
		dataBytes, _ := json.Marshal(dataObj)
		switch msgType {
		case "keyboard":
			var kb KeyboardEvent
			json.Unmarshal(dataBytes, &kb)
			if err := w.hid.SendKeyReport(kb); err != nil {
				conn.WriteJSON(map[string]string{"type": "reset_hid"})
			}
		case "mouse":
			var m MouseEvent
			json.Unmarshal(dataBytes, &m)
			w.hid.SendMouseReport(m)
		}
	}
}

func wakeHandler(hid *HIDManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		log.Printf("HTTP Wake request received from %s", r.RemoteAddr)
		
		const udcFile = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
		const udcName = "fe980000.usb"

		// Ефективний метод пробудження для вашої материнської плати:
		// Віртуальне витягування та вставляння кабелю (Rebind)
		
		log.Printf("Executing Magic Wake Sequence (Rebind UDC)...")
		
		// 1. Unbind (це будить комп'ютер миттєво)
		err := os.WriteFile(udcFile, []byte("\n"), 0644)
		if err != nil {
			log.Printf("Unbind failed: %v", err)
		}
		
		time.Sleep(1 * time.Second)
		
		// 2. Bind назад (щоб керування відразу запрацювало)
		err = os.WriteFile(udcFile, []byte(udcName), 0644)
		if err != nil {
			log.Printf("Bind failed: %v", err)
			http.Error(w, "UDC Bind failed", 500)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"ok","message":"host woke up by virtual unplug"}`)
		log.Printf("Wake sequence complete. Host should be active.")
	}
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	if err := loadConfig(""); err != nil {
		log.Fatalf("Config failure: %v", err)
	}
	hid, err := NewHIDManager()
	if err != nil {
		log.Fatalf("HID failure: %v", err)
	}
	defer hid.Close()

	http.Handle("/ws/control", &WSHandler{hid: hid})
	http.HandleFunc("/wake", wakeHandler(hid))
	http.HandleFunc("/ws/wake", wakeHandler(hid))

	port := fmt.Sprintf(":%d", config.Server.Port)
	log.Printf("HID Server v3.0 (Magic-Wake enabled) starting on %s", port)
	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatal(err)
	}
}
