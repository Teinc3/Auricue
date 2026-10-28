# Design/Technical Specification

## Scoping
### Problem Formulation
Auricue's solution simultaneously tackles 3 out of the 5 tracks suggested in
the problem statement:

- A. Accessibility: making voice tech more inclusive for differently-abled
    communities.
- B. Productivity: streamlining workflows with Voice AI automation
- E. Real-Time Assistance: coaching, transcription, translation and more

### Stakeholders
The end user engaged in a conversation and requiring contextual assistance.
All data is stored locally and only accessable by the user.

### Scoping
- Personal context and conversation transcripts stored locally under DB.
- Real-time search engine/fact checker component for contextual cues.
- Transcription, speaker diarisation and accuracy/fidelity API.
- Mobile UI for viewing data/logs

### Constraints
- Latency requirements, <2000 ms E2E is a must factor.
- Minimise bandwidth and unnecessary IO due to connection stability
- Privacy/consent factor, must require user authorisation
- Localisation: Support only English/derivatives for MVP.

## Process/Data Flow Diagram
```mermaid
flowchart TD
    EarPiece["Ear piece"]
    App["Mobile App<br/>(UI)"]
    Agent["Auricue Agent"]
    DB[("DB<br/>Context Logs<br/>(Device Storage)")]

    subgraph ExternalAPI ["External API"]
        STT["STT / Diarisation"]
        Search["Google Search"]
    end

    EarPiece <-->|Bluetooth| Agent
    App <-->|HTTP/WS| Agent
    Agent <-->|Streaming| STT
    Agent <-->|MCP| Search
    Agent <-->|R/W| DB

    style ExternalAPI stroke-dasharray: 5 5
```

## Relational Mapping
TBD
