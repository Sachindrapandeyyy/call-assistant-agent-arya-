"""
AI Call Assistant - Phase 0: Bidirectional Audio Diagnostic

Tests whether bidirectional audio works through the selected audio bridge
(VB-Cable or USB sound card).

This script:
1. Opens an input stream (captures caller audio)
2. Opens an output stream (sends test audio to caller)
3. Records everything for verification
4. Measures audio levels and latency
5. Generates a diagnostic report

Usage:
    python diagnostic_audio.py                    # Interactive device selection
    python diagnostic_audio.py --input 5 --output 7   # Specify device indices
    python diagnostic_audio.py --list             # List devices and exit

The script runs for a configurable duration (default 15 seconds).
During the test:
  - First 3 seconds: silence (baseline noise measurement)
  - Seconds 3-12: plays a test tone AND records incoming audio
  - Seconds 12-15: silence (cooldown)

After the test, a diagnostic report is printed and audio is saved.
"""

import argparse
import datetime
import os
import sys
import time
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile


# --- Configuration ---
SAMPLE_RATE = 16000  # 16kHz (matches HFP wideband / good for Whisper later)
CHANNELS = 1  # Mono (HFP is always mono)
BLOCK_SIZE = 1024  # ~64ms blocks at 16kHz
TEST_DURATION = 15  # seconds
TONE_START = 3  # seconds into test when tone starts
TONE_END = 12  # seconds into test when tone stops
TONE_FREQ = 440  # Hz (A4 - easily recognizable)
TONE_AMPLITUDE = 0.3  # 0.0 to 1.0 (keep moderate to avoid clipping)
GREETING_TEXT = "Test audio from AI Call Assistant diagnostic"


