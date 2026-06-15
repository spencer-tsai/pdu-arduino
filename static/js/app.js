// Dashboard logic: render live PDU status and send control commands to the
// REST API. Status is polled on an interval; control buttons POST and then
// re-render from the response.
(function () {
  "use strict";

  const POLL_MS = 4000;

  const els = {
    indicator: document.getElementById("state-indicator"),
    label: document.getElementById("state-label"),
    connPill: document.getElementById("conn-pill"),
    connText: document.getElementById("conn-text"),
    error: document.getElementById("error-banner"),
    on: document.getElementById("btn-on"),
    off: document.getElementById("btn-off"),
    toggle: document.getElementById("btn-toggle"),
  };

  const buttons = [els.on, els.off, els.toggle];

  function setBusy(busy) {
    buttons.forEach((b) => {
      if (b) b.disabled = busy;
    });
  }

  function render(data) {
    const state = (data && data.state) || "unknown";

    els.indicator.classList.remove("state-on", "state-off", "state-unknown");
    els.indicator.classList.add("state-" + state);
    els.label.textContent = state.toUpperCase();

    const connected = !!(data && data.connected);
    els.connPill.classList.remove("pill-muted", "pill-ok", "pill-bad");
    els.connPill.classList.add(connected ? "pill-ok" : "pill-bad");
    els.connText.textContent = connected ? "Connected" : "Disconnected";

    const errMsg = data && data.error;
    if (errMsg) {
      els.error.textContent = errMsg;
      els.error.hidden = false;
    } else {
      els.error.hidden = true;
      els.error.textContent = "";
    }
  }

  function renderFailure(message) {
    els.connPill.classList.remove("pill-muted", "pill-ok", "pill-bad");
    els.connPill.classList.add("pill-bad");
    els.connText.textContent = "Unreachable";
    els.error.textContent = message;
    els.error.hidden = false;
  }

  async function fetchStatus() {
    try {
      const res = await fetch("/api/pdu/status", {
        headers: { Accept: "application/json" },
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      render(data);
    } catch (err) {
      renderFailure("Could not reach the server.");
    }
  }

  async function command(path) {
    setBusy(true);
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      render(data);
    } catch (err) {
      renderFailure("Command failed: could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  els.on.addEventListener("click", () => command("/api/pdu/on"));
  els.off.addEventListener("click", () => command("/api/pdu/off"));
  els.toggle.addEventListener("click", () => command("/api/pdu/toggle"));

  fetchStatus();
  setInterval(fetchStatus, POLL_MS);
})();
