(function () {
  const logEl = document.getElementById("log");
  function log(msg) {
    const t = new Date().toISOString();
    logEl.textContent += `[${t}] ${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }
  let socket = null;
  const statusEl = document.getElementById("ws-status");
  function setStatus(s) {
    statusEl.textContent = s;
  }
  const subsEl = document.getElementById("subs");
  async function refreshSubs() {
    try {
      const j = await TB.fetchJsonWithTimeout(
        "/api/v2/ws/pool/status",
        { headers: TB.headersWithToken() },
        6000
      );
      const arr = (j && j.subscriptions) || [];
      subsEl.textContent = arr.join("\n");
    } catch (e) {
      subsEl.textContent = String(e);
    }
  }
  document.getElementById("ws-connect").onclick = () => {
    if (socket) {
      log("Already connected");
      return;
    }
    socket = io("/", { path: "/ws/socket.io" });
    socket.on("connect", () => {
      setStatus("connected");
      log("WS connected");
    });
    socket.on("disconnect", () => {
      setStatus("disconnected");
      log("WS disconnected");
      socket = null;
    });
    socket.on("message", (m) => {
      log("WS message: " + JSON.stringify(m));
    });
  };
  document.getElementById("ws-disconnect").onclick = () => {
    if (socket) {
      socket.close();
    }
  };

  function authHeaders() {
    return window.TB
      ? TB.headersWithToken("token")
      : { "Content-Type": "application/json" };
  }

  document.getElementById("sub").onclick = async () => {
    const sym = document.getElementById("sym").value.trim() || "tBTCUSD";
    const chan = document.getElementById("chan").value || "ticker";
    const tf = document.getElementById("tf").value.trim();
    const body =
      tf && chan === "candles"
        ? { channel: chan, symbol: sym, timeframe: tf }
        : { channel: chan, symbol: sym };
    try {
      const j = await TB.fetchJsonWithTimeout(
        "/api/v2/ws/subscribe",
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify(body),
        },
        6000
      );
      log("SUB " + JSON.stringify(j));
      refreshSubs();
    } catch (e) {
      log("ERR " + e);
    }
  };
  document.getElementById("unsub").onclick = async () => {
    const sym = document.getElementById("sym").value.trim() || "tBTCUSD";
    const chan = document.getElementById("chan").value || "ticker";
    const tf = document.getElementById("tf").value.trim();
    const body =
      tf && chan === "candles"
        ? { channel: chan, symbol: sym, timeframe: tf }
        : { channel: chan, symbol: sym };
    try {
      const j = await TB.fetchJsonWithTimeout(
        "/api/v2/ws/unsubscribe",
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify(body),
        },
        6000
      );
      log("UNSUB " + JSON.stringify(j));
      refreshSubs();
    } catch (e) {
      log("ERR " + e);
    }
  };
  document.getElementById("rest-call").onclick = () => {
    const url = (document.getElementById("rest-url").value || "/health").trim();
    fetch(url)
      .then((r) => r.text())
      .then((t) => log("REST " + url + "\n" + t))
      .catch((e) => log("ERR " + e));
  };
  setInterval(refreshSubs, 5000);
})();
