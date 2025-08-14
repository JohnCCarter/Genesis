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

  document.getElementById("sub").onclick = () => {
    const sym = document.getElementById("sym").value.trim() || "tBTCUSD";
    fetch("/api/v2/ws/subscribe", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ channel: "ticker", symbol: sym }),
    })
      .then((r) => r.json())
      .then((j) => log("SUB " + JSON.stringify(j)))
      .catch((e) => log("ERR " + e));
  };
  document.getElementById("unsub").onclick = () => {
    const sym = document.getElementById("sym").value.trim() || "tBTCUSD";
    fetch("/api/v2/ws/unsubscribe", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ channel: "ticker", symbol: sym }),
    })
      .then((r) => r.json())
      .then((j) => log("UNSUB " + JSON.stringify(j)))
      .catch((e) => log("ERR " + e));
  };
  document.getElementById("rest-call").onclick = () => {
    const url = (document.getElementById("rest-url").value || "/health").trim();
    fetch(url)
      .then((r) => r.text())
      .then((t) => log("REST " + url + "\n" + t))
      .catch((e) => log("ERR " + e));
  };
})();
