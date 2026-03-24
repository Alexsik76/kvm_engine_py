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
	CheckOrigin: func(r *http.Request) bool { return true },
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

	kb, err := os.OpenFile(config.Server.KeyboardDevice, os.O_WRONLY, 0666)
	if err != nil {
		return fmt.Errorf("failed to open keyboard: %v", err)
	}
	m, err := os.OpenFile(config.Server.MouseDevice, os.O_WRONLY, 0666)
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
	if err != nil && (strings.Contains(err.Error(), "shutdown") || strings.Contains(err.Error(), "invalid")) {
		log.Printf("Detected dead HID handle, reopening...")
		if h.reopen() == nil {
			_, err = h.kbFile.Write(report)
		}
	}
	return err
}

func (h *HIDManager) SendMouseReport(event MouseEvent) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	report := []byte{event.Buttons, byte(event.X), byte(event.Y), byte(event.Wheel)}
	_, err := h.mFile.Write(report)
	if err != nil && (strings.Contains(err.Error(), "shutdown") || strings.Contains(err.Error(), "invalid")) {
		if h.reopen() == nil {
			_, err = h.mFile.Write(report)
		}
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
	if h.kbFile != nil { h.kbFile.Close() }
	if h.mFile != nil { h.mFile.Close() }
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
	conn, err := upgrader.Upgrade(rw, r, nil)
	if err != nil { return }
	defer conn.Close()
	
	for {
		_, message, err := conn.ReadMessage()
		if err != nil { break }
		var generic map[string]interface{}
		if err := json.Unmarshal(message, &generic); err != nil { continue }
		msgType, _ := generic["type"].(string)
		dataObj, ok := generic["data"]; if !ok { continue }
		dataBytes, _ := json.Marshal(dataObj)

		switch msgType {
		case "keyboard":
			var kb KeyboardEvent
			if err := json.Unmarshal(dataBytes, &kb); err == nil {
				w.hid.SendKeyReport(kb)
			}
		case "mouse":
			var m MouseEvent
			if err := json.Unmarshal(dataBytes, &m); err == nil {
				w.hid.SendMouseReport(m)
			}
		}
	}
}

func wakeHandler(hid *HIDManager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		log.Printf("HTTP Wake request received")
		const udcFile = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
		const udcName = "fe980000.usb"

		os.WriteFile(udcFile, []byte("\n"), 0644)
		time.Sleep(1 * time.Second)
		os.WriteFile(udcFile, []byte(udcName), 0644)
		
		log.Printf("Hardware reset complete. Re-opening device handles...")
		time.Sleep(2 * time.Second)
		
		// Ключовий момент: примусово перевідкриваємо файли після Rebind
		hid.ForceReset()

		log.Printf("Sending ENTER to wake up monitor...")
		hid.SendKeyReport(KeyboardEvent{Modifiers: 0, Keys: []byte{0x28}})
		time.Sleep(100 * time.Millisecond)
		hid.ClearAll()

		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"ok"}`)
	}
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	loadConfig("")
	hid, _ := NewHIDManager()
	defer hid.Close()

	http.Handle("/ws/control", &WSHandler{hid: hid})
	http.HandleFunc("/wake", wakeHandler(hid))
	http.HandleFunc("/ws/wake", wakeHandler(hid))

	port := fmt.Sprintf(":%d", config.Server.Port)
	log.Printf("HID Server v3.3 (Auto-Reconnect) starting on %s", port)
	http.ListenAndServe(port, nil)
}
