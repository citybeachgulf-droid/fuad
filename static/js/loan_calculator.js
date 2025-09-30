(function () {
  function formatCurrency(value) {
    if (!isFinite(value)) return '—';
    return new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(value) + ' ر.ع';
  }

  function computeMonthlyPayment(principal, annualRatePercent, tenureMonths) {
    var p = Number(principal);
    var annualRate = Number(annualRatePercent);
    var n = Number(tenureMonths);
    if (!p || !annualRate || !n) return { monthly: NaN, totalInterest: NaN, totalCost: NaN };
    var r = (annualRate / 100) / 12; // monthly rate
    var factor = Math.pow(1 + r, n);
    var monthly = (p * r * factor) / (factor - 1);
    var totalCost = monthly * n;
    var totalInterest = totalCost - p;
    return { monthly: monthly, totalInterest: totalInterest, totalCost: totalCost };
  }

  function byId(id) { return document.getElementById(id); }

  function updateTenureHint(min, max) {
    var hint = byId('tenureHint');
    if (!hint) return;
    if (min || max) {
      var parts = [];
      if (min) parts.push('الأدنى: ' + min + ' شهر');
      if (max) parts.push('الأقصى: ' + max + ' شهر');
      hint.textContent = parts.join(' — ');
    } else {
      hint.textContent = '';
    }
  }

  function recalc() {
    var amount = byId('loanAmount')?.value;
    var months = byId('tenureMonths')?.value;
    var rate = byId('interestRate')?.value;
    var result = computeMonthlyPayment(amount, rate, months);
    var monthlyEl = byId('monthlyPayment');
    var interestEl = byId('totalInterest');
    var totalEl = byId('totalCost');
    if (monthlyEl) monthlyEl.textContent = formatCurrency(result.monthly);
    if (interestEl) interestEl.textContent = formatCurrency(result.totalInterest);
    if (totalEl) totalEl.textContent = formatCurrency(result.totalCost);
  }

  function onOfferChange() {
    var select = byId('offerSelect');
    if (!select) return;
    var selected = select.options[select.selectedIndex];
    var rate = selected && selected.value ? Number(selected.value) : null;
    var min = selected && selected.dataset.minMonths ? Number(selected.dataset.minMonths) : null;
    var max = selected && selected.dataset.maxMonths ? Number(selected.dataset.maxMonths) : null;
    if (rate) {
      byId('interestRate').value = rate;
    }
    updateTenureHint(min, max);
    recalc();
  }

  function attachEvents() {
    var inputs = ['loanAmount', 'tenureMonths', 'interestRate'];
    inputs.forEach(function (id) {
      var el = byId(id);
      if (el) {
        el.addEventListener('input', recalc);
        el.addEventListener('change', recalc);
      }
    });
    var offer = byId('offerSelect');
    if (offer) offer.addEventListener('change', onOfferChange);
    var btn = byId('calcBtn');
    if (btn) btn.addEventListener('click', function (e) { e.preventDefault(); recalc(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachEvents);
  } else {
    attachEvents();
  }
})();

