(function() {
  function byId(id) { return document.getElementById(id); }
  function fmt(val) {
    if (!isFinite(val)) return '—';
    try { return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: 'OMR', maximumFractionDigits: 2 }).format(val); }
    catch(e) { return Number(val).toFixed(2) + ' ر.ع'; }
  }

  var state = {
    bankSlug: null,
    loanType: 'housing',
    maxRatio: null,
    defaultYears: null,
    defaultAnnualRate: null
  };

  function loadPolicyDefaults() {
    var bank = state.bankSlug;
    var type = state.loanType;
    if (!bank) return;
    fetch('/client/loan_policies?bank_slug=' + encodeURIComponent(bank) + '&loan_type=' + encodeURIComponent(type), { credentials: 'same-origin' })
      .then(function(r){ return r.json(); })
      .then(function(items) {
        var p = items && items.length ? items[0] : null;
        state.maxRatio = p ? p.max_ratio : null;
        state.defaultYears = p ? p.default_years : null;
        state.defaultAnnualRate = p ? p.default_annual_rate : null;
        if (state.defaultYears && !byId('years').value) byId('years').value = state.defaultYears;
        if (state.defaultAnnualRate && !byId('annualRate').value) byId('annualRate').value = state.defaultAnnualRate;
        var info = 'نسبة التحمل: ' + (state.maxRatio ? Math.round(state.maxRatio * 100) + '%' : '—');
        if (state.defaultAnnualRate) info += ' • فائدة افتراضية: ' + state.defaultAnnualRate + '%';
        if (state.defaultYears) info += ' • مدة افتراضية: ' + state.defaultYears + ' سنة';
        byId('policyInfo').textContent = info;
        recalc();
      })
      .catch(function(){ /* ignore */ });
  }

  function recalc() {
    var bank = state.bankSlug;
    if (!bank) return;
    var payload = {
      bank_slug: bank,
      loan_type: state.loanType,
      income: byId('income').value,
      years: byId('years').value,
      annual_rate: byId('annualRate').value
    };
    fetch('/client/compute_max_loan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    }).then(function(r){ return r.json(); })
      .then(function(res){
        if (res && res.max_principal != null) {
          byId('maxPrincipal').textContent = fmt(res.max_principal);
          byId('maxMonthly').textContent = fmt(res.max_monthly_payment);
          var u = res.used || {};
          byId('formulaUsed').textContent = 'r = ' + (u.annual_rate/100/12).toFixed(6) + ', n = ' + (u.years*12) + ', نسبة التحمل = ' + Math.round((u.max_ratio||0)*100) + '%';
        }
      }).catch(function(){ /* ignore */ });
  }

  function attach() {
    var bankSel = byId('bankSelect');
    var typeSel = byId('loanType');
    ['income','years','annualRate'].forEach(function(id){ var el = byId(id); if (el) { el.addEventListener('input', recalc); el.addEventListener('change', recalc); }});
    if (bankSel) bankSel.addEventListener('change', function(){ state.bankSlug = bankSel.value || null; loadPolicyDefaults(); });
    if (typeSel) typeSel.addEventListener('change', function(){ state.loanType = typeSel.value; loadPolicyDefaults(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
  else attach();
})();

