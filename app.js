/* ── STATE ── */
let apiKey = '', apiSecret = '';
let sessionOrders = [];

/* ── INIT ── */
document.addEventListener('DOMContentLoaded', () => {
  loadKeys();
  setupNav();
  setupMenuBtn();
  setupSettings();
  setupPlaceOrder();
  setupQuickOrder();
  setupChat();
  refreshDashboard();
});

/* ── KEY PERSISTENCE ── */
function loadKeys() {
  apiKey    = sessionStorage.getItem('cb_api_key')    || '';
  apiSecret = sessionStorage.getItem('cb_api_secret') || '';
  if (apiKey) {
    document.getElementById('s-apikey').value = apiKey;
    document.getElementById('s-secret').value = apiSecret;
    setConnected(true);
  }
}
function saveKeys() {
  apiKey    = document.getElementById('s-apikey').value.trim();
  apiSecret = document.getElementById('s-secret').value.trim();
  sessionStorage.setItem('cb_api_key',    apiKey);
  sessionStorage.setItem('cb_api_secret', apiSecret);
}

/* ── CONNECTED STATE ── */
function setConnected(ok, error) {
  const dot   = document.getElementById('conn-dot');
  const label = document.getElementById('conn-label');
  if (ok) {
    dot.className   = 'status-dot connected';
    label.textContent = 'Connected';
  } else if (error) {
    dot.className   = 'status-dot error';
    label.textContent = 'Auth Error';
  } else {
    dot.className   = 'status-dot';
    label.textContent = 'Not Connected';
  }
}

/* ── NAV TABS ── */
function setupNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      const tab = item.dataset.tab;
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      item.classList.add('active');
      document.getElementById('tab-' + tab).classList.add('active');
      document.getElementById('breadcrumb').textContent =
        tab.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase());
      // Auto-actions per tab
      if (tab === 'logs')    loadLogs();
      if (tab === 'history') loadHistory();
      if (tab === 'dashboard') refreshDashboard();
      // Close sidebar on mobile
      document.getElementById('sidebar').classList.remove('open');
    });
  });
}

