/* ── Particle System ─────────────────────────────────────────────────────── */
(function initParticles() {
  const canvas = document.getElementById('particles');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function Particle() {
    this.x    = Math.random() * W;
    this.y    = Math.random() * H;
    this.vx   = (Math.random() - .5) * .3;
    this.vy   = (Math.random() - .5) * .3;
    this.r    = Math.random() * 1.8 + .4;
    this.life = Math.random();
    this.dLife = .003 + Math.random() * .003;
    this.col  = Math.random() < .6 ? '124,92,255' : Math.random() < .5 ? '96,165,250' : '74,222,128';
  }

  Particle.prototype.update = function () {
    this.x    += this.vx;
    this.y    += this.vy;
    this.life += this.dLife;
    if (this.life > 1) this.life = 0;
    if (this.x < 0 || this.x > W) this.vx *= -1;
    if (this.y < 0 || this.y > H) this.vy *= -1;
  };

  Particle.prototype.draw = function () {
    const alpha = Math.sin(this.life * Math.PI) * .4;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${this.col},${alpha})`;
    ctx.fill();
  };

  function initParticlePool(n) {
    particles = [];
    for (let i = 0; i < n; i++) particles.push(new Particle());
  }

  function frame() {
    ctx.clearRect(0, 0, W, H);
    // Connection lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 100) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(124,92,255,${(1 - d / 100) * .06})`;
          ctx.lineWidth = .5;
          ctx.stroke();
        }
      }
    }
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(frame);
  }

  resize();
  initParticlePool(60);
  frame();
  window.addEventListener('resize', () => { resize(); initParticlePool(60); });
})();


/* ── State ───────────────────────────────────────────────────────────────── */
let ws       = null;
let running  = false;


/* ── DOM Helpers ─────────────────────────────────────────────────────────── */
const $  = id  => document.getElementById(id);
const el = sel => document.querySelector(sel);


/* ── Status Badge ────────────────────────────────────────────────────────── */
function setStatus(state, label) {
  const badge = $('header-badge');
  badge.className = 'header-badge ' + (state || '');
  $('status-label').textContent = label || 'Ready';
}


/* ── Trace Panel ─────────────────────────────────────────────────────────── */
function clearTrace() {
  const log = $('trace-log');
  log.innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'trace-empty'; empty.id = 'trace-empty';
  empty.innerHTML = '<div class="empty-icon">🤖</div><p>Agent standing by.<br/>Send a query to watch it reason and act.</p>';
  log.appendChild(empty);
  resetResultCards();
}

function hideTraceEmpty() {
  const e = $('trace-empty');
  if (e) e.style.display = 'none';
}

function addTrace(type, label, text, extra) {
  hideTraceEmpty();
  const log = $('trace-log');
  const row = document.createElement('div');
  row.className = 'trace-event ' + type + (extra && extra.fail ? ' fail' : '');

  let content = `<div class="trace-label">${label}</div><div class="trace-text">${escHtml(text)}</div>`;
  if (extra && extra.args) {
    content += `<div class="trace-args">${escHtml(JSON.stringify(extra.args, null, 2))}</div>`;
  }

  row.innerHTML = `<div class="trace-dot"></div><div class="trace-content">${content}</div>`;
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}


/* ── Result Cards ────────────────────────────────────────────────────────── */
function resetResultCards() {
  $('results-empty').style.display = '';
  $('result-cards').style.display  = 'none';
  ['card-stock','card-price','card-delivery','card-answer'].forEach(id => {
    $(id).style.display = 'none';
  });
}

function showResultCards() {
  $('results-empty').style.display = 'none';
  $('result-cards').style.display  = 'flex';
}

function populateStock(data) {
  showResultCards();
  const card = $('card-stock');
  card.style.display = '';

  const avail  = data.available;
  const icon   = $('stock-icon');
  const badge  = $('stock-badge');
  const main   = $('stock-main');
  const detail = $('stock-detail');
  const alts   = $('stock-alts');

  icon.textContent  = avail ? '✅' : '❌';
  badge.textContent = avail ? 'Available' : 'Out of Stock';
  badge.className   = 'card-badge' + (avail ? ' success' : '');
  main.textContent  = data.message || '—';

  if (avail && data.product_id) {
    detail.textContent = `${data.product_id}  ·  ₹${(data.unit_price||0).toLocaleString('en-IN')} each  ·  ${data.stock} units`;
  } else {
    detail.textContent = '';
  }

  const alternatives = data.alternatives || [];
  if (!avail && alternatives.length) {
    alts.style.display = '';
    alts.innerHTML = `<div class="card-alts-title">Alternatives available:</div>` +
      alternatives.map(a =>
        `<div class="alt-item">
          <span>📦</span>
          <span>${escHtml(a.name)} · ${escHtml(a.color)} · Size ${escHtml(a.size)} · ${a.stock} in stock · ₹${(a.unit_price||0).toLocaleString('en-IN')}</span>
        </div>`
      ).join('');
  } else {
    alts.style.display = 'none';
  }
}

