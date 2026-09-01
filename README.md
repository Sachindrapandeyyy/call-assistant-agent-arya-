# 🤖 Aura AI — Autonomous Personal Call Assistant & Receptionist

> **Production-grade, zero-cost AI Call Receptionist designed and engineered by Sachindra Shekhar Pandey.**
> Runs locally on your Windows PC with GPU acceleration, wirelessly answering and handling incoming cellular phone calls from an Android smartphone via Phone Link & Bluetooth HFP.

---

## 🌟 Overview & Capabilities

Aura AI acts as your personal, executive AI receptionist named **Arya**. When a call comes in on your Android phone, Aura AI automatically answers, engages the caller in polite, high-EQ Romanized Hinglish/Hindi/English conversation, collects structured messages, rejects telemarketers, and delivers instant call summaries with audio recordings to your Telegram.

* 🎙️ **Hardware Mic Shield:** Automatically mutes laptop's physical microphone on call answer, preventing room chatter and fan noise from leaking into the call.
* ⚡ **GPU Accelerated STT:** Real-time speech transcription via aster-whisper (cuda:int8) on NVIDIA RTX 4050 GPU (~1.08s latency).
* 🧠 **Deterministic State Machine + Local LLM:** Zero-name-hallucination guardrail, anti-repetition filter, and sentiment-adaptive intelligence.
* 🔊 **Studio Quality Voice:** Edge-TTS (hi-IN-SwaraNeural) with instantaneous 0.00s in-memory prewarmed cache and 100% crash-proof offline SAPI fallback.
* 🛑 **Instant Barge-In Interruption:** Stops AI speech immediately when the caller interrupts.
* 📱 **Modern Android Dialer UI:** Custom ROLE_DIALER app with Cyan & Charcoal call interface.
* 🔒 **100% Private & Local Storage:** Call recordings and SQLite transcripts remain on your local disk with configurable automatic data retention.

---

## 🏗️ System Architecture

`
                                  [ CELLULAR NETWORK ]
                                            │
                                            ▼
                              ┌───────────────────────────┐
                              │    Infinix Zero 5G 2023   │
                              │   (Android 13 Dialer App) │
                              └─────────────┬─────────────┘
                                            │ (Bluetooth HFP + Wi-Fi)
                                            ▼
                              ┌───────────────────────────┐
                              │    Windows Phone Link     │
                              └───────┬───────────▲───────┘
                                      │           │
           (WASAPI Loopback Capture)  │           │ (VB-Cable Audio Injection)
                                      ▼           │
 ┌────────────────────────────────────────────────┴─────────────────────────────────┐
 │                               AURA AI LOCAL ENGINE                               │
 │                                                                                  │
 │  [ Realtek Loopback ] ──► [ Polyphase FIR VAD ] ──► [ faster-whisper (CUDA) ]    │
 │                                                              │                   │
 │                                                              ▼                   │
 │  [ Dual Route Uplink ] ◄── [ Edge-TTS / SAPI ] ◄── [ State Machine + Ollama ]    │
 └────────────────────────────────────┬─────────────────────────────────────────────┘
                                      │ (Post-Call)
                                      ▼
                      ┌───────────────────────────────┐
                      │    Local SQLite + Telegram    │
                      └───────────────────────────────┘
`

---

## 💻 Hardware & Software Requirements

### Hardware:
* **PC:** Intel Core i5-13450HX (or equivalent), 16GB+ RAM, NVIDIA RTX 4050 (6GB VRAM) running Windows 11.
* **Phone:** Android 10+ smartphone (Tested on Infinix Zero 5G 2023, MediaTek Dimensity 1080).
* **Audio Hardware:** Realtek Audio Speakers/Headphones + VB-Audio Virtual Cable (Free).

### Software Stack:
* **Python:** 3.10 - 3.12 (64-bit)
* **Ollama:** llama3.2:latest or qwen2.5:3b
* **Android Studio / JDK:** Eclipse Temurin JDK 17
* **Windows Phone Link:** Paired via Bluetooth to Android Phone

---

## ⚙️ Step-by-Step Setup Guide

### 1. Windows Audio Setup (VB-Cable)
1. Download and install **VB-Audio Virtual Cable** (Reboot PC after install).
2. Set your default Windows playback device to **Speakers (Realtek Audio)**.
3. In **Windows Phone Link Settings $\to$ Features $\to$ Calls**:
   * Set **Microphone** input to CABLE Output (VB-Audio Virtual Cable).
   * Set **Speaker** output to Speakers (Realtek Audio).

### 2. Local AI & LLM Setup (Ollama)
1. Install [Ollama](https://ollama.ai).
2. Open terminal and pull the conversational model:
   `ash
   ollama pull llama3.2:latest
   `
3. Start the Ollama background service:
   `ash
   ollama serve
   `

### 3. Python Backend Installation
1. Clone repository and navigate to directory:
   `ash
   cd ai-call-assistant
   `
2. Create and activate a virtual environment:
   `ash
   python -m venv .venv
   .venv\Scripts\activate
   `
3. Install dependencies:
   `ash
   pip install -r requirements.txt
   `
4. Configure environment:
   `ash
   copy .env.example .env
   `
   *(Add your Telegram Bot Token & Chat ID in .env if notifications are desired).*

### 4. Android App Installation
1. Enable **Developer Options** and **Wireless Debugging** (or USB Debugging) on your phone.
2. Build and install via Gradle:
   `ash
   cd android/CallAssistant
   gradlew.bat assembleDebug
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   `
3. Open **Aura AI** on your phone:
   * Set as **Default Phone App** (ROLE_DIALER).
   * Grant Phone, Contacts, Call Log, and Notification permissions.

---

## 🚀 Running Aura AI

Start the production server in 1 click:
`ash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
`
Or launch using Start_AI_Assistant.bat.

---

## 🔍 System & Architectural Disclosures

* **Speech-to-Text (aster-whisper):** 100% Local (Runs on RTX GPU).
* **LLM Engine (Ollama):** 100% Local (Runs on RTX GPU).
* **Audio Routing & VAD:** 100% Local (WASAPI loopback + Polyphase FIR).
* **Database & Storage:** 100% Local (SQLite WAL mode + local WAV recordings).
* **Text-to-Speech (Edge-TTS):** Network-dependent (Microsoft Cloud WebSocket). Automatically falls back to **100% Local SAPI** if offline.
* **Telegram Notifications:** Network-dependent (Telegram Bot API).
* **WhatsApp Notifications:** *Currently NOT implemented (Pending for V2).*

---

## 🔒 Privacy & Data Retention

* **Local Storage:** Call recordings and SQLite transcripts remain strictly on your local disk.
* **Automatic Retention Cleanup:** Configurable via .env:
  * RECORDING_RETENTION_DAYS=30 (Audio auto-purged after 30 days).
  * TRANSCRIPT_RETENTION_DAYS=60 (Transcripts auto-purged after 60 days).
* **Zero Cloud Data Mining:** Audio is never uploaded to third-party AI training APIs.

---

## 📄 License & Attribution

Created and engineered by **Sachindra Shekhar Pandey**.
Distributed under the MIT License.
