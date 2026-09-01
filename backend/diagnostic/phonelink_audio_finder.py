"""
AI Call Assistant - Phase 0B: Phone Link Audio Endpoint Finder

This script identifies exactly which Windows audio endpoints carry
Phone Link's cellular call audio. It must be run DURING an active
Phone Link call.

It performs three tests:
  1. Enumerates all devices using both sounddevice and soundcard
  2. Probes each input device for audio activity (non-silence)
  3. Tests WASAPI loopback capture via soundcard library

Usage:
  1. Start a Phone Link call (call the Infinix from another phone,
     answer via Phone Link on the laptop)
  2. Ask the caller to speak continuously ("testing 1 2 3...")
  3. Run: python phonelink_audio_finder.py
  4. Review the results to see which endpoints carry caller audio
"""

import sys
import time
import datetime
from pathlib import Path

import numpy as np

# ── Helpers ──────────────────────────────────────────────────────────

def rms(data: np.ndarray) -> float:
    """Root mean square of audio data."""
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))


def peak(data: np.ndarray) -> float:
    """Peak absolute level of audio data."""
    if data.size == 0:
        return 0.0
    return float(np.max(np.abs(data.astype(np.float64))))


def level_bar(level: float, max_width: int = 30) -> str:
    """Visual level bar."""
    clamped = min(level, 1.0)
    filled = int(clamped * max_width)
    return "|" + "#" * filled + "-" * (max_width - filled) + "|"


# ── Test 1: Enumerate with sounddevice ───────────────────────────────

def enumerate_sounddevice():
    """List all devices via sounddevice (PortAudio)."""
    import sounddevice as sd

    print()
    print("=" * 70)
    print("  TEST 1: DEVICE ENUMERATION (sounddevice / PortAudio)")
    print("=" * 70)

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    # Focus on WASAPI and WDM-KS (most relevant for programmatic access)
    for api_idx, api in enumerate(hostapis):
        api_devices = [
            (i, d) for i, d in enumerate(devices) if d["hostapi"] == api_idx
        ]
        if not api_devices:
            continue

        print(f"\n  [{api['name']}]")
        for idx, dev in api_devices:
            direction = ""
            if dev["max_input_channels"] > 0:
                direction += f"IN({dev['max_input_channels']}ch)"
            if dev["max_output_channels"] > 0:
                if direction:
                    direction += "/"
                direction += f"OUT({dev['max_output_channels']}ch)"

            sr = int(dev["default_samplerate"])
            name = dev["name"]

            # Flag interesting devices
            flags = []
            name_lower = name.lower()
            if "bthhfenum" in name_lower or "hands-free" in name_lower or "bluetooth" in name_lower:
                flags.append("BT-HFP")
            if "stereo mix" in name_lower:
                flags.append("LOOPBACK")
            if "virtual" in name_lower or "cable" in name_lower or "vb-" in name_lower:
                flags.append("VIRTUAL")

            flag_str = f"  <{'|'.join(flags)}>" if flags else ""
            print(f"    [{idx:>2}] {name[:55]:<55} {direction:<15} {sr}Hz{flag_str}")

    return devices


# ── Test 2: Probe each input device for audio activity ───────────────