function populatePrice(data) {
  showResultCards();
  const card = $('card-price');
  card.style.display = '';
  $('price-badge').textContent = data.discount_percent ? `${data.discount_percent}% off` : 'No discount';
  $('price-main').textContent  = data.total_price
    ? `₹${data.total_price.toLocaleString('en-IN')}`
    : (data.message || '—');
  $('price-detail').textContent = data.discount_percent
    ? `Saved ₹${(data.discount_amount||0).toLocaleString('en-IN')} · ${(data.discount_breakdown||[]).join(', ')}`
    : `₹${(data.unit_price||0).toLocaleString('en-IN')} × ${data.quantity||1}`;
}

function populateDelivery(data) {
  showResultCards();
  const card = $('card-delivery');
  card.style.display = '';

  if (!data.success) {
    $('delivery-badge').textContent = 'Error';
    $('delivery-badge').className   = 'card-badge';
    $('delivery-main').textContent  = data.message || 'Delivery unavailable';
    $('delivery-detail').textContent = '';
    return;
  }

  const std   = data.standard_delivery || {};
  const exp   = data.express_delivery   || {};
  const free  = data.free_standard_shipping;

  $('delivery-badge').textContent = free ? 'FREE' : `₹${std.cost}`;
  $('delivery-badge').className   = 'card-badge ' + (free ? 'success' : '');
  $('delivery-main').textContent  = `${std.date || '—'} via ${std.carrier || '—'}`;
  $('delivery-detail').textContent = `Express: ${exp.date || '—'} · ₹${exp.cost || '—'}  |  City: ${data.city || '—'}`;
}

function populateAnswer(text) {
  showResultCards();
  const card = $('card-answer');
  card.style.display = '';
  $('answer-text').textContent = text || '';
}


