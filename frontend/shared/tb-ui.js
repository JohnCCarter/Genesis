(function () {
  if (window.TB) return;
  const TB = {};
  TB.toast = function (msg) {
    try {
      const n = document.createElement("div");
      n.className = "toast";
      n.textContent = String(msg || "OK");
      Object.assign(n.style, {
        position: "fixed",
        right: "16px",
        bottom: "16px",
        background: "#24292f",
        color: "#fff",
        padding: "10px 14px",
        borderRadius: "6px",
        zIndex: 1000,
      });
      document.body.appendChild(n);
      setTimeout(() => n.remove(), 2200);
    } catch {}
  };
  TB.headersWithToken = function (inputId) {
    const id = inputId || "token";
    const el = document.getElementById(id);
    const token = el && el.value ? String(el.value).trim() : "";
    const h = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = "Bearer " + token;
    return h;
  };
  TB.fetchJsonWithTimeout = async function (url, options, timeoutMs) {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), timeoutMs || 8000);
    try {
      const res = await fetch(url, { ...(options || {}), signal: ctrl.signal });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      if (!res.ok) {
        const errTxt = ct.includes("application/json")
          ? JSON.stringify(await res.json())
          : await res.text();
        throw new Error(`HTTP ${res.status} ${res.statusText} - ${errTxt}`);
      }
      return ct.includes("application/json")
        ? await res.json()
        : await res.text();
    } finally {
      clearTimeout(to);
    }
  };
  TB.resolvePublicSymbol = function (symbol) {
    try {
      const s = (symbol || "").trim();
      let m = s.match(/^tTEST([A-Z0-9]+):TESTUSD$/);
      if (m) return `t${m[1]}USD`;
      m = s.match(/^tTEST([A-Z0-9]+):TESTUSDT$/);
      if (m) return `t${m[1]}UST`;
      m = s.match(/^tTESTUSDT:TEST([A-Z0-9]+)$/);
      if (m) return `t${m[1]}UST`;
      m = s.match(/^tTESTUSD:TEST([A-Z0-9]+)$/);
      if (m) return `t${m[1]}USD`;
      m = s.match(/^tTEST([A-Z0-9]+)USD$/);
      if (m) return `t${m[1]}USD`;
      return s;
    } catch {
      return symbol;
    }
  };
  TB.toPlainDecimalString = function (value, decimals) {
    const num = Number(value);
    if (!isFinite(num)) return "";
    const str = num.toFixed(decimals || 8);
    return str.replace(/\.?0+$/, "");
  };
  window.TB = TB;
})();
