#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║           MONSTER FX AUTO ENGINE — COMMAND CENTER v5.0             ║
║           Professional Grade Trading Dashboard                     ║
║           Run: python monster_fx_engine.py                         ║
║           Open: http://localhost:5000                               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, Response
import json, math, random, time
from datetime import datetime, timezone
from functools import wraps

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = 'mfx_secret_2025'

# ══════════════════════════════════════════════════════════════════════
#  IN-MEMORY STORE  (persists for the session; replace with SQLite for production)
# ══════════════════════════════════════════════════════════════════════
STORE = {
    "trades": [],
    "starting_capital": 100.0
}

PAIR_FLAGS = {
    'AUD/JPY': '🇦🇺🇯🇵', 'AUD/USD': '🇦🇺🇺🇸', 'USD/JPY': '🇺🇸🇯🇵',
    'GBP/AUD': '🇬🇧🇦🇺', 'EUR/GBP': '🇪🇺🇬🇧', 'EUR/CHF': '🇪🇺🇨🇭',
    'USD/CAD': '🇺🇸🇨🇦', 'EUR/USD': '🇪🇺🇺🇸', 'GBP/USD': '🇬🇧🇺🇸',
}


def current_capital():
    closed = [t for t in STORE["trades"] if t.get("result") != "PENDING" and t.get("pnlAmt") is not None]
    return STORE["starting_capital"] + sum(t["pnlAmt"] for t in closed)


# ══════════════════════════════════════════════════════════════════════
#  API ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/trades", methods=["GET"])
def get_trades():
    return jsonify({"trades": STORE["trades"], "starting_capital": STORE["starting_capital"], "current_capital": current_capital()})


@app.route("/api/trades", methods=["POST"])
def add_trade():
    data = request.get_json()
    cap = current_capital()
    alloc_frac = (data.get("alloc", 10)) / 100
    amt = cap * alloc_frac
    lev = float(data.get("lev", 250))
    entry = float(data.get("entry", 0))
    tp = float(data.get("tp", 0)) if data.get("tp") else None
    sl = float(data.get("sl", 0)) if data.get("sl") else None
    result = data.get("result", "PENDING")
    pnl_pct = None
    pnl_amt = None
    if result != "PENDING" and entry:
        if result == "WIN" and tp:
            pnl_pct = abs(tp - entry) / entry * 100 * lev
            pnl_amt = amt * abs(tp - entry) / entry * lev
        elif result == "LOSS" and sl:
            pnl_pct = -(abs(sl - entry) / entry * 100 * lev)
            pnl_amt = -(amt * abs(sl - entry) / entry * lev)
        else:
            pnl_pct = lev * 0.14 if result == "WIN" else -(lev * 0.14)
            pnl_amt = amt * abs(pnl_pct) / 100
            if result == "LOSS": pnl_amt = -pnl_amt
        pnl_pct = round(pnl_pct, 2)
        pnl_amt = round(pnl_amt, 4)
    trade = {
        "id": int(time.time() * 1000),
        "pair": data.get("pair", "AUD/JPY"),
        "dir": data.get("dir", "BUY"),
        "entry": entry, "tp": tp, "sl": sl,
        "lev": lev, "conf": data.get("conf", 0),
        "setup": data.get("setup", ""), "alloc": data.get("alloc", 10),
        "result": result, "pnlPct": pnl_pct, "pnlAmt": pnl_amt,
        "capitalAfter": round(cap + (pnl_amt or 0), 4) if result != "PENDING" else None,
        "time": datetime.now(timezone.utc).isoformat()
    }
    STORE["trades"].insert(0, trade)
    return jsonify({"ok": True, "trade": trade, "current_capital": current_capital()})


@app.route("/api/trades/<int:trade_id>", methods=["PATCH"])
def update_trade(trade_id):
    data = request.get_json()
    trade = next((t for t in STORE["trades"] if t["id"] == trade_id), None)
    if not trade: return jsonify({"error": "Not found"}), 404
    idx = STORE["trades"].index(trade)
    before = [t for t in STORE["trades"][idx+1:] if t.get("result") != "PENDING" and t.get("pnlAmt") is not None]
    cap = STORE["starting_capital"] + sum(t["pnlAmt"] for t in before)
    amt = cap * (trade.get("alloc", 10)) / 100
    result = data.get("result", trade["result"])
    trade["result"] = result
    entry = trade.get("entry", 0)
    tp = trade.get("tp"); sl = trade.get("sl")
    if result != "PENDING" and entry:
        if result == "WIN" and tp:
            trade["pnlPct"] = round(abs(tp - entry) / entry * 100 * trade["lev"], 2)
            trade["pnlAmt"] = round(amt * abs(tp - entry) / entry * trade["lev"], 4)
        elif result == "LOSS" and sl:
            trade["pnlPct"] = -round(abs(sl - entry) / entry * 100 * trade["lev"], 2)
            trade["pnlAmt"] = -round(amt * abs(sl - entry) / entry * trade["lev"], 4)
        trade["capitalAfter"] = round(cap + (trade.get("pnlAmt") or 0), 4)
    return jsonify({"ok": True, "trade": trade, "current_capital": current_capital()})


@app.route("/api/trades/<int:trade_id>", methods=["DELETE"])
def delete_trade(trade_id):
    STORE["trades"] = [t for t in STORE["trades"] if t["id"] != trade_id]
    return jsonify({"ok": True, "current_capital": current_capital()})


@app.route("/api/trades", methods=["DELETE"])
def clear_trades():
    STORE["trades"] = []
    return jsonify({"ok": True})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    trades = STORE["trades"]
    closed = [t for t in trades if t.get("result") != "PENDING"]
    wins = [t for t in closed if t.get("result") == "WIN"]
    losses = [t for t in closed if t.get("result") == "LOSS"]
    pending = [t for t in trades if t.get("result") == "PENDING"]
    wr = round(len(wins) / len(closed) * 100) if closed else 0
    net_pnl = sum(t.get("pnlPct") or 0 for t in closed)
    avg_conf = round(sum(t.get("conf") or 0 for t in trades) / len(trades)) if trades else 0
    sorted_closed = sorted([t for t in closed if t.get("pnlPct") is not None], key=lambda x: x["pnlPct"])
    best = sorted_closed[-1] if sorted_closed else None
    worst = sorted_closed[0] if sorted_closed else None

    # Equity curve
    equity = [STORE["starting_capital"]]
    run = STORE["starting_capital"]
    for t in reversed(closed):
        if t.get("pnlAmt") is not None:
            run += t["pnlAmt"]
            equity.append(round(run, 2))

    # Pair performance
    pair_perf = {}
    for t in closed:
        p = t["pair"]
        if p not in pair_perf: pair_perf[p] = {"wins": 0, "losses": 0, "pnl": 0}
        pair_perf[p]["pnl"] += t.get("pnlPct") or 0
        if t.get("result") == "WIN": pair_perf[p]["wins"] += 1
        else: pair_perf[p]["losses"] += 1

    return jsonify({
        "total": len(trades), "wins": len(wins), "losses": len(losses),
        "pending": len(pending), "win_rate": wr, "net_pnl": round(net_pnl, 2),
        "avg_conf": avg_conf,
        "best": {"pnl": best["pnlPct"], "pair": best["pair"]} if best else None,
        "worst": {"pnl": worst["pnlPct"], "pair": worst["pair"]} if worst else None,
        "equity_curve": equity, "current_capital": current_capital(),
        "pair_performance": pair_perf,
        "starting_capital": STORE["starting_capital"]
    })


# ══════════════════════════════════════════════════════════════════════
#  MAIN ROUTE — Serves the full SPA
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


# ══════════════════════════════════════════════════════════════════════
#  THE COMPLETE FRONTEND (embedded HTML)
# ══════════════════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MONSTER FX ENGINE v5.0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* ═══════════════════════════════════════════════════
   DESIGN SYSTEM — OBSIDIAN PLATINUM THEME
═══════════════════════════════════════════════════ */
:root {
  --bg-void:      #080a0e;
  --bg-deep:      #0c0f16;
  --bg-surface:   #111520;
  --bg-raised:    #161c2c;
  --bg-float:     #1c2438;

  --gold:         #c9a84c;
  --gold-bright:  #f0c84a;
  --gold-dim:     #7a621f;
  --gold-glow:    rgba(201,168,76,0.18);

  --emerald:      #00c896;
  --emerald-dim:  rgba(0,200,150,0.15);
  --ruby:         #e03060;
  --ruby-dim:     rgba(224,48,96,0.15);
  --sapphire:     #2d7ef5;
  --sapphire-dim: rgba(45,126,245,0.12);

  --platinum:     #c8d4e8;
  --silver:       #8a9ab8;
  --muted:        #4a5570;
  --faint:        #2a3048;

  --border:       rgba(201,168,76,0.12);
  --border-hi:    rgba(201,168,76,0.35);
  --shadow-deep:  0 24px 64px rgba(0,0,0,0.6);
  --shadow-card:  0 4px 24px rgba(0,0,0,0.35);

  --r-sm: 8px;
  --r-md: 12px;
  --r-lg: 18px;
  --r-xl: 24px;

  --font-display: 'Bebas Neue', sans-serif;
  --font-body:    'Syne', sans-serif;
  --font-mono:    'JetBrains Mono', monospace;

  --ease-spring:  cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-smooth:  cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  background: var(--bg-void);
  color: var(--platinum);
  font-family: var(--font-body);
  min-height: 100vh;
  overflow-x: hidden;
  line-height: 1.5;
}

