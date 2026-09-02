# Aura AI (Arya) — Personal Voice Receptionist

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/NVIDIA-RTX%20GPU%20CUDA-green?style=for-the-badge&logo=nvidia&logoColor=white" alt="CUDA Acceleration" />
  <img src="https://img.shields.io/badge/Android-10%20to%2014-success?style=for-the-badge&logo=android&logoColor=white" alt="Android Support" />
  <img src="https://img.shields.io/badge/FastAPI-Production%20Ready-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License" />
</p>

Aura AI is a zero-subscription personal AI voice receptionist designed and engineered by Sachindra Shekhar Pandey. It combines an Android smartphone, Windows Phone Link, local GPU inference, real-time audio digital signal processing (DSP), deterministic conversation orchestration, and Telegram notifications to automatically answer and handle incoming cellular phone calls.

---

## 1. Overview

Aura AI is a **personal device telephony assistant**, not a cloud telephony platform (such as Twilio or Exotel). It operates directly on personal hardware: incoming cellular calls on an Android smartphone are routed to a local Windows workstation via Bluetooth Hands-Free Profile (HFP) and Windows Phone Link.

The local workstation executes speech recognition (STT), natural language processing (LLM), and speech synthesis (TTS) to engage callers in natural Romanized Hinglish, Hindi, and English conversation, capture structured messages, note meeting times and urgency, and deliver instant summaries and recordings to Telegram.

---

## 2. Key Features

* **Android Telecom Automation:** Implements Android `ROLE_DIALER` and `InCallService` to detect incoming calls and automatically answer after a configurable delay (~4 seconds).
* **Hardware Acoustic Shield (`pycaw`):** Automatically mutes the PC's physical microphone hardware on call answer, preventing room background noise from leaking into the call downlink.
* **Low-Latency Audio Decimation:** Downsamples 48kHz WASAPI loopback capture to 16kHz mono using Polyphase FIR filtering (`scipy.signal.resample_poly`) to eliminate spectral Gibbs ringing.
* **GPU-Accelerated Local STT:** Transcribes speech locally on NVIDIA RTX GPU using `faster-whisper` (`cuda:int8`) with multilingual text purification (Devanagari, Urdu, Latin).
* **Deterministic Conversation Control:** State machine enforces business logic, slot extraction, anti-hallucination name quarantine, and call termination rules.
* **Hybrid Speech Synthesis:** Primary voice powered by Edge-TTS (`hi-IN-SwaraNeural`) with 0.00s in-memory prewarmed caching, with seamless offline fallback to native Windows SAPI TTS.
* **Low-Latency Barge-In:** Immediately halts AI speech playback when the caller speaks or interrupts.
* **Two-Way Audio Recording:** Mixes both caller downlink audio and assistant synthesized audio into master `.wav` recording files.
* **Telegram Executive Briefing:** Automatically delivers structured HTML summary cards, full turn-by-turn dialogue transcripts, and audio recordings to a configured private Telegram chat.

---

## 3. Architecture

```text
                                 [ CELLULAR CARRIER ]
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │   Android Smartphone      │
                             │  (InCallService Dialer)   │
                             └─────────────┬─────────────┘
                                           │ (Bluetooth HFP + Wi-Fi)
                                           ▼
                             ┌───────────────────────────┐
                             │    Windows Phone Link     │
                             └───────┬───────────▲───────┘
                                     │           │
          (WASAPI Loopback Capture)  │           │ (VB-Cable Audio Injection)
                                     ▼           │
  ┌──────────────────────────────────────────────┴───────────────────────────────────┐
  │                            AURA AI LOCAL WORKSTATION                             │
  │                                                                                  │
  │  [ Realtek Loopback ] ──► [ Polyphase FIR VAD ] ──► [ faster-whisper (CUDA) ]    │
  │                                                              │                   │
  │                                                              ▼                   │
  │  [ VB-Cable Input ]   ◄── [ Edge-TTS / SAPI ]   ◄── [ State Machine + Ollama ]   │
  └──────────────────────────────────┬───────────────────────────────────────────────┘
                                     │ (Post-Call)
                                     ▼
                     ┌───────────────────────────────┐
                     │    Local SQLite + Telegram    │
                     └───────────────────────────────┘
```

---

## 4. Hardware Specifications (Validated Profile)

