import sounddevice as sd
import numpy as np
import time

devices = sd.query_devices()
print("=== AUDIO OUTPUT DEVICES IN SOUNDDEVICE ===")
for idx, dev in enumerate(devices):
    if dev['max_output_channels'] > 0:
        print(f"[{idx}] {dev['name']} | Channels: {dev['max_output_channels']} | Default SR: {dev['default_samplerate']}")

cable_idx = None
for idx, dev in enumerate(devices):
    if 'cable input' in dev['name'].lower() and dev['max_output_channels'] > 0:
        cable_idx = idx
        break

print(f"\nTarget VB-Cable Index: {cable_idx}")
if cable_idx is not None:
    sr = int(devices[cable_idx]['default_samplerate'])
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone = (0.6 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo = np.column_stack([tone, tone])
    print(f"Playing 2s 440Hz tone directly to device [{cable_idx}] at {sr}Hz...")
    sd.play(stereo, samplerate=sr, device=cable_idx)
    sd.wait()
    print("Direct playback via sounddevice finished!")
