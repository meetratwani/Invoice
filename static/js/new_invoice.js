(function () {
  const itemsBody = document.getElementById('items-body');
  const addItemBtn = document.getElementById('add-item');
  const subtotalDisplay = document.getElementById('subtotal-display');
  const totalDisplay = document.getElementById('total-display');
  const discountInput = document.getElementById('discount');
  const taxInput = document.getElementById('tax');

  function recalcTotals() {
    let subtotal = 0;
    itemsBody.querySelectorAll('tr').forEach((row) => {
      const qtyInput = row.querySelector("input[name='item_quantity[]']");
      const priceInput = row.querySelector("input[name='item_unit_price[]']");
      const lineTotalCell = row.querySelector('.line-total');

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

  function attachRowEvents(row) {
    const qtyInput = row.querySelector("input[name='item_quantity[]']");
    const priceInput = row.querySelector("input[name='item_unit_price[]']");
    const removeBtn = row.querySelector('.remove-row');

    if (qtyInput) qtyInput.addEventListener('input', recalcTotals);
    if (priceInput) priceInput.addEventListener('input', recalcTotals);
    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        if (itemsBody.querySelectorAll('tr').length > 1) {
          row.remove();
          recalcTotals();
        } else {
          // Clear row instead of removing last row
          row.querySelector("input[name='item_description[]']").value = '';
          qtyInput.value = '1';
          priceInput.value = '0';
          recalcTotals();
        }
      });
    }
  }

  if (addItemBtn) {
    addItemBtn.addEventListener('click', () => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>
          <input type="text" name="item_description[]" placeholder="Item description" />
        </td>
        <td>
          <input type="number" name="item_quantity[]" min="0" step="1" value="1" />
        </td>
        <td>
          <input type="number" name="item_unit_price[]" min="0" step="0.01" value="0" />
        </td>
        <td class="line-total">0.00</td>
        <td>
          <button type="button" class="btn small danger remove-row">X</button>
        </td>
      `;
      itemsBody.appendChild(row);
      attachRowEvents(row);
      recalcTotals();
    });
  }

  // Attach events for initial row
  itemsBody.querySelectorAll('tr').forEach(attachRowEvents);

  if (discountInput) discountInput.addEventListener('input', recalcTotals);
  if (taxInput) taxInput.addEventListener('input', recalcTotals);

  recalcTotals();
})();
