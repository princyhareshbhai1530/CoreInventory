// ─────────────────────────────────────────
// GLOBALS
// ─────────────────────────────────────────
let allProducts  = [];
let allLedger    = [];
let trendChart, categoryChart, topProductsChart;

// ─────────────────────────────────────────
// BOOT
// ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadAllData();
  renderKPIs();
  renderHealthGauge();
  renderCategoryChart();
  renderTopProducts();
  renderStockValueChart();
  renderForecastTable();
  generateAIInsights();
});

// ─────────────────────────────────────────
// DATA LOADING
// ─────────────────────────────────────────
async function loadAllData() {
  try {
    const [pRes, lRes] = await Promise.all([
      fetch('/api/products'),
      fetch('/api/stock-ledger'),
    ]);
    allProducts = await pRes.json();
    allLedger   = await lRes.json();
  } catch (e) {
    console.error('Failed to load data', e);
  }
}

// ─────────────────────────────────────────
// KPI STRIP
// ─────────────────────────────────────────
function renderKPIs() {
  const total    = allProducts.length;
  const lowStock = allProducts.filter(p => p.quantity_on_hand <= p.reorder_level).length;
  const movements = allLedger.length;

  // Stock health: % of products above reorder level
  const healthyCount = allProducts.filter(p => p.quantity_on_hand > p.reorder_level).length;
  const health = total > 0 ? Math.round((healthyCount / total) * 100) : 100;
  const healthColor = health >= 80 ? 'var(--emerald-dark)' : health >= 50 ? '#d97706' : 'var(--red)';

  setText('kpi-total',         total);
  setText('kpi-total-sub',     `${total} SKUs tracked`);
  setText('kpi-lowstock',      lowStock);
  setText('kpi-lowstock-sub',  lowStock === 0 ? 'All healthy ✓' : `${lowStock} need attention`);
  setText('kpi-movements',     movements);
  setText('kpi-movements-sub', `Total logged entries`);
  setText('kpi-health',        health + '%');
  setText('kpi-health-sub',    `${healthyCount} of ${total} products healthy`);
  document.getElementById('kpi-health').style.color = healthColor;
}

// ─────────────────────────────────────────
// CHART 1 — Stock Health Gauge (Doughnut)
// ─────────────────────────────────────────
function renderHealthGauge() {
  const total   = allProducts.length;
  const outOf   = allProducts.filter(p => p.quantity_on_hand <= 0).length;
  const low     = allProducts.filter(p => p.quantity_on_hand > 0 && p.quantity_on_hand <= p.reorder_level).length;
  const healthy = total - low - outOf;
  const healthPct = total > 0 ? Math.round((healthy / total) * 100) : 100;

  // Gauge color
  const color = healthPct >= 80 ? '#10b981' : healthPct >= 50 ? '#f59e0b' : '#ef4444';

  // Doughnut gauge
  const ctx = document.getElementById('healthGaugeChart');
  if (ctx._chart) ctx._chart.destroy();
  ctx._chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [healthy, low, outOf, Math.max(0, total === 0 ? 1 : 0)],
        backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#f1f5f9'],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 900 },
    },
  });

  // Center value
  const valEl = document.getElementById('health-gauge-val');
  if (valEl) { valEl.textContent = healthPct + '%'; valEl.style.color = color; }

  // Bars
  const animate = (id, count) => {
    const el = document.getElementById(id);
    if (el && total > 0) setTimeout(() => { el.style.width = Math.round((count/total)*100) + '%'; }, 100);
  };
  animate('bar-healthy', healthy);
  animate('bar-low', low);
  animate('bar-out', outOf);
  setText('count-healthy', healthy);
  setText('count-low', low);
  setText('count-out', outOf);

  // Insight pills
  const pills = document.getElementById('health-pills');
  if (pills) {
    const daysData = [];
    if (outOf > 0) daysData.push({ text: `${outOf} out of stock`, bg: '#fee2e2', color: '#ef4444' });
    if (low > 0)   daysData.push({ text: `${low} low stock`, bg: '#fef3c7', color: '#d97706' });
    if (healthy === total) daysData.push({ text: '✓ All products healthy', bg: '#d1fae5', color: '#059669' });
    daysData.push({ text: `${allLedger.length} movements logged`, bg: '#dbeafe', color: '#3b82f6' });

    pills.innerHTML = daysData.map(p =>
      `<span class="health-pill" style="background:${p.bg};color:${p.color};">${esc(p.text)}</span>`
    ).join('');
  }
}

