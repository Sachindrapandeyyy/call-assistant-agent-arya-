import sounddevice as sd
import soundcard as sc

print("=== SOUNDCARD SPEAKERS (OUTPUTS) ===")
for spk in sc.all_speakers():
    print(f"  - {spk.name} (channels: {spk.channels})")

print("\n=== SOUNDCARD MICROPHONES (INPUTS) ===")
for mic in sc.all_microphones(include_loopback=True):
    print(f"  - {mic.name} (loopback={mic.isloopback})")

print("\n=== DEFAULT DEVICES ===")
try:
    print("Default Speaker:", sc.default_speaker().name)
except Exception as e:
    print("Default Speaker Error:", e)

try:
    print("Default Mic:", sc.default_microphone().name)
except Exception as e:
    print("Default Mic Error:", e)

try:
    print("Default Loopback:", sc.default_microphone(include_loopback=True).name)
except Exception as e:
    print("Default Loopback Error:", e)