def probe_input_devices():
    """Record 2 seconds from each input device and measure audio levels."""
    import sounddevice as sd

    print()
    print("=" * 70)
    print("  TEST 2: PROBING INPUT DEVICES FOR CALLER AUDIO")
    print("=" * 70)
    print()
    print("  Recording 2 seconds from each input device...")
    print("  (Ensure the caller is speaking during this test)")
    print()

    devices = sd.query_devices()
    results = []

    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] < 1:
            continue

        name = dev["name"]
        sr = int(dev["default_samplerate"])
        channels = min(dev["max_input_channels"], 2)

        try:
            # Record 2 seconds
            recording = sd.rec(
                frames=int(sr * 2),
                samplerate=sr,
                channels=channels,
                device=idx,
                dtype="float32",
                blocking=True,
            )

            rms_val = rms(recording)
            peak_val = peak(recording)

            # Classify
            if peak_val > 0.05:
                status = "** ACTIVE **"
            elif peak_val > 0.005:
                status = "low signal"
            else:
                status = "silent"

            bar = level_bar(peak_val)
            print(f"    [{idx:>2}] {name[:45]:<45} peak={peak_val:.5f} {bar} {status}")

            results.append({
                "index": idx,
                "name": name,
                "samplerate": sr,
                "channels": channels,
                "rms": rms_val,
                "peak": peak_val,
                "status": status,
                "recording": recording,
            })

        except Exception as e:
            err_msg = str(e)[:60]
            print(f"    [{idx:>2}] {name[:45]:<45} ERROR: {err_msg}")
            results.append({
                "index": idx,
                "name": name,
                "samplerate": sr,
                "channels": channels,
                "rms": 0,
                "peak": 0,
                "status": f"error: {err_msg}",
                "recording": None,
            })

    return results


# ── Test 3: WASAPI loopback capture via soundcard ────────────────────

def probe_wasapi_loopback():
    """Use the soundcard library for WASAPI loopback capture."""
    print()
    print("=" * 70)
    print("  TEST 3: WASAPI LOOPBACK CAPTURE (soundcard library)")
    print("=" * 70)
    print()
    print("  This captures audio being PLAYED through output devices.")
    print("  If Phone Link plays caller audio through speakers,")
    print("  loopback capture will pick it up here.")
    print()

    try:
        import soundcard as sc
    except ImportError:
        print("  ERROR: soundcard library not installed")
        print("  Run: python -m pip install soundcard")
        return []

    # List all speakers (output devices)
    speakers = sc.all_speakers()
    print(f"  Found {len(speakers)} output devices:")
    for i, spk in enumerate(speakers):
        print(f"    [{i}] {spk.name}")

    print()
    print("  Attempting loopback capture from each (2 seconds)...")
    print()

    results = []

    for i, spk in enumerate(speakers):
        name = spk.name
        try:
            # Loopback capture - records what's being played through this device
            with spk.recorder(samplerate=48000, channels=2, blocksize=1024) as mic:
                # Record 2 seconds
                frames = []
                start = time.time()
                while time.time() - start < 2.0:
                    data = mic.record(numframes=1024)
                    frames.append(data)

                if frames:
                    recording = np.concatenate(frames, axis=0)
                    rms_val = rms(recording)
                    peak_val = peak(recording)

                    if peak_val > 0.05:
                        status = "** ACTIVE **"
                    elif peak_val > 0.005:
                        status = "low signal"
                    else:
                        status = "silent"

                    bar = level_bar(peak_val)
                    print(f"    [{i}] {name[:45]:<45} peak={peak_val:.5f} {bar} {status}")
                    results.append({
                        "index": i,
                        "name": name,
                        "peak": peak_val,
                        "rms": rms_val,
                        "status": status,
                        "recording": recording,
                    })
                else:
                    print(f"    [{i}] {name[:45]:<45} no frames captured")

        except Exception as e:
            err_msg = str(e)[:60]
            print(f"    [{i}] {name[:45]:<45} ERROR: {err_msg}")
            results.append({
                "index": i,
                "name": name,
                "peak": 0,
                "rms": 0,
                "status": f"error: {err_msg}",
                "recording": None,
            })

    return results


# ── Test 4: Check if Bluetooth HFP endpoints appear for Infinix ──────

