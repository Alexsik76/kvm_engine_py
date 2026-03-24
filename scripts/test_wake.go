package main

import (
	"fmt"
	"log"
	"os"
	"time"
)

const (
	hidg0          = "/dev/hidg0"
	gadgetPath     = "/sys/kernel/config/usb_gadget/kvm_gadget"
	udcFile        = gadgetPath + "/UDC"
	bmAttributes   = gadgetPath + "/configs/c.1/bmAttributes"
	maxPower       = gadgetPath + "/configs/c.1/MaxPower"
	udcName        = "fe980000.usb"
)

func optimizeGadget() error {
	fmt.Println("Step 1: Optimizing USB Gadget for Sleep (Self-powered, 0mA)...")
	
	// 1. Unbind first to change attributes
	fmt.Println(" -> Unbinding UDC...")
	_ = os.WriteFile(udcFile, []byte("\n"), 0644)
	time.Sleep(500 * time.Millisecond)

	// 2. Change to Self-powered + Remote Wakeup (0xe0)
	fmt.Println(" -> Setting bmAttributes to 0xe0 (Self-powered)...")
	err := os.WriteFile(bmAttributes, []byte("0xe0"), 0644)
	if err != nil {
		return fmt.Errorf("failed to set bmAttributes: %v", err)
	}

	// 3. Set power consumption to 0mA
	fmt.Println(" -> Setting MaxPower to 0 (Zero draw)...")
	err = os.WriteFile(maxPower, []byte("0"), 0644)
	if err != nil {
		return fmt.Errorf("failed to set MaxPower: %v", err)
	}

	// 4. Bind back
	fmt.Printf(" -> Binding back to %s...\n", udcName)
	err = os.WriteFile(udcFile, []byte(udcName), 0644)
	if err != nil {
		return fmt.Errorf("failed to bind UDC: %v", err)
	}

	fmt.Println(" -> Optimization complete. Waiting for host to re-enumerate...")
	time.Sleep(3 * time.Second)
	return nil
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("Run as root")
	}

	fmt.Println("=== KVM Wake Optimization Test ===")

	// Apply power optimizations
	if err := optimizeGadget(); err != nil {
		log.Fatalf("Critical optimization failure: %v", err)
	}

	fmt.Println("\nNOW: Put your host to Sleep and run this script again (or check its status).")
	fmt.Println("Check if UDC state becomes 'suspended' instead of 'not attached' when the host sleeps.")
	
	// Try a test write
	f, err := os.OpenFile(hidg0, os.O_WRONLY, 0666)
	if err != nil {
		fmt.Printf("\nNote: Could not open %s (normal if host is asleep and cut power).\n", hidg0)
		return
	}
	defer f.Close()

	fmt.Println("\nSUCCESS: USB link is active! Host is still providing power.")
	fmt.Println("Sending test Left Shift report...")
	_, _ = f.Write([]byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})
	time.Sleep(100 * time.Millisecond)
	_, _ = f.Write(make([]byte, 8))
}
