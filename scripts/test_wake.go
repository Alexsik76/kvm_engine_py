package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	gadgetDir = "/sys/kernel/config/usb_gadget/kvm_gadget"
	udcPath   = "/sys/class/udc"
	hidg0     = "/dev/hidg0"
)

func getUDCName() string {
	files, _ := os.ReadDir(udcPath)
	if len(files) > 0 {
		return files[0].Name()
	}
	return ""
}

func readUDCFile(udc, filename string) string {
	path := filepath.Join(udcPath, udc, filename)
	data, err := os.ReadFile(path)
	if err != nil {
		return "ERROR"
	}
	return strings.TrimSpace(string(data))
}

func diagnose() {
	udc := getUDCName()
	if udc == "" {
		fmt.Println("CRITICAL: No USB Device Controllers found!")
		return
	}

	fmt.Printf("\n--- STEP 1: Current Kernel Status (UDC: %s) ---\n", udc)
	fmt.Printf("State:          %s\n", readUDCFile(udc, "state"))
	fmt.Printf("Current Speed:  %s\n", readUDCFile(udc, "current_speed"))
	fmt.Printf("Maximum Speed:  %s\n", readUDCFile(udc, "maximum_speed"))
	
	isBound := "no"
	data, _ := os.ReadFile(gadgetDir + "/UDC")
	if len(strings.TrimSpace(string(data))) > 0 {
		isBound = "yes (" + strings.TrimSpace(string(data)) + ")"
	}
	fmt.Printf("Gadget bound:   %s\n", isBound)

	fmt.Println("\n--- STEP 2: Cleaning Stale States (Unbind/Rebind) ---")
	fmt.Println("Unbinding gadget...")
	_ = os.WriteFile(gadgetDir+"/UDC", []byte("\n"), 0644)
	time.Sleep(1 * time.Second)
	
	fmt.Printf("State after unbind: %s\n", readUDCFile(udc, "state"))

	fmt.Println("Re-binding gadget to UDC...")
	err := os.WriteFile(gadgetDir+"/UDC", []byte(udc), 0644)
	if err != nil {
		fmt.Printf("BIND ERROR: %v\n", err)
		return
	}

	fmt.Println("\n--- STEP 3: Real-time Connection Monitor (10 seconds) ---")
	fmt.Println("Watching state transitions... (Expected: not attached -> powered -> configured)")
	for i := 0; i < 10; i++ {
		state := readUDCFile(udc, "state")
		fmt.Printf("[%d sec] Current State: %s\n", i, state)
		if state == "suspended" {
			fmt.Println("!!! Detected SUSPEND state (Host is providing power but bus is idle) !!!")
		}
		time.Sleep(1 * time.Second)
	}

	fmt.Println("\n--- STEP 4: Final Attempt to Write ---")
	f, err := os.OpenFile(hidg0, os.O_WRONLY, 0666)
	if err != nil {
		fmt.Printf("Failed to open %s: %v\n", hidg0, err)
		return
	}
	defer f.Close()

	fmt.Println("Sending Left Shift report...")
	_, err = f.Write([]byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})
	if err != nil {
		fmt.Printf("WRITE FAILED: %v\n", err)
	} else {
		fmt.Println("SUCCESS: Report accepted by kernel buffer!")
		f.Write(make([]byte, 8)) // release
	}
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("Run as root (sudo)")
	}
	diagnose()
}
