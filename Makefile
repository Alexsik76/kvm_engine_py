CXX ?= g++

build:
	$(CXX) -O2 -mcpu=cortex-a72 -mtune=cortex-a72 -I src/video_engine/include src/video_engine/main.cpp src/video_engine/CaptureDevice.cpp src/video_engine/EncoderDevice.cpp src/video_engine/Config.cpp -o kvm_engine