* **PC Workstation:**
  * CPU: Intel Core i5-13450HX
  * GPU: NVIDIA GeForce RTX 4050 (6GB VRAM, CUDA capability)
  * RAM: 24GB DDR5
  * OS: Windows 11 (64-bit)
* **Smartphone:**
  * Model: Infinix Zero 5G 2023
  * OS: Android 13
  * SoC: MediaTek Dimensity 1080, 8GB RAM, 256GB Storage
* **Audio Routing:**
  * Playback: Realtek Audio (Speakers)
  * Virtual Uplink: VB-Audio Virtual Cable (Free)

---

## 5. Software Stack & Local vs Network Classification

| Component | Subsystem | Classification | Notes |
|---|---|---|---|
| **Telephony Control** | Android InCallService | **LOCAL** | Operates on-device via Android Telecom framework |
| **Audio Capture** | WASAPI Loopback (`soundcard`) | **LOCAL** | 48kHz stereo loopback on Realtek endpoint |
| **Acoustic Shield** | Windows CoreAudio (`pycaw`) | **LOCAL** | Hardware mic volume control |
| **VAD & Filtering** | SciPy Polyphase FIR | **LOCAL** | 1/3 decimation (48kHz to 16kHz) |
| **Speech-to-Text** | `faster-whisper` (`cuda:int8`) | **LOCAL** | Executes on RTX 4050 GPU VRAM |
| **LLM Inference** | Ollama (`llama3.2:latest`) | **LOCAL** | Executes on RTX 4050 GPU VRAM |
| **Conversation Engine** | Deterministic State Machine | **LOCAL** | Python business logic and slot tracking |
| **Database** | SQLite (WAL mode) | **LOCAL** | `data/calls.db` on local filesystem |
| **File Storage** | WAV Master Recordings | **LOCAL** | `recordings/` on local filesystem |
| **Voice Synthesis (Primary)** | Edge-TTS (`hi-IN-SwaraNeural`) | **NETWORK-DEPENDENT** | Requires active Internet for Microsoft Edge WebSocket |
| **Voice Synthesis (Fallback)**| Windows Native SAPI | **LOCAL** | 100% offline text-to-speech fallback |
| **Notifications (V1)** | Telegram Bot API | **NETWORK-DEPENDENT** | Transmits summary, transcript, and audio |
| **Notifications (V2)** | WhatsApp | **NOT IMPLEMENTED** | Excluded from V1 scope |

---

## 6. Android Telephony Integration

The Android module (`android/CallAssistant`) implements:
1. `RoleManager.ROLE_DIALER`: Registered as the default phone dialer application.
2. `InCallService`: Intercepts `onCallAdded()` and `onCallRemoved()` callbacks.
3. `Auto-Answer Handler`: Automatically calls `call.answer(VideoProfile.STATE_AUDIO_ONLY)` after a configurable delay (~4 seconds).
4. `WebSocket Telemetry`: Connects to `ws://<PC_IP>:8000/ws/telephony` to signal call answer and disconnection events.

---

## 7. Windows Audio Bridge & VB-Cable Configuration

1. **Audio Downlink (Caller to AI):**
   * Windows Phone Link plays caller audio to the default Windows playback device: **Speakers (Realtek Audio)**.
   * Aura AI captures this audio stream via non-exclusive WASAPI Loopback.
2. **Audio Uplink (AI to Caller):**
   * In Windows Phone Link Settings -> Features -> Calls:
     * Set **Microphone** to `CABLE Output (VB-Audio Virtual Cable)`.
   * Aura AI plays synthesized audio into `CABLE Input (VB-Audio Virtual Cable)`.

---

## 8. Local AI Pipeline

* **STT (`faster-whisper`):**
  * Model: `small` with `int8` quantization on CUDA.
  * Measured latency: **~1.08s** on 3.0s speech segments.
  * Audio pre-processing: Telephony bandpass filtering (250Hz - 3800Hz) and noise gating.
* **LLM (`Ollama`):**
  * Model: `llama3.2:latest` (or `qwen2.5:3b`).
  * Measured latency: **~0.48s** for 30 generated tokens.
  * Settings: `repeat_penalty: 1.25`, `frequency_penalty: 0.35`, `temperature: 0.45`.

---

## 9. Conversation State Machine & Guardrails

