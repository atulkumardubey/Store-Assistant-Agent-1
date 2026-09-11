/* ══════════════════════════════════════════════
   Store Assistant Agent — Frontend
   ══════════════════════════════════════════════ */

// ── Particle System ─────────────────────────────
const canvas = document.getElementById('particles');
const ctx = canvas.getContext('2d');

let particles = [];
const PARTICLE_COUNT = 70;

function resizeCanvas() {
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
}

function randomBetween(a, b) { return a + Math.random() * (b - a); }

function createParticle() {
  return {
    x:  randomBetween(0, canvas.width),
    y:  randomBetween(0, canvas.height),
    vx: randomBetween(-0.3, 0.3),
    vy: randomBetween(-0.3, 0.3),
    r:  randomBetween(1, 2.5),
    alpha: randomBetween(0.1, 0.45),
    hue: randomBetween(260, 300),
  };
}

function initParticles() {
  particles = Array.from({ length: PARTICLE_COUNT }, createParticle);
}

function drawParticles() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let i = 0; i < particles.length; i++) {
    const p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    if (p.x < 0) p.x = canvas.width;
    if (p.x > canvas.width) p.x = 0;
    if (p.y < 0) p.y = canvas.height;
    if (p.y > canvas.height) p.y = 0;

    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${p.hue}, 85%, 65%, ${p.alpha})`;
    ctx.fill();

    // Connect nearby particles
    for (let j = i + 1; j < particles.length; j++) {
      const q = particles[j];
      const dx = p.x - q.x;
      const dy = p.y - q.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 100) {
        const opacity = (1 - dist / 100) * 0.08;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.strokeStyle = `hsla(${p.hue}, 70%, 60%, ${opacity})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }
    }
  }
  requestAnimationFrame(drawParticles);
}

resizeCanvas();
initParticles();
drawParticles();
window.addEventListener('resize', () => { resizeCanvas(); initParticles(); });


// ── DOM refs ────────────────────────────────────
const queryInput  = document.getElementById('query-input');
const sendBtn     = document.getElementById('send-btn');
const clearBtn    = document.getElementById('clear-btn');
const traceLog    = document.getElementById('trace-log');
const traceEmpty  = document.getElementById('trace-empty');
const resultCards = document.getElementById('result-cards');
const resultsEmpty= document.getElementById('results-empty');
const statusLabel = document.getElementById('status-label');
const headerBadge = document.querySelector('.header-badge');

// Result card elements
const cardStock    = document.getElementById('card-stock');
const stockIcon    = document.getElementById('stock-icon');
const stockBadge   = document.getElementById('stock-badge');
const stockMain    = document.getElementById('stock-main');
const stockDetail  = document.getElementById('stock-detail');

const cardPrice    = document.getElementById('card-price');
const priceBadge   = document.getElementById('price-badge');
const priceMain    = document.getElementById('price-main');
const priceDetail  = document.getElementById('price-detail');

const cardDelivery = document.getElementById('card-delivery');
const deliveryBadge= document.getElementById('delivery-badge');
const deliveryMain = document.getElementById('delivery-main');
const deliveryDetail = document.getElementById('delivery-detail');

const cardAnswer   = document.getElementById('card-answer');
const answerText   = document.getElementById('answer-text');


// ── State ───────────────────────────────────────
let ws = null;
let busy = false;


