let allMovements  = [];
let currentFilter = 'all';
let currentView   = 'list';

document.addEventListener('DOMContentLoaded', () => {
  loadLedger();
  setInterval(loadLedger, 15000);
});

/* ── Fetch all movements ────────────────────────── */
async function loadLedger() {
  try {
    const res    = await fetch('/api/stock-ledger');
    if (!res.ok) throw new Error();
    allMovements = await res.json();
    renderSummary(allMovements);
    render(applyFilters());
  } catch(e) {
    document.getElementById('ledger-body').innerHTML = `
      <tr><td colspan="7">
        <div class="empty-state">
          <i class="bi bi-wifi-off"></i>
          <h6>Could not load move history</h6>
          <p>Make sure the Flask server is running.</p>
        </div>
      </td></tr>`;
  }
}

/* ── Summary cards ──────────────────────────────── */
function renderSummary(items) {
  document.getElementById('sum-total').textContent = items.length;
  document.getElementById('sum-in').textContent    = items.filter(m => m.movement_type==='IN').length;
  document.getElementById('sum-out').textContent   = items.filter(m => m.movement_type==='OUT').length;
  document.getElementById('sum-adj').textContent   = items.filter(m => m.movement_type==='ADJUST').length;
}

/* ── Filter by type ─────────────────────────────── */
function setFilter(type, btn) {
  currentFilter = type;
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  render(applyFilters());
}

/* ── Search by reference + contact ─────────────── */
function filterLedger() { render(applyFilters()); }

function applyFilters() {
  const search = (document.getElementById('ledger-search').value || '').toLowerCase();
  return allMovements.filter(m => {
    const matchType   = currentFilter === 'all' || m.movement_type === currentFilter;
    const matchSearch = !search ||
      (m.reference    || '').toLowerCase().includes(search) ||
      (m.contact      || '').toLowerCase().includes(search) ||
      (m.product_name || '').toLowerCase().includes(search);
    return matchType && matchSearch;
  });
}

/* ── View toggle ────────────────────────────────── */
function setView(view) {
  currentView = view;
  const listEl   = document.getElementById('list-view');
  const kanbanEl = document.getElementById('kanban-view');
  const btnList  = document.getElementById('btn-list-view');
  const btnKanban= document.getElementById('btn-kanban-view');

  if (view === 'list') {
    listEl.style.display   = 'block';
    kanbanEl.style.display = 'none';
    btnList.style.background   = 'var(--emerald)';
    btnList.style.color        = '#fff';
    btnKanban.style.background = 'var(--card-bg)';
    btnKanban.style.color      = 'var(--text-secondary)';
  } else {
    listEl.style.display   = 'none';
    kanbanEl.style.display = 'block';
    btnList.style.background   = 'var(--card-bg)';
    btnList.style.color        = 'var(--text-secondary)';
    btnKanban.style.background = 'var(--emerald)';
    btnKanban.style.color      = '#fff';
    renderKanban(applyFilters());
  }
}

/* ── Main render dispatcher ─────────────────────── */
function render(items) {
  if (currentView === 'kanban') renderKanban(items);
  else renderList(items);
}