* **Strict Name Quarantine:** Prevents the LLM from hallucinating names from prompt few-shot examples. The caller is marked `Unknown` until explicitly introduced.
* **Dynamic Slot Extraction:** Captures volunteered caller names, organizations, dates, times (with Devanagari numeral conversion `०-९` to `0-9`), and callback preferences.
* **Anti-Redundancy:** If the caller states their name and reason in their opening sentence, the state machine skips asking for name or reason.
* **Language Adaptation:** Automatically responds in Hindi, Hinglish, or English matching the caller's language.

---

## 10. Recording & Transcription

* **Two-Way Audio Recording:** Assistant playback frames are appended to the loopback recording buffer, producing a single comprehensive `.wav` file containing both caller and assistant speech.
* **Storage Location:** `recordings/<session_id>/call_full_<session_id>.wav`.
* **Configurable Retention:** Automated retention scheduler purges audio files older than 30 days and SQLite database logs older than 60 days.

---

## 11. Telegram Notifications

When a call concludes, Aura AI automatically dispatches an alert to your configured Telegram chat:
1. **Summary Card:** Caller name, phone number, category, urgency flag, message, and follow-up action.
2. **Turn-by-Turn Transcript:** Full readable conversation (`🤖 Arya` & `👤 Caller`).
3. **Master Audio Recording:** Attached `.wav` file.

*All dynamic text fields are escaped using `html.escape()` to prevent Telegram API parsing errors.*

---

## 12. Installation & Setup

