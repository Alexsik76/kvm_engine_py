package main

import (
	"fmt"
	"os"
	"syscall"
	"time"
)

func main() {
	const (
		hidPath    = "/dev/hidg0"
		descPath   = "/sys/kernel/config/usb_gadget/kvm_gadget/functions/hid.usb0/report_desc"
		statePath  = "/sys/class/udc/fe980000.usb/state"
	)

	fmt.Println("--- SYSTEM CHECK ---")
	
	// 1. Check if descriptors exist
	if _, err := os.Stat(descPath); err == nil {
		fmt.Println("HID Descriptors:  LOADED (Kernel knows this is a keyboard)")
	} else {
		fmt.Println("HID Descriptors:  MISSING (Gadget not initialized!)")
	}

	// 2. Check UDC State
	state, _ := os.ReadFile(statePath)
	fmt.Printf("UDC State:        %s", string(state))

	// 3. Open Device in NON-BLOCKING mode
	// We use syscall.O_NONBLOCK to prevent hanging if the host is not polling
	f, err := os.OpenFile(hidPath, os.O_WRONLY|syscall.O_NONBLOCK, 0666)
	if err != nil {
		fmt.Printf("ERROR: Cannot open %s: %v\n", hidPath, err)
		return
	}
	defer f.Close()

	sendKey := func(name string, report []byte) {
		fmt.Printf("\nAttempting: %s... ", name)
		
		// Try to write. If host is asleep and not polling, this might return EAGAIN
		_, err := f.Write(report)
		if err != nil {
			if err.Error() == "resource temporarily unavailable" {
				fmt.Println("FAILED (Host is NOT polling USB. It is in deep sleep)")
			} else {
				fmt.Printf("FAILED (%v)\n", err)
			}
			return
		}
		
		fmt.Println("SUCCESS (Report accepted by kernel)")
		f.Write(make([]byte, 8)) // release
	}

	fmt.Println("\n--- WAKE ATTEMPTS (NON-BLOCKING) ---")
	sendKey("SPACE bar", []byte{0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00, 0x00})
	time.Sleep(1 * time.Second)
	sendKey("LEFT CTRL", []byte{0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})

	fmt.Println("\n--- FINISHED ---")
}
