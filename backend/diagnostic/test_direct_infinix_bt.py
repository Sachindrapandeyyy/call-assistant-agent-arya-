import sounddevice as sd
import numpy as np
import time

def find_infinix_output():
    for idx, dev in enumerate(sd.query_devices()):
        name = dev['name'].lower()
        if 'infinix' in name and dev['max_output_channels'] > 0:
            return idx, dev
    return None, None

def play_test():
    idx, dev = find_infinix_output()
    print(f"Infinix Output Index: {idx} -> {dev['name'] if dev else 'Not Found'}")
    if idx is not None:
        sr = 16000
        duration = 3.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        print("Playing 3s 440Hz tone directly to Infinix Bluetooth Output...")
        sd.play(tone, samplerate=sr, device=idx)
        sd.wait()
        print("Direct Bluetooth playback complete!")

if __name__ == "__main__":
    play_test()