### Prerequisites
* Windows 10/11 (64-bit)
* Python 3.10 - 3.12 (64-bit)
* NVIDIA GPU with CUDA Toolkit installed
* [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (Free)
* [Ollama](https://ollama.ai)

### 1. Clone & Python Environment
```bash
git clone https://github.com/Sachindrapandeyyy/call-assistant-agent-arya-.git
cd call-assistant-agent-arya-
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
copy .env.example .env
```
Edit `.env` to configure your optional Telegram Bot Token and Chat ID.

### 3. Pull Local LLM
```bash
ollama pull llama3.2:latest
ollama serve
```

### 4. Build & Install Android App
```bash
cd android/CallAssistant
gradlew.bat assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
Open the app on your phone, set it as the **Default Phone App**, and grant permissions.

---

## 13. Configuration Reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | FastAPI server bind address |
| `PORT` | `8000` | FastAPI server port |
| `ANSWER_DELAY_SECONDS` | `4.0` | InCallService auto-answer delay |
| `VAD_THRESHOLD` | `0.035` | Energy VAD sensitivity threshold |
| `SILENCE_TIMEOUT` | `0.85` | Silence duration to trigger speech turn end |
| `UPLINK_MODE` | `vb_cable` | Audio injection target (`vb_cable`) |
| `RECORDING_RETENTION_DAYS` | `30` | Number of days to retain WAV recordings |
| `TRANSCRIPT_RETENTION_DAYS` | `60` | Number of days to retain transcript logs |
| `STT_MODEL_SIZE` | `small` | faster-whisper model size |
| `STT_DEVICE` | `cuda` | STT compute device (`cuda` or `cpu`) |
| `STT_COMPUTE_TYPE` | `int8` | STT quantization precision |
| `LLM_MODEL` | `llama3.2:latest` | Ollama model identifier |
| `TELEGRAM_ENABLED` | `true` | Enable/disable Telegram notifications |
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | `""` | Target Telegram chat/user ID |

---

## 14. Running Aura AI

**1-Click Desktop Launcher:**
```bash
Start_AI_Assistant.bat
```
**Manual CLI Execution:**
```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
**1-Click Shutdown:**
```bash
Stop_AI_Assistant.bat
```

---

## 15. Testing & Verification

Run the automated diagnostic test suite:
```bash
# Verify 12 conversational test scenarios
python backend/diagnostic/run_12_scenarios.py

# Measure real hardware component latencies
python backend/diagnostic/measure_real_latencies.py

# Run pre-commit repository security scan
python backend/diagnostic/security_scan.py
```

---

## 16. Security & Privacy

* **Localhost Binding:** FastAPI listens locally on `127.0.0.1` to prevent unauthorized local network access.
* **Zero External STT/LLM Telemetry:** Speech audio and conversational reasoning are processed entirely in GPU VRAM on the local PC.
* **Network Transmissions:**
  * Synthesized response text is transmitted to Edge-TTS when online.
  * Summary cards, transcripts, and audio recordings are transmitted to Telegram when configured.
* **Credentials Isolation:** All tokens and identifiers are loaded exclusively from `.env` and are strictly excluded from Git tracking.

---

## 17. GitHub Security & Repository Hygiene

The repository enforces strict `.gitignore` rules:
* Excluded: `.env`, `recordings/`, `*.wav`, `data/*.db`, build caches, logs, virtual environments.
* Staged: Android Kotlin source, Python backend, diagnostic harnesses, `.env.example`, `README.md`.
* Automated Pre-Commit Audit: Verified 0 API keys, bot tokens, or private phone numbers in tracked files and Git history.

---

## 18. Measured Performance Benchmarks

*Hardware: Lenovo LOQ (Intel i5-13450HX, NVIDIA RTX 4050 6GB VRAM)*

```text
┌───────────────────────────────────────────────┬───────────────────────────┐
│ Pipeline Step                                 │ Measured Hardware Latency │
├───────────────────────────────────────────────┼───────────────────────────┤
│ VAD Turn Evaluation                           │ 0.008 ms per 32ms chunk   │
│ Trailing Silence Trimmer                      │ 0.012 ms                  │
│ faster-whisper STT (GPU cuda:int8)            │ 1084.1 ms (3.0s audio)    │
│ Ollama LLM Inference (GPU RTX 4050)           │ 480.5 ms (30 tokens)      │
│ TTS Synthesis (Prewarmed In-Memory Cache)     │ 0.001 ms (Instantaneous)  │
│ TTS Synthesis (Local Offline SAPI)            │ 787.6 ms                  │
│ TTS Synthesis (Edge-TTS hi-IN-SwaraNeural)    │ 2327.5 ms                 │
│ Audio Buffer Output Dispatch                  │ 15.0 ms                   │
├───────────────────────────────────────────────┼───────────────────────────┤
│ TOTAL TURNAROUND (Prewarmed Greeting/VIP):    │ ~1.58s                    │
│ TOTAL TURNAROUND (Offline SAPI Fallback):     │ ~2.37s                    │
│ TOTAL TURNAROUND (Online Edge-TTS):           │ ~3.91s                    │
└───────────────────────────────────────────────┴───────────────────────────┘
```

---

## 19. Known Limitations

1. **Personal Telephony Nature:** Designed for personal cellular telephony on a single paired Android smartphone via Windows Phone Link; not designed for concurrent multi-line enterprise PBX routing.
2. **Phone Link & Bluetooth Dependency:** Requires active Bluetooth pairing between the Android phone and PC workstation.
3. **Live Call Transfer:** Urgent calls are detected and flagged with high priority; live call transfer to another phone number requires cellular network conference support and is not currently implemented in V1.
4. **WhatsApp Support:** WhatsApp notification dispatch is currently **NOT IMPLEMENTED** (Telegram is the supported notification channel for V1).
5. **Edge-TTS Connectivity:** High-fidelity natural voice synthesis requires an active Internet connection. In offline scenarios, the system automatically falls back to local SAPI speech synthesis.

---

## 20. Troubleshooting

| Symptom | Probable Cause | Resolution |
|---|---|---|
| Caller cannot hear Arya | Phone Link microphone not set to VB-Cable | In Phone Link Settings -> Calls, set Microphone to `CABLE Output`. |
| Arya cannot hear caller | Playback device mismatch | Ensure default Windows playback device is set to `Speakers (Realtek Audio)`. |
| Telegram alert not arriving | Bot token or chat ID missing in `.env` | Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are configured, and you have clicked `/start` on your bot. |
| InCallService not auto-answering | App not set as default phone app | Open Aura AI on phone -> tap "Set as Default Dialer" (`ROLE_DIALER`). |
| Ollama connection error | Ollama background daemon not running | Run `ollama serve` in a terminal window. |

---

## 21. Roadmap (V2 Considerations)

* [ ] Direct on-device local Piper TTS integration for offline neural Indian voices.
* [ ] Official WhatsApp Business Cloud API notification dispatcher.
* [ ] Multi-caller contact memory with long-term conversational recall.
* [ ] Cellular conference call bridging for authorized urgent call transfer.

---

## 📄 License & Attribution

Created, architected, and engineered by **Sachindra Shekhar Pandey**.  
Distributed under the **MIT License**.
