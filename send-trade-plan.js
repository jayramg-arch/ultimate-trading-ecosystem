/**
 * send-trade-plan.js  —  Commander Risk Allocator → Telegram
 *
 * Usage (from any terminal):
 *   node "C:\Users\jayra\Documents\GeminiVSCode\send-trade-plan.js"
 *   node send-trade-plan.js --debug     ← prints raw input keys for troubleshooting
 *
 * Requirements:
 *   - TradingView Desktop open with Commander Risk Allocator on the chart
 *   - All 3 prices clicked (Entry, Stop, Target)
 *   - TradingView running with CDP on port 9222
 *     (it is when the TradingView MCP server is active)
 *
 * No npm install needed — uses only Node.js built-ins.
 */

import http  from 'http';
import https from 'https';

// ── Config ───────────────────────────────────────────────────────────────────
const TELEGRAM_TOKEN   = '8663579162:AAGuSv5mftQolQbP4cNH5SUbk9Ph5qHXSDo';
const TELEGRAM_CHAT_ID = '5906061665';
const CDP_PORT         = 9222;
const STUDY_FILTER     = 'Commander Risk Allocator';
const DEBUG            = process.argv.includes('--debug');

// ── Minimal CDP client (no external deps) ────────────────────────────────────
function httpGet(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch(e) { reject(e); } });
    }).on('error', reject);
  });
}

function cdpSession(wsUrl) {
  // Use built-in WebSocket (Node 22+) or fall back with a helpful error
  if (typeof WebSocket === 'undefined') {
    throw new Error(
      'Built-in WebSocket not available.\n' +
      'Run with: node --experimental-websocket send-trade-plan.js\n' +
      'Or upgrade to Node.js 22+.'
    );
  }

  let msgId = 1;
  const pending = new Map();
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    }
  };

  const ready = new Promise((resolve, reject) => {
    ws.onopen  = resolve;
    ws.onerror = (e) => reject(new Error('CDP WebSocket error: ' + (e.message || 'connection refused')));
  });

  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = msgId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: false });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'CDP eval error');
    return r.result.value;
  };

  const close = () => ws.close();

  return { ready, evaluate, close };
}

// ── Read indicator from TradingView ──────────────────────────────────────────
const READ_JS = `
  (function() {
    try {
      var chart = window.TradingViewApi._activeChartWidgetWV.value();
      var studies = chart.getAllStudies();
      var found = null;
      for (var i = 0; i < studies.length; i++) {
        if (studies[i].name && studies[i].name.indexOf('Commander Risk Allocator') !== -1) {
          found = studies[i]; break;
        }
      }
      if (!found) return { error: 'Commander Risk Allocator not found. Add it to the chart first.' };
      var study = chart.getStudyById(found.id);
      if (!study) return { error: 'Could not load study by id: ' + found.id };
      var rawInputs = study.getInputValues();
      var inp = {}, keyList = [];
      rawInputs.forEach(function(x, i) {
        inp[x.id] = x.value;
        keyList.push({ pos: i, id: x.id, value: x.value });
      });
      return { ticker: chart.symbol(), tf: chart.resolution(), inputs: inp, keyList: keyList };
    } catch(e) { return { error: e.message }; }
  })()
`;

// ── Compute trade plan ───────────────────────────────────────────────────────
// Pine input order for Commander Risk Allocator v1.0:
//  0: asset_type   1: capital    2: etf_risk%   3: stock_risk%  4: max_alloc
//  5: multiplier   6: entry      7: stop        8: target        9: tick_size
// 10: use_kelly   11: use_vol   12: use_regime  13: fire_alert  14: chat_id
// 15: show_table  16: tbl_pos   17: show_lines  18: line_ext
function computePlan(ticker, tf, inputs, keyList) {
  const byPos = (p)    => keyList[p]?.value;
  const byId  = (id)   => inputs[id];
  const get   = (id, p) => { const v = byId(id); return v !== undefined ? v : byPos(p); };

  const capital    = get('in_1', 1)  || 100000;
  const stockRisk  = get('in_3', 3)  || 0.75;
  const maxAlloc   = get('in_4', 4)  || 25000;
  const multiplier = get('in_5', 5)  || 1;
  const entryRaw   = get('in_6', 6)  || 0;
  const stopRaw    = get('in_7', 7)  || 0;
  const targetRaw  = get('in_8', 8)  || 0;
  const tickSize   = get('in_9', 9)  || 0.10;

  if (!entryRaw || !stopRaw || !targetRaw) {
    const hint = DEBUG ? '' : ' Run with --debug to see all input keys.';
    throw new Error(`Entry/Stop/Target is 0. Click all 3 prices on the chart first.${hint}`);
  }

  const rnd    = (p) => tickSize > 0 ? Math.round(p / tickSize) * tickSize : p;
  const entry  = rnd(entryRaw);
  const stop   = rnd(stopRaw);
  const target = rnd(targetRaw);
  const dist   = Math.abs(entry - stop);

  const riskAmt    = capital * (stockRisk / 100);
  const qtyByRisk  = dist > 0 ? Math.floor((riskAmt / dist) / multiplier) : 0;
  const qtyByCap   = entry > 0 ? Math.floor((maxAlloc / entry) / multiplier) : 0;
  const qty        = Math.min(qtyByRisk, qtyByCap);
  const invested   = qty * entry * multiplier;
  const riskActual = qty * dist * multiplier;
  const t1R        = dist > 0 ? (target - entry) / dist : 0;
  const t2Mult     = 3.5;
  const t2         = entry + dist * t2Mult;

  return { ticker, tf, entry, stop, target, qty, invested, riskActual, stockRisk, t1R, t2, t2Mult };
}

// ── Format message ───────────────────────────────────────────────────────────
function formatMessage(p) {
  const f = (n) => n.toFixed(2);
  const fK = (n) => n >= 1000 ? `${(n / 1000).toFixed(2)}K` : n.toFixed(2);
  const now = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false });
  return [
    `📊 ${p.ticker} | ${p.tf}m`,
    `─────────────────`,
    `Entry:         ${f(p.entry)}`,
    `SL:            ${f(p.stop)}`,
    `T1 (${f(p.t1R)}R): ${f(p.target)}  → exit 50%`,
    `T2 (${p.t2Mult}R):   ${f(p.t2)}  → exit 25%`,
    `─────────────────`,
    `Qty:      ${p.qty} share${p.qty !== 1 ? 's' : ''}`,
    `Invested: ${fK(p.invested)}  |  Risk: ${fK(p.riskActual)} (${p.stockRisk}%)`,
    `─────────────────`,
    `${now} IST`,
  ].join('\n');
}

// ── Send to Telegram ─────────────────────────────────────────────────────────
function sendTelegram(text) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text });
    const req = https.request({
      hostname: 'api.telegram.org',
      path: `/bot${TELEGRAM_TOKEN}/sendMessage`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(JSON.parse(d)));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// ── Main ─────────────────────────────────────────────────────────────────────
(async () => {
  let session;
  try {
    // 1. Find TradingView CDP target
    process.stdout.write('Connecting to TradingView... ');
    let targets;
    try {
      targets = await httpGet(`http://localhost:${CDP_PORT}/json/list`);
    } catch {
      throw new Error(
        `Cannot reach TradingView on port ${CDP_PORT}.\n` +
        `Make sure the TradingView MCP server is running (it enables CDP).\n` +
        `Start it with: cd C:\\Users\\jayra\\tradingview-mcp-jackson && npm start`
      );
    }

    const target =
      targets.find(t => t.type === 'page' && /tradingview\.com\/chart/i.test(t.url)) ||
      targets.find(t => t.type === 'page' && /tradingview/i.test(t.url));
    if (!target) throw new Error('No TradingView chart tab found. Open a chart in TradingView.');

    // 2. Open CDP WebSocket session
    session = cdpSession(target.webSocketDebuggerUrl);
    await session.ready;
    await session.evaluate('1'); // warm-up
    console.log('OK');

    // 3. Read indicator
    process.stdout.write('Reading indicator... ');
    const data = await session.evaluate(READ_JS);
    if (data?.error) throw new Error(data.error);
    console.log(`OK  (${data.ticker} | ${data.tf}m)`);

    if (DEBUG) {
      console.log('\n── Raw inputs ──────────────────────────');
      data.keyList.forEach(k => console.log(`  [${k.pos}] ${k.id.padEnd(8)} = ${JSON.stringify(k.value)}`));
      console.log('────────────────────────────────────────\n');
    }

    // 4. Compute and format
    const plan = computePlan(data.ticker, data.tf, data.inputs, data.keyList);
    const msg  = formatMessage(plan);
    console.log('\n' + msg + '\n');

    // 5. Send
    process.stdout.write('Sending to Telegram... ');
    const result = await sendTelegram(msg);
    if (result.ok) {
      console.log('✅ Delivered.');
    } else {
      throw new Error(`Telegram rejected: ${result.description}`);
    }

  } catch (err) {
    console.error(`\n❌ ${err.message}`);
    process.exit(1);
  } finally {
    session?.close();
  }
})();
