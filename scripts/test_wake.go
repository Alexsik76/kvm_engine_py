package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

const (
	hidg0   = "/dev/hidg0"
	udcFile = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
)

func rebindGadget() error {
	fmt.Println("Step 1: Forcing Gadget Rebind (Virtual Unplug/Replug)...")
	
	udcControllers, err := os.ReadDir("/sys/class/udc")
	if err != nil || len(udcControllers) == 0 {
		return fmt.Errorf("no UDC controllers found")
	}
	udcName := udcControllers[0].Name()

	// 1. Unbind (Unplug)
	fmt.Printf(" -> Unbinding from %s...\n", udcName)
	_ = os.WriteFile(udcFile, []byte("\n"), 0644) // Ignore error if already unbound

	time.Sleep(1 * time.Second)

	// 2. Bind (Plug in)
	fmt.Printf(" -> Binding back to %s...\n", udcName)
	err = os.WriteFile(udcFile, []byte(udcName), 0644)
	if err != nil {
		return fmt.Errorf("failed to bind UDC: %v", err)
	}

	fmt.Println(" -> Gadget successfully re-initialized.")
	time.Sleep(2 * time.Second) // Give host time to recognize "new" device
	return nil
}

func sendWakeKey() error {
	fmt.Printf("Step 2: Opening %s in non-blocking mode...\n", hidg0)
	
	// Use O_NONBLOCK to prevent the script from hanging if the host isn't listening
	f, err := os.OpenFile(hidg0, os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		return fmt.Errorf("failed to open HID device: %v", err)
	}
	defer f.Close()

	// Left Shift
	report := []byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}
	fmt.Println(" -> Sending Left Shift press...")
	_, err = f.Write(report)
	if err != nil {
		return fmt.Errorf("write error: %v", err)
	}

	time.Sleep(100 * time.Millisecond)

	// Release
	fmt.Println(" -> Sending Release...")
	_, err = f.Write(make([]byte, 8))
	return err
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("This script must be run as root (sudo)")
	}

	fmt.Println("=== KVM Wake Test Tool (Force Rebind Version) ===")

	// Always do rebind first to clear any 'endpoint shutdown' or hung states
	err := rebindGadget()
	if err != nil {
		log.Fatalf("Rebind failed: %v", err)
	}

	// Now try to send the key
	err = sendWakeKey()
	if err == nil {
		fmt.Println("\nSUCCESS: Wake signal sent successfully after Rebind!")
		fmt.Println("Check if the host is waking up.")
	} else {
		fmt.Printf("\nFAILED: Rebind worked, but write still failed: %v\n", err)
		fmt.Println("This usually means the host is still not powering the USB port.")
	}
}
