(function () {
  const wsConnEl = document.getElementById("ws-connected");
  const wsAuthEl = document.getElementById("ws-auth");
  const toggleWs = document.getElementById("toggle-ws-strategy");
  const toggleVal = document.getElementById("toggle-validation-warmup");

  function setBadge(el, ok, labelIfOk, labelIfNot) {
    if (!el) return;
    el.classList.remove("ok", "warn", "err");
    el.classList.add(ok ? "ok" : "warn");
    el.textContent = ok ? (labelIfOk || "OK") : (labelIfNot || "-");
  }

  async function refreshWsStatus() {
    try {
      const data = await TB.fetchJsonWithTimeout("/api/v2/ws/pool/status", {
        headers: TB.headersWithToken(),
      }, 6000);
      const main = (data && data.main) || {};
      setBadge(wsConnEl, !!main.connected, "Connected", "Disc");
      setBadge(wsAuthEl, !!main.authenticated, "Auth", "NoAuth");
    } catch (e) {
      setBadge(wsConnEl, false, "Connected", "Disc");
      setBadge(wsAuthEl, false, "Auth", "NoAuth");
    }
  }

  async function loadToggles() {
    try {
      const ws = await TB.fetchJsonWithTimeout("/api/v2/mode/ws-strategy", { headers: TB.headersWithToken() }, 6000);
      if (toggleWs) toggleWs.checked = !!(ws && ws.enabled);
    } catch {}
    try {
      const v = await TB.fetchJsonWithTimeout("/api/v2/mode/validation-warmup", { headers: TB.headersWithToken() }, 6000);
      if (toggleVal) toggleVal.checked = !!(v && v.validation_on_start);
    } catch {}
  }

  async function bindEvents() {
    if (toggleWs) {
      toggleWs.onchange = async () => {
        try {
          await TB.fetchJsonWithTimeout("/api/v2/mode/ws-strategy", {
            method: "POST",
            headers: TB.headersWithToken(),
            body: JSON.stringify({ enabled: !!toggleWs.checked }),
          }, 6000);
          TB.toast("WS strategy: " + (toggleWs.checked ? "On" : "Off"));
        } catch (e) {
          TB.toast("Fel: " + e);
          toggleWs.checked = !toggleWs.checked;
        }
      };
    }
    if (toggleVal) {
      toggleVal.onchange = async () => {
        try {
          await TB.fetchJsonWithTimeout("/api/v2/mode/validation-warmup", {
            method: "POST",
            headers: TB.headersWithToken(),
            body: JSON.stringify({ enabled: !!toggleVal.checked }),
          }, 6000);
          TB.toast("Validation warm-up: " + (toggleVal.checked ? "On" : "Off"));
        } catch (e) {
          TB.toast("Fel: " + e);
          toggleVal.checked = !toggleVal.checked;
        }
      };
    }
  }

  async function init() {
    await loadToggles();
    await refreshWsStatus();
    bindEvents();
    // Poll WS-status lätt (ej blockerande)
    setInterval(refreshWsStatus, 5000);
  }

  window.addEventListener("load", init);
})();