// ── WebSocket ───────────────────────────────────
function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws/query`);

  ws.onclose = () => {
    setStatus('Reconnecting…', 'busy');
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => ws.close();

  ws.onmessage = (ev) => {
    try { handleEvent(JSON.parse(ev.data)); }
    catch (e) { console.error('Parse error', e); }
  };

  ws.onopen = () => setStatus('Ready', '');
}

connectWS();


// ── Event handler ───────────────────────────────
function handleEvent(ev) {
  switch (ev.type) {
    case 'start':
      resetResults();
      showTraceItem('status', '🚀', 'Query received', ev.query);
      setStatus('Thinking…', 'busy');
      break;

    case 'status':
      updateOrAddStatus(ev.message);
      break;

    case 'thinking':
      addTraceItem('thinking', '🧠', 'Agent Reasoning', ev.text);
      break;

    case 'tool_call':
      addTraceItem(
        'tool-call',
        toolIcon(ev.tool),
        `Calling tool: ${ev.tool}`,
        `Input: ${JSON.stringify(ev.input, null, 2)}`
      );
      break;

    case 'tool_result':
      addTraceItem(
        ev.success === false ? 'tool-result fail' : 'tool-result ok',
        ev.success === false ? '❌' : '✅',
        `Result: ${ev.tool}`,
        ev.result.message || JSON.stringify(ev.result, null, 2)
      );
      updateResultCard(ev.tool, ev.result);
      break;

    case 'answer':
      addTraceItem('answer', '✨', 'Final Answer', ev.text);
      showAnswerCard(ev.text);
      break;

    case 'error':
      addTraceItem('error-msg', '⚠️', 'Error', ev.message);
      setStatus('Error', 'error-state');
      setBusy(false);
      break;

    case 'done':
      setStatus('Done', '');
      setBusy(false);
      break;
  }
}

function toolIcon(name) {
  const map = { check_stock: '📦', price_order: '💰', delivery_eta: '🚚' };
  return map[name] || '🔧';
}


// ── Trace helpers ───────────────────────────────
let statusItem = null;

function resetTrace() {
  traceLog.querySelectorAll('.trace-item').forEach(el => el.remove());
  statusItem = null;
  traceEmpty.style.display = '';
}

function showTraceItem(type, icon, label, text) {
  traceEmpty.style.display = 'none';
  const el = makeTraceEl(type, icon, label, text);
  traceLog.appendChild(el);
  scrollTrace();
  return el;
}

function addTraceItem(type, icon, label, text) {
  return showTraceItem(type, icon, label, text);
}

function updateOrAddStatus(msg) {
  if (statusItem) {
    statusItem.querySelector('.trace-text').textContent = msg;
    return;
  }
  statusItem = showTraceItem('status', '⚙️', 'Status', msg);
  // Replace text with animated dots version
  const textEl = statusItem.querySelector('.trace-text');
  textEl.innerHTML = `${msg} <span class="loading-dots"><span></span><span></span><span></span></span>`;
}

function makeTraceEl(type, icon, label, text) {
  const el = document.createElement('div');
  el.className = `trace-item ${type}`;

  const iconEl = document.createElement('span');
  iconEl.className = 'trace-icon';
  iconEl.textContent = icon;

  const body = document.createElement('div');
  body.className = 'trace-body';

  const lbl = document.createElement('div');
  lbl.className = 'trace-label';
  lbl.textContent = label;

  const txt = document.createElement('div');
  txt.className = 'trace-text';

  if (type === 'tool-call' || type === 'tool-result ok' || type === 'tool-result fail') {
    const code = document.createElement('div');
    code.className = 'trace-code';
    code.textContent = text;
    body.appendChild(lbl);
    body.appendChild(code);
  } else {
    txt.textContent = text;
    body.appendChild(lbl);
    body.appendChild(txt);
  }

  el.appendChild(iconEl);
  el.appendChild(body);
  return el;
}

function scrollTrace() {
  traceLog.scrollTop = traceLog.scrollHeight;
}


// ── Result cards ────────────────────────────────
function resetResults() {
  cardStock.style.display    = 'none';
  cardPrice.style.display    = 'none';
  cardDelivery.style.display = 'none';
  cardAnswer.style.display   = 'none';
  resultCards.style.display  = 'none';
  resultsEmpty.style.display = '';
}

function showResultCards() {
  resultsEmpty.style.display = 'none';
  resultCards.style.display  = 'flex';
}

function updateResultCard(tool, result) {
  showResultCards();
  if (tool === 'check_stock') populateStockCard(result);
  if (tool === 'price_order') populatePriceCard(result);
  if (tool === 'delivery_eta') populateDeliveryCard(result);
}

function populateStockCard(r) {
  cardStock.style.display = '';
  animateCard(cardStock);

  if (r.available) {
    stockIcon.textContent  = '✅';
    stockBadge.textContent = 'In Stock';
    stockBadge.className   = 'card-badge success';
    stockMain.textContent  = `${r.stock} units`;
    stockDetail.innerHTML  = `${r.product_name || ''} · Size ${r.size || ''}` +
      (r.unit_price ? ` · ₹${r.unit_price.toLocaleString('en-IN')} each` : '');
  } else {
    stockIcon.textContent  = '❌';
    stockBadge.textContent = 'Out of Stock';
    stockBadge.className   = 'card-badge error';
    stockMain.textContent  = 'Unavailable';
    stockDetail.textContent = r.message || '';
  }
}

function populatePriceCard(r) {
  cardPrice.style.display = '';
  animateCard(cardPrice);

  if (r.success) {
    priceMain.textContent = `₹${r.total_price.toLocaleString('en-IN')}`;
    const parts = [];
    if (r.discount_percent) parts.push(`${r.discount_percent}% off · saved ₹${r.discount_amount.toLocaleString('en-IN')}`);
    parts.push(`${r.quantity} × ₹${r.unit_price.toLocaleString('en-IN')}`);
    priceDetail.textContent = parts.join(' · ');
    priceBadge.textContent  = r.discount_percent ? `${r.discount_percent}% off` : 'No discount';
    priceBadge.className    = `card-badge ${r.discount_percent ? 'success' : 'info'}`;
  } else {
    priceMain.textContent  = 'Error';
    priceDetail.textContent = r.message || '';
    priceBadge.textContent  = 'Failed';
    priceBadge.className    = 'card-badge error';
  }
}

function populateDeliveryCard(r) {
  cardDelivery.style.display = '';
  animateCard(cardDelivery);

  if (r.success) {
    const std = r.standard_delivery;
    deliveryMain.textContent   = std.date;
    deliveryBadge.textContent  = r.free_standard_shipping ? 'FREE Shipping' : `₹${std.cost}`;
    deliveryBadge.className    = `card-badge ${r.free_standard_shipping ? 'success' : 'info'}`;
    const exp = r.express_delivery;
    deliveryDetail.innerHTML =
      `<strong>${r.city}, ${r.state}</strong> via ${std.carrier}` +
      `<br>Express: ${exp.date} · ₹${exp.cost}`;
  } else {
    deliveryMain.textContent   = 'Error';
    deliveryDetail.textContent = r.message || '';
    deliveryBadge.textContent  = 'Failed';
    deliveryBadge.className    = 'card-badge error';
  }
}

function showAnswerCard(text) {
  showResultCards();
  cardAnswer.style.display = '';
  animateCard(cardAnswer);
  answerText.textContent = text;
}

function animateCard(el) {
  el.style.animation = 'none';
  el.offsetHeight; // reflow
  el.style.animation = '';
}


// ── Send / clear ────────────────────────────────
function sendQuery() {
  const q = queryInput.value.trim();
  if (!q || busy) return;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    alert('Not connected. Please wait…');
    return;
  }

  resetTrace();
  setBusy(true);
  ws.send(JSON.stringify({ query: q }));
}

function clearAll() {
  resetTrace();
  resetResults();
  traceEmpty.style.display   = '';
  resultsEmpty.style.display = '';
  queryInput.value = '';
  setStatus('Ready', '');
}

sendBtn.addEventListener('click', sendQuery);

queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(); }
});

clearBtn.addEventListener('click', clearAll);

document.querySelectorAll('.example-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    queryInput.value = chip.dataset.q;
    queryInput.focus();
  });
});


// ── UI state ────────────────────────────────────
function setBusy(state) {
  busy = state;
  sendBtn.disabled = state;
  queryInput.disabled = state;
  if (!state) statusItem = null; // allow new status item next query
}

function setStatus(text, cls) {
  statusLabel.textContent = text;
  headerBadge.className = 'header-badge' + (cls ? ` ${cls}` : '');
}
