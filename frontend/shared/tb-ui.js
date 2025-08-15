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
  // Enkel helper som skriver fel i ett <pre> om något går snett
  TB.fetchJsonSafeToPre = async function (url, options, timeoutMs, preEl) {
    try {
      const data = await TB.fetchJsonWithTimeout(url, options, timeoutMs);
      if (preEl)
        preEl.textContent =
          typeof data === "string" ? data : JSON.stringify(data, null, 2);
      return data;
    } catch (e) {
      if (preEl) preEl.textContent = String(e);
      throw e;
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
  // Liten state‑persist i localStorage
  TB.persistSetJSON = function (key, value) {
    try {
      localStorage.setItem(String(key), JSON.stringify(value));
    } catch {}
  };
  TB.persistGetJSON = function (key, fallback) {
    try {
      const v = localStorage.getItem(String(key));
      return v ? JSON.parse(v) : fallback;
    } catch {
      return fallback;
    }
  };
  window.TB = TB;
})();
