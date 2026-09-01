import sounddevice as sd

print("=== ALL BLUETOOTH / INFINIX ENDPOINTS ===")
for idx, dev in enumerate(sd.query_devices()):
    name = dev['name'].lower()
    if 'infinix' in name or 'hands-free' in name or 'bthhf' in name:
        api = sd.query_hostapis(dev['hostapi'])['name']
        print(f"[{idx:2d}] {dev['name']}")
        print(f"     In: {dev['max_input_channels']} | Out: {dev['max_output_channels']} | API: {api} | SR: {dev['default_samplerate']}")
