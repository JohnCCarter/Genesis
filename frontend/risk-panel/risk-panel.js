(function () {
  const wsConnEl = document.getElementById("ws-connected");
  const wsAuthEl = document.getElementById("ws-auth");
  const toggleWs = document.getElementById("toggle-ws-strategy");
  const toggleVal = document.getElementById("toggle-validation-warmup");

  function setBadge(el, ok, labelIfOk, labelIfNot) {
    if (!el) return;
    el.classList.remove("ok", "warn", "err");
    el.classList.add(ok ? "ok" : "warn");
    el.textContent = ok ? labelIfOk || "OK" : labelIfNot || "-";
  }

  async function refreshWsStatus() {
    try {
      const data = await TB.fetchJsonWithTimeout(
        "/api/v2/ws/pool/status",
        {
          headers: TB.headersWithToken(),
        },
        6000
      );
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
      const ws = await TB.fetchJsonWithTimeout(
        "/api/v2/mode/ws-strategy",
        { headers: TB.headersWithToken() },
        6000
      );
      if (toggleWs) toggleWs.checked = !!(ws && ws.enabled);
    } catch {}
    try {
      const v = await TB.fetchJsonWithTimeout(
        "/api/v2/mode/validation-warmup",
        { headers: TB.headersWithToken() },
        6000
      );
      if (toggleVal) toggleVal.checked = !!(v && v.validation_on_start);
    } catch {}
  }

  async function bindEvents() {
    if (toggleWs) {
      toggleWs.onchange = async () => {
        try {
          await TB.fetchJsonWithTimeout(
            "/api/v2/mode/ws-strategy",
            {
              method: "POST",
              headers: TB.headersWithToken(),
              body: JSON.stringify({ enabled: !!toggleWs.checked }),
            },
            6000
          );
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
          await TB.fetchJsonWithTimeout(
            "/api/v2/mode/validation-warmup",
            {
              method: "POST",
              headers: TB.headersWithToken(),
              body: JSON.stringify({ enabled: !!toggleVal.checked }),
            },
            6000
          );
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

    // Quick Trade
    const elSym = document.getElementById("qt-symbol");
    const elSide = document.getElementById("qt-side");
    const elAmt = document.getElementById("qt-amount");
    const elPx = document.getElementById("qt-price");
    const elOut = document.getElementById("qt-out");
    const elStat = document.getElementById("qt-status");
    const btnPrev = document.getElementById("qt-preview");
    const btnTrade = document.getElementById("qt-trade");
    function busy(btn, on) {
      if (!btn) return;
      btn.disabled = !!on;
      btn.textContent = on
        ? btn.textContent.replace(/\.\.\.$/, "") + "..."
        : btn.getAttribute("data-label") ||
          btn.textContent.replace(/\.\.\.$/, "");
    }
    if (btnPrev) btnPrev.setAttribute("data-label", btnPrev.textContent);
    if (btnTrade) btnTrade.setAttribute("data-label", btnTrade.textContent);

    // Persist small form state
    const qtKey = "rp.qt";
    const qtState = TB.persistGetJSON(qtKey, {});
    if (elSym && qtState.symbol) elSym.value = qtState.symbol;
    if (elSide && qtState.side) elSide.value = qtState.side;
    if (elAmt && qtState.amount) elAmt.value = qtState.amount;
    if (elPx && qtState.price) elPx.value = qtState.price;
    function saveQt() {
      TB.persistSetJSON(qtKey, {
        symbol: elSym ? elSym.value : undefined,
        side: elSide ? elSide.value : undefined,
        amount: elAmt ? elAmt.value : undefined,
        price: elPx ? elPx.value : undefined,
      });
    }
    [elSym, elSide, elAmt, elPx].forEach((el) => el && (el.onchange = saveQt));

    function parsePosNumber(val) {
      const n = Number(String(val || "").replace(",", "."));
      return isFinite(n) && n > 0 ? n : NaN;
    }
    function requireAmount() {
      const amt = parsePosNumber(elAmt && elAmt.value);
      if (!isFinite(amt)) {
        elStat.textContent = "Amount måste vara > 0";
        return null;
      }
      return amt;
    }

    async function preview() {
      try {
        busy(btnPrev, true);
        elStat.textContent = "";
        const sym = TB.resolvePublicSymbol((elSym && elSym.value) || "tBTCUSD");
        const eff = sym;
        const t = await TB.fetchJsonWithTimeout(
          `/api/v2/market/ticker/${encodeURIComponent(eff)}`,
          { headers: TB.headersWithToken() },
          6000
        );
        const last = t && t.last_price ? Number(t.last_price) : NaN;
        const amt = requireAmount();
        if (amt === null) return;
        const side = (elSide && elSide.value) || "buy";
        const pxIn = parsePosNumber(elPx && elPx.value);
        const price = isFinite(pxIn) && pxIn > 0 ? pxIn : last;
        const notional = isFinite(price) ? amt * price : 0;
        const estFee = notional * 0.0002; // 2 bps antagande
        const out = {
          symbol: eff,
          side,
          amount: amt,
          price,
          notional,
          est_fee: estFee,
        };
        if (elOut) elOut.textContent = JSON.stringify(out, null, 2);
        elStat.textContent = isFinite(price)
          ? `OK · ${side.toUpperCase()} ${amt} @ ${TB.toPlainDecimalString(
              price,
              6
            )} (≈${TB.toPlainDecimalString(notional, 2)})`
          : "Kunde inte hämta pris";
      } catch (e) {
        if (elOut) elOut.textContent = String(e);
      } finally {
        busy(btnPrev, false);
      }
    }

    async function trade() {
      try {
        busy(btnTrade, true);
        elStat.textContent = "";
        const sym = TB.resolvePublicSymbol((elSym && elSym.value) || "tBTCUSD");
        const side = (elSide && elSide.value) || "buy";
        const amtNum = requireAmount();
        if (amtNum === null) return;
        const amt = String(amtNum);
        const pxNum = parsePosNumber(elPx && elPx.value);
        const px = isFinite(pxNum) ? String(pxNum) : "";
        const payload =
          px && Number(px) > 0
            ? {
                symbol: sym,
                amount: amt,
                type:
                  side.toUpperCase() === "BUY"
                    ? "EXCHANGE LIMIT"
                    : "EXCHANGE LIMIT",
                price: px,
              }
            : {
                symbol: sym,
                amount: amt,
                type:
                  side.toUpperCase() === "BUY"
                    ? "EXCHANGE MARKET"
                    : "EXCHANGE MARKET",
              };
        const res = await TB.fetchJsonWithTimeout(
          "/api/v2/order",
          {
            method: "POST",
            headers: TB.headersWithToken(),
            body: JSON.stringify(payload),
          },
          10000
        );
        if (elOut) elOut.textContent = JSON.stringify(res, null, 2);
        TB.toast("Order skickad");
        elStat.textContent = `Skickad ${side.toUpperCase()} ${amt}`;
        saveQt();
      } catch (e) {
        if (elOut) elOut.textContent = String(e);
        TB.toast("Fel: " + e);
      } finally {
        busy(btnTrade, false);
      }
    }

    if (btnPrev) btnPrev.onclick = preview;
    if (btnTrade) btnTrade.onclick = trade;

    // Validation (on-demand)
    const vSym = document.getElementById("val-symbol");
    const vTf = document.getElementById("val-tf");
    const vLim = document.getElementById("val-limit");
    const vMax = document.getElementById("val-max");
    const vBtn = document.getElementById("val-run");
    const vOut = document.getElementById("val-out");
    const vStat = document.getElementById("val-status");
    if (vBtn) vBtn.setAttribute("data-label", vBtn.textContent);
    async function valRun() {
      try {
        busy(vBtn, true);
        vStat.textContent = "";
        const payload = {
          symbols: [TB.resolvePublicSymbol((vSym && vSym.value) || "tBTCUSD")],
          timeframe: (vTf && vTf.value) || undefined,
          limit: vLim && vLim.value ? Number(vLim.value) : undefined,
          max_samples: vMax && vMax.value ? Number(vMax.value) : undefined,
        };
        const res = await TB.fetchJsonWithTimeout(
          "/api/v2/prob/validate/run",
          {
            method: "POST",
            headers: TB.headersWithToken(),
            body: JSON.stringify(payload),
          },
          15000
        );
        if (vOut) vOut.textContent = JSON.stringify(res, null, 2);
        TB.toast("Validation klar");
      } catch (e) {
        if (vOut) vOut.textContent = String(e);
        TB.toast("Fel: " + e);
      } finally {
        busy(vBtn, false);
      }
    }
    if (vBtn) vBtn.onclick = valRun;

    // Strategy evaluate (weighted)
    const sSym = document.getElementById("st-symbol");
    const sEma = document.getElementById("st-ema");
    const sRsi = document.getElementById("st-rsi");
    const sAtr = document.getElementById("st-atr");
    const sBtn = document.getElementById("st-eval");
    const sOut = document.getElementById("st-out");
    const sStat = document.getElementById("st-status");
    if (sBtn) sBtn.setAttribute("data-label", sBtn.textContent);
    async function stEval() {
      try {
        busy(sBtn, true);
        sStat.textContent = "";
        const payload = {
          ema: (sEma && sEma.value) || "neutral",
          rsi: (sRsi && sRsi.value) || "neutral",
          atr: (sAtr && sAtr.value) || undefined,
          symbol: (sSym && sSym.value) || undefined,
        };
        const res = await TB.fetchJsonWithTimeout(
          "/api/v2/strategy/evaluate-weighted",
          {
            method: "POST",
            headers: TB.headersWithToken(),
            body: JSON.stringify(payload),
          },
          10000
        );
        if (sOut) sOut.textContent = JSON.stringify(res, null, 2);
        TB.toast("Strategy eval klar");
      } catch (e) {
        if (sOut) sOut.textContent = String(e);
        TB.toast("Fel: " + e);
      } finally {
        busy(sBtn, false);
      }
    }
    if (sBtn) sBtn.onclick = stEval;
  }

  window.addEventListener("load", init);
})();
