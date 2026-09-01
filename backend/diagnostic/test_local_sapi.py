import subprocess
import time
import os

ps_script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $synth.GetInstalledVoices()) {
    Write-Host "Voice:" $v.VoiceInfo.Name
}
$synth.SelectVoice("Microsoft Zira Desktop")
$synth.SetOutputToWaveFile("test_sapi.wav")
$synth.Speak("Hello Sachindra sir, this is your 100 percent local offline assistant.")
$synth.Dispose()
"""

t0 = time.time()
res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
dt = time.time() - t0

print("Stdout:", res.stdout)
print("Stderr:", res.stderr)
print(f"Generated test_sapi.wav in {dt:.3f}s! File size: {os.path.getsize('test_sapi.wav') if os.path.exists('test_sapi.wav') else 0} bytes")