/* ── WebSocket ───────────────────────────────────────────────────────────── */
function connectWS(onOpen) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/query`);

  ws.onopen = () => { if (onOpen) onOpen(); };

  ws.onmessage = ({ data }) => {
    let ev;
    try { ev = JSON.parse(data); } catch { return; }
    handleEvent(ev);
  };

  ws.onerror = () => {
    addTrace('error', 'Connection', 'WebSocket error — is the server running?');
    setStatus('error', 'Error');
    finishRun();
  };

  ws.onclose = () => {
    if (running) {
      setStatus('error', 'Disconnected');
      finishRun();
    }
  };
}

function handleEvent(ev) {
  switch (ev.type) {
    case 'start':
      setStatus('thinking', 'Thinking…');
      break;

    case 'status':
      addTrace('status', 'Status', ev.message);
      break;

    case 'thinking':
      addTrace('thinking', `Thought (step ${ev.step||'?'})`, ev.text);
      break;

    case 'tool_call':
      addTrace('tool', `▶ ${ev.tool} (step ${ev.step||'?'})`, ev.tool, { args: ev.input });
      break;

    case 'tool_result': {
      const ok   = ev.success !== false;
      const res  = ev.result  || {};
      const msg  = res.message || JSON.stringify(res).slice(0, 120);
      addTrace('result', `◀ ${ev.tool} result`, msg, { fail: !ok });

      if (ev.tool === 'check_stock')  populateStock(res);
      if (ev.tool === 'price_order')  populatePrice(res);
      if (ev.tool === 'delivery_eta') populateDelivery(res);
      break;
    }

    case 'answer':
      addTrace('answer', 'Final Answer', ev.text);
      populateAnswer(ev.text);
      setStatus('done', 'Done');
      break;

    case 'error':
      addTrace('error', 'Error', ev.message || 'Unknown error');
      setStatus('error', 'Error');
      break;

    case 'done':
      finishRun();
      break;
  }
}


/* ── Run / Finish ────────────────────────────────────────────────────────── */
function startRun() {
  running = true;
  $('send-btn').disabled = true;
  setStatus('thinking', 'Thinking…');
  resetResultCards();
  hideTraceEmpty();
  // Clear old trace entries except the empty placeholder (already hidden)
  const log = $('trace-log');
  [...log.querySelectorAll('.trace-event')].forEach(n => n.remove());
}

function finishRun() {
  running = false;
  $('send-btn').disabled = false;
  if ($('status-label').textContent === 'Thinking…') setStatus('', 'Ready');
}

function sendQuery(query) {
  if (!query.trim()) return;
  startRun();

  // Scroll trace into view
  $('trace-log').scrollIntoView({ behavior: 'smooth', block: 'start' });

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    connectWS(() => {
      ws.send(JSON.stringify({ query }));
    });
  } else {
    ws.send(JSON.stringify({ query }));
  }
}


/* ── Input Wiring ────────────────────────────────────────────────────────── */
$('send-btn').addEventListener('click', () => {
  const q = $('query-input').value.trim();
  if (q) sendQuery(q);
});

$('query-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const q = $('query-input').value.trim();
    if (q) sendQuery(q);
  }
});

$('clear-btn').addEventListener('click', clearTrace);

document.querySelectorAll('.example-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    $('query-input').value = btn.dataset.q;
    $('query-input').focus();
  });
});


/* ── Demo Scenarios ──────────────────────────────────────────────────────── */
async function loadScenarios() {
  const grid = $('scenario-grid');
  try {
    const res  = await fetch('/api/demo-scenarios');
    const data = await res.json();
    renderScenarios(data.scenarios || []);
  } catch (e) {
    grid.innerHTML = `<div class="scenario-loading" style="color:var(--red)">Failed to load scenarios: ${escHtml(String(e))}</div>`;
  }
}

function renderScenarios(scenarios) {
  const grid = $('scenario-grid');
  grid.innerHTML = '';

  const tagIcons = { 'Happy Path': '✅', 'Out of Stock': '❌', 'Max Discount': '💰', 'Error Recovery': '⚠️', 'Paid Shipping': '🚢' };

  scenarios.forEach((s, i) => {
    const card = document.createElement('div');
    card.className = 'scenario-card';
    card.dataset.color = s.color;
    card.style.animationDelay = (i * 0.08) + 's';

    const icon = tagIcons[s.tag] || '▶';

    card.innerHTML = `
      <div class="scenario-tag">${icon} ${escHtml(s.tag)}</div>
      <div class="scenario-title">${escHtml(s.title)}</div>
      <div class="scenario-desc">${escHtml(s.desc)}</div>
      <div class="scenario-expected">${escHtml(s.expected)}</div>
      <button class="scenario-run">▶ Run this scenario</button>
    `;

    card.querySelector('.scenario-run').addEventListener('click', () => {
      runScenario(s.query);
    });

    card.addEventListener('click', e => {
      if (!e.target.classList.contains('scenario-run')) {
        $('query-input').value = s.query;
        $('query-input').focus();
        // Scroll to input
        $('query-input').scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });

    grid.appendChild(card);
  });
}

function runScenario(query) {
  $('query-input').value = query;
  // Scroll to trace area first
  document.querySelector('.main-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
  setTimeout(() => sendQuery(query), 300);
}


/* ── Proof Modal ─────────────────────────────────────────────────────────── */
function openProofModal() {
  $('proof-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeProofModal() {
  $('proof-modal').classList.remove('open');
  document.body.style.overflow = '';
}
function closeProofOnBackdrop(e) {
  if (e.target === $('proof-modal')) closeProofModal();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeProofModal(); });

async function runModalBatchTest() {
  const btn = $('modal-run-btn');
  btn.disabled = true;
  $('modal-idle').style.display    = 'none';
  $('modal-loading').style.display = 'flex';
  $('modal-results').style.display = 'none';

  let data;
  try {
    data = await fetch('/api/batch-test').then(r => r.json());
  } catch (e) {
    $('modal-loading').style.display = 'none';
    $('modal-idle').style.display    = '';
    $('modal-idle').innerHTML = `<span style="color:var(--red)">Error: ${escHtml(String(e))}</span>`;
    btn.disabled = false;
    return;
  }

  $('modal-loading').style.display = 'none';
  $('modal-results').style.display = '';
  btn.disabled = false;

  // Summary row
  $('modal-summary').innerHTML = `
    <div class="summary-stat passed"><span class="stat-num">${data.passed}</span><span class="stat-lbl">Passed</span></div>
    <div class="summary-stat failed"><span class="stat-num">${data.failed}</span><span class="stat-lbl">Failed</span></div>
    <div class="summary-stat total"><span class="stat-num">${data.total}</span><span class="stat-lbl">Total</span></div>
    ${data.failed === 0 ? `<div class="summary-all-pass">🏆 All ${data.total} tests passed!</div>` : ''}
  `;

  // Results table
  const tbody = $('modal-tbody');
  tbody.innerHTML = '';
  (data.results || []).forEach(r => {
    const steps = r.steps || {};
    const cell = key => {
      const s = steps[key];
      if (!s || s.skipped) return '<td class="td-step step-skip">—</td>';
      return `<td class="td-step ${s.passed ? 'step-pass' : 'step-fail'}">${s.passed ? '✓' : '✗'} ${escHtml((s.result||'').slice(0,55))}</td>`;
    };
    const badge = { happy:'<span class="row-badge happy">Happy</span>', oos:'<span class="row-badge oos">OOS</span>', error:'<span class="row-badge error">Error</span>' }[r.type] || '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="td-num">${r.id}</td>
      <td class="td-query"><div>${escHtml(r.label)}</div><div style="margin-top:3px">${badge}</div></td>
      ${cell('check_stock')}${cell('price_order')}${cell('delivery_eta')}
      <td class="td-note">${escHtml(r.note||'')}</td>
      <td class="td-result">${r.passed ? '✅' : '❌'}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* ── Init ────────────────────────────────────────────────────────────────── */
loadScenarios();