function setupMenuBtn() {
  document.getElementById('menuBtn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
}

/* ── SETTINGS TAB ── */
function setupSettings() {
  document.getElementById('save-keys').addEventListener('click', async () => {
    saveKeys();
    const result = await testConnection();
    const el = document.getElementById('conn-result');
    el.style.display = 'block';
    if (result.success) {
      el.innerHTML = `<div class="alert alert-success">Connected! ${result.assets.length} asset(s) found. Balances loaded.</div>`;
      setConnected(true);
      renderBalanceCards(result.assets);
      updateStatCards(result.assets);
    } else {
      el.innerHTML = `<div class="alert alert-error">Error: ${result.error}</div>`;
      setConnected(false, true);
    }
  });

  document.getElementById('test-keys').addEventListener('click', async () => {
    saveKeys();
    const result = await testConnection();
    const el = document.getElementById('conn-result');
    el.style.display = 'block';
    el.innerHTML = result.success
      ? `<div class="alert alert-success">Connection successful! Found ${result.assets.length} asset(s).</div>`
      : `<div class="alert alert-error">Failed: ${result.error}</div>`;
    setConnected(result.success, !result.success);
  });

  document.getElementById('clear-keys').addEventListener('click', () => {
    sessionStorage.removeItem('cb_api_key');
    sessionStorage.removeItem('cb_api_secret');
    apiKey = ''; apiSecret = '';
    document.getElementById('s-apikey').value = '';
    document.getElementById('s-secret').value = '';
    setConnected(false);
    document.getElementById('conn-result').style.display = 'none';
  });

  document.getElementById('toggle-secret').addEventListener('click', () => {
    const inp = document.getElementById('s-secret');
    const btn = document.getElementById('toggle-secret');
    if (inp.type === 'password') { inp.type = 'text'; btn.textContent = 'Hide Secret'; }
    else { inp.type = 'password'; btn.textContent = 'Show Secret'; }
  });
}

async function testConnection() {
  try {
    const res = await fetch('/api/balance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret })
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: 'Network error: ' + e.message };
  }
}

/* ── DASHBOARD ── */
async function refreshDashboard() {
  document.getElementById('refresh-balance').addEventListener('click', refreshDashboard);
  document.getElementById('stat-orders').textContent = sessionOrders.length;

  if (!apiKey) {
    document.getElementById('balance-content').innerHTML =
      `<div style="text-align:center;color:var(--muted);padding:32px">Go to <b>Settings</b> and enter your API keys to see balances.</div>`;
    return;
  }

  document.getElementById('balance-content').innerHTML =
    `<div style="text-align:center;color:var(--muted);padding:24px"><div class="spinner"></div> Loading balances...</div>`;

  const result = await testConnection();
  if (result.success) {
    renderBalanceCards(result.assets);
    updateStatCards(result.assets);
    setConnected(true);
  } else {
    document.getElementById('balance-content').innerHTML =
      `<div class="alert alert-error">${result.error}</div>`;
  }

  renderRecentOrders();
}

function updateStatCards(assets) {
  const usdt = assets.find(a => a.asset === 'USDT');
  const btc  = assets.find(a => a.asset === 'BTC');
  if (usdt) document.getElementById('stat-usdt').textContent = usdt.balance.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
  if (btc)  document.getElementById('stat-btc').textContent  = btc.balance.toFixed(4);
}

function renderBalanceCards(assets) {
  if (!assets || assets.length === 0) {
    document.getElementById('balance-content').innerHTML =
      '<div style="color:var(--muted);padding:16px">No assets with balance found.</div>';
    return;
  }
  const colorMap = { USDT:'#00ff88', USDC:'#00d4ff', BTC:'#ffa502', ETH:'#a78bfa', BNB:'#ffd32a' };
  const cards = assets.map(a => {
    const color = colorMap[a.asset] || '#8b949e';
    return `
      <div style="background:var(--surface3);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center">
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">${a.asset}</div>
        <div style="font-size:28px;font-weight:800;color:${color}">${a.balance.toLocaleString(undefined,{minimumFractionDigits:4,maximumFractionDigits:4})}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px">Available: ${a.available.toLocaleString(undefined,{minimumFractionDigits:4,maximumFractionDigits:4})}</div>
      </div>`;
  }).join('');
  document.getElementById('balance-content').innerHTML =
    `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px">${cards}</div>`;
}

function renderRecentOrders() {
  const tbody = document.getElementById('dash-recent-body');
  if (sessionOrders.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px">No orders yet this session</td></tr>`;
    return;
  }
  tbody.innerHTML = sessionOrders.slice(0, 5).map(o => `
    <tr>
      <td class="oid">${o.order_id || '—'}</td>
      <td><span class="pill ${o.side==='BUY'?'p-buy':'p-sell'}">${o.side}</span></td>
      <td>${o.order_type || o.type}</td>
      <td><span class="pill p-new">${o.status}</span></td>
    </tr>`).join('');
  document.getElementById('stat-orders').textContent = sessionOrders.length;
}

/* ── QUICK ORDER (Dashboard) ── */
function setupQuickOrder() {
  document.getElementById('q-buy').addEventListener('click',  () => placeQuickOrder('BUY'));
  document.getElementById('q-sell').addEventListener('click', () => placeQuickOrder('SELL'));
}

async function placeQuickOrder(side) {
  const symbol = document.getElementById('q-symbol').value;
  const qty    = document.getElementById('q-qty').value;
  const resultEl = document.getElementById('q-result');
  resultEl.style.display = 'block';
  resultEl.innerHTML = `<div class="alert" style="background:var(--surface3);border:1px solid var(--border)"><div class="spinner"></div> Placing ${side} order...</div>`;

  const res = await submitOrder({ symbol, side, order_type: 'MARKET', quantity: qty });
  if (res.success) {
    resultEl.innerHTML = `<div class="alert alert-success">Order placed! ID: <b>${res.order_id}</b> | Status: ${res.status}</div>`;
    sessionOrders.unshift(res);
    renderRecentOrders();
  } else {
    resultEl.innerHTML = `<div class="alert alert-error">${res.error}</div>`;
  }
}

/* ── PLACE ORDER TAB ── */
function setupPlaceOrder() {
  // Type buttons
  document.querySelectorAll('.type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const type = btn.dataset.type;
      document.getElementById('o-type').value = type;
      document.getElementById('price-group').style.display = (type==='LIMIT'||type==='LIMIT_IOC') ? 'block' : 'none';
      document.getElementById('tif-group').style.display   = (type==='LIMIT') ? 'block' : 'none';
      document.getElementById('prev-price-row').style.display = (type==='LIMIT'||type==='LIMIT_IOC') ? 'flex' : 'none';
      updatePreview();
    });
  });

  // Side buttons
  document.querySelectorAll('.side-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.side-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('o-side').value = btn.dataset.side;
      updatePreview();
    });
  });

  // Live preview
  ['o-symbol','o-qty','o-price','o-tif'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updatePreview);
    if (el) el.addEventListener('change', updatePreview);
  });

  // Place button
  document.getElementById('place-btn').addEventListener('click', handlePlaceOrder);
}

