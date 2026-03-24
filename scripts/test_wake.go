package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

const (
	hidg0 = "/dev/hidg0"
	// Path to the UDC file for the gadget
	udcFile = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
)

func triggerSRP() {
	fmt.Println("Attempting USB SRP trigger...")
	files, _ := filepath.Glob("/sys/class/udc/*/srp")
	for _, f := range files {
		err := os.WriteFile(f, []byte("1"), 0200)
		if err != nil {
			fmt.Printf("SRP trigger failed for %s: %v\n", f, err)
		} else {
			fmt.Printf("SRP trigger sent to %s\n", f)
		}
	}
}

func rebindGadget() error {
	fmt.Println("Attempting Gadget Rebind (Virtual Unplug/Replug)...")
	
	// Read current UDC name
	udcControllers, err := os.ReadDir("/sys/class/udc")
	if err != nil || len(udcControllers) == 0 {
		return fmt.Errorf("no UDC controllers found")
	}
	udcName := udcControllers[0].Name()

	// 1. Unbind
	fmt.Printf("Unbinding from %s...\n", udcName)
	err = os.WriteFile(udcFile, []byte("\n"), 0644)
	if err != nil {
		return fmt.Errorf("failed to unbind UDC: %v", err)
	}

	time.Sleep(1 * time.Second)

	// 2. Bind
	fmt.Printf("Binding back to %s...\n", udcName)
	err = os.WriteFile(udcFile, []byte(udcName), 0644)
	if err != nil {
		return fmt.Errorf("failed to bind UDC: %v", err)
	}

	time.Sleep(1 * time.Second)
	return nil
}

func sendWakeKey() error {
	fmt.Printf("Opening %s...\n", hidg0)
	f, err := os.OpenFile(hidg0, os.O_WRONLY, 0666)
	if err != nil {
		return fmt.Errorf("failed to open HID device: %v", err)
	}
	defer f.Close()

	// Left Shift: Modifier 0x02, followed by 7 null bytes
	report := []byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}
	fmt.Println("Sending Left Shift press...")
	_, err = f.Write(report)
	if err != nil {
		return err
	}

	time.Sleep(100 * time.Millisecond)

	// Release: 8 null bytes
	fmt.Println("Sending Release...")
	_, err = f.Write(make([]byte, 8))
	return err
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("This script must be run as root (sudo)")
	}

	fmt.Println("=== KVM Wake Test Tool ===")

	// Strategy 1: Simple SRP + Write
	triggerSRP()
	time.Sleep(500 * time.Millisecond)
	
	err := sendWakeKey()
	if err == nil {
		fmt.Println("SUCCESS: Wake signal sent using Strategy 1 (SRP)!")
		return
	}
	fmt.Printf("Strategy 1 failed: %v\n", err)

	// Strategy 2: Rebind + Write
	fmt.Println("\nSwitching to Strategy 2 (UDC Rebind)...")
	err = rebindGadget()
	if err != nil {
		log.Fatalf("Critical Rebind failure: %v", err)
	}

	err = sendWakeKey()
	if err == nil {
		fmt.Println("SUCCESS: Wake signal sent using Strategy 2 (Rebind)!")
		return
	}

	fmt.Printf("FATAL: Both strategies failed. Final error: %v\n", err)
	fmt.Println("\nPossible causes:")
	fmt.Println("1. USB Cable is not data-capable or disconnected.")
	fmt.Println("2. Host BIOS settings prevent USB Wake (look for 'Power management' or 'Legacy USB Support').")
	fmt.Println("3. Hardware failure on the Raspberry Pi USB port.")
}
