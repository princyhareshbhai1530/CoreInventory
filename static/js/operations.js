let availableProducts = []; // Cached products for dropdowns

/* ── Load products into memory for dropdowns ────── */
async function loadProductsForDropdown() {
  try {
    const res        = await fetch('/api/products');
    availableProducts = await res.json();
  } catch (e) {
    console.warn('Could not load products for dropdown:', e);
  }
}

/* ── Add a product row to the modal items table ─── */
function addProductRow() {
  const tbody  = document.getElementById('receipt-items-body') ||
                 document.getElementById('delivery-items-body');
  const noMsg  = document.getElementById('no-items-msg');

  if (noMsg) noMsg.style.display = 'none';

  // Build product options HTML
  const options = availableProducts.map(p =>
    `<option value="${p.id}">${p.name} (${p.sku}) — ${p.quantity_on_hand} ${p.unit_of_measure} on hand</option>`
  ).join('');

  const rowId = `row-${Date.now()}`;
  const tr    = document.createElement('tr');
  tr.className = 'receipt-item-row';
  tr.id        = rowId;
  tr.innerHTML = `
    <td>
      <select class="ci-select item-product-select" style="font-size:13px;">
        <option value="">— Select product —</option>
        ${options}
      </select>
    </td>
    <td>
      <input type="number" class="ci-input item-qty-input"
             placeholder="Qty" min="0.01" step="0.01"
             style="font-size:13px;">
    </td>
    <td>
      <button onclick="removeProductRow('${rowId}')"
              style="background:none;border:none;cursor:pointer;
                     color:var(--red);font-size:16px;padding:4px 6px;"
              title="Remove">
        <i class="bi bi-trash3"></i>
      </button>
    </td>`;

  tbody.appendChild(tr);
}

/* ── Remove a product row ────────────────────────── */
function removeProductRow(rowId) {
  const row   = document.getElementById(rowId);
  const tbody = row?.parentElement;
  if (row) row.remove();

  // Show "no items" message if table is now empty
  const remaining = tbody?.querySelectorAll('.receipt-item-row').length || 0;
  if (remaining === 0) {
    const noMsg = document.getElementById('no-items-msg');
    if (noMsg) noMsg.style.display = 'block';
  }
}