class AudioDiagnostic:
    """Runs a bidirectional audio test and generates a diagnostic report."""

    def __init__(self, input_device, output_device, sample_rate=SAMPLE_RATE):
        self.input_device = input_device
        self.output_device = output_device
        self.sample_rate = sample_rate
        self.channels = CHANNELS

        # Recording buffer
        self.recorded_frames = []
        self.played_frames = []

        # Metrics
        self.input_peak_levels = []
        self.output_started = False
        self.test_start_time = None
        self.errors = []

        # State
        self.running = False

    def _generate_test_tone(self, num_frames, start_frame):
        """Generate a sine wave test tone."""
        t = (start_frame + np.arange(num_frames)) / self.sample_rate
        tone = (TONE_AMPLITUDE * np.sin(2 * np.pi * TONE_FREQ * t)).astype(np.float32)
        return tone.reshape(-1, 1)

    def _generate_announcement(self):
        """Generate a simple beep pattern instead of speech (no TTS yet).
        
        Pattern: beep-beep-pause-beep (like a phone test signal)
        """
        total_samples = int(self.sample_rate * (TONE_END - TONE_START))
        signal = np.zeros(total_samples, dtype=np.float32)

        beep_duration = int(self.sample_rate * 0.3)  # 300ms beeps
        pause_duration = int(self.sample_rate * 0.2)  # 200ms pauses
        long_pause = int(self.sample_rate * 0.5)  # 500ms long pause

        # Pattern: beep, pause, beep, long_pause, beep, pause, beep, long_pause, ...
        pos = 0
        pattern = [beep_duration, pause_duration, beep_duration, long_pause]

        while pos < total_samples:
            for segment_idx, segment_len in enumerate(pattern):
                end = min(pos + segment_len, total_samples)
                if segment_idx % 2 == 0:  # beep segments
                    t = np.arange(end - pos) / self.sample_rate
                    freq = TONE_FREQ if segment_idx == 0 else TONE_FREQ * 1.5  # vary pitch
                    signal[pos:end] = TONE_AMPLITUDE * np.sin(2 * np.pi * freq * t)
                pos = end
                if pos >= total_samples:
                    break

        return signal.reshape(-1, 1)

    def run_test(self):
        """Run the bidirectional audio test."""
        print()
        print("=" * 60)
        print("  BIDIRECTIONAL AUDIO DIAGNOSTIC TEST")
        print("=" * 60)
        print()

        # Get device info
        try:
            in_info = sd.query_devices(self.input_device)
            out_info = sd.query_devices(self.output_device)
        except Exception as e:
            self.errors.append(f"Device query failed: {e}")
            self._print_report()
            return False

        print(f"  Input device:  [{self.input_device}] {in_info['name']}")
        print(f"  Output device: [{self.output_device}] {out_info['name']}")
        print(f"  Sample rate:   {self.sample_rate} Hz")
        print(f"  Channels:      {self.channels}")
        print(f"  Duration:      {TEST_DURATION} seconds")
        print()

        # Validate devices
        if in_info["max_input_channels"] < 1:
            self.errors.append(f"Device [{self.input_device}] has no input channels")
            self._print_report()
            return False

        if out_info["max_output_channels"] < 1:
            self.errors.append(f"Device [{self.output_device}] has no output channels")
            self._print_report()
            return False

        # Pre-generate the test audio
        print("  Generating test audio...")
        test_audio = self._generate_announcement()
        test_audio_pos = 0
        tone_active = False

        # Recording buffer
        self.recorded_frames = []
        self.running = True
        self.test_start_time = time.time()

        print()
        print(f"  Starting test ({TEST_DURATION}s)...")
        print(f"    0-{TONE_START}s:   Silence (baseline)")
        print(f"    {TONE_START}-{TONE_END}s:  Test tone playing + recording")
        print(f"    {TONE_END}-{TEST_DURATION}s: Silence (cooldown)")
        print()
        print("  " + "-" * 50)

        try:
            # Open streams
            input_stream = sd.InputStream(
                device=self.input_device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=BLOCK_SIZE,
            )

            output_stream = sd.OutputStream(
                device=self.output_device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=BLOCK_SIZE,
            )

            input_stream.start()
            output_stream.start()

            elapsed = 0
            last_status = ""

            while elapsed < TEST_DURATION:
                elapsed = time.time() - self.test_start_time

                # Read input
                try:
                    data, overflowed = input_stream.read(BLOCK_SIZE)
                    if overflowed:
                        self.errors.append(f"Input overflow at {elapsed:.1f}s")
                    self.recorded_frames.append(data.copy())

                    # Calculate peak level
                    peak = float(np.max(np.abs(data)))
                    self.input_peak_levels.append((elapsed, peak))
                except Exception as e:
                    self.errors.append(f"Input read error at {elapsed:.1f}s: {e}")

                # Write output (only during tone period)
                in_tone_period = TONE_START <= elapsed < TONE_END
                try:
                    if in_tone_period:
                        if not tone_active:
                            tone_active = True
                            test_audio_pos = 0
                        # Get next chunk from pre-generated audio
                        chunk_end = min(test_audio_pos + BLOCK_SIZE, len(test_audio))
                        if test_audio_pos < len(test_audio):
                            chunk = test_audio[test_audio_pos:chunk_end]
                            # Pad if needed
                            if len(chunk) < BLOCK_SIZE:
                                chunk = np.pad(chunk, ((0, BLOCK_SIZE - len(chunk)), (0, 0)))
                            output_stream.write(chunk)
                            test_audio_pos = chunk_end
                        else:
                            # Loop the test audio
                            test_audio_pos = 0
                    else:
                        # Write silence
                        silence = np.zeros((BLOCK_SIZE, self.channels), dtype=np.float32)
                        output_stream.write(silence)
                except Exception as e:
                    self.errors.append(f"Output write error at {elapsed:.1f}s: {e}")

                # Status bar
                progress = int((elapsed / TEST_DURATION) * 40)
                bar = "█" * progress + "░" * (40 - progress)
                phase = "BASELINE" if elapsed < TONE_START else ("TONE" if elapsed < TONE_END else "COOLDOWN")
                status = f"\r  [{bar}] {elapsed:5.1f}s / {TEST_DURATION}s  {phase}"
                if status != last_status:
                    print(status, end="", flush=True)
                    last_status = status

            print()  # newline after progress bar
            print("  " + "-" * 50)

            input_stream.stop()
            output_stream.stop()
            input_stream.close()
            output_stream.close()

        except sd.PortAudioError as e:
            self.errors.append(f"PortAudio error: {e}")
            self._print_report()
            return False
        except Exception as e:
            self.errors.append(f"Unexpected error: {e}")
            self._print_report()
            return False

        self.running = False

        # Save and analyze
        self._save_recording()
        self._print_report()

        return len(self.errors) == 0

    def _save_recording(self):
        """Save the recorded audio to a WAV file."""
        if not self.recorded_frames:
            self.errors.append("No audio was recorded")
            return

        recording = np.concatenate(self.recorded_frames, axis=0)

        # Create output directory
        output_dir = Path(__file__).parent.parent.parent / "recordings" / "diagnostic"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"diagnostic_{timestamp}.wav"
        filepath = output_dir / filename

        # Convert to int16 for WAV
        recording_int16 = (recording * 32767).astype(np.int16)
        wavfile.write(str(filepath), self.sample_rate, recording_int16)

        print(f"\n  Recording saved: {filepath}")
        self.recording_path = str(filepath)
        self.recording_data = recording

    def _print_report(self):
        """Print the diagnostic report."""
        print()
        print("╔" + "═" * 58 + "╗")
        print("║" + "  PHASE 0 — AUDIO PATH DIAGNOSTIC REPORT".center(58) + "║")
        print("╠" + "═" * 58 + "╣")

        # Check 1: Input device accessible
        input_ok = len(self.recorded_frames) > 0
        self._report_line("Audio input device accessible", input_ok)

        # Check 2: Output device accessible
        output_ok = not any("Output write error" in e for e in self.errors)
        self._report_line("Audio output device accessible", output_ok)

        # Check 3: Audio captured (non-silent)
        if self.recorded_frames:
            recording = np.concatenate(self.recorded_frames, axis=0)
            overall_peak = float(np.max(np.abs(recording)))
            overall_rms = float(np.sqrt(np.mean(recording ** 2)))

            # Check if we captured any meaningful audio
            # (peak > 0.01 means something other than digital silence)
            audio_captured = overall_peak > 0.01
            self._report_line(
                f"Audio captured (peak={overall_peak:.4f})",
                audio_captured,
            )

            # Check baseline vs tone period
            samples_per_sec = self.sample_rate
            baseline_end = int(TONE_START * samples_per_sec)
            tone_start_sample = int(TONE_START * samples_per_sec)
            tone_end_sample = int(TONE_END * samples_per_sec)

            if len(recording) > tone_end_sample:
                baseline_rms = float(np.sqrt(np.mean(recording[:baseline_end] ** 2)))
                tone_rms = float(np.sqrt(np.mean(recording[tone_start_sample:tone_end_sample] ** 2)))

                # If using loopback, tone_rms should be much higher than baseline
                if baseline_rms > 0:
                    snr_db = 20 * np.log10(tone_rms / baseline_rms) if tone_rms > 0 and baseline_rms > 0 else 0
                else:
                    snr_db = 60.0 if tone_rms > 0.01 else 0.0

                self._report_line(f"Baseline noise (RMS={baseline_rms:.5f})", True)
                self._report_line(f"Tone period level (RMS={tone_rms:.5f})", tone_rms > baseline_rms)
                self._report_line(f"Signal-to-Noise Ratio", True, f"{snr_db:.1f} dB")
            else:
                self._report_line("Insufficient recording length", False)
        else:
            self._report_line("Audio captured", False)

        # Check 4: No errors
        no_errors = len(self.errors) == 0
        self._report_line(f"Errors ({len(self.errors)} total)", no_errors)

        print("╠" + "═" * 58 + "╣")

        # Overall result
        all_pass = input_ok and output_ok and len(self.errors) == 0
        if all_pass:
            result = "✅  ALL CHECKS PASSED"
        else:
            result = "❌  SOME CHECKS FAILED"
        print("║" + result.center(58) + "║")
        print("╚" + "═" * 58 + "╝")

        # Print errors if any
        if self.errors:
            print()
            print("  ERRORS:")
            for i, err in enumerate(self.errors, 1):
                print(f"    {i}. {err}")

        # Print guidance
        print()
        if all_pass:
            print("  ✅ Audio path is working!")
            print("  Next step: Test with an actual phone call to verify")
            print("  that caller audio reaches this device and test")
            print("  audio reaches the caller.")
        else:
            print("  ❌ Audio path has issues.")
            print()
            print("  Troubleshooting:")
            print("    1. Run 'python list_audio_devices.py' to verify device indices")
            print("    2. Check that the correct audio devices are selected")
            print("    3. Check cable connections (if using physical loopback)")
            print("    4. Check VB-Cable routing (if using Phone Link approach)")
            print("    5. Check Windows Sound settings for the selected devices")
        print()

    def _report_line(self, label, passed, value=None):
        """Print a single report line."""
        status = "PASS" if passed else "FAIL"
        if value:
            line = f"  {label:<40} {status:>6}  {value}"
        else:
            line = f"  {label:<40} {status:>6}"
        print("║" + line.ljust(58) + "║")