/* ── LIST VIEW ──────────────────────────────────── */
function renderList(items) {
  const tbody  = document.getElementById('ledger-body');
  const footer = document.getElementById('ledger-footer');

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="7">
      <div class="empty-state">
        <i class="bi bi-arrow-left-right"></i>
        <h6>No movements found</h6>
        <p>Validate a receipt or delivery to see movements here.</p>
      </div></td></tr>`;
    footer.textContent = 'No movements';
    return;
  }

  tbody.innerHTML = items.map(m => {
    const isIN  = m.movement_type === 'IN';
    const isOUT = m.movement_type === 'OUT';

    // Row color: IN = light green, OUT = light red (exact mockup requirement)
    const rowStyle = isIN
      ? 'background:rgba(16,185,129,0.07);'
      : isOUT
      ? 'background:rgba(239,68,68,0.07);'
      : '';

    // Reference with color coding
    const refColor = isIN ? 'var(--emerald-dark)' : isOUT ? '#dc2626' : 'var(--blue)';

    // Quantity display
    const qty    = parseFloat(m.quantity);
    const qtyHtml= qty > 0
      ? `<span style="color:var(--emerald-dark);font-weight:700;">+${qty}</span>`
      : `<span style="color:var(--red);font-weight:700;">${qty}</span>`;

    // Status badge
    const statusHtml = statusBadge(m.status || 'done');

    return `<tr style="${rowStyle}">
      <td>
        <span style="font-family:'DM Mono',monospace;font-size:12.5px;
                     font-weight:600;color:${refColor};">
          ${m.reference}
        </span>
      </td>
      <td class="muted" style="font-size:12px;white-space:nowrap;">${m.date || m.timestamp?.split(' ')[0] || '—'}</td>
      <td style="font-weight:500;">${m.contact || '—'}</td>
      <td>
        <span style="background:var(--slate-light);color:var(--slate);
                     padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">
          ${m.from_location}
        </span>
      </td>
      <td>
        <span style="background:var(--blue-light);color:#1d4ed8;
                     padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">
          ${m.to_location}
        </span>
      </td>
      <td>${qtyHtml}</td>
      <td>${statusHtml}</td>
    </tr>`;
  }).join('');

  footer.textContent =
    `${items.length} movement${items.length!==1?'s':''}` +
    (currentFilter!=='all' ? ` · ${currentFilter}` : '') +
    ' · auto-refreshes every 15s';
}

/* ── KANBAN VIEW (by status) ────────────────────── */
function renderKanban(items) {
  const board = document.getElementById('kanban-board');

  const columns = {
    draft:     { label:'Draft',     color:'var(--slate)',        items:[] },
    waiting:   { label:'Waiting',   color:'var(--amber)',        items:[] },
    ready:     { label:'Ready',     color:'var(--blue)',         items:[] },
    done:      { label:'Done',      color:'var(--emerald)',      items:[] },
    cancelled: { label:'Cancelled', color:'var(--red)',          items:[] },
  };

  // Group by status
  items.forEach(m => {
    const s = m.status || 'done';
    if (columns[s]) columns[s].items.push(m);
    else columns.done.items.push(m);
  });

  board.innerHTML = Object.entries(columns).map(([key, col]) => `
    <div class="col-12 col-md-6 col-xl" style="min-width:200px;">
      <div class="ci-card h-100">
        <div style="padding:12px 16px;border-bottom:3px solid ${col.color};
                    display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:13px;font-weight:600;color:var(--text-primary);">
            ${col.label}
          </span>
          <span style="background:var(--content-bg);border-radius:12px;
                       padding:2px 9px;font-size:12px;font-weight:700;
                       color:var(--text-secondary);">
            ${col.items.length}
          </span>
        </div>
        <div style="padding:10px 10px;display:flex;flex-direction:column;gap:8px;min-height:120px;">
          ${col.items.length === 0
            ? `<div style="text-align:center;color:var(--text-muted);font-size:12px;padding:20px 0;">Empty</div>`
            : col.items.map(m => {
                const isIN  = m.movement_type === 'IN';
                const isOUT = m.movement_type === 'OUT';
                const qty   = parseFloat(m.quantity);
                const border= isIN ? 'var(--emerald)' : isOUT ? 'var(--red)' : 'var(--slate)';
                return `
                  <div style="background:var(--content-bg);border-radius:8px;
                               padding:10px 12px;border-left:3px solid ${border};">
                    <div style="font-size:12px;font-weight:600;font-family:'DM Mono',monospace;
                                color:${border};margin-bottom:3px;">${m.reference}</div>
                    <div style="font-size:12px;font-weight:500;color:var(--text-primary);
                                margin-bottom:4px;">${m.product_name}</div>
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                      <span style="font-size:11px;color:var(--text-muted);">
                        ${m.from_location} → ${m.to_location}
                      </span>
                      <span style="font-size:12px;font-weight:700;
                                   color:${qty>0?'var(--emerald-dark)':'var(--red)'};">
                        ${qty>0?'+':''}${qty}
                      </span>
                    </div>
                    ${m.contact ? `<div style="font-size:10px;color:var(--text-muted);margin-top:3px;">${m.contact}</div>` : ''}
                  </div>`;
              }).join('')
          }
        </div>
      </div>
    </div>`).join('');
}