function updatePreview() {
  const symbol = document.getElementById('o-symbol').value;
  const side   = document.getElementById('o-side').value;
  const type   = document.getElementById('o-type').value;
  const qty    = document.getElementById('o-qty').value;
  const price  = document.getElementById('o-price').value;

  document.getElementById('prev-symbol').textContent = symbol;
  document.getElementById('prev-side').textContent   = side;
  document.getElementById('prev-side').style.color   = side === 'BUY' ? 'var(--green)' : 'var(--red)';
  document.getElementById('prev-type').textContent   = type;
  document.getElementById('prev-qty').textContent    = qty || '—';
  document.getElementById('prev-price').textContent  = price ? `$${Number(price).toLocaleString()}` : '—';
}

async function handlePlaceOrder() {
  const btn = document.getElementById('place-btn');
  const spinner = document.getElementById('order-spinner');
  btn.disabled = true;
  spinner.style.display = 'block';

  const payload = {
    symbol:     document.getElementById('o-symbol').value,
    side:       document.getElementById('o-side').value,
    order_type: document.getElementById('o-type').value,
    quantity:   document.getElementById('o-qty').value,
    price:      document.getElementById('o-price').value || null,
    time_in_force: document.getElementById('o-tif').value,
  };

  const res = await submitOrder(payload);
  renderOrderResult(res);
  if (res.success) {
    sessionOrders.unshift(res);
    document.getElementById('stat-orders').textContent = sessionOrders.length;
  }

  btn.disabled = false;
  spinner.style.display = 'none';
}

async function submitOrder(payload) {
  if (!apiKey || !apiSecret) {
    return { success: false, error: 'No API keys. Go to Settings and enter your keys first.' };
  }
  try {
    const res = await fetch('/api/place_order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, api_key: apiKey, api_secret: apiSecret })
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: 'Network error: ' + e.message };
  }
}

function renderOrderResult(res) {
  const el = document.getElementById('order-result-content');
  if (res.success) {
    el.innerHTML = `
      <div class="result-success">
        <span class="result-badge" style="color:var(--green)">Order Placed Successfully</span>
        <div class="result-id" style="color:var(--green)">${res.order_id}</div>
        <div class="result-row"><span>Symbol</span><span>${res.symbol}</span></div>
        <div class="result-row"><span>Side</span><span style="color:${res.side==='BUY'?'var(--green)':'var(--red)'}">${res.side}</span></div>
        <div class="result-row"><span>Type</span><span>${res.order_type}</span></div>
        <div class="result-row"><span>Status</span><span style="color:var(--accent)">${res.status}</span></div>
        <div class="result-row"><span>Quantity</span><span>${res.orig_qty}</span></div>
        <div class="result-row"><span>Executed</span><span>${res.executed_qty}</span></div>
        ${res.price && res.price !== '0' && res.price !== '0.00' ? `<div class="result-row"><span>Price</span><span>$${Number(res.price).toLocaleString()}</span></div>` : ''}
        ${res.avg_price && res.avg_price !== '0' ? `<div class="result-row"><span>Avg Price</span><span>$${Number(res.avg_price).toLocaleString()}</span></div>` : ''}
        ${res.time_in_force ? `<div class="result-row"><span>Time-In-Force</span><span>${res.time_in_force}</span></div>` : ''}
        <div class="result-row"><span>Client OID</span><span style="font-family:monospace;font-size:11px">${res.client_order_id}</span></div>
      </div>`;
  } else {
    el.innerHTML = `
      <div class="result-fail">
        <span class="result-badge" style="color:var(--red)">Order Failed</span>
        <div style="color:var(--red);font-size:14px;margin-top:8px">${res.error}</div>
      </div>`;
  }
}