/* ── NOISE TEXTURE OVERLAY ── */
body::before {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E");
  background-size: 200px;
  pointer-events: none; z-index: 0; opacity: 0.6;
}

/* ── AMBIENT GLOW ── */
body::after {
  content: '';
  position: fixed;
  top: -30vh; left: 50%;
  transform: translateX(-50%);
  width: 80vw; height: 60vh;
  background: radial-gradient(ellipse, rgba(201,168,76,0.06) 0%, transparent 70%);
  pointer-events: none; z-index: 0;
}

.app { position: relative; z-index: 1; max-width: 1800px; margin: 0 auto; padding: 0 20px 40px; }

/* ═══════════════════════════════════════════════════
   HEADER
═══════════════════════════════════════════════════ */
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 28px; margin: 20px 0;
  background: linear-gradient(135deg, var(--bg-surface), var(--bg-raised));
  border: 1px solid var(--border); border-radius: var(--r-xl);
  position: relative; overflow: hidden;
  animation: slideDown 0.6s var(--ease-spring);
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.header::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--gold) 30%, var(--gold-bright) 50%, var(--gold) 70%, transparent 100%);
  animation: shimmer 4s linear infinite;
  background-size: 200%;
}
@keyframes shimmer { 0% { background-position: -200%; } 100% { background-position: 200%; } }
.header::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold-dim), transparent);
}

.logo { display: flex; align-items: center; gap: 16px; }
.logo-mark {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, var(--gold-dim), var(--gold));
  border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  box-shadow: 0 0 24px var(--gold-glow);
  animation: pulseGlow 3s ease-in-out infinite;
}
@keyframes pulseGlow {
  0%,100% { box-shadow: 0 0 16px var(--gold-glow); }
  50%      { box-shadow: 0 0 36px rgba(201,168,76,0.35); }
}
.logo-text h1 {
  font-family: var(--font-display);
  font-size: 26px; letter-spacing: 4px;
  background: linear-gradient(90deg, var(--gold), var(--gold-bright), var(--gold));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-size: 200%;
  animation: textShimmer 4s linear infinite;
}
@keyframes textShimmer { 0% { background-position: 0%; } 100% { background-position: 200%; } }
.logo-text p {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 3px;
  color: var(--muted); text-transform: uppercase; margin-top: 2px;
}

.header-right { display: flex; align-items: center; gap: 12px; }

.live-indicator {
  display: flex; align-items: center; gap: 8px;
  background: rgba(0,200,150,0.08);
  border: 1px solid rgba(0,200,150,0.3);
  border-radius: 100px; padding: 7px 16px;
  font-family: var(--font-mono); font-size: 10px; color: var(--emerald);
  letter-spacing: 2px;
}
.live-dot {
  width: 7px; height: 7px;
  background: var(--emerald); border-radius: 50%;
  animation: livePulse 1.8s ease-in-out infinite;
  box-shadow: 0 0 8px var(--emerald);
}
@keyframes livePulse {
  0%,100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.4); opacity: 0.5; }
}

#utc-clock {
  font-family: var(--font-mono); font-size: 13px; font-weight: 600;
  color: var(--gold); letter-spacing: 2px;
  padding: 7px 14px;
  background: var(--gold-glow);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
}

/* ═══════════════════════════════════════════════════
   CAPITAL HERO STRIP
═══════════════════════════════════════════════════ */
.capital-strip {
  display: grid; grid-template-columns: 1fr 1fr 2fr 1fr;
  gap: 16px; margin-bottom: 20px;
  animation: fadeUp 0.6s var(--ease-spring) 0.1s both;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

.capital-card {
  background: linear-gradient(135deg, var(--bg-surface), var(--bg-raised));
  border: 1px solid var(--border); border-radius: var(--r-lg);
  padding: 22px 24px; position: relative; overflow: hidden;
  transition: border-color 0.3s, transform 0.3s;
}
.capital-card:hover { border-color: var(--border-hi); transform: translateY(-2px); }
.capital-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
  opacity: 0.6;
}
.cap-label {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 3px;
  color: var(--muted); text-transform: uppercase; margin-bottom: 8px;
}
.cap-value {
  font-family: var(--font-display); font-size: 38px; letter-spacing: 2px;
  color: var(--gold-bright); line-height: 1;
  transition: all 0.4s var(--ease-smooth);
}
.cap-sub {
  font-family: var(--font-mono); font-size: 10px;
  color: var(--silver); margin-top: 6px;
}
.growth-val {
  font-family: var(--font-display); font-size: 30px; letter-spacing: 1px;
}
.growth-val.pos { color: var(--emerald); }
.growth-val.neg { color: var(--ruby); }

/* Milestone pills */
.milestones { display: flex; flex-wrap: wrap; gap: 6px; }
.ms-pill {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1px;
  padding: 4px 12px; border-radius: 100px;
  border: 1px solid var(--faint); color: var(--muted);
  transition: all 0.3s;
}
.ms-pill.done {
  background: rgba(0,200,150,0.12); border-color: var(--emerald);
  color: var(--emerald);
}
.ms-pill.next {
  background: rgba(201,168,76,0.1); border-color: var(--gold);
  color: var(--gold);
  animation: msGlow 2s ease-in-out infinite;
}
@keyframes msGlow {
  0%,100% { box-shadow: 0 0 0 rgba(201,168,76,0); }
  50%      { box-shadow: 0 0 16px rgba(201,168,76,0.3); }
}

/* ═══════════════════════════════════════════════════
   STATS ROW
═══════════════════════════════════════════════════ */
.stats-row {
  display: grid; grid-template-columns: repeat(7, 1fr);
  gap: 12px; margin-bottom: 20px;
  animation: fadeUp 0.6s var(--ease-spring) 0.2s both;
}
.stat-card {
  background: var(--bg-surface); border-radius: var(--r-md);
  border: 1px solid var(--faint); padding: 16px 14px;
  position: relative; overflow: hidden;
  transition: border-color 0.3s, transform 0.25s;
  cursor: default;
}
.stat-card:hover { transform: translateY(-3px); border-color: var(--border); }
.stat-card::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
  opacity: 0.8;
}
.stat-card:nth-child(1)::after { background: var(--gold); }
.stat-card:nth-child(2)::after { background: var(--emerald); }
.stat-card:nth-child(3)::after { background: var(--sapphire); }
.stat-card:nth-child(4)::after { background: #b48ef5; }
.stat-card:nth-child(5)::after { background: var(--emerald); }
.stat-card:nth-child(6)::after { background: var(--ruby); }
.stat-card:nth-child(7)::after { background: var(--gold-dim); }

.stat-lbl { font-family: var(--font-mono); font-size: 8px; letter-spacing: 2px; color: var(--muted); margin-bottom: 8px; text-transform: uppercase; }
.stat-val { font-family: var(--font-display); font-size: 22px; letter-spacing: 1px; }
.stat-sub { font-family: var(--font-mono); font-size: 9px; color: var(--silver); margin-top: 4px; }
.stat-card:nth-child(1) .stat-val { color: var(--gold); }
.stat-card:nth-child(2) .stat-val { color: var(--emerald); }
.stat-card:nth-child(3) .stat-val { color: var(--sapphire); }
.stat-card:nth-child(4) .stat-val { color: #b48ef5; }
.stat-card:nth-child(5) .stat-val { color: var(--emerald); }
.stat-card:nth-child(6) .stat-val { color: var(--ruby); }
.stat-card:nth-child(7) .stat-val { color: var(--gold-dim); }

/* ═══════════════════════════════════════════════════
   MAIN LAYOUT
═══════════════════════════════════════════════════ */
.main-grid {
  display: grid; grid-template-columns: 1fr 400px;
  gap: 20px;
  animation: fadeUp 0.6s var(--ease-spring) 0.3s both;
}

/* ═══════════════════════════════════════════════════
   PANEL BASE
═══════════════════════════════════════════════════ */
.panel {
  background: linear-gradient(160deg, var(--bg-surface) 0%, var(--bg-raised) 100%);
  border: 1px solid var(--border); border-radius: var(--r-xl);
  overflow: hidden; margin-bottom: 16px;
}
.panel-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 22px; border-bottom: 1px solid var(--faint);
  background: rgba(0,0,0,0.15);
}
.panel-head h2 {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 3px;
  color: var(--gold); text-transform: uppercase; font-weight: 600;
}
.panel-icon { font-size: 16px; }
.panel-head-right { margin-left: auto; display: flex; gap: 10px; align-items: center; }

/* ═══════════════════════════════════════════════════
   EQUITY CHART PANEL
═══════════════════════════════════════════════════ */
.chart-container { padding: 20px; }
#equityChart { width: 100% !important; }

/* ═══════════════════════════════════════════════════
   PAIR PERFORMANCE
═══════════════════════════════════════════════════ */
.pair-perf-wrap { padding: 16px 22px; }
.pair-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.03);
}
.pair-row:last-child { border-bottom: none; }
.pair-flag { font-size: 22px; width: 36px; text-align: center; }
.pair-name { font-family: var(--font-mono); font-size: 11px; font-weight: 600; width: 76px; color: var(--platinum); }
.pair-wr   { font-family: var(--font-mono); font-size: 9px; color: var(--muted); width: 42px; }
.pair-bar  { flex: 1; height: 6px; background: var(--faint); border-radius: 4px; overflow: hidden; }
.pair-fill { height: 100%; border-radius: 4px; transition: width 0.8s var(--ease-spring); }
.pair-fill.pos { background: linear-gradient(90deg, var(--emerald), #00f5a0); }
.pair-fill.neg { background: linear-gradient(90deg, var(--ruby), #ff8060); }
.pair-pnl  { font-family: var(--font-mono); font-size: 11px; font-weight: 600; width: 64px; text-align: right; }

/* ═══════════════════════════════════════════════════
   TRADE FORM
═══════════════════════════════════════════════════ */
.form-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }

.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.field { display: flex; flex-direction: column; gap: 6px; }
.field label {
  font-family: var(--font-mono); font-size: 8px; letter-spacing: 3px;
  color: var(--muted); text-transform: uppercase;
}
.field input, .field select {
  background: var(--bg-void); border: 1px solid var(--faint);
  border-radius: var(--r-sm); padding: 10px 14px;
  color: var(--platinum); font-family: var(--font-mono); font-size: 12px;
  outline: none; transition: border-color 0.2s, box-shadow 0.2s;
  -webkit-appearance: none; appearance: none;
}
.field input:focus, .field select:focus {
  border-color: var(--gold); box-shadow: 0 0 0 3px var(--gold-glow);
}
.field select option { background: var(--bg-deep); color: var(--platinum); }

/* Direction Buttons */
.dir-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.dir-btn {
  padding: 14px; border-radius: var(--r-md);
  border: 2px solid transparent; cursor: pointer;
  font-family: var(--font-display); font-size: 16px; letter-spacing: 2px;
  background: transparent; color: var(--muted);
  transition: all 0.25s var(--ease-spring); position: relative; overflow: hidden;
}
.dir-btn::before {
  content: ''; position: absolute; inset: 0;
  background: currentColor; opacity: 0; transition: opacity 0.2s;
}
.dir-btn:hover::before { opacity: 0.06; }
.dir-btn.buy  { border-color: rgba(0,200,150,0.3); }
.dir-btn.sell { border-color: rgba(224,48,96,0.3); }
.dir-btn.buy.active  { background: var(--emerald-dim); border-color: var(--emerald); color: var(--emerald); box-shadow: 0 0 24px rgba(0,200,150,0.2); }
.dir-btn.sell.active { background: var(--ruby-dim);    border-color: var(--ruby);    color: var(--ruby);    box-shadow: 0 0 24px rgba(224,48,96,0.2); }

/* Result Buttons */
.res-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.res-btn {
  padding: 10px; border-radius: var(--r-sm);
  border: 1px solid var(--faint); cursor: pointer;
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  background: transparent; color: var(--muted);
  transition: all 0.2s; letter-spacing: 1px;
}
.res-btn.win.active  { background: var(--emerald-dim); border-color: var(--emerald); color: var(--emerald); }
.res-btn.loss.active { background: var(--ruby-dim);    border-color: var(--ruby);    color: var(--ruby); }
.res-btn.pend.active { background: rgba(201,168,76,0.12); border-color: var(--gold); color: var(--gold); }

/* Risk Calculator */
.risk-calc {
  background: var(--bg-void); border: 1px solid var(--faint);
  border-radius: var(--r-md); padding: 16px;
}
.risk-calc-title { font-family: var(--font-mono); font-size: 9px; letter-spacing: 2px; color: var(--muted); margin-bottom: 12px; }
.risk-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center; }
.risk-item-val { font-family: var(--font-display); font-size: 18px; letter-spacing: 1px; }
.risk-item-lbl { font-family: var(--font-mono); font-size: 9px; color: var(--muted); margin-top: 2px; }

/* Verdict Box */
.verdict-box {
  border-radius: var(--r-md); padding: 14px; display: none;
  animation: popIn 0.3s var(--ease-spring);
  border: 1px solid;
}
@keyframes popIn { from { opacity:0; transform:scale(0.95); } to { opacity:1; transform:scale(1); } }
.verdict-box.show { display: block; }
.verdict-box.go   { background: rgba(0,200,150,0.07); border-color: var(--emerald); }
.verdict-box.warn { background: rgba(201,168,76,0.07); border-color: var(--gold); }
.verdict-box.stop { background: rgba(224,48,96,0.07);  border-color: var(--ruby); }
.verdict-title { font-family: var(--font-display); font-size: 14px; letter-spacing: 2px; margin-bottom: 6px; }
.verdict-box.go   .verdict-title { color: var(--emerald); }
.verdict-box.warn .verdict-title { color: var(--gold); }
.verdict-box.stop .verdict-title { color: var(--ruby); }
.verdict-desc { font-family: var(--font-mono); font-size: 10px; color: var(--silver); line-height: 1.6; }

/* Submit Button */
.submit-btn {
  padding: 16px; border-radius: var(--r-md); cursor: pointer;
  background: linear-gradient(135deg, rgba(201,168,76,0.15), rgba(240,200,74,0.1));
  border: 1px solid var(--border-hi); color: var(--gold);
  font-family: var(--font-display); font-size: 16px; letter-spacing: 3px;
  transition: all 0.25s var(--ease-spring); position: relative; overflow: hidden;
}
.submit-btn:hover {
  background: linear-gradient(135deg, rgba(201,168,76,0.25), rgba(240,200,74,0.2));
  box-shadow: 0 0 32px rgba(201,168,76,0.25);
  transform: translateY(-1px);
}
.submit-btn:active { transform: translateY(1px); }

/* ═══════════════════════════════════════════════════
   TRADE JOURNAL TABLE
═══════════════════════════════════════════════════ */
.table-wrap { overflow-x: auto; max-height: 440px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 11px; }
thead { position: sticky; top: 0; z-index: 2; }
thead tr { background: rgba(0,0,0,0.4); }
th {
  padding: 11px 14px; text-align: left;
  font-family: var(--font-mono); font-size: 8px; letter-spacing: 2px;
  color: var(--gold); white-space: nowrap; border-bottom: 1px solid var(--border);
  text-transform: uppercase;
}
tbody tr {
  border-bottom: 1px solid rgba(255,255,255,0.025);
  transition: background 0.15s;
}
tbody tr:hover { background: rgba(201,168,76,0.04); }
tbody tr.win-row  td:first-child { border-left: 2px solid var(--emerald); }
tbody tr.loss-row td:first-child { border-left: 2px solid var(--ruby); }
tbody tr.pend-row td:first-child { border-left: 2px solid var(--gold); }
td { padding: 11px 14px; white-space: nowrap; vertical-align: middle; }

.pair-cell { display: flex; align-items: center; gap: 8px; }
.pair-emoji { font-size: 18px; }
.pair-txt { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--platinum); }

.dir-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 100px;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
}
.dir-badge.BUY  { background: var(--emerald-dim); color: var(--emerald); border: 1px solid rgba(0,200,150,0.3); }
.dir-badge.SELL { background: var(--ruby-dim);    color: var(--ruby);    border: 1px solid rgba(224,48,96,0.3); }

.conf-bar-wrap { display: flex; align-items: center; gap: 8px; }
.conf-bar { width: 48px; height: 4px; background: var(--faint); border-radius: 2px; overflow: hidden; }
.conf-fill { height: 100%; background: linear-gradient(90deg, var(--gold), var(--gold-bright)); }

.pnl-val { font-family: var(--font-mono); font-size: 11px; font-weight: 600; }
.pnl-val.pos { color: var(--emerald); }
.pnl-val.neg { color: var(--ruby); }
.pnl-val.zero{ color: var(--gold); }

.result-select {
  background: transparent; border: none;
  font-family: var(--font-mono); font-size: 10px; cursor: pointer;
  outline: none; padding: 4px 6px; border-radius: 4px;
  border: 1px solid var(--faint);
  transition: border-color 0.2s;
}
.result-select:hover { border-color: var(--border); }
.result-select.WIN  { color: var(--emerald); }
.result-select.LOSS { color: var(--ruby); }
.result-select.PENDING { color: var(--gold); }

.del-btn {
  background: transparent; border: 1px solid rgba(224,48,96,0.2);
  border-radius: 4px; padding: 4px 8px; cursor: pointer;
  color: var(--ruby); font-size: 10px; transition: all 0.2s;
}
.del-btn:hover { background: var(--ruby-dim); }

/* ═══════════════════════════════════════════════════
   EXPORT + RULES PANELS
═══════════════════════════════════════════════════ */
.export-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 16px; }
.exp-btn {
  padding: 14px 10px; border-radius: var(--r-md); cursor: pointer;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  letter-spacing: 2px; text-transform: uppercase;
  background: transparent; transition: all 0.22s var(--ease-spring);
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.exp-btn span { font-size: 8px; font-weight: 400; letter-spacing: 1px; color: var(--muted); text-transform: none; }
.exp-btn:hover { transform: translateY(-2px); }
.exp-btn.csv   { border: 1px solid rgba(0,200,150,0.4);  color: var(--emerald); }
.exp-btn.json  { border: 1px solid rgba(45,126,245,0.4); color: var(--sapphire); }
.exp-btn.model { border: 1px solid rgba(201,168,76,0.4); color: var(--gold); }
.exp-btn.clear { border: 1px solid rgba(224,48,96,0.4);  color: var(--ruby); }
.exp-btn.csv:hover   { background: rgba(0,200,150,0.08); }
.exp-btn.json:hover  { background: rgba(45,126,245,0.08); }
.exp-btn.model:hover { background: rgba(201,168,76,0.08); }
.exp-btn.clear:hover { background: rgba(224,48,96,0.08); }

/* Rules */
.rules-list { padding: 14px 18px; display: flex; flex-direction: column; gap: 8px; }
.rule-item {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 11px 14px; border-radius: var(--r-sm);
  border: 1px solid transparent; transition: border-color 0.2s, background 0.2s;
}
.rule-item:hover { background: rgba(255,255,255,0.02); border-color: var(--faint); }
.rule-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
.rule-text strong { font-family: var(--font-mono); font-size: 10px; color: var(--platinum); display: block; margin-bottom: 3px; letter-spacing: 1px; }
.rule-text span   { font-family: var(--font-mono); font-size: 9px;  color: var(--muted); line-height: 1.6; }
.rule-item.go   { border-left: 2px solid var(--emerald); }
.rule-item.warn { border-left: 2px solid var(--gold); }
.rule-item.stop { border-left: 2px solid var(--ruby); }

/* ═══════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════ */
#toast {
  position: fixed; bottom: 32px; right: 28px; z-index: 9999;
  background: var(--bg-raised); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: 14px 22px;
  font-family: var(--font-mono); font-size: 12px; color: var(--gold);
  opacity: 0; transform: translateY(20px) scale(0.95);
  transition: all 0.3s var(--ease-spring); pointer-events: none;
  box-shadow: var(--shadow-deep); max-width: 320px;
}
#toast.show { opacity: 1; transform: translateY(0) scale(1); }
#toast.ok   { border-color: var(--emerald); color: var(--emerald); }
#toast.err  { border-color: var(--ruby);    color: var(--ruby); }

/* ═══════════════════════════════════════════════════
   RECOVERY MODAL
═══════════════════════════════════════════════════ */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.8); backdrop-filter: blur(6px);
  z-index: 9000; display: none; align-items: center; justify-content: center;
  padding: 20px;
}
.modal-overlay.open { display: flex; }
.recovery-modal {
  background: var(--bg-deep);
  border: 1px solid rgba(224,48,96,0.3);
  border-radius: var(--r-xl); width: 100%; max-width: 700px;
  max-height: 90vh; overflow-y: auto;
  animation: slideUp 0.35s var(--ease-spring);
}
@keyframes slideUp { from { opacity:0; transform:translateY(40px) scale(0.97); } to { opacity:1; transform:none; } }
.rec-head {
  padding: 22px 28px 18px;
  border-bottom: 1px solid rgba(224,48,96,0.2);
  background: linear-gradient(135deg, rgba(224,48,96,0.07), transparent);
  display: flex; align-items: center; justify-content: space-between;
}
.rec-title { font-family: var(--font-display); font-size: 22px; letter-spacing: 3px; color: var(--ruby); }
.rec-close {
  background: transparent; border: 1px solid rgba(224,48,96,0.3);
  border-radius: var(--r-sm); padding: 7px 14px; cursor: pointer;
  color: var(--silver); font-family: var(--font-mono); font-size: 10px;
  transition: all 0.2s;
}
.rec-close:hover { background: var(--ruby-dim); color: var(--ruby); }
.rec-body { padding: 24px 28px; }

.loss-summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 22px; }
.ls-card { background: var(--bg-surface); border: 1px solid var(--faint); border-radius: var(--r-md); padding: 16px; text-align: center; }
.ls-val { font-family: var(--font-display); font-size: 22px; letter-spacing: 1px; margin-bottom: 5px; }
.ls-lbl { font-family: var(--font-mono); font-size: 8px; letter-spacing: 2px; color: var(--muted); }
.ls-card.danger .ls-val { color: var(--ruby); }
.ls-card.warn   .ls-val { color: var(--gold); }
.ls-card.info   .ls-val { color: var(--sapphire); }

.scenarios { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 20px; }
.sc-card {
  background: var(--bg-surface); border-radius: var(--r-md);
  border: 2px solid var(--faint); padding: 18px; cursor: pointer;
  text-align: center; transition: all 0.25s var(--ease-spring);
}
.sc-card:hover { transform: translateY(-4px); }
.sc-card.picked { border-color: var(--gold); background: var(--gold-glow); }
.sc-name { font-family: var(--font-display); font-size: 13px; letter-spacing: 2px; margin-bottom: 8px; }
.sc-card.conservative .sc-name { color: var(--emerald); }
.sc-card.balanced     .sc-name { color: var(--gold); }
.sc-card.aggressive   .sc-name { color: var(--ruby); }
.sc-alloc { font-family: var(--font-display); font-size: 28px; margin-bottom: 2px; }
.sc-card.conservative .sc-alloc { color: var(--emerald); }
.sc-card.balanced     .sc-alloc { color: var(--gold); }
.sc-card.aggressive   .sc-alloc { color: var(--ruby); }
.sc-sub { font-family: var(--font-mono); font-size: 9px; color: var(--muted); margin-bottom: 10px; }
.sc-trades { font-family: var(--font-display); font-size: 32px; color: var(--platinum); margin: 8px 0 2px; }
.sc-trades-lbl { font-family: var(--font-mono); font-size: 9px; color: var(--muted); }

.rec-section-title { font-family: var(--font-mono); font-size: 9px; letter-spacing: 3px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; }
.path-steps { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 20px; }
.path-step {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  border: 2px solid var(--faint); color: var(--muted);
  transition: all 0.3s; cursor: default;
}
.path-step.recovered { border-color: var(--emerald); background: rgba(0,200,150,0.15); color: var(--emerald); }
.path-step.milestone { border-color: var(--gold); background: var(--gold-glow); color: var(--gold); }

.rec-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rec-btn {
  padding: 15px; border-radius: var(--r-md); cursor: pointer;
  font-family: var(--font-display); font-size: 14px; letter-spacing: 2px;
  transition: all 0.22s;
}
.rec-btn.apply {
  background: var(--gold-glow); border: 1px solid var(--border-hi); color: var(--gold);
}
.rec-btn.apply:hover { background: rgba(201,168,76,0.2); box-shadow: 0 0 24px var(--gold-glow); }
.rec-btn.dismiss { background: transparent; border: 1px solid var(--faint); color: var(--silver); }
.rec-btn.dismiss:hover { border-color: var(--muted); color: var(--platinum); }

/* ═══════════════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-void); }
::-webkit-scrollbar-thumb { background: var(--faint); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ═══════════════════════════════════════════════════
   EMPTY STATE
═══════════════════════════════════════════════════ */
.empty { text-align: center; padding: 50px 20px; }
.empty-icon { font-size: 40px; opacity: 0.25; margin-bottom: 12px; }
.empty-txt { font-family: var(--font-mono); font-size: 11px; color: var(--muted); }

/* ═══════════════════════════════════════════════════
   NUMBER COUNTER ANIMATION
═══════════════════════════════════════════════════ */
@keyframes countUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-num { animation: countUp 0.4s var(--ease-spring); }

/* ═══════════════════════════════════════════════════
   RESPONSIVE
═══════════════════════════════════════════════════ */
@media (max-width: 1200px) {
  .main-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(4, 1fr); }
  .capital-strip { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 768px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .capital-strip { grid-template-columns: 1fr 1fr; }
  .header { padding: 14px 18px; }
  .logo-text h1 { font-size: 20px; }
}
</style>
</head>
<body>
<div class="app">

  <!-- ── HEADER ── -->
  <header class="header">
    <div class="logo">
      <div class="logo-mark">🤖</div>
      <div class="logo-text">
        <h1>MONSTER FX ENGINE</h1>
        <p>$100 Growth Machine — Survival Trading Command Center v5.0</p>
      </div>
    </div>
    <div class="header-right">
      <div class="live-indicator"><div class="live-dot"></div>LIVE</div>
      <div id="utc-clock">--:--:-- UTC</div>
    </div>
  </header>

  <!-- ── CAPITAL STRIP ── -->
  <div class="capital-strip">
    <div class="capital-card">
      <div class="cap-label">💰 Current Capital</div>
      <div class="cap-value" id="cap-val">$100.00</div>
      <div class="cap-sub" id="cap-sub">Starting: $100.00</div>
    </div>
    <div class="capital-card">
      <div class="cap-label">📈 Total Growth</div>
      <div class="growth-val pos" id="growth-val">+0.0%</div>
      <div class="cap-sub" id="cap-trades">0 completed trades</div>
    </div>
    <div class="capital-card">
      <div class="cap-label">🏆 Milestones</div>
      <div class="milestones" id="milestones">
        <span class="ms-pill next" data-t="200">$200 🎯</span>
        <span class="ms-pill" data-t="500">$500 🚀</span>
        <span class="ms-pill" data-t="1000">$1K 💎</span>
        <span class="ms-pill" data-t="5000">$5K 🔥</span>
        <span class="ms-pill" data-t="10000">$10K 👑</span>
        <span class="ms-pill" data-t="50000">$50K 🏎️</span>
      </div>
    </div>
    <div class="capital-card">
      <div class="cap-label">🎯 Next Target</div>
      <div class="cap-value" id="next-target" style="font-size:26px;color:var(--gold)">$200</div>
      <div class="cap-sub" id="next-need">Need $100.00 more</div>
    </div>
  </div>

  <!-- ── STATS ROW ── -->
  <div class="stats-row">
    <div class="stat-card"><div class="stat-lbl">Total Trades</div><div class="stat-val" id="s-total">0</div><div class="stat-sub">All logged</div></div>
    <div class="stat-card"><div class="stat-lbl">Win Rate</div><div class="stat-val" id="s-wr">0%</div><div class="stat-sub" id="s-wl">0W / 0L</div></div>
    <div class="stat-card"><div class="stat-lbl">Net PnL%</div><div class="stat-val" id="s-pnl">+0%</div><div class="stat-sub">On capital</div></div>
    <div class="stat-card"><div class="stat-lbl">Avg Confidence</div><div class="stat-val" id="s-conf">0%</div><div class="stat-sub">Model signal</div></div>
    <div class="stat-card"><div class="stat-lbl">Best Trade</div><div class="stat-val" id="s-best">—</div><div class="stat-sub" id="s-best-p">—</div></div>
    <div class="stat-card"><div class="stat-lbl">Worst Trade</div><div class="stat-val" id="s-worst">—</div><div class="stat-sub" id="s-worst-p">—</div></div>
    <div class="stat-card"><div class="stat-lbl">Pending</div><div class="stat-val" id="s-pend">0</div><div class="stat-sub">Open trades</div></div>
  </div>

  <!-- ── MAIN GRID ── -->
  <div class="main-grid">

    <!-- LEFT COLUMN -->
    <div class="left-col">

      <!-- Equity Chart -->
      <div class="panel">
        <div class="panel-head">
          <span class="panel-icon">📊</span>
          <h2>Equity Curve — $100 Growth Tracker</h2>
          <div class="panel-head-right">
            <span id="eq-label" style="font-family:var(--font-mono);font-size:9px;color:var(--muted)">Starting: $100</span>
          </div>
        </div>
        <div class="chart-container">
          <canvas id="equityChart" height="155"></canvas>
        </div>
      </div>

      <!-- Pair Performance -->
      <div class="panel">
        <div class="panel-head">
          <span class="panel-icon">🌍</span>
          <h2>Pair Performance Breakdown</h2>
        </div>
        <div class="pair-perf-wrap" id="pair-perf">
          <div class="empty"><div class="empty-icon">🌐</div><div class="empty-txt">Log trades to see pair breakdown</div></div>
        </div>
      </div>

      <!-- Trade Journal -->
      <div class="panel">
        <div class="panel-head">
          <span class="panel-icon">📋</span>
          <h2>Trade Journal</h2>
          <div class="panel-head-right">
            <span id="tcount" style="font-family:var(--font-mono);font-size:9px;color:var(--muted)">0 trades</span>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Pair</th><th>Dir</th><th>Entry</th>
                <th>TP</th><th>SL</th><th>Leverage</th><th>Confidence</th>
                <th>Result</th><th>PnL%</th><th>Capital</th><th>Setup</th><th>Time</th>
                <th>Recover</th><th>Del</th>
              </tr>
            </thead>
            <tbody id="trade-tbody"></tbody>
          </table>
        </div>
      </div>

    </div><!-- left-col -->

    <!-- RIGHT COLUMN -->
    <div class="right-col">

      <!-- Log Trade -->
      <div class="panel">
        <div class="panel-head"><span class="panel-icon">➕</span><h2>Log Trade</h2></div>
        <div class="form-body">
          <div class="form-row">
            <div class="field">
              <label>Pair</label>
              <select id="f-pair" onchange="updateVerdict();calcRisk()">
                <option>AUD/JPY</option><option>AUD/USD</option><option>USD/JPY</option>
                <option>GBP/AUD</option><option>EUR/GBP</option><option>EUR/CHF</option>
                <option>USD/CAD</option><option>EUR/USD</option><option>GBP/USD</option>
              </select>
            </div>
            <div class="field">
              <label>Leverage</label>
              <input type="number" id="f-lev" value="250" min="1" oninput="updateVerdict();calcRisk()">
            </div>
          </div>
          <div class="dir-row">
            <button class="dir-btn buy"  onclick="setDir('BUY',this)">📈 BUY</button>
            <button class="dir-btn sell" onclick="setDir('SELL',this)">📉 SELL</button>
          </div>
          <div class="form-row">
            <div class="field"><label>Entry Price</label><input type="number" id="f-entry" placeholder="0.00000" step="0.00001" oninput="calcRisk()"></div>
            <div class="field"><label>Confidence %</label><input type="number" id="f-conf" placeholder="57" min="0" max="100" oninput="updateVerdict()"></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Take Profit</label><input type="number" id="f-tp" placeholder="0.00000" step="0.00001" oninput="calcRisk()"></div>
            <div class="field"><label>Stop Loss</label><input type="number" id="f-sl" placeholder="0.00000" step="0.00001" oninput="calcRisk()"></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Allocation % of Capital</label><input type="number" id="f-alloc" value="10" min="1" max="100" oninput="calcRisk()"></div>
            <div class="field">
              <label>Setup Type</label>
              <select id="f-setup">
                <option>YES | NEUTRAL_SETUP</option><option>YES | WITH_TREND</option>
                <option>YES | SWEEP_CONFIRMED</option><option>YES | SWEEP_BOUNCE — LOW LEV</option>
                <option>NO — MANUAL TRADE</option>
              </select>
            </div>
          </div>

          <!-- Risk Calc -->
          <div class="risk-calc">
            <div class="risk-calc-title">⚙ RISK CALCULATOR</div>
            <div class="risk-grid">
              <div>
                <div class="risk-item-val" id="r-alloc" style="color:var(--gold)">$10.00</div>
                <div class="risk-item-lbl">Allocated</div>
              </div>
              <div>
                <div class="risk-item-val" id="r-profit" style="color:var(--emerald)">$0.00</div>
                <div class="risk-item-lbl">If TP Hit</div>
              </div>
              <div>
                <div class="risk-item-val" id="r-loss" style="color:var(--ruby)">$0.00</div>
                <div class="risk-item-lbl">If SL Hit</div>
              </div>
            </div>
          </div>

          <!-- Result -->
          <div class="field">
            <label>Result</label>
            <div class="res-row">
              <button class="res-btn win"  onclick="setRes('WIN',this)">✅ WIN</button>
              <button class="res-btn loss" onclick="setRes('LOSS',this)">❌ LOSS</button>
              <button class="res-btn pend active" onclick="setRes('PENDING',this)">⏳ PENDING</button>
            </div>
          </div>

          <!-- Verdict -->
          <div class="verdict-box" id="verdict-box">
            <div class="verdict-title" id="verdict-title"></div>
            <div class="verdict-desc" id="verdict-desc"></div>
          </div>

          <button class="submit-btn" onclick="addTrade()">⚡ LOG THIS TRADE</button>
        </div>
      </div>

      <!-- Export Panel -->
      <div class="panel">
        <div class="panel-head"><span class="panel-icon">📤</span><h2>Export &amp; Analysis</h2></div>
        <div class="export-grid">
          <button class="exp-btn csv"   onclick="exportCSV()">📄 Export CSV<span>Trade Journal</span></button>
          <button class="exp-btn json"  onclick="exportJSON()">📦 Export JSON<span>Full Raw Data</span></button>
          <button class="exp-btn model" onclick="exportModelCSV()">🧠 Model CSV<span>Retrain Engine</span></button>
          <button class="exp-btn clear" onclick="clearAll()">🗑 Clear All<span>Reset Journal</span></button>
        </div>
      </div>

      <!-- Rules Panel -->
      <div class="panel">
        <div class="panel-head"><span class="panel-icon">🧠</span><h2>Survival Rules</h2></div>
        <div class="rules-list">
          <div class="rule-item go">
            <div class="rule-icon">✅</div>
            <div class="rule-text"><strong>TAKE THE TRADE</strong><span>SAFE=YES + Confidence ≥55% + NEUTRAL/WITH_TREND flow</span></div>
          </div>
          <div class="rule-item warn">
            <div class="rule-icon">⚠️</div>
            <div class="rule-text"><strong>SWEEP BOUNCE — 40% LEV</strong><span>BUY_SIDE_SWEEP when taking BUY. Reduce leverage to 40%.</span></div>
          </div>
          <div class="rule-item stop">
            <div class="rule-icon">🚫</div>
            <div class="rule-text"><strong>SKIP — NO SWEEP CONFIRM</strong><span>EARLY_EXHAUSTION + NONE sweep = no edge. Skip entirely.</span></div>
          </div>
          <div class="rule-item stop">
            <div class="rule-icon">💀</div>
            <div class="rule-text"><strong>NEVER FIGHT THE FLOW</strong><span>STRONG_DOWN+BUY or STRONG_UP+SELL = liquidation guaranteed.</span></div>
          </div>
          <div class="rule-item go">
            <div class="rule-icon">🎯</div>
            <div class="rule-text"><strong>RR=1.0 IS YOUR EDGE</strong><span>57% WR × 1:1 RR = +490% net on 100 trades. Stay disciplined.</span></div>
          </div>
          <div class="rule-item warn">
            <div class="rule-icon">💰</div>
            <div class="rule-text"><strong>$100 SURVIVAL RULE</strong><span>Never allocate more than 15% per trade. Survive first, grow second.</span></div>
          </div>
        </div>
      </div>

    </div><!-- right-col -->
  </div><!-- main-grid -->

</div><!-- app -->

<!-- ── RECOVERY MODAL ── -->
<div class="modal-overlay" id="rec-modal" onclick="closeModalOutside(event)">
  <div class="recovery-modal" id="rec-inner">
    <div class="rec-head">
      <div class="rec-title">💀 LOSS RECOVERY PLANNER</div>
      <button class="rec-close" onclick="closeRecovery()">✕ CLOSE</button>
    </div>
    <div class="rec-body">
      <div style="font-family:var(--font-mono);font-size:9px;color:var(--muted);margin-bottom:18px" id="rec-trade-lbl">—</div>
      <div class="loss-summary">
        <div class="ls-card danger"><div class="ls-val" id="rec-loss">-$0.00</div><div class="ls-lbl">LOSS AMOUNT</div></div>
        <div class="ls-card warn">  <div class="ls-val" id="rec-cap">$100.00</div><div class="ls-lbl">CAPITAL NOW</div></div>
        <div class="ls-card info">  <div class="ls-val" id="rec-dd">0.0%</div><div class="ls-lbl">DRAWDOWN</div></div>
      </div>
      <div class="rec-section-title">🎯 Choose Recovery Scenario</div>
      <div class="scenarios">
        <div class="sc-card conservative" onclick="pickScenario('conservative',this)">
          <div class="sc-name">CONSERVATIVE</div>
          <div class="sc-alloc" id="sc-a-c">5%</div>
          <div class="sc-sub">PER TRADE ALLOC</div>
          <div class="sc-trades" id="sc-t-c">—</div>
          <div class="sc-trades-lbl">TRADES TO RECOVER</div>
        </div>
        <div class="sc-card balanced" onclick="pickScenario('balanced',this)">
          <div class="sc-name">BALANCED</div>
          <div class="sc-alloc" id="sc-a-b">10%</div>
          <div class="sc-sub">PER TRADE ALLOC</div>
          <div class="sc-trades" id="sc-t-b">—</div>
          <div class="sc-trades-lbl">TRADES TO RECOVER</div>
        </div>
        <div class="sc-card aggressive" onclick="pickScenario('aggressive',this)">
          <div class="sc-name">AGGRESSIVE</div>
          <div class="sc-alloc" id="sc-a-a">15%</div>
          <div class="sc-sub">PER TRADE ALLOC</div>
          <div class="sc-trades" id="sc-t-a">—</div>
          <div class="sc-trades-lbl">TRADES TO RECOVER</div>
        </div>
      </div>
      <div class="rec-section-title">🛣️ Recovery Path</div>
      <div class="path-steps" id="rec-path">
        <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">Select scenario above →</span>
      </div>
      <div class="rec-actions">
        <button class="rec-btn apply"   onclick="applyRecovery()">⚡ APPLY TO FORM</button>
        <button class="rec-btn dismiss" onclick="closeRecovery()">↩ DISMISS</button>
      </div>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
/* ══════════════════════════════════════════
   STATE
══════════════════════════════════════════ */
let trades = [];
let startingCapital = 100;
let currentCap = 100;
let selectedDir = '';
let selectedRes = 'PENDING';
let pickedScenario = null;
let currentRecoveryTrade = null;
let equityChart = null;

const FLAGS = {
  'AUD/JPY':'🇦🇺🇯🇵','AUD/USD':'🇦🇺🇺🇸','USD/JPY':'🇺🇸🇯🇵',
  'GBP/AUD':'🇬🇧🇦🇺','EUR/GBP':'🇪🇺🇬🇧','EUR/CHF':'🇪🇺🇨🇭',
  'USD/CAD':'🇺🇸🇨🇦','EUR/USD':'🇪🇺🇺🇸','GBP/USD':'🇬🇧🇺🇸'
};

/* ══ CLOCK ══ */
function tick() {
  const n = new Date();
  document.getElementById('utc-clock').textContent =
    String(n.getUTCHours()).padStart(2,'0') + ':' +
    String(n.getUTCMinutes()).padStart(2,'0') + ':' +
    String(n.getUTCSeconds()).padStart(2,'0') + ' UTC';
}
setInterval(tick, 1000); tick();