def check_bluetooth_hfp():
    """Specifically look for Bluetooth HFP endpoints."""
    import sounddevice as sd

    print()
    print("=" * 70)
    print("  TEST 4: BLUETOOTH HFP ENDPOINT DETECTION")
    print("=" * 70)
    print()

    devices = sd.query_devices()
    hfp_devices = []

    for idx, dev in enumerate(devices):
        name_lower = dev["name"].lower()
        if any(kw in name_lower for kw in ["bthhfenum", "hands-free", "handsfree", "infinix"]):
            hfp_devices.append((idx, dev))

    if hfp_devices:
        print(f"  Found {len(hfp_devices)} Bluetooth HFP device(s):")
        for idx, dev in hfp_devices:
            direction = []
            if dev["max_input_channels"] > 0:
                direction.append(f"IN({dev['max_input_channels']}ch)")
            if dev["max_output_channels"] > 0:
                direction.append(f"OUT({dev['max_output_channels']}ch)")
            print(f"    [{idx}] {dev['name']}")
            print(f"         {'/'.join(direction)}, {int(dev['default_samplerate'])}Hz")
    else:
        print("  No Bluetooth HFP endpoints found.")
        print()
        print("  This could mean:")
        print("    1. Phone Link manages HFP audio internally")
        print("    2. The phone is not currently connected via Bluetooth")
        print("    3. HFP endpoints only appear during an active call")
        print()
        print("  If you're running this during a call and see no HFP devices,")
        print("  Phone Link is routing audio through the default communication devices.")

    return hfp_devices


# ── Test 5: Check Windows default communication devices ──────────────

def check_communication_devices():
    """Identify the Windows Default Communication Devices."""
    print()
    print("=" * 70)
    print("  TEST 5: DEFAULT COMMUNICATION DEVICES")
    print("=" * 70)
    print()
    print("  Phone Link typically uses the 'Default Communication Device'")
    print("  (separate from the regular Default Device in Windows Sound settings).")
    print()

    try:
        import soundcard as sc

        default_speaker = sc.default_speaker()
        default_mic = sc.default_microphone()

        print(f"  Default Playback:   {default_speaker.name}")
        print(f"  Default Recording:  {default_mic.name}")
        print()
        print("  Note: Windows has separate 'Default Device' and")
        print("  'Default Communication Device' settings.")
        print("  Phone Link uses the Communication Device.")
        print("  Check: Settings > System > Sound > Advanced")

    except Exception as e:
        print(f"  Error querying defaults: {e}")


# ── Save recordings from active endpoints ────────────────────────────

def save_active_recordings(probe_results, loopback_results, output_dir):
    """Save recordings from any endpoint that had audio activity."""
    from scipy.io import wavfile

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    # Save active probe recordings
    for r in probe_results:
        if r.get("recording") is not None and r["peak"] > 0.005:
            safe_name = r["name"][:30].replace(" ", "_").replace("/", "-").replace("\\", "-")
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
            filename = f"probe_{timestamp}_dev{r['index']}_{safe_name}.wav"
            filepath = output_dir / filename

            rec = r["recording"]
            rec_int16 = (rec * 32767).clip(-32768, 32767).astype(np.int16)
            wavfile.write(str(filepath), r["samplerate"], rec_int16)
            saved.append((filepath, r["name"], r["peak"]))

    # Save active loopback recordings
    for r in loopback_results:
        if r.get("recording") is not None and r["peak"] > 0.005:
            safe_name = r["name"][:30].replace(" ", "_").replace("/", "-").replace("\\", "-")
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")
            filename = f"loopback_{timestamp}_dev{r['index']}_{safe_name}.wav"
            filepath = output_dir / filename

            rec = r["recording"]
            rec_int16 = (rec * 32767).clip(-32768, 32767).astype(np.int16)
            wavfile.write(str(filepath), 48000, rec_int16)
            saved.append((filepath, r["name"], r["peak"]))

    return saved


# ── Summary report ───────────────────────────────────────────────────

