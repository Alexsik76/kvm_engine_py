package main

import (
	"fmt"
	"log"
	"os"
	"strings"
	"time"
)

const (
	hidg0    = "/dev/hidg0"
	udcFile  = "/sys/kernel/config/usb_gadget/kvm_gadget/UDC"
	stateFile = "/sys/class/udc/fe980000.usb/state"
)

func checkState() {
	state, err := os.ReadFile(stateFile)
	if err != nil {
		fmt.Printf("Could not read UDC state: %v\n", err)
		return
	}
	fmt.Printf("Current UDC State: %s", string(state))
}

func rebindGadget() {
	fmt.Println("Forcing Gadget Rebind...")
	_ = os.WriteFile(udcFile, []byte("\n"), 0644)
	time.Sleep(1 * time.Second)
	_ = os.WriteFile(udcFile, []byte("fe980000.usb"), 0644)
	fmt.Println("Waiting for host to enumerate...")
	time.Sleep(3 * time.Second)
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("Run as root")
	}

	fmt.Println("=== KVM Wake Diagnosis ===")
	
	fmt.Print("Initial: ")
	checkState()

	rebindGadget()

	fmt.Print("Final:   ")
	checkState()

	f, err := os.OpenFile(hidg0, os.O_WRONLY, 0666)
	if err != nil {
		fmt.Printf("CRITICAL: Failed to open %s: %v\n", hidg0, err)
		fmt.Println("This happens if the host has not acknowledged the USB device.")
		return
	}
	defer f.Close()

	fmt.Println("Sending Wake Key (Left Shift)...")
	_, err = f.Write([]byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})
	if err != nil {
		fmt.Printf("Write failed: %v\n", err)
	} else {
		fmt.Println("SUCCESS: Key report sent to buffer!")
		f.Write(make([]byte, 8)) // release
	}
}
