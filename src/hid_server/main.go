package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"hid_server/auth"

	"github.com/gorilla/websocket"
)

type Config struct {
	Server struct {
		Port           uint16 `json:"port"`
		JWTSecret      string `json:"jwt_secret"`
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
		// Дозволяємо підключення з будь-якого Origin, 
		// оскільки безпека забезпечується перевіркою JWT токена.
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
	mu     sync.Mutex
	kbFile *os.File
	mFile  *os.File
}

func NewHIDManager() (*HIDManager, error) {
	h := &HIDManager{}
	if err := h.reopen(); err != nil {
		return nil, err
	}
	return h, nil
}

func (h *HIDManager) reopen() error {
	if h.kbFile != nil {
		h.kbFile.Close()
	}
	if h.mFile != nil {
		h.mFile.Close()
	}

	kb, err := os.OpenFile(config.Server.KeyboardDevice, os.O_WRONLY, 0600)
	if err != nil {
		return fmt.Errorf("failed to open keyboard: %v", err)
	}
	m, err := os.OpenFile(config.Server.MouseDevice, os.O_WRONLY, 0600)
	if err != nil {
		kb.Close()
		return fmt.Errorf("failed to open mouse: %v", err)
	}

	h.kbFile = kb
	h.mFile = m
	return nil
}

func (h *HIDManager) SendKeyReport(event KeyboardEvent) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	report := make([]byte, 8)
	report[0] = event.Modifiers
	for i := 0; i < len(event.Keys) && i < 6; i++ {
		report[i+2] = event.Keys[i]
	}

	_, err := h.kbFile.Write(report)
	if err != nil {
		log.Printf("Keyboard write error: %v", err)
	}
	return err
}

func (h *HIDManager) SendMouseReport(event MouseEvent) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	report := []byte{event.Buttons, byte(event.X), byte(event.Y), byte(event.Wheel)}
	_, err := h.mFile.Write(report)
	if err != nil {
		log.Printf("Mouse write error: %v", err)
	}
	return err
}

func (h *HIDManager) ClearAll() {
	h.SendKeyReport(KeyboardEvent{Modifiers: 0, Keys: []byte{}})
	h.SendMouseReport(MouseEvent{Buttons: 0, X: 0, Y: 0, Wheel: 0})
}

func (h *HIDManager) Close() {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.ClearAll()
	if h.kbFile != nil {
		h.kbFile.Close()
	}
	if h.mFile != nil {
		h.mFile.Close()
	}
}

func (h *HIDManager) ForceReset() {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.reopen()
}

type WSHandler struct {
	hid *HIDManager
}

func (w *WSHandler) ServeHTTP(rw http.ResponseWriter, r *http.Request) {
	// Extract the token from the query parameter
	token := r.URL.Query().Get("token")
	if token == "" {
		http.Error(rw, "Unauthorized: Missing token", http.StatusUnauthorized)
		return
	}

	// Validate the token using the secret from config
	userID, err := auth.ValidateAccessToken(token, config.Server.JWTSecret)
	if err != nil {
		log.Printf("Auth failed for %s: %v", r.RemoteAddr, err)
		http.Error(rw, "Unauthorized: Invalid token", http.StatusUnauthorized)
		return
	}

	log.Printf("User %s connected to HID control from %s", userID, r.RemoteAddr)

	conn, err := upgrader.Upgrade(rw, r, nil)
	if err != nil {
		log.Printf("WS Upgrade error: %v", err)
		return
	}
	defer conn.Close()

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			break
		}
		var generic map[string]interface{}
		if err := json.Unmarshal(message, &generic); err != nil {
			log.Printf("JSON Unmarshal error: %v", err)
			continue
		}
		msgType, _ := generic["type"].(string)
		dataObj, ok := generic["data"]
		if !ok {
			log.Printf("Missing 'data' field in WS message")
			continue
		}
		dataBytes, err := json.Marshal(dataObj)
		if err != nil {
			log.Printf("JSON Marshal error: %v", err)
			continue
		}

		switch msgType {
		case "keyboard":
			var kb KeyboardEvent
			if err := json.Unmarshal(dataBytes, &kb); err == nil {
				w.hid.SendKeyReport(kb)
			} else {
				log.Printf("Failed to unmarshal KeyboardEvent: %v", err)
			}
		case "mouse":
			var m MouseEvent
			if err := json.Unmarshal(dataBytes, &m); err == nil {
				w.hid.SendMouseReport(m)
			} else {
				log.Printf("Failed to unmarshal MouseEvent: %v", err)
			}
		}
	}
}

func wakeHandler(hid *HIDManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Handle CORS preflight
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		log.Printf("HTTP Wake request received from %s", r.RemoteAddr)

		// Check JWT Token
		authHeader := r.Header.Get("Authorization")
		if len(authHeader) < 8 || authHeader[:7] != "Bearer " {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}
		token := authHeader[7:]
		
		_, err := auth.ValidateAccessToken(token, config.Server.JWTSecret)
		if err != nil {
			log.Printf("Wake Auth failed: %v", err)
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}

		const udcFile = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
		const udcName = "fe980000.usb"

		// Magic Wake Sequence
		_ = os.WriteFile(udcFile, []byte("\n"), 0644)
		time.Sleep(1 * time.Second)
		_ = os.WriteFile(udcFile, []byte(udcName), 0644)

		log.Printf("Hardware reset complete. Re-opening device handles...")
		time.Sleep(2 * time.Second)

		hid.ForceReset()

		log.Printf("Sending ENTER to wake up monitor...")
		_ = hid.SendKeyReport(KeyboardEvent{Modifiers: 0, Keys: []byte{0x28}})
		time.Sleep(100 * time.Millisecond)
		hid.ClearAll()

		w.Header().Set("Content-Type", "application/json")
		_, _ = fmt.Fprintf(w, `{"status":"ok","message":"Magic Wake cycle complete"}`)
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
	// Only /ws/wake is exposed through the tunnel
	http.HandleFunc("/ws/wake", wakeHandler(hid))

	port := fmt.Sprintf(":%d", config.Server.Port)
	log.Printf("HID Server v3.4 (Lean & Audit-Cleaned) starting on %s", port)
	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatal(err)
	}
}
