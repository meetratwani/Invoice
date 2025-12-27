(function () {
  const itemsBody = document.getElementById('items-body');
  const emptyState = document.getElementById('empty-state');
  const addItemBtn = document.getElementById('add-item');
  const subtotalDisplay = document.getElementById('subtotal-display');
  const totalDisplay = document.getElementById('total-display');
  const discountInput = document.getElementById('discount');
  const taxInput = document.getElementById('tax');
  const products = (window.INVOICE_PRODUCTS || []).slice();

  // Quick Add UI
  const quickAddInput = document.getElementById('quick-add-input');
  const btnProductPicker = document.getElementById('btn-product-picker');
  const btnCameraScan = document.getElementById('btn-camera-scan');

  // Picker Modal
  const pickerModal = document.getElementById('product-picker-modal');
  const pickerCloseBtn = document.getElementById('picker-close');
  const pickerSearch = document.getElementById('picker-search');
  const pickerGrid = document.getElementById('picker-grid');

  // Camera Scanner Modal (Optional)
  const scanModal = document.getElementById('barcode-scanner-modal');
  const scanCloseBtn = document.getElementById('barcode-scan-close');
  const scanStatusEl = document.getElementById('barcode-scan-status');

  let html5QrCode = null;
  let scannerRunning = false;

  function updateEmptyState() {
    const hasItems = itemsBody.querySelectorAll('tr:not(#empty-state)').length > 0;
    if (emptyState) {
      emptyState.hidden = hasItems;
    }
  }

  function recalcTotals() {
    let subtotal = 0;
    itemsBody.querySelectorAll('tr:not(#empty-state)').forEach((row) => {
      const qtyInput = row.querySelector("input[name='item_quantity[]']");
      const priceInput = row.querySelector("input[name='item_unit_price[]']");
      const lineTotalCell = row.querySelector('.line-total');

      if (!qtyInput || !priceInput) return;

      const qty = parseFloat(qtyInput.value || '0');
      const price = parseFloat(priceInput.value || '0');
      const lineTotal = qty * price;
      lineTotalCell.textContent = lineTotal.toFixed(2);
      subtotal += lineTotal;
    });

    subtotalDisplay.textContent = subtotal.toFixed(2);

    const discount = parseFloat(discountInput.value || '0');
    const tax = parseFloat(taxInput.value || '0');
    const total = subtotal - discount + tax;
    totalDisplay.textContent = total.toFixed(2);
  }

  function createRowHTML(product = null) {
    const desc = product ? product.name : '';
    const pid = product ? product.id : '';
    const price = product ? (product.unit_price || 0) : 0;
    const qty = 1;
    const sku = product && product.sku ? ` [${product.sku}]` : '';
    const stock = product ? (product.stock_quantity || 0) : 0;
    const stockWarning = product && stock <= 0 ? ' ⚠️ Out of stock' : '';

    return `
        <td>
          <div style="display: flex; flex-direction: column; gap: 0.25rem;">
            <input type="text" name="item_description[]" class="item-description" 
                   value="${desc}${sku}" placeholder="Item description" ${product ? 'readonly' : ''} 
                   style="font-weight: 500;" />
            <input type="hidden" name="item_product_id[]" class="item-product-id" value="${pid}" />
            ${product ? `<small style="color: #6b7280;">Stock: ${stock}${stockWarning}</small>` : ''}
          </div>
        </td>
        <td>
          <input type="number" name="item_quantity[]" min="0" step="1" value="${qty}" 
                 style="font-size: 1rem; text-align: center;" />
        </td>
        <td>
          <input type="number" name="item_unit_price[]" min="0" step="0.01" value="${price}" 
                 style="font-size: 1rem; text-align: right;" />
        </td>
        <td class="line-total" style="font-weight: 600; text-align: right;">0.00</td>
        <td style="text-align: center;">
          <button type="button" class="btn small danger remove-row" style="padding: 0.5rem;">Delete</button>
        </td>
      `;
  }

  function addRow(product = null) {
    // If product exists, check if we can just increment quantity
    if (product) {
      const existingRow = Array.from(itemsBody.querySelectorAll('tr:not(#empty-state)')).find(row => {
        const pidVal = row.querySelector('.item-product-id').value;
        return pidVal === String(product.id);
      });

      if (existingRow) {
        const qtyInput = existingRow.querySelector("input[name='item_quantity[]']");
        qtyInput.value = (parseFloat(qtyInput.value || 0) + 1);

        // Highlight animation
        existingRow.style.transition = 'background-color 0.3s';
        existingRow.style.backgroundColor = '#dcfce7';
        setTimeout(() => existingRow.style.backgroundColor = '', 500);

        recalcTotals();
        return existingRow;
      }
    }

    const row = document.createElement('tr');
    row.innerHTML = createRowHTML(product);
    row.style.animation = 'slideIn 0.3s ease-out';
    itemsBody.appendChild(row);
    attachRowEvents(row);
    updateEmptyState();
    recalcTotals();

    // Scroll to the new row
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return row;
  }

  function attachRowEvents(row) {
    const qtyInput = row.querySelector("input[name='item_quantity[]']");
    const priceInput = row.querySelector("input[name='item_unit_price[]']");
    const removeBtn = row.querySelector('.remove-row');

    if (qtyInput) qtyInput.addEventListener('input', recalcTotals);
    if (priceInput) priceInput.addEventListener('input', recalcTotals);
    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        row.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
          row.remove();
          updateEmptyState();
          recalcTotals();
        }, 300);
      });
    }
  }

  if (addItemBtn) {
    addItemBtn.addEventListener('click', () => {
      addRow(null);
    });
  }

  // --- Quick Add Logic ---
  if (quickAddInput) {
    quickAddInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const val = quickAddInput.value.trim();
        if (!val) return;

        // Find product by Barcode (exact) or SKU (exact) or Name (fuzzy)
        const match = products.find(p => {
          const b = (p.barcode || '').trim().toLowerCase();
          const s = (p.sku || '').trim().toLowerCase();
          const n = (p.name || '').trim().toLowerCase();
          const v = val.toLowerCase();
          return b === v || s === v || n === v;
        });

        if (match) {
          addRow(match);
          quickAddInput.value = '';
          quickAddInput.focus();

          // Success feedback
          quickAddInput.style.borderColor = '#10b981';
          setTimeout(() => quickAddInput.style.borderColor = '', 500);
        } else {
          // Not found feedback
          quickAddInput.style.borderColor = '#ef4444';
          setTimeout(() => quickAddInput.style.borderColor = '', 1000);

          const retry = confirm(`Product "${val}" not found.\n\nWould you like to add it as a manual item?`);
          if (retry) {
            const row = addRow(null);
            const descInput = row.querySelector('.item-description');
            descInput.value = val;
            descInput.readOnly = false;
            quickAddInput.value = '';
          }
        }
      }
    });
  }

  // --- Product Picker Logic ---
  function renderPickerItems(filterText = '') {
    pickerGrid.innerHTML = '';
    const term = filterText.toLowerCase();

    const matches = products.filter(p => {
      if (!term) return true;
      const text = [p.name || '', p.sku || '', p.barcode || '', p.category || ''].join(' ').toLowerCase();
      return text.includes(term);
    });

    matches.forEach(p => {
      const card = document.createElement('div');
      const stock = p.stock_quantity || 0;

      // Simple stock indicator text instead of colors
      const stockText = stock <= 0 ? '(Out of Stock)' : `(Stock: ${stock})`;

      card.style.cssText = `
          border: 1px solid #ddd;
          padding: 1rem;
          cursor: pointer;
          background: white;
          transition: all 0.2s;
        `;

      card.onmouseover = () => {
        card.style.borderColor = '#333';
        card.style.background = '#f9f9f9';
      };
      card.onmouseout = () => {
        card.style.borderColor = '#ddd';
        card.style.background = 'white';
      };

      card.innerHTML = `
            <div style="font-weight:700; margin-bottom:0.5rem; font-size: 1rem; color: #333;">${p.name}</div>
            <div style="font-size:0.875rem; color:#666; margin-bottom: 0.25rem;">SKU: ${p.sku || '-'}</div>
            <div style="font-size:0.875rem; color:#666; margin-bottom: 0.5rem;">Barcode: ${p.barcode || '-'}</div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #eee;">
              <span style="font-weight:700; font-size: 1.1rem; color: #333;">${p.unit_price}</span>
              <span style="font-size:0.875rem; color: #666;">${stockText}</span>
            </div>
        `;

      card.onclick = () => {
        addRow(p);
        closePicker();
        if (quickAddInput) quickAddInput.focus();
      };

      pickerGrid.appendChild(card);
    });

    if (matches.length === 0) {
      pickerGrid.innerHTML = `
          <div style="grid-column:1/-1; text-align:center; padding:3rem; color:#6b7280;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">Search</div>
            <div style="font-size: 1.1rem; font-weight: 500;">No products found</div>
            <div style="font-size: 0.875rem; margin-top: 0.5rem;">Try a different search term</div>
          </div>
        `;
    }
  }

  function openPicker() {
    if (!pickerModal) return;
    renderPickerItems('');
    if (pickerSearch) pickerSearch.value = '';
    pickerModal.hidden = false;
    pickerModal.style.display = 'block'; // Inline block
    if (pickerSearch) setTimeout(() => pickerSearch.focus(), 100);
  }

  function closePicker() {
    if (!pickerModal) return;
    pickerModal.hidden = true;
    pickerModal.style.display = 'none';
  }

  if (btnProductPicker) {
    btnProductPicker.addEventListener('click', openPicker);
  }
  if (pickerCloseBtn) {
    pickerCloseBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closePicker();
    });
  }
  if (pickerSearch) {
    pickerSearch.addEventListener('input', (e) => renderPickerItems(e.target.value));
  }

  // --- Camera Scanner (Optional) ---
  function openCameraScanner() {
    if (!scanModal) return;
    if (!window.Html5Qrcode) {
      alert('Barcode scanner library not loaded. Please refresh the page.');
      return;
    }

    scanModal.hidden = false;
    scanModal.style.display = 'block'; // Inline block
    startScanner();
  }

  function closeCameraScanner() {
    if (!scanModal) return;
    stopScanner().finally(() => {
      scanModal.hidden = true;
      scanModal.style.display = 'none';
    });
  }

  function startScanner() {
    if (!html5QrCode) {
      html5QrCode = new Html5Qrcode('barcode-reader');
    }

    // Optimized config for faster barcode recognition
    const config = {
      fps: 20,  // Increased from 10 for faster scanning
      qrbox: { width: 300, height: 150 },  // Wider box, better for barcodes
      aspectRatio: 1.7777778,  // 16:9 aspect ratio for better camera view
      disableFlip: false,
      // Focus on common retail barcode formats for faster processing
      formatsToSupport: [
        Html5QrcodeSupportedFormats.EAN_13,
        Html5QrcodeSupportedFormats.EAN_8,
        Html5QrcodeSupportedFormats.UPC_A,
        Html5QrcodeSupportedFormats.UPC_E,
        Html5QrcodeSupportedFormats.CODE_128,
        Html5QrcodeSupportedFormats.CODE_39,
        Html5QrcodeSupportedFormats.CODE_93,
        Html5QrcodeSupportedFormats.ITF,
        Html5QrcodeSupportedFormats.QR_CODE,
      ],
      experimentalFeatures: {
        useBarCodeDetectorIfSupported: true  // Use native API if available (much faster)
      }
    };

    scanStatusEl.textContent = 'Starting camera...';
    scanStatusEl.style.color = '#3b82f6';

    html5QrCode.start(
      { facingMode: 'environment' },
      config,
      (decodedText) => {
        const text = decodedText.trim();
        if (!text) return;

        const product = products.find(p =>
          (p.barcode || '').trim() === text || (p.sku || '').trim() === text
        );

        if (product) {
          addRow(product);
          scanStatusEl.textContent = `✓ Added: ${product.name}`;
          scanStatusEl.style.color = '#10b981';

          // Play a short beep sound for feedback (optional)
          try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.1;
            oscillator.start();
            setTimeout(() => oscillator.stop(), 100);
          } catch (e) { /* Audio not supported */ }
        } else {
          scanStatusEl.textContent = `✗ Not found: ${text}`;
          scanStatusEl.style.color = '#ef4444';
        }
      },
      () => {
        // Ignore scan errors (expected when no barcode in frame)
      }
    ).then(() => {
      scannerRunning = true;
      scanStatusEl.textContent = '📷 Scanning... Point camera at barcode';
      scanStatusEl.style.color = '#3b82f6';
    }).catch((err) => {
      scanStatusEl.textContent = `Camera error: ${err}`;
      scanStatusEl.style.color = '#ef4444';
    });
  }

  function stopScanner() {
    if (!html5QrCode || !scannerRunning) return Promise.resolve();
    scannerRunning = false;
    return html5QrCode.stop().then(() => {
      try {
        html5QrCode.clear();
      } catch (e) { }
    }).catch(() => { });
  }

  if (btnCameraScan) {
    btnCameraScan.addEventListener('click', openCameraScanner);
  }
  if (scanCloseBtn) {
    scanCloseBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeCameraScanner();
    });
  }

  // Close sections on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (pickerModal && !pickerModal.hidden) closePicker();
      if (scanModal && !scanModal.hidden) closeCameraScanner();
    }
  });

  if (discountInput) discountInput.addEventListener('input', recalcTotals);
  if (taxInput) taxInput.addEventListener('input', recalcTotals);

  // Add CSS animations
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    @keyframes slideOut {
      from {
        opacity: 1;
        transform: translateX(0);
      }
      to {
        opacity: 0;
        transform: translateX(20px);
      }
    }
  `;
  document.head.appendChild(style);

  // Initialize
  updateEmptyState();
  recalcTotals();
})();
