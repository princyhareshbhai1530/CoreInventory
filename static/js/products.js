let allProducts = []; // Cache for client-side filtering

document.addEventListener('DOMContentLoaded', loadProducts);

/* ── Load all products from API ─────────────────── */
async function loadProducts() {
  try {
    const res  = await fetch('/api/products');
    if (!res.ok) throw new Error('Failed to load products');
    allProducts = await res.json();

    renderSummaryCards(allProducts);
    populateCategoryFilter(allProducts);
    renderProductsTable(allProducts);

  } catch (err) {
    console.error(err);
    document.getElementById('products-body').innerHTML = `
      <tr><td colspan="9">
        <div class="empty-state">
          <i class="bi bi-wifi-off"></i>
          <h6>Could not load products</h6>
          <p>Make sure the Flask server is running.</p>
        </div>
      </td></tr>`;
  }
}

/* ── Summary KPI Cards ──────────────────────────── */
function renderSummaryCards(products) {
  const total   = products.length;
  const low     = products.filter(p => p.is_low_stock && p.quantity_on_hand > 0).length;
  const out     = products.filter(p => p.quantity_on_hand === 0).length;
  const inStock = total - low - out;

  document.getElementById('sum-total').textContent   = total;
  document.getElementById('sum-instock').textContent = inStock;
  document.getElementById('sum-low').textContent     = low;
  document.getElementById('sum-out').textContent     = out;
}

/* ── Populate category dropdown ─────────────────── */
function populateCategoryFilter(products) {
  const categories = [...new Set(products.map(p => p.category).filter(Boolean))].sort();
  const sel = document.getElementById('category-filter');
  categories.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    sel.appendChild(opt);
  });
}

/* ── Render products table ──────────────────────── */
function renderProductsTable(products) {
  const tbody  = document.getElementById('products-body');
  const footer = document.getElementById('products-footer');

  if (products.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="9">
        <div class="empty-state">
          <i class="bi bi-box"></i>
          <h6>No products found</h6>
          <p>Add your first product using the button above.</p>
        </div>
      </td></tr>`;
    footer.textContent = 'No products';
    return;
  }

  tbody.innerHTML = products.map(p => {
    // Stock level bar calculation
    const pct     = p.reorder_level > 0
      ? Math.min(100, (p.quantity_on_hand / (p.reorder_level * 3)) * 100)
      : 100;
    const isOut   = p.quantity_on_hand === 0;
    const isLow   = p.is_low_stock && !isOut;
    const rowCls  = isOut ? 'low-stock-row' : isLow ? 'low-stock-row' : '';
    const fillCls = isOut ? 'fill-critical' : isLow ? 'fill-low' : 'fill-ok';
    const qtyCls  = isOut ? 'stock-critical' : isLow ? 'stock-low' : 'stock-ok';

    // Low stock warning icon
    const warningIcon = (isLow || isOut)
      ? `<i class="bi bi-exclamation-triangle-fill text-warning ms-1" title="Low stock"></i>`
      : '';

    return `
      <tr class="${rowCls}">
        <td>
          <div style="font-weight:600;color:var(--text-primary);">
            ${p.name} ${warningIcon}
          </div>
        </td>
        <td><span class="table-ref">${p.sku}</span></td>
        <td>
          <span style="background:var(--blue-light);color:#1d4ed8;padding:2px 8px;
                       border-radius:12px;font-size:11px;font-weight:600;">
            ${p.category || 'General'}
          </span>
        </td>
        <td class="muted">${p.unit_of_measure}</td>
        <td>
          <span class="${qtyCls}" style="font-size:15px;">
            ${p.quantity_on_hand}
          </span>
        </td>
        <td class="muted">${p.reorder_level}</td>
        <td>
          <div class="stock-bar-wrap">
            <div class="stock-bar">
              <div class="stock-bar-fill ${fillCls}" style="width:${pct}%;"></div>
            </div>
            <span style="font-size:11px;color:var(--text-muted);min-width:30px;">
              ${Math.round(pct)}%
            </span>
          </div>
        </td>
        <td class="muted">₹${p.unit_cost.toLocaleString('en-IN')}</td>
        <td>
          <div style="display:flex;gap:6px;">
            <button class="btn-ci-secondary" style="padding:5px 10px;font-size:12px;"
                    onclick="openAdjustModal(${p.id}, '${p.name.replace(/'/g,"\\'")}', ${p.quantity_on_hand})"
                    title="Adjust Stock">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn-ci-danger" style="padding:5px 10px;font-size:12px;"
                    onclick="deleteProduct(${p.id}, '${p.name.replace(/'/g,"\\'")}', event)"
                    title="Delete Product">
              <i class="bi bi-trash3"></i>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  footer.textContent = `Showing ${products.length} product${products.length !== 1 ? 's' : ''}`;
}

/* ── Client-side filter (instant, no API call) ─── */
function filterProducts() {
  const search = document.getElementById('product-search').value.toLowerCase();
  const cat    = document.getElementById('category-filter').value;

  const filtered = allProducts.filter(p => {
    const matchSearch = !search ||
      p.name.toLowerCase().includes(search) ||
      p.sku.toLowerCase().includes(search) ||
      (p.category || '').toLowerCase().includes(search);
    const matchCat = !cat || p.category === cat;
    return matchSearch && matchCat;
  });

  renderProductsTable(filtered);
}

/* ── Add Product Modal ──────────────────────────── */
function openAddModal() {
  // Clear all fields
  ['p-name','p-sku','p-category','p-cost','p-qty','p-reorder'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('add-product-error').style.display = 'none';
  new bootstrap.Modal(document.getElementById('addProductModal')).show();
}

async function saveProduct() {
  const btn      = document.getElementById('save-product-btn');
  const errorEl  = document.getElementById('add-product-error');

  // Gather values
  const name    = document.getElementById('p-name').value.trim();
  const sku     = document.getElementById('p-sku').value.trim();
  const category= document.getElementById('p-category').value.trim();
  const uom     = document.getElementById('p-uom').value;
  const cost    = parseFloat(document.getElementById('p-cost').value) || 0;
  const qty     = parseFloat(document.getElementById('p-qty').value) || 0;
  const reorder = parseFloat(document.getElementById('p-reorder').value) || 10;

  // Client-side validation
  errorEl.style.display = 'none';
  if (!name) return showError(errorEl, 'Product name is required.');
  if (!sku)  return showError(errorEl, 'SKU is required.');

  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Saving...';

  try {
    const res = await fetch('/api/products', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name, sku, category, unit_of_measure: uom,
                                unit_cost: cost, quantity_on_hand: qty,
                                reorder_level: reorder }),
    });

    const data = await res.json();

    if (!res.ok) {
      showError(errorEl, data.error || 'Failed to save product.');
      return;
    }

    // Success
    bootstrap.Modal.getInstance(document.getElementById('addProductModal')).hide();
    showToast(`${name} added successfully!`, 'success');
    await loadProducts(); // Refresh table

  } catch (err) {
    showError(errorEl, 'Server error. Please try again.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-lg"></i> Save Product';
  }
}

/* ── Adjust Stock Modal ─────────────────────────── */
function openAdjustModal(id, name, currentQty) {
  document.getElementById('adjust-product-id').value   = id;
  document.getElementById('adjust-product-name').textContent = name;
  document.getElementById('adjust-qty').value          = currentQty;
  document.getElementById('adjust-reason').value       = '';
  document.getElementById('adjust-error').style.display = 'none';
  new bootstrap.Modal(document.getElementById('adjustModal')).show();
}

async function saveAdjustment() {
  const id      = document.getElementById('adjust-product-id').value;
  const qty     = parseFloat(document.getElementById('adjust-qty').value);
  const reason  = document.getElementById('adjust-reason').value.trim() || 'Manual adjustment';
  const errorEl = document.getElementById('adjust-error');

  errorEl.style.display = 'none';

  if (isNaN(qty) || qty < 0) {
    return showError(errorEl, 'Please enter a valid quantity (0 or more).');
  }

  try {
    const res = await fetch(`/api/products/${id}/adjust`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ quantity: qty, reason }),
    });

    const data = await res.json();
    if (!res.ok) {
      showError(errorEl, data.error || 'Adjustment failed.');
      return;
    }

    bootstrap.Modal.getInstance(document.getElementById('adjustModal')).hide();
    showToast(`Stock updated to ${qty}`, 'success');
    await loadProducts();

  } catch (err) {
    showError(errorEl, 'Server error. Please try again.');
  }
}

/* ── Helper: show inline error ──────────────────── */
function showError(el, msg) {
  el.style.display = 'flex';
  el.innerHTML = `<i class="bi bi-x-circle-fill"></i> ${msg}`;
}

/* ── Delete Product ─────────────────────────────── */
async function deleteProduct(id, name, event) {
  event.stopPropagation();
  if (!confirm(`Delete "${name}"?\n\nThis will permanently remove the product. This cannot be undone.`)) return;
  try {
    const res  = await fetch(`/api/products/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Could not delete product.', 'danger'); return; }
    showToast(`"${name}" deleted.`, 'warning');
    await loadProducts();
  } catch (err) {
    showToast('Server error. Please try again.', 'danger');
  }
}
