"""
AI Call Assistant - Phase 0: Audio Device Enumeration

Lists all audio input and output devices on the system.
Helps identify the correct device for the audio bridge
(VB-Cable virtual device or USB sound card).

Usage:
    python list_audio_devices.py
"""

import sounddevice as sd
import sys


def list_devices():
    """List all audio devices with detailed information."""
    print("=" * 70)
    print("  AUDIO DEVICE ENUMERATION")
    print("=" * 70)
    print()

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    # Print host API info
    print("Host APIs:")
    print("-" * 40)
    for i, api in enumerate(hostapis):
        print(f"  [{i}] {api['name']}")
    print()

    # Categorize devices
    input_devices = []
    output_devices = []
    duplex_devices = []

    for i, dev in enumerate(devices):
        has_input = dev["max_input_channels"] > 0
        has_output = dev["max_output_channels"] > 0
        entry = {
            "index": i,
            "name": dev["name"],
            "hostapi": hostapis[dev["hostapi"]]["name"],
            "max_input_channels": dev["max_input_channels"],
            "max_output_channels": dev["max_output_channels"],
            "default_samplerate": dev["default_samplerate"],
        }
        if has_input and has_output:
            duplex_devices.append(entry)
        elif has_input:
            input_devices.append(entry)
        elif has_output:
            output_devices.append(entry)

    # Print input devices
    print("INPUT DEVICES (Microphones / Line-In / Virtual Inputs):")
    print("-" * 70)
    if not input_devices and not duplex_devices:
        print("  (none found)")
    for dev in input_devices:
        _print_device(dev, "IN")
    for dev in duplex_devices:
        _print_device(dev, "DUPLEX")
    print()

    # Print output devices
    print("OUTPUT DEVICES (Speakers / Line-Out / Virtual Outputs):")
    print("-" * 70)
    if not output_devices and not duplex_devices:
        print("  (none found)")
    for dev in output_devices:
        _print_device(dev, "OUT")
    for dev in duplex_devices:
        _print_device(dev, "DUPLEX")
    print()

    # Print defaults
    try:
        default_input = sd.query_devices(kind="input")
        default_output = sd.query_devices(kind="output")
        print("DEFAULTS:")
        print("-" * 70)
        print(f"  Default Input:  [{devices.index(default_input) if default_input in devices else '?'}] {default_input['name']}")
        print(f"  Default Output: [{devices.index(default_output) if default_output in devices else '?'}] {default_output['name']}")
    except Exception as e:
        print(f"  Could not determine defaults: {e}")
    print()

    # Look for interesting devices
    print("DEVICES OF INTEREST:")
    print("-" * 70)
    keywords = {
        "VB-Cable": "Virtual Audio Cable (for Phone Link approach)",
        "CABLE": "Virtual Audio Cable",
        "Virtual": "Virtual audio device",
        "USB": "USB sound card (for physical loopback approach)",
        "Hands-Free": "Bluetooth Hands-Free (HFP)",
        "Headset": "Bluetooth or wired headset",
        "Phone Link": "Microsoft Phone Link",
        "Infinix": "Infinix Phone HFP Audio Stream",
    }
    found_any = False
    for i, dev in enumerate(devices):
        for keyword, description in keywords.items():
            if keyword.lower() in dev["name"].lower():
                found_any = True
                direction = []
                if dev["max_input_channels"] > 0:
                    direction.append("IN")
                if dev["max_output_channels"] > 0:
                    direction.append("OUT")
                print(f"  * [{i}] {dev['name']} ({'/'.join(direction)})")
                print(f"    -> {description}")
    if not found_any:
        print("  (no specific target devices detected)")
    print()

    return devices


def _print_device(dev, direction_label):
    """Print a single device entry."""
    marker = ""
    name_lower = dev["name"].lower()
    if any(kw in name_lower for kw in ["vb-cable", "cable input", "cable output", "virtual", "usb", "infinix"]):
        marker = " *"
    print(
        f"  [{dev['index']:>2}] {dev['name']}{marker}"
        f"  | {direction_label}"
        f"  | ch={dev['max_input_channels']}in/{dev['max_output_channels']}out"
        f"  | {int(dev['default_samplerate'])}Hz"
        f"  | {dev['hostapi']}"
    )


if __name__ == "__main__":
    try:
        list_devices()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("\nMake sure 'sounddevice' is installed: pip install sounddevice", file=sys.stderr)
        sys.exit(1)