def print_summary(probe_results, loopback_results, hfp_devices, saved_files):
    """Print the final summary report."""
    print()
    print("=" * 70)
    print("  SUMMARY: PHONE LINK AUDIO ENDPOINT ANALYSIS")
    print("=" * 70)
    print()

    # Active input devices
    active_inputs = [r for r in probe_results if r["peak"] > 0.005]
    if active_inputs:
        print("  Input devices with audio activity:")
        for r in sorted(active_inputs, key=lambda x: -x["peak"]):
            print(f"    [{r['index']:>2}] {r['name'][:50]:<50} peak={r['peak']:.5f}")
    else:
        print("  No input devices had audio activity.")
        print("  This likely means:")
        print("    - The caller was not speaking during the test")
        print("    - Phone Link routes audio differently than expected")

    print()

    # Active loopback devices
    active_loopback = [r for r in loopback_results if r["peak"] > 0.005]
    if active_loopback:
        print("  Loopback capture devices with audio:")
        for r in sorted(active_loopback, key=lambda x: -x["peak"]):
            print(f"    [{r['index']:>2}] {r['name'][:50]:<50} peak={r['peak']:.5f}")
    else:
        print("  No loopback capture had audio activity.")

    print()

    # HFP devices
    if hfp_devices:
        print(f"  Bluetooth HFP endpoints: {len(hfp_devices)} found")
        for idx, dev in hfp_devices:
            print(f"    [{idx}] {dev['name']}")
    else:
        print("  Bluetooth HFP endpoints: None found")

    print()

    # Saved files
    if saved_files:
        print("  Saved recordings (listen to verify caller audio):")
        for filepath, name, peak_val in saved_files:
            print(f"    {filepath}")
            print(f"      Source: {name}, peak: {peak_val:.5f}")
    else:
        print("  No recordings saved (no audio detected).")

    # Recommendations
    print()
    print("-" * 70)
    print("  NEXT STEPS:")
    print("-" * 70)

    if active_loopback or active_inputs:
        print()
        print("  GOOD NEWS: Audio was detected on one or more endpoints!")
        print()
        print("  1. Listen to the saved WAV files to confirm they contain")
        print("     the CALLER'S voice (not just ambient noise).")
        print()
        print("  2. The endpoint(s) with caller audio are the ones we need")
        print("     for the AI pipeline's input (caller -> Whisper -> LLM).")
        print()
        print("  3. For the OUTPUT direction (AI voice -> caller), we need")
        print("     to install VB-Cable (free virtual audio driver) to create")
        print("     a virtual microphone that Python writes to and Phone Link")
        print("     reads from.")
        print()
        print("  4. Report these results back so we can build the next")
        print("     diagnostic: bidirectional audio with VB-Cable.")
    else:
        print()
        print("  No audio was detected. Possible causes:")
        print("    - Was the caller actually speaking during the test?")
        print("    - Was Phone Link actively handling the call?")
        print("    - Is the call audio volume turned up?")
        print()
        print("  Try again ensuring the caller speaks continuously")
        print("  throughout the entire 2-second probe period.")

    print()


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print()
    print("  ================================================================")
    print("    AI Call Assistant - Phase 0B")
    print("    Phone Link Audio Endpoint Finder")
    print("  ================================================================")
    print()
    print("  REQUIREMENTS:")
    print("    1. Phone Link must be connected to the Infinix Zero Turbo")
    print("    2. An active phone call must be in progress via Phone Link")
    print("    3. The caller should be speaking (say 'testing 1 2 3')")
    print()
    print("  This script will probe all audio endpoints to find where")
    print("  Phone Link's call audio is flowing.")
    print()

    try:
        input("  Press ENTER when the call is active and caller is speaking...")
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        return

    # Run all tests
    sd_devices = enumerate_sounddevice()
    hfp_devices = check_bluetooth_hfp()
    check_communication_devices()

    print()
    print("  Now probing each input device (caller should keep speaking)...")
    input("  Press ENTER to start probing...")

    probe_results = probe_input_devices()
    loopback_results = probe_wasapi_loopback()

    # Save recordings from active endpoints
    output_dir = Path(__file__).parent.parent.parent / "recordings" / "diagnostic"
    saved_files = save_active_recordings(probe_results, loopback_results, output_dir)

    # Print summary
    print_summary(probe_results, loopback_results, hfp_devices, saved_files)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  FATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