/* ── ORDER HISTORY ── */
async function loadHistory() {
  document.getElementById('refresh-history').onclick = loadHistory;
  const tbody = document.getElementById('history-body');
  try {
    const res = await fetch('/api/orders');
    const data = await res.json();
    const orders = data.orders || [];
    if (orders.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:32px">No orders placed this session yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = orders.map(o => `
      <tr>
        <td style="font-size:12px;color:var(--muted)">${o.timestamp || '—'}</td>
        <td class="oid">${o.order_id || '—'}</td>
        <td>${o.symbol || '—'}</td>
        <td><span class="pill ${(o.side||'').toUpperCase()==='BUY'?'p-buy':'p-sell'}">${o.side || '—'}</span></td>
        <td>${o.order_type || '—'}</td>
        <td>${o.orig_qty || '—'}</td>
        <td>${o.price && o.price!=='0' && o.price!=='0.00' ? '$'+Number(o.price).toLocaleString() : 'Market'}</td>
        <td><span class="pill p-new">${o.status || '—'}</span></td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="alert alert-error">Failed to load orders: ${e.message}</div></td></tr>`;
  }
}

/* ── LOGS ── */
async function loadLogs() {
  document.getElementById('refresh-logs').onclick = loadLogs;
  document.getElementById('clear-logs').onclick   = () => { document.getElementById('log-body').innerHTML = ''; };

  const body = document.getElementById('log-body');
  body.innerHTML = '<div style="color:var(--muted)"><div class="spinner"></div> Loading logs...</div>';

  try {
    const res  = await fetch('/api/logs');
    const data = await res.json();
    const lines = data.logs || [];
    if (lines.length === 0) {
      body.innerHTML = '<div style="color:var(--muted)">Log file is empty.</div>';
      return;
    }
    body.innerHTML = lines.map(line => {
      let cls = 'log-body';
      if (line.includes('| ERROR'))   cls = 'log-error';
      else if (line.includes('| WARNING')) cls = 'log-warn';
      else if (line.includes('| INFO'))    cls = 'log-info';
      else if (line.includes('| DEBUG'))   cls = 'log-debug';
      if (line.includes('Order completed')) cls = 'log-ok';
      return `<div class="log-line ${cls}">${escHtml(line)}</div>`;
    }).join('');
    body.scrollTop = body.scrollHeight;
  } catch (e) {
    body.innerHTML = `<div class="alert alert-error">Failed to load logs: ${e.message}</div>`;
  }
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ── AI CHAT BOT ── */

function setupChat() {
  const input   = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const clearBtn= document.getElementById('clear-chat');

  sendBtn.addEventListener('click', sendChatMessage);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') sendChatMessage(); });

  if (clearBtn) clearBtn.addEventListener('click', () => {
    const msgs = document.getElementById('chat-messages');
    msgs.innerHTML = `
      <div class="msg bot">
        <div class="msg-bubble">Chat cleared! How can I help you?</div>
        <div class="msg-time">Just now</div>
      </div>`;
  });

  // Quick question buttons
  document.querySelectorAll('.qq-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('chat-input').value = btn.textContent;
      sendChatMessage();
    });
  });
}

function formatTime() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function appendMessage(text, role) {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  // Simple markdown: **bold** and `code`
  const formatted = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>');
  div.innerHTML = `
    <div class="msg-bubble">${formatted}</div>
    <div class="msg-time">${formatTime()}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTyping() {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.id = 'typing-indicator';
  div.innerHTML = `<div class="msg-bubble msg-typing">
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  </div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing-indicator');
  if (t) t.remove();
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text  = input.value.trim();
  if (!text) return;
  input.value = '';

  appendMessage(text, 'user');
  showTyping();

  const connected = !!apiKey && !!apiSecret;
  const orderCount = sessionOrders.length;

  // Small delay to feel natural
  await new Promise(r => setTimeout(r, 600 + Math.random() * 600));

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, connected, order_count: orderCount })
    });
    const data = await res.json();
    removeTyping();
    appendMessage(data.reply || 'Sorry, I had trouble responding.', 'bot');
  } catch (e) {
    removeTyping();
    appendMessage('Connection error. Make sure the Flask server is running!', 'bot');
  }
}