/* ══ API ══ */
async function api(path, opts={}) {
  const res = await fetch('/api/' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  return res.json();
}

/* ══ LOAD ══ */
async function loadAll() {
  const data = await api('stats');
  trades = (await api('trades')).trades;
  startingCapital = data.starting_capital;
  currentCap = data.current_capital;
  renderAll(data);
}

/* ══ FORM ══ */
function setDir(d, el) {
  selectedDir = d;
  document.querySelectorAll('.dir-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  updateVerdict(); calcRisk();
}
function setRes(r, el) {
  selectedRes = r;
  document.querySelectorAll('.res-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
}

function calcRisk() {
  const alloc = (parseFloat(document.getElementById('f-alloc').value)||10)/100;
  const lev   = parseFloat(document.getElementById('f-lev').value)||250;
  const entry = parseFloat(document.getElementById('f-entry').value)||0;
  const tp    = parseFloat(document.getElementById('f-tp').value)||0;
  const sl    = parseFloat(document.getElementById('f-sl').value)||0;
  const amt   = currentCap * alloc;
  let profit=0, loss=0;
  if (entry && tp) profit = amt * (Math.abs(tp-entry)/entry) * lev;
  if (entry && sl) loss   = amt * (Math.abs(sl-entry)/entry) * lev;
  document.getElementById('r-alloc').textContent  = '$' + amt.toFixed(2);
  document.getElementById('r-profit').textContent = profit ? '+$'+profit.toFixed(2) : '$0.00';
  document.getElementById('r-loss').textContent   = loss   ? '-$'+loss.toFixed(2)   : '$0.00';
}

function updateVerdict() {
  const conf = parseFloat(document.getElementById('f-conf').value)||0;
  const lev  = parseFloat(document.getElementById('f-lev').value)||250;
  const vb = document.getElementById('verdict-box');
  const vt = document.getElementById('verdict-title');
  const vd = document.getElementById('verdict-desc');
  if (!selectedDir || !conf) { vb.className='verdict-box'; return; }
  if (conf >= 60 && lev <= 350) {
    vb.className = 'verdict-box go show';
    vt.textContent = '✅ TAKE THIS TRADE';
    vd.textContent = `Confidence ${conf}% ≥ 60%. Leverage ${lev}x within survival range. Execute with discipline.`;
  } else if (conf >= 50 && lev <= 450) {
    vb.className = 'verdict-box warn show';
    vt.textContent = '⚠️ PROCEED WITH CAUTION';
    vd.textContent = `Confidence ${conf}% is marginal. Consider reducing leverage to ${Math.round(lev*0.7)}x.`;
  } else {
    vb.className = 'verdict-box stop show';
    vt.textContent = '🚫 HIGH RISK — STAND DOWN';
    vd.textContent = `${conf<50?'Confidence '+conf+'% too low. ':''}${lev>450?'Leverage '+lev+'x — liquidation zone. ':''}Capital at severe risk.`;
  }
}

async function addTrade() {
  const pair  = document.getElementById('f-pair').value;
  const entry = parseFloat(document.getElementById('f-entry').value);
  const tp    = parseFloat(document.getElementById('f-tp').value)||null;
  const sl    = parseFloat(document.getElementById('f-sl').value)||null;
  const lev   = parseFloat(document.getElementById('f-lev').value)||250;
  const conf  = parseFloat(document.getElementById('f-conf').value)||0;
  const setup = document.getElementById('f-setup').value;
  const alloc = parseFloat(document.getElementById('f-alloc').value)||10;
  if (!entry || !selectedDir) { showToast('⚠️ Fill Entry and Direction', 'err'); return; }
  const data = await api('trades', {
    method: 'POST',
    body: JSON.stringify({ pair, entry, tp, sl, lev, conf, setup, alloc, dir: selectedDir, result: selectedRes })
  });
  if (data.ok) {
    showToast(`✅ ${FLAGS[pair]||''} ${pair} ${selectedDir} logged`, 'ok');
    ['f-entry','f-tp','f-sl','f-conf'].forEach(id => document.getElementById(id).value='');
    await loadAll();
    if (selectedRes === 'LOSS') setTimeout(() => openRecovery(data.trade), 500);
  }
}

async function deleteTrade(id) {
  await api(`trades/${id}`, { method: 'DELETE' });
  await loadAll();
  showToast('🗑 Trade removed');
}

async function updateResult(id, result) {
  const data = await api(`trades/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ result })
  });
  await loadAll();
  if (result === 'LOSS') {
    const trade = trades.find(t => t.id === id);
    if (trade) setTimeout(() => openRecovery(trade), 400);
  }
}

/* ══ RENDER ALL ══ */
function renderAll(stats) {
  renderCapital(stats);
  renderStats(stats);
  renderTable();
  renderEquityChart(stats.equity_curve);
  renderPairPerf(stats.pair_performance);
  calcRisk();
}

function renderCapital(s) {
  const cap = s.current_capital;
  const growth = ((cap - s.starting_capital) / s.starting_capital * 100);
  const gEl = document.getElementById('growth-val');

  animateNum(document.getElementById('cap-val'), '$' + cap.toFixed(2));
  gEl.textContent = (growth>=0?'+':'') + growth.toFixed(1) + '%';
  gEl.className = 'growth-val ' + (growth>=0?'pos':'neg');

  const closed = trades.filter(t=>t.result!=='PENDING');
  document.getElementById('cap-sub').textContent = 'Starting: $' + s.starting_capital.toFixed(2);
  document.getElementById('cap-trades').textContent = closed.length + ' completed trades';
  document.getElementById('eq-label').textContent = `Current: $${cap.toFixed(2)}`;

  const targets = [200,500,1000,5000,10000,50000];
  let next = targets.find(t => cap < t);
  document.querySelectorAll('.ms-pill').forEach((p, i) => {
    const t = targets[i];
    p.className = 'ms-pill' + (cap>=t?' done': t===next?' next':'');
  });
  if (next) {
    document.getElementById('next-target').textContent = '$' + next.toLocaleString();
    document.getElementById('next-need').textContent = 'Need $' + (next - cap).toFixed(2) + ' more';
  } else {
    document.getElementById('next-target').textContent = '🏆 ALL!';
    document.getElementById('next-need').textContent = 'Ferrari acquired 🏎️';
  }
}

function animateNum(el, val) {
  el.textContent = val;
  el.classList.remove('animate-num');
  void el.offsetWidth;
  el.classList.add('animate-num');
}

function renderStats(s) {
  document.getElementById('s-total').textContent = s.total;
  document.getElementById('s-wr').textContent = s.win_rate + '%';
  document.getElementById('s-wl').textContent = s.wins + 'W / ' + s.losses + 'L';
  document.getElementById('s-pnl').textContent = (s.net_pnl>=0?'+':'') + s.net_pnl.toFixed(1) + '%';
  document.getElementById('s-conf').textContent = s.avg_conf + '%';
  document.getElementById('s-best').textContent = s.best ? '+' + s.best.pnl + '%' : '—';
  document.getElementById('s-worst').textContent = s.worst ? s.worst.pnl + '%' : '—';
  document.getElementById('s-best-p').textContent = s.best ? (FLAGS[s.best.pair]||'') + ' ' + s.best.pair : '—';
  document.getElementById('s-worst-p').textContent = s.worst ? (FLAGS[s.worst.pair]||'') + ' ' + s.worst.pair : '—';
  document.getElementById('s-pend').textContent = s.pending;
  document.getElementById('tcount').textContent = s.total + ' trades';
}

function renderTable() {
  const tbody = document.getElementById('trade-tbody');
  if (!trades.length) {
    tbody.innerHTML = `<tr><td colspan="15"><div class="empty"><div class="empty-icon">🎯</div><div class="empty-txt">No trades yet. Log your first trade →</div></div></td></tr>`;
    return;
  }
  tbody.innerHTML = trades.map((t, i) => {
    const ts = new Date(t.time);
    const pnl = t.pnlPct !== null && t.pnlPct !== undefined
      ? `<span class="pnl-val ${t.pnlPct>=0?'pos':'neg'}">${t.pnlPct>=0?'+':''}${t.pnlPct}%</span>`
      : `<span class="pnl-val zero">OPEN</span>`;
    const capStr = t.capitalAfter ? `<span style="font-family:var(--font-mono);font-size:10px;color:var(--gold)">$${t.capitalAfter.toFixed(2)}</span>` : '—';
    const recBtn = t.result === 'LOSS'
      ? `<button style="background:var(--ruby-dim);border:1px solid rgba(224,48,96,0.4);border-radius:4px;padding:3px 8px;cursor:pointer;color:var(--ruby);font-size:9px;font-family:var(--font-mono)" onclick="openRecovery(trades[${i}])">🔴 RECOVER</button>`
      : '—';
    const rowClass = t.result === 'WIN' ? 'win-row' : t.result === 'LOSS' ? 'loss-row' : 'pend-row';
    return `<tr class="${rowClass}">
      <td style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">${trades.length-i}</td>
      <td><div class="pair-cell"><span class="pair-emoji">${FLAGS[t.pair]||'🌐'}</span><span class="pair-txt">${t.pair}</span></div></td>
      <td><span class="dir-badge ${t.dir}">${t.dir==='BUY'?'▲':'▼'} ${t.dir}</span></td>
      <td style="font-family:var(--font-mono);font-size:11px">${t.entry}</td>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--emerald)">${t.tp||'—'}</td>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--ruby)">${t.sl||'—'}</td>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--gold)">${t.lev}x</td>
      <td>
        <div class="conf-bar-wrap">
          <div class="conf-bar"><div class="conf-fill" style="width:${t.conf||0}%"></div></div>
          <span style="font-family:var(--font-mono);font-size:9px;color:var(--silver)">${t.conf||0}%</span>
        </div>
      </td>
      <td><select class="result-select ${t.result}" onchange="updateResult(${t.id},this.value)">
        <option value="WIN" ${t.result==='WIN'?'selected':''}>✅ WIN</option>
        <option value="LOSS" ${t.result==='LOSS'?'selected':''}>❌ LOSS</option>
        <option value="PENDING" ${t.result==='PENDING'?'selected':''}>⏳ PENDING</option>
      </select></td>
      <td>${pnl}</td>
      <td>${capStr}</td>
      <td style="font-size:9px;color:var(--muted);font-family:var(--font-mono);max-width:90px;overflow:hidden;text-overflow:ellipsis">${t.setup||'—'}</td>
      <td style="font-size:9px;color:var(--muted);font-family:var(--font-mono)">${ts.toLocaleDateString('en-GB',{month:'short',day:'numeric'})}<br>${ts.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}</td>
      <td>${recBtn}</td>
      <td><button class="del-btn" onclick="deleteTrade(${t.id})">✕</button></td>
    </tr>`;
  }).join('');
}

/* ══ EQUITY CHART ══ */
function renderEquityChart(pts) {
  const canvas = document.getElementById('equityChart');
  const ctx = canvas.getContext('2d');
  if (equityChart) { equityChart.destroy(); equityChart = null; }

  if (!pts || pts.length < 2) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(201,168,76,0.2)';
    ctx.font = "11px 'JetBrains Mono'";
    ctx.fillText('Log 2+ completed trades to see equity curve', 20, 80);
    return;
  }

  const isProfit = pts[pts.length-1] >= pts[0];
  const lineColor = isProfit ? '#00c896' : '#e03060';
  const labels = pts.map((_, i) => i === 0 ? 'Start' : `T${i}`);

  const gradient = ctx.createLinearGradient(0, 0, 0, 155);
  gradient.addColorStop(0, isProfit ? 'rgba(0,200,150,0.25)' : 'rgba(224,48,96,0.25)');
  gradient.addColorStop(1, 'rgba(0,0,0,0)');

  equityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: pts,
        borderColor: lineColor,
        borderWidth: 2.5,
        backgroundColor: gradient,
        pointBackgroundColor: lineColor,
        pointRadius: pts.map((_, i) => (i === 0 || i === pts.length-1) ? 5 : 0),
        pointHoverRadius: 6,
        tension: 0.35,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 700, easing: 'easeInOutQuart' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#161c2c',
          borderColor: 'rgba(201,168,76,0.3)',
          borderWidth: 1,
          titleColor: '#c9a84c',
          bodyColor: '#c8d4e8',
          titleFont: { family: 'JetBrains Mono', size: 10 },
          bodyFont: { family: 'JetBrains Mono', size: 11 },
          callbacks: {
            title: items => `Trade ${items[0].dataIndex}`,
            label: item => `Capital: $${parseFloat(item.raw).toFixed(2)}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
          ticks: { color: '#4a5570', font: { family: 'JetBrains Mono', size: 9 }, maxTicksLimit: 10 }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
          ticks: { color: '#4a5570', font: { family: 'JetBrains Mono', size: 9 }, callback: v => '$' + v.toFixed(0) },
          position: 'right'
        }
      }
    }
  });
}