def select_device(direction: str, devices) -> int:
    """Interactive device selection."""
    print(f"\nSelect {direction} device:")
    print("-" * 50)
    for i, dev in enumerate(devices):
        has_dir = (
            dev["max_input_channels"] > 0
            if direction == "INPUT"
            else dev["max_output_channels"] > 0
        )
        if has_dir:
            marker = ""
            name_lower = dev["name"].lower()
            if any(kw in name_lower for kw in ["vb-cable", "cable", "virtual", "usb"]):
                marker = " ★"
            channels = (
                dev["max_input_channels"]
                if direction == "INPUT"
                else dev["max_output_channels"]
            )
            print(f"  [{i:>2}] {dev['name']}{marker} ({channels}ch, {int(dev['default_samplerate'])}Hz)")

    while True:
        try:
            idx = int(input(f"\nEnter {direction} device index: "))
            if 0 <= idx < len(devices):
                return idx
            print("  Invalid index. Try again.")
        except (ValueError, KeyboardInterrupt):
            print("\n  Cancelled.")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 0: Bidirectional Audio Diagnostic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python diagnostic_audio.py                      # Interactive mode
  python diagnostic_audio.py --input 5 --output 7 # Specify devices
  python diagnostic_audio.py --list                # List devices only
  python diagnostic_audio.py --loopback            # Test using same device for input/output
        """,
    )
    parser.add_argument("--input", "-i", type=int, help="Input device index")
    parser.add_argument("--output", "-o", type=int, help="Output device index")
    parser.add_argument("--list", "-l", action="store_true", help="List devices and exit")
    parser.add_argument(
        "--loopback",
        action="store_true",
        help="Use default devices for a basic loopback test (speaker → mic)",
    )
    parser.add_argument(
        "--samplerate",
        "-r",
        type=int,
        default=SAMPLE_RATE,
        help=f"Sample rate in Hz (default: {SAMPLE_RATE})",
    )

    args = parser.parse_args()

    # List devices
    if args.list:
        from list_audio_devices import list_devices
        list_devices()
        return

    devices = sd.query_devices()

    print()
    print("  AI Call Assistant — Phase 0 Audio Diagnostic")
    print("  " + "=" * 45)

    if args.loopback:
        # Use system defaults
        input_dev = sd.default.device[0]
        output_dev = sd.default.device[1]
        if input_dev is None or output_dev is None:
            # Fallback to querying
            try:
                input_dev = devices.index(sd.query_devices(kind="input"))
            except Exception:
                input_dev = 0
            try:
                output_dev = devices.index(sd.query_devices(kind="output"))
            except Exception:
                output_dev = 1
        print(f"\n  Loopback mode: using system default devices")
    elif args.input is not None and args.output is not None:
        input_dev = args.input
        output_dev = args.output
    else:
        # Interactive selection
        print("\n  No devices specified. Starting interactive selection.")
        print("  (Use --input and --output flags to skip this step)")
        print("  (Use --list to see all devices first)")
        input_dev = select_device("INPUT", devices)
        output_dev = select_device("OUTPUT", devices)

    # Run diagnostic
    diag = AudioDiagnostic(
        input_device=input_dev,
        output_device=output_dev,
        sample_rate=args.samplerate,
    )

    print()
    print("  ⚠  IMPORTANT: During the test, ensure the audio path is active.")
    print("     If testing with a phone call: the call must be active and")
    print("     audio routed to the bridge (Bluetooth/cable).")
    print()
    input("  Press ENTER to start the test...")

    success = diag.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
