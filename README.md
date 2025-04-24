# Auricue
Hear the Cue, Own the Room

## Project goal
Help fast-thinking but conversation-shy people glide through small-talk,
networking and debates by giving them *just-in-time* audio-cues,
without breaking eye contact or privacy.

## Tech stack (Provisional)

| Layer | Choice | Notes |
| :---- | :----- | :---- |
| **Hardware** | Any earbuds (mic + stereo output) • iPhone / Android Phone | No custom boards needed for now |
| **Capture** | Bluetooth HFP 16-kHz PCM | One mono stream into the app |
| **Voice Activity Detection** | `webrtcvad` | Gates silence, keeps latency low |
| **Speaker diarisation** | `pyannote.audio` tiny model | Tags each frame *S1, S2…* so AI can identify unique speakers |
| **ASR** | OpenAI **`whisper-1`** (streaming) | Plus quota, ~120 ms RTT (Manually upload chunks) |
| **Suggestion LLM** | OpenAI **Custom-GPT** | JSON response: `{facts, strategy}` |
| **Fade-out logic** | Simple interval-doubler after 5 min “flow” | Prevents over-coaching |
| **TTS** | iOS `AVSpeechSynthesizer` / Android `TextToSpeech` | Strategy → Left ear (female), Facts → Right ear (male) |
| **App framework** | React Native + Expo | Hot-reload, iOS & Android |


## Data Pipeline (Provisional)

Schematic text diagram as shown:
```
┌──────────────┐  HFP PCM  ┌────────────────────┐   JSON   ┌──────────────────┐
│   Earbuds    │ ────────▶ │   AuriCue App      │ ───────▶ │    OpenAI GPT    │
│  (Incl. Mic) │           │  • webrtcvad       │          │    (coach)       │
│              │           │  • diarize (S1,S2) │          └──────────────────┘
└──────────────┘           │  • Whisper ASR     │                    ▲
      ▲  ▲  A2DP ↖──────── │  • Fade-out        │   stream response  │
      │  │                 │  • TTS L/R pan     │ ◀──────────────────┘
      │  └─ Left = strat   │                    |
      └──── Right = fact   └────────────────────┘
```

> **Latency target:** ≤ 500 ms end-to-end (mic → suggestion → Earbuds).

## Roadmap (v0)

| # | Milestone | On Completion |
|---|-----------|------------------------|
| **1** | **Standalone Modules** | • VAD, diarisation, ASR (Whisper API) and GPT coach each run in isolation with unit tests.<br>• Latency & accuracy baselines recorded. |
| **2** | **Pipeline Wiring** | • WeebSocket service chains the four modules on the laptop.<br>• End-to-end test script feeds recorded audio ↔ receives stereo TTS JSON.<br>• Passes <500 ms average round-trip target. |
| **3** | **Desktop “BenchRig” Prototype** | • Earbuds mic streams into the laptop; stereo TTS back.<br>• Minimal GUI shows transcript + last hint.<br>• 5min live-chat demo without crashes. |
| **4** | **Mobile App + Configs** | • React-Native (Expo) app replicates the desktop loop on device.<br>• BLE scanning, Start/Stop, fade-out slider.<br>• Field test on iOS & Android with <700 ms latency. |

## Version
Currently in MVP development.
<!--See [CHANGELOG.md](CHANGELOG.md) for details.-->

## License and Contributing

Auricue code is released under the PolyForm Noncommercial 1.0 license;
Bug reports, feature requests and pull-requests are welcome, but contributors must sign the included Copyright-Assignment CLA.
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines, the CLA template, and [`LICENSE`](LICENSE) for the full license text.