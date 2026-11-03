let ws = null;
let isRunning = false;
let currentMode = "live";

const el = {
  dot: document.getElementById("status-dot"),
  btn: document.getElementById("toggle-btn"),
  sessionSelect: document.getElementById("session-select"),
  sessionContext: document.getElementById("session-context"),
  speakersList: document.getElementById("speakers-list"),
  deviceIn: document.getElementById("device-in"),
  deviceOut: document.getElementById("device-out"),
  weightFact: document.getElementById("weight-fact"),
  weightContext: document.getElementById("weight-context"),
  weightStrategy: document.getElementById("weight-strategy"),
  feed: document.getElementById("feed"),
  emptyFeed: document.getElementById("empty-feed"),
};

function connectWs() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/api/session`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWsEvent(msg);
    } catch {
      // Ignore unparseable frames
    }
  };

  ws.onclose = () => {
    updateStatus(false);
    setTimeout(connectWs, 2000);
  };
}

function handleWsEvent(msg) {
  if (msg.type === "status") {
    updateStatus(msg.running);
    if (msg.running) refreshSessions();
  } else if (msg.type === "sentence" && currentMode === "live") {
    appendSentence(msg);
  } else if (msg.type === "cue" && currentMode === "live") {
    appendCue(msg);
  } else if (msg.type === "context" && currentMode === "live") {
    renderContext(msg.context, msg.speakers);
  } else if (msg.type === "weights") {
    syncWeights(msg.weights);
  }
}

function updateStatus(running) {
  isRunning = running;
  el.dot.classList.toggle("running", running);
  el.btn.textContent = running ? "Stop" : "Start";
  el.btn.className = running ? "btn btn-danger" : "btn btn-primary";
}

function renderSentenceNode(sent) {
  const div = document.createElement("div");
  div.className = "sentence-item";
  if (sent.id) div.dataset.sentenceId = sent.id;

  const spkClass = sent.speaker_idx <= 3 ? `spk-${sent.speaker_idx}` : "spk-other";
  const latency = sent.diarisation_latency != null ? `${sent.diarisation_latency}ms` : "";

  div.innerHTML = `
    <div class="sentence-header">
      <span class="spk-badge ${spkClass}">S${sent.speaker_idx}</span>
      <span class="meta-latency">${latency}</span>
    </div>
    <div class="transcript-text">${escapeHtml(sent.transcript)}</div>
  `;
  return div;
}

function renderCueNode(cue) {
  const div = document.createElement("div");
  const typeClass = `cue-${cue.cue_type || "OTHER"}`;
  div.className = `cue-card ${typeClass}${cue.surfaced ? "" : " suppressed"}`;

  const important = cue.important ? '<span class="important-flag">!</span>' : "";
  const suppressed = cue.surfaced ? "" : '<span class="suppressed-badge">[cooldown]</span>';
  const latency = cue.agent_latency != null ? `Agent: ${cue.agent_latency}ms` : "";

  let sourceHtml = "";
  if (cue.source && cue.source.uri) {
    const yr = cue.source.year ? ` (${cue.source.year})` : "";
    const auth = escapeHtml(cue.source.authority || "Source");
    sourceHtml = `<div class="cue-source"><a href="${escapeHtml(cue.source.uri)}" target="_blank" rel="noopener">${auth}${yr}</a></div>`;
  }

  div.innerHTML = `
    <div class="cue-header">
      <span class="cue-badge ${cue.cue_type}">${cue.cue_type}${important}${suppressed}</span>
      <span class="meta-latency">${latency}</span>
    </div>
    <div class="cue-content">${escapeHtml(cue.content)}</div>
    ${sourceHtml}
  `;
  return div;
}

function appendSentence(sent) {
  if (el.emptyFeed) el.emptyFeed.remove();
  const node = renderSentenceNode(sent);
  el.feed.appendChild(node);
  scrollToBottom();
}

function appendCue(cue) {
  if (el.emptyFeed) el.emptyFeed.remove();
  const node = renderCueNode(cue);
  if (cue.sentence_id) {
    const sentEl = el.feed.querySelector(`[data-sentence-id="${cue.sentence_id}"]`);
    if (sentEl) {
      let target = sentEl;
      while (target.nextElementSibling && target.nextElementSibling.classList.contains("cue-card")) {
        target = target.nextElementSibling;
      }
      target.insertAdjacentElement("afterend", node);
      scrollToBottom();
      return;
    }
  }
  el.feed.appendChild(node);
  scrollToBottom();
}

function renderContext(ctxText, speakers) {
  el.sessionContext.textContent = ctxText || "No context recorded yet.";
  if (!speakers || speakers.length === 0) {
    el.speakersList.innerHTML = '<span class="empty-hint">No speaker profiles yet.</span>';
    return;
  }
  el.speakersList.innerHTML = speakers.map(s => {
    const spkClass = s.speaker_idx <= 3 ? `spk-${s.speaker_idx}` : "spk-other";
    return `
      <div class="speaker-chip">
        <span class="spk-badge ${spkClass}">S${s.speaker_idx}</span>
        <span>${escapeHtml(s.context || "No context")}</span>
      </div>
    `;
  }).join("");
}

function scrollToBottom() {
  el.feed.scrollTop = el.feed.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function loadDevices() {
  try {
    const res = await fetch("/api/devices");
    const data = await res.json();
    el.deviceIn.innerHTML = data.devices
      .filter(d => d.inputs > 0)
      .map(d => `<option value="${d.id}">${d.name}</option>`)
      .join("");
    el.deviceOut.innerHTML = data.devices
      .filter(d => d.outputs > 0)
      .map(d => `<option value="${d.id}">${d.name}</option>`)
      .join("");

    if (data.selected.device_in != null) el.deviceIn.value = data.selected.device_in;
    if (data.selected.device_out != null) el.deviceOut.value = data.selected.device_out;
  } catch (e) {
    console.error("Failed to load devices", e);
  }
}

async function loadWeights() {
  try {
    const res = await fetch("/api/weights");
    const data = await res.json();
    syncWeights(data);
  } catch (e) {
    console.error("Failed to load weights", e);
  }
}

function syncWeights(w) {
  if (w.FACT) el.weightFact.value = w.FACT;
  if (w.CONTEXT) el.weightContext.value = w.CONTEXT;
  if (w.STRATEGY) el.weightStrategy.value = w.STRATEGY;
}

async function refreshSessions() {
  try {
    const res = await fetch("/api/sessions");
    const sessions = await res.json();
    const curr = el.sessionSelect.value;
    el.sessionSelect.innerHTML = '<option value="live">Live Stream</option>' +
      sessions.map(s => {
        const time = s.start_time ? new Date(s.start_time).toLocaleTimeString() : "";
        return `<option value="${s.id}">Session #${s.id} (${time})</option>`;
      }).join("");
    el.sessionSelect.value = curr;
  } catch (e) {
    console.error("Failed to refresh sessions", e);
  }
}

async function loadSessionHistory(sessionId) {
  el.feed.innerHTML = '<div class="empty-feed"><span>Loading session history...</span></div>';
  try {
    const [sessRes, spkRes, sentRes, cueRes] = await Promise.all([
      fetch(`/api/session/${sessionId}`).then(r => r.json()),
      fetch(`/api/session/${sessionId}/speakers`).then(r => r.json()),
      fetch(`/api/session/${sessionId}/sentences`).then(r => r.json()),
      fetch(`/api/session/${sessionId}/cues`).then(r => r.json()),
    ]);

    renderContext(sessRes.context, spkRes);

    el.feed.innerHTML = "";
    if (sentRes.length === 0) {
      el.feed.innerHTML = '<div class="empty-feed"><span>No sentences recorded for this session.</span></div>';
      return;
    }

    const sentMap = {};
    for (const sent of sentRes) {
      const node = renderSentenceNode(sent);
      sentMap[sent.id] = node;
      el.feed.appendChild(node);
    }

    for (const cue of cueRes) {
      const cueNode = renderCueNode(cue);
      if (cue.sentence_id && sentMap[cue.sentence_id]) {
        let target = sentMap[cue.sentence_id];
        while (target.nextElementSibling && target.nextElementSibling.classList.contains("cue-card")) {
          target = target.nextElementSibling;
        }
        target.insertAdjacentElement("afterend", cueNode);
      } else {
        el.feed.appendChild(cueNode);
      }
    }
  } catch (e) {
    el.feed.innerHTML = `<div class="empty-feed"><span>Error loading session: ${escapeHtml(e.message)}</span></div>`;
  }
}

function bindEvents() {
  el.btn.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ action: isRunning ? "stop" : "start" }));
  });

  el.deviceIn.addEventListener("change", () => {
    fetch("/api/devices", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_in: parseInt(el.deviceIn.value, 10) }),
    });
  });

  el.deviceOut.addEventListener("change", () => {
    fetch("/api/devices", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_out: parseInt(el.deviceOut.value, 10) }),
    });
  });

  [el.weightFact, el.weightContext, el.weightStrategy].forEach(sel => {
    sel.addEventListener("change", () => {
      fetch(`/api/weights/${sel.dataset.type}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: sel.value }),
      });
    });
  });

  el.sessionSelect.addEventListener("change", (e) => {
    currentMode = e.target.value;
    if (currentMode === "live") {
      el.feed.innerHTML = '<div id="empty-feed" class="empty-feed"><span>Live feed active. Waiting for audio...</span></div>';
      el.emptyFeed = document.getElementById("empty-feed");
      renderContext("", []);
    } else {
      loadSessionHistory(currentMode);
    }
  });
}

// Bootstrap
bindEvents();
loadDevices();
loadWeights();
refreshSessions();
connectWs();