// ─────────────────────────────────────────
// TOP PRODUCTS — Enhanced horizontal bars
// ─────────────────────────────────────────
function renderTopProducts() {
  const volMap = {};
  const productMeta = {};
  allProducts.forEach(p => { productMeta[p.name] = p; });
  allLedger.forEach(m => {
    const name = m.product_name || 'Unknown';
    volMap[name] = (volMap[name] || 0) + Math.abs(m.quantity);
  });

  const sorted = Object.entries(volMap).sort((a,b) => b[1]-a[1]).slice(0, 6);
  const max    = sorted[0]?.[1] || 1;

  const rankColors = [
    { bg: '#fef3c7', color: '#d97706', bar: '#f59e0b' }, // gold
    { bg: '#f1f5f9', color: '#64748b', bar: '#94a3b8' }, // silver
    { bg: '#fdf2e9', color: '#b45309', bar: '#f97316' }, // bronze
    { bg: '#dbeafe', color: '#2563eb', bar: '#3b82f6' },
    { bg: '#f0fdf4', color: '#15803d', bar: '#22c55e' },
    { bg: '#faf5ff', color: '#7c3aed', bar: '#8b5cf6' },
  ];

  const medals = ['🥇','🥈','🥉','4','5','6'];
  const container = document.getElementById('top-products-list');
  if (!container) return;

  if (sorted.length === 0) {
    container.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No movement data yet.</div>`;
    return;
  }

  container.innerHTML = sorted.map(([name, vol], i) => {
    const c    = rankColors[i] || rankColors[3];
    const pct  = Math.round((vol / max) * 100);
    const meta = productMeta[name];
    const sku  = meta?.sku || '';
    const unit = meta?.unit_of_measure || '';
    return `
      <div class="top-product-row">
        <div class="top-product-rank" style="background:${c.bg};color:${c.color};">${medals[i]}</div>
        <div class="top-product-info">
          <div class="top-product-name">${esc(name)}</div>
          ${sku ? `<div class="top-product-sku">${esc(sku)}</div>` : ''}
        </div>
        <div class="top-product-bar-wrap">
          <div class="top-product-bar" data-width="${pct}" style="background:${c.bar};width:0%;"></div>
        </div>
        <div class="top-product-vol">${fmt(vol)}<span style="font-size:10px;font-weight:500;color:var(--text-muted);margin-left:2px;">${esc(unit)}</span></div>
      </div>
    `;
  }).join('');

  // Animate bars after render
  setTimeout(() => {
    container.querySelectorAll('.top-product-bar').forEach(bar => {
      bar.style.width = bar.dataset.width + '%';
    });
  }, 100);
}


// ─────────────────────────────────────────
// STOCK VALUE BY CATEGORY — Bar Chart
// ─────────────────────────────────────────
let stockValueChart;
function renderStockValueChart() {
  const catVal = {};
  allProducts.forEach(p => {
    const cat  = p.category || 'General';
    const val  = (p.quantity_on_hand || 0) * (p.unit_cost || 0);
    catVal[cat] = (catVal[cat] || 0) + val;
  });

  const sorted  = Object.entries(catVal).sort((a,b) => b[1]-a[1]);
  const labels  = sorted.map(e => e[0]);
  const data    = sorted.map(e => Math.round(e[1]));
  const colors  = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899','#84cc16'];

  if (stockValueChart) stockValueChart.destroy();
  const ctx = document.getElementById('stockValueChart');
  if (!ctx) return;

  // If all values are 0, show a message overlay
  const hasValue = data.some(v => v > 0);

  stockValueChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Stock Value (₹)',
        data: hasValue ? data : labels.map(() => 1),
        backgroundColor: colors.slice(0, labels.length).map(c => c + 'cc'),
        borderColor:     colors.slice(0, labels.length),
        borderWidth: 1.5,
        borderRadius: 8,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => hasValue ? '₹ ' + ctx.parsed.y.toLocaleString('en-IN') : 'No unit cost set',
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { family: 'DM Sans', size: 11 } } },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0,0,0,0.04)' },
          ticks: {
            font: { family: 'DM Sans', size: 11 },
            callback: v => hasValue ? '₹' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v) : '',
          },
        },
      },
    },
  });

  if (!hasValue) {
    // Show overlay hint
    ctx.parentElement.style.position = 'relative';
    const hint = document.createElement('div');
    hint.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;';
    hint.innerHTML = `<span style="background:rgba(255,255,255,0.85);padding:8px 14px;border-radius:8px;font-size:12px;color:#64748b;font-weight:500;">Set unit cost on products to see value</span>`;
    ctx.parentElement.appendChild(hint);
  }
}

// ─────────────────────────────────────────
// CHART 2 — Category Pie
// ─────────────────────────────────────────
function renderCategoryChart() {
  const catMap = {};
  allProducts.forEach(p => {
    const cat = p.category || 'General';
    catMap[cat] = (catMap[cat] || 0) + (p.quantity_on_hand || 0);
  });
  const labels = Object.keys(catMap);
  const data   = Object.values(catMap);
  const colors = ['#10b981','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#84cc16'];

  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(document.getElementById('categoryChart'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors.slice(0, labels.length), borderWidth: 2, borderColor: '#fff' }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { font: { family: 'DM Sans', size: 12 }, boxWidth: 12, padding: 14 } },
      },
      cutout: '60%',
    },
  });
}

// ─────────────────────────────────────────
// FORECAST TABLE — Rule-based (enhanced)
// ─────────────────────────────────────────
function renderForecastTable() {
  const tbody = document.getElementById('forecast-body');


  // Calculate velocity: how much stock has been consumed per product in last 7 days
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const cutoff = sevenDaysAgo.toISOString().split('T')[0];

  const velocityMap = {};
  allLedger.forEach(m => {
    if (m.date >= cutoff && (m.movement_type === 'delivery' || m.movement_type === 'adjustment')) {
      velocityMap[m.product_id] = (velocityMap[m.product_id] || 0) + Math.abs(m.quantity);
    }
  });

  // Score each product
  const rows = allProducts.map(p => {
    const vel     = velocityMap[p.id] || 0;
    const daily   = vel / 7;
    const stock   = p.quantity_on_hand;
    const reorder = p.reorder_level;
    const ratio   = reorder > 0 ? stock / reorder : 99;

    let risk, riskClass;
    if (stock <= 0)          { risk = 'Out of Stock'; riskClass = 'risk-high'; }
    else if (stock <= reorder) { risk = 'High';       riskClass = 'risk-high'; }
    else if (ratio < 2)      { risk = 'Medium';       riskClass = 'risk-medium'; }
    else                     { risk = 'Low';           riskClass = 'risk-low'; }

    return { p, vel, daily, risk, riskClass };
  }).sort((a,b) => {
    const order = { 'Out of Stock': 0, 'High': 1, 'Medium': 2, 'Low': 3 };
    return (order[a.risk] ?? 4) - (order[b.risk] ?? 4);
  });

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted);">No products found.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(({ p, vel, daily, risk, riskClass }) => {
    const daysLeft = daily > 0 ? Math.round(p.quantity_on_hand / daily) : null;
    const daysColor = daysLeft === null ? 'var(--text-muted)' : daysLeft <= 3 ? '#ef4444' : daysLeft <= 7 ? '#d97706' : '#16a34a';
    return `
    <tr>
      <td>
        <div style="font-weight:600;color:var(--text-primary);">${esc(p.name)}</div>
        <div style="font-size:11px;color:var(--text-muted);">${esc(p.sku)}</div>
      </td>
      <td><span style="font-size:11px;background:var(--slate-light);padding:2px 8px;border-radius:20px;color:var(--text-secondary);">${esc(p.category || 'General')}</span></td>
      <td style="font-weight:600;">${fmt(p.quantity_on_hand)} <span style="font-size:11px;color:var(--text-muted);">${esc(p.unit_of_measure)}</span></td>
      <td>${fmt(p.reorder_level)} <span style="font-size:11px;color:var(--text-muted);">${esc(p.unit_of_measure)}</span></td>
      <td style="color:var(--text-secondary);">${daily > 0 ? fmt(daily) + '/day' : '—'}</td>
      <td style="font-weight:700;color:${daysColor};">${daysLeft !== null ? daysLeft + ' days' : '—'}</td>
      <td><span class="risk-badge ${riskClass}">${risk}</span></td>
    </tr>
  `}).join('');
}

// ─────────────────────────────────────────
// AI NARRATIVE — via Flask proxy → Claude API
// ─────────────────────────────────────────
async function generateAIInsights() {
  const btn  = document.getElementById('ai-refresh-btn');
  const icon = document.getElementById('ai-refresh-icon');
  const body = document.getElementById('ai-body');
  const ts   = document.getElementById('ai-timestamp');

  btn.disabled = true;
  icon.className = 'bi bi-arrow-clockwise spin';
  body.innerHTML = `<div class="intel-loading">
    <div class="skel" style="height:14px;width:90%;"></div>
    <div class="skel" style="height:14px;width:70%;"></div>
    <div class="skel" style="height:14px;width:82%;"></div>
    <div class="skel" style="height:14px;width:55%;"></div>
  </div>`;

  try {
    // Build compact data summary
    const lowStock    = allProducts.filter(p => p.quantity_on_hand <= p.reorder_level);
    const outOfStock  = allProducts.filter(p => p.quantity_on_hand <= 0);

    const volMap = {};
    allLedger.forEach(m => { volMap[m.product_name] = (volMap[m.product_name]||0) + Math.abs(m.quantity); });
    const topMovers = Object.entries(volMap).sort((a,b)=>b[1]-a[1]).slice(0,3).map(e=>e[0]);

    const sevenAgo = new Date(); sevenAgo.setDate(sevenAgo.getDate()-7);
    const cutoff = sevenAgo.toISOString().split('T')[0];
    const recentReceipts   = allLedger.filter(m => m.date >= cutoff && m.movement_type === 'receipt').length;
    const recentDeliveries = allLedger.filter(m => m.date >= cutoff && m.movement_type === 'delivery').length;

    const data_context = `Inventory Summary:
- Total products: ${allProducts.length}
- Low stock items: ${lowStock.length} (${lowStock.map(p=>p.name).join(', ') || 'none'})
- Out of stock items: ${outOfStock.length} (${outOfStock.map(p=>p.name).join(', ') || 'none'})
- Top 3 moving products (by volume): ${topMovers.join(', ') || 'none'}
- Last 7 days: ${recentReceipts} receipt entries, ${recentDeliveries} delivery entries
- Total stock movements logged: ${allLedger.length}
- Categories in use: ${[...new Set(allProducts.map(p=>p.category))].join(', ') || 'General'}`;

    // Call Flask proxy — no API key exposed in browser
    const resp = await fetch('/api/ai-insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data_context }),
    });

    const data = await resp.json();
    const lines = data.insights || [];
    const source = data.source || 'claude';

    if (!lines.length) throw new Error('Empty insights');

    body.innerHTML = lines.map(line => `
      <div class="insight-line">
        <span class="insight-dot" style="${source==='fallback'?'background:var(--amber);':''}"></span>
        <span>${esc(line)}</span>
      </div>
    `).join('');

    const label = source === 'fallback' ? '⚡ Rule-based mode' : '✦ Gemini AI';
    ts.textContent = `${label} · ${new Date().toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit'})}`;

  } catch (err) {
    console.error('AI error:', err);
    body.innerHTML = `<div class="insight-line"><span class="insight-dot" style="background:var(--red);"></span><span>❌ Could not generate insights. Check server logs.</span></div>`;
    ts.textContent = 'Error — ' + new Date().toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit'});
  } finally {
    btn.disabled = false;
    icon.className = 'bi bi-arrow-clockwise';
  }
}

// ─────────────────────────────────────────
// UTILS
// ─────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
function fmt(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 1 });
}
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
