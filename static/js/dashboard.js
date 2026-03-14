document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();

  // Set date label
  const d = new Date();
  const label = document.getElementById('dash-date-label');
  if (label) label.textContent = 'Today — ' + d.toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
});

async function loadDashboard() {
  try {
    const res  = await fetch('/api/dashboard');
    if (!res.ok) throw new Error('API error');
    const data = await res.json();

    // Receipt card
    setText('r-to-receive',  data.receipt_to_receive  ?? data.pending_receipts ?? 0);
    setText('r-late',        data.receipt_late        ?? 0);
    setText('r-operations',  data.receipt_operations  ?? 0);

    // Delivery card
    setText('d-to-deliver',  data.delivery_to_deliver ?? data.pending_deliveries ?? 0);
    setText('d-late',        data.delivery_late       ?? 0);
    setText('d-waiting',     data.delivery_waiting    ?? 0);
    setText('d-operations',  data.delivery_operations ?? 0);

    // Bottom panels
    renderRecentMovements(data.recent_movements);
    renderLowStockList(data.low_stock_products);
    renderAlertBanner(data.low_stock_count, data.low_stock_products);

  } catch (err) {
    console.error('Dashboard load error:', err);
    showToast('Could not load dashboard. Is the server running?', 'danger');
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function renderRecentMovements(movements) {
  const tbody = document.getElementById('recent-movements-body');
  if (!movements || movements.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:30px;">
      <i class="bi bi-inbox"></i><h6>No activity yet</h6>
      <p>Validate a receipt or delivery to see movements.</p></div></td></tr>`;
    return;
  }
  tbody.innerHTML = movements.map(m => {
    const typeIcon = m.movement_type === 'IN'
      ? `<span style="color:var(--emerald-dark);font-weight:600;"><i class="bi bi-arrow-down-circle-fill"></i> IN</span>`
      : m.movement_type === 'OUT'
      ? `<span style="color:var(--red);font-weight:600;"><i class="bi bi-arrow-up-circle-fill"></i> OUT</span>`
      : `<span style="color:var(--slate);font-weight:600;"><i class="bi bi-pencil-fill"></i> ADJ</span>`;
    const time = m.timestamp ? m.timestamp.split(' ')[1] : '—';
    return `<tr onclick="location.href='/move-history'" style="cursor:pointer;">
      <td><span class="table-ref">${m.reference||'—'}</span></td>
      <td>${m.product_name}</td>
      <td>${typeIcon}</td>
      <td>${fmtQty(m.quantity)}</td>
      <td class="muted">${time}</td></tr>`;
  }).join('');
}

function renderLowStockList(products) {
  const container = document.getElementById('low-stock-list');
  const noStock   = document.getElementById('no-low-stock');
  if (!products || products.length === 0) {
    container.style.display = 'none';
    noStock.style.display   = 'block';
    return;
  }
  container.innerHTML = products.map(p => {
    const pct     = Math.min(100, (p.quantity_on_hand / (p.reorder_level * 2)) * 100);
    const isCrit  = p.quantity_on_hand === 0;
    const fillCls = isCrit ? 'fill-critical' : 'fill-low';
    const qtyCol  = isCrit ? 'stock-critical' : 'stock-low';
    return `<div style="display:flex;align-items:center;gap:14px;padding:12px 22px;border-bottom:1px solid var(--border-light);">
      <div style="width:36px;height:36px;background:var(--amber-light);border-radius:8px;
                  display:flex;align-items:center;justify-content:center;flex-shrink:0;">
        <i class="bi bi-box-seam" style="color:#d97706;"></i>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:13.5px;font-weight:600;color:var(--text-primary);
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${p.name}</div>
        <div style="font-size:11px;color:var(--text-muted);">SKU: ${p.sku}</div>
      </div>
      <div style="text-align:right;flex-shrink:0;">
        <div class="${qtyCol}" style="font-size:14px;font-weight:700;">${p.quantity_on_hand} ${p.unit_of_measure}</div>
        <div style="font-size:11px;color:var(--text-muted);">Min: ${p.reorder_level}</div>
        <div class="stock-bar" style="width:70px;margin-top:4px;">
          <div class="stock-bar-fill ${fillCls}" style="width:${pct}%;"></div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderAlertBanner(count, products) {
  const banner = document.getElementById('low-stock-alert');
  const text   = document.getElementById('low-stock-alert-text');
  if (!banner || count === 0) return;
  const names = (products||[]).slice(0,2).map(p=>p.name).join(', ');
  const more  = (products||[]).length > 2 ? ` and ${products.length-2} more` : '';
  text.textContent = `${count} item${count>1?'s':''} below reorder level: ${names}${more}`;
  banner.style.display = 'flex';
}

function goNewReceipt() {
  sessionStorage.setItem('autoOpenModal','receipt');
  window.location.href = '/receipts';
}
function goNewDelivery() {
  sessionStorage.setItem('autoOpenModal','delivery');
  window.location.href = '/deliveries';
}
