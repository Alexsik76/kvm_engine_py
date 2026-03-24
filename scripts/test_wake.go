package main

import (
	"fmt"
	"log"
	"os"
	"time"
)

const (
	hidg0   = "/dev/hidg0"
)

func sendReport(f *os.File, report []byte) {
	_, err := f.Write(report)
	if err != nil {
		fmt.Printf("Write error: %v\n", err)
	}
	time.Sleep(100 * time.Millisecond)
}

func main() {
	if os.Geteuid() != 0 {
		log.Fatal("Run as root")
	}

	fmt.Println("=== KVM Ultimate Wake Test ===")
	
	f, err := os.OpenFile(hidg0, os.O_WRONLY, 0666)
	if err != nil {
		log.Fatalf("Failed to open %s: %v", hidg0, err)
	}
	defer f.Close()

	// 1. Спробуємо "Left Shift" (те, що було)
	fmt.Println("Attempt 1: Sending Left Shift...")
	sendReport(f, []byte{0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})
	sendReport(f, make([]byte, 8)) // release

	time.Sleep(2 * time.Second)

	// 2. Спробуємо клавішу SPACE (вона частіше будить старі BIOS)
	fmt.Println("Attempt 2: Sending SPACE bar...")
	sendReport(f, []byte{0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00, 0x00})
	sendReport(f, make([]byte, 8)) // release

	time.Sleep(2 * time.Second)

	// 3. Спробуємо клавішу ENTER
	fmt.Println("Attempt 3: Sending ENTER...")
	sendReport(f, []byte{0x00, 0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00})
	sendReport(f, make([]byte, 8)) // release

	fmt.Println("\nFinished attempts. Did anything happen?")
}