/* ══ PAIR PERFORMANCE ══ */
function renderPairPerf(perf) {
  const el = document.getElementById('pair-perf');
  if (!perf || !Object.keys(perf).length) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">🌐</div><div class="empty-txt">Log trades to see breakdown</div></div>';
    return;
  }
  const sorted = Object.entries(perf).sort((a,b)=>b[1].pnl-a[1].pnl);
  const maxAbs = Math.max(...sorted.map(([,v])=>Math.abs(v.pnl)), 1);
  el.innerHTML = sorted.map(([pair, d]) => {
    const pct = Math.abs(d.pnl) / maxAbs * 100;
    const pos = d.pnl >= 0;
    const tot = d.wins + d.losses;
    const wr = tot ? Math.round(d.wins/tot*100) : 0;
    return `<div class="pair-row">
      <div class="pair-flag">${FLAGS[pair]||'🌐'}</div>
      <div class="pair-name">${pair}</div>
      <div class="pair-wr">${wr}% WR</div>
      <div class="pair-bar"><div class="pair-fill ${pos?'pos':'neg'}" style="width:${pct}%"></div></div>
      <div class="pair-pnl" style="color:${pos?'var(--emerald)':'var(--ruby)'}">${pos?'+':''}${d.pnl.toFixed(1)}%</div>
    </div>`;
  }).join('');
}

/* ══ RECOVERY ENGINE ══ */
function calcRecoveryTrades(lostAmt, cap, allocPct, wr=0.57) {
  if (lostAmt <= 0) return 0;
  const target = cap + lostAmt;
  const alloc = allocPct / 100;
  const ev = alloc * (2 * wr - 1);
  if (ev <= 0) return 999;
  let c = cap, n = 0;
  while (c < target && n < 200) { c = c * (1 + ev); n++; }
  return n;
}

function openRecovery(trade) {
  if (!trade) return;
  currentRecoveryTrade = trade;
  pickedScenario = null;
  const lostAmt = trade.pnlAmt !== null ? Math.abs(trade.pnlAmt) : 0;
  const capNow = trade.capitalAfter || currentCap;
  const dd = lostAmt > 0 ? lostAmt / (capNow + lostAmt) * 100 : 0;
  document.getElementById('rec-trade-lbl').textContent = `${FLAGS[trade.pair]||''} ${trade.pair} ${trade.dir} — ${trade.setup||''}`;
  document.getElementById('rec-loss').textContent = '-$' + lostAmt.toFixed(2);
  document.getElementById('rec-cap').textContent  = '$' + capNow.toFixed(2);
  document.getElementById('rec-dd').textContent   = dd.toFixed(1) + '%';
  [['c',5,0.55],['b',10,0.57],['a',15,0.60]].forEach(([id,alloc,wr])=>{
    const n = calcRecoveryTrades(lostAmt, capNow, alloc, wr);
    document.getElementById(`sc-t-${id}`).textContent = n>=200?'∞':String(n);
  });
  document.querySelectorAll('.sc-card').forEach(c=>c.classList.remove('picked'));
  document.getElementById('rec-path').innerHTML = '<span style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">Select scenario above →</span>';
  document.getElementById('rec-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function pickScenario(type, el) {
  pickedScenario = type;
  document.querySelectorAll('.sc-card').forEach(c=>c.classList.remove('picked'));
  el.classList.add('picked');
  const trade = currentRecoveryTrade; if (!trade) return;
  const lostAmt = Math.abs(trade.pnlAmt||0);
  const capNow  = trade.capitalAfter || currentCap;
  const cfgs = { conservative:{alloc:5,wr:0.55}, balanced:{alloc:10,wr:0.57}, aggressive:{alloc:15,wr:0.60} };
  const cfg = cfgs[type];
  // Build path
  const target = capNow + lostAmt;
  const ev = (cfg.alloc/100) * (2*cfg.wr-1);
  let c = capNow, steps = [], n = 0;
  while (c < target && n < 30) {
    c = c*(1+ev); n++;
    steps.push({n, cap:c.toFixed(2), done:c>=target, milestone:n%5===0});
    if(c>=target) break;
  }
  const pathEl = document.getElementById('rec-path');
  if (!steps.length) { pathEl.innerHTML='<span style="font-family:var(--font-mono);font-size:10px;color:var(--muted)">Already recovered!</span>'; return; }
  pathEl.innerHTML = steps.map(s=>`<div class="path-step ${s.done?'recovered':s.milestone?'milestone':''}" title="Trade ${s.n}: $${s.cap}">${s.done?'✓':s.n}</div>`).join('');
  showToast(`📋 ${type.toUpperCase()} scenario selected`, 'ok');
}

function applyRecovery() {
  const cfgs = { conservative:{alloc:5,lev:150}, balanced:{alloc:10,lev:250}, aggressive:{alloc:15,lev:200} };
  const cfg = cfgs[pickedScenario||'balanced'];
  document.getElementById('f-alloc').value = cfg.alloc;
  document.getElementById('f-lev').value   = cfg.lev;
  calcRisk(); closeRecovery();
  showToast(`⚡ ${(pickedScenario||'balanced').toUpperCase()} settings applied`, 'ok');
}

function closeRecovery() {
  document.getElementById('rec-modal').classList.remove('open');
  document.body.style.overflow = '';
}
function closeModalOutside(e) {
  if (e.target === document.getElementById('rec-modal')) closeRecovery();
}

/* ══ EXPORT ══ */
async function exportCSV() {
  if (!trades.length) { showToast('No trades to export', 'err'); return; }
  const hdrs = ['#','Pair','Dir','Entry','TP','SL','Leverage','Confidence','Alloc%','Result','PnL%','PnL_Amt','Capital_After','Setup','Time'];
  const rows = trades.map((t,i)=>[trades.length-i,t.pair,t.dir,t.entry,t.tp||'',t.sl||'',t.lev,t.conf,t.alloc,t.result,t.pnlPct??'',t.pnlAmt??'',t.capitalAfter??'',`"${t.setup}"`,t.time]);
  download('monster_fx_journal.csv','text/csv',[hdrs,...rows].map(r=>r.join(',')).join('\n'));
  showToast('📄 CSV exported!', 'ok');
}
async function exportJSON() {
  if (!trades.length) { showToast('No trades to export', 'err'); return; }
  download('monster_fx.json','application/json',JSON.stringify({exported:new Date().toISOString(),startingCapital,currentCapital:currentCap,trades},null,2));
  showToast('📦 JSON exported!', 'ok');
}
async function exportModelCSV() {
  const closed = trades.filter(t=>t.result!=='PENDING');
  if (!closed.length) { showToast('No completed trades', 'err'); return; }
  const hdrs = ['pair','direction','entry','confidence','leverage','pnl_pct','result','setup','win_binary'];
  const rows = closed.map(t=>[t.pair,t.dir,t.entry,t.conf,t.lev,t.pnlPct??'',t.result,`"${t.setup}"`,t.result==='WIN'?1:0]);
  download('monster_fx_model.csv','text/csv',[hdrs,...rows].map(r=>r.join(',')).join('\n'));
  showToast('🧠 Model CSV exported!', 'ok');
}
async function clearAll() {
  if (!confirm('Clear ALL trade data? Cannot be undone.')) return;
  await api('trades', { method: 'DELETE' });
  await loadAll();
  showToast('🗑 All data cleared');
}
function download(filename, mime, content) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content],{type:mime}));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
}

/* ══ TOAST ══ */
function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast '+(type||'')+' show';
  setTimeout(() => t.classList.remove('show'), 3000);
}

/* ══ INIT ══ */
loadAll();
setInterval(loadAll, 30000); // auto-refresh every 30s
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║    MONSTER FX ENGINE v5.0 — COMMAND CENTER               ║
║                                                          ║
║    Open in browser: http://localhost:5000                ║
║    Press Ctrl+C to stop                                  ║
╚══════════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=5000, debug=False)
