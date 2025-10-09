(function(){
  function byId(id){ return document.getElementById(id); }
  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }
  function formatCurrency(value){
    if (!isFinite(value)) return '—';
    try { return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: 'OMR', maximumFractionDigits: 0 }).format(value); }
    catch(e) { return Number(value).toFixed(0) + ' ر.ع'; }
  }

  var ui = {
    btnInstant: null, btnCertified: null,
    instantSection: null, certifiedSection: null,
    landArea: null, locationSelect: null, buildingAge: null, builtArea: null,
    instantValue: null,
    applicantTiles: null, purposeContainer: null, individualPurposes: null, companyPurposes: null,
    certAmount: null, certBank: null, btnFindCompanies: null,
    companiesGrid: null, companiesEmpty: null, companiesLoading: null
  };

  var state = {
    applicantType: null, // 'individual' | 'company'
    purpose: null
  };

  // Simple heuristic model for instant valuation
  function computeInstantValuation(landArea, location, buildingAge, builtArea){
    var baseLandPrice = 25_000; // fallback for small land
    var locationMultiplier = 1.0;
    switch(location){
      case 'muscat': locationMultiplier = 1.60; break;
      case 'bawshar': locationMultiplier = 1.45; break;
      case 'seeb': locationMultiplier = 1.25; break;
      case 'mabella': locationMultiplier = 1.10; break;
      case 'sohar': locationMultiplier = 1.05; break;
      case 'salalah': locationMultiplier = 1.15; break;
      case 'nizwa': locationMultiplier = 0.95; break;
      default: locationMultiplier = 1.00;
    }

    var landSqmPrice = 45 * locationMultiplier; // OMR per sqm baseline
    var buildingSqmPrice = 120 * locationMultiplier; // OMR per sqm baseline

    var age = Math.max(0, Number(buildingAge)||0);
    var depreciation = Math.min(0.5, age * 0.01); // up to 50%
    var buildingMultiplier = 1 - depreciation;

    var land = Math.max(0, Number(landArea)||0);
    var built = Math.max(0, Number(builtArea)||0);

    var landValue = land * landSqmPrice;
    var buildingValue = built * buildingSqmPrice * buildingMultiplier;
    var total = landValue + buildingValue;

    // ensure a minimum base when inputs are tiny but present
    if (total === 0 && (land > 0 || built > 0)) total = baseLandPrice * locationMultiplier;
    return Math.round(total);
  }

  function updateInstantValuation(){
    var v = computeInstantValuation(
      ui.landArea && ui.landArea.value,
      ui.locationSelect && ui.locationSelect.value,
      ui.buildingAge && ui.buildingAge.value,
      ui.builtArea && ui.builtArea.value
    );
    if (ui.instantValue) ui.instantValue.textContent = formatCurrency(v);
  }

  function markActiveTile(groupRoot, dataAttr, value){
    qsa('.choice-tile', groupRoot).forEach(function(el){ el.classList.remove('active'); });
    var sel = '.choice-tile['+dataAttr+'="'+value+'"]';
    var el = qs(sel, groupRoot);
    if (el) el.classList.add('active');
  }

  function renderCompanies(items){
    var grid = ui.companiesGrid; if (!grid) return;
    grid.innerHTML = '';
    items.forEach(function(item){
      var col = document.createElement('div'); col.className = 'col-12 col-md-6 col-lg-4';
      var card = document.createElement('div'); card.className = 'card h-100 shadow-sm';
      var body = document.createElement('div'); body.className = 'card-body d-flex flex-column';
      var img = document.createElement('img'); img.className = 'mb-3'; img.style.maxHeight = '48px'; img.style.objectFit = 'contain';
      if (item.logo_url) { img.src = item.logo_url; img.alt = item.company_name; }
      else { img.style.display = 'none'; }
      var title = document.createElement('h5'); title.className = 'card-title'; title.textContent = item.company_name;
      var limit = document.createElement('div'); limit.className = 'text-muted small mt-auto';
      var limitText = item.approved_limit!=null ? ('اعتماد لدى البنك حتى ' + formatCurrency(item.approved_limit))
                       : (item.profile_limit!=null ? ('حد الشركة ' + formatCurrency(item.profile_limit)) : '');
      limit.textContent = limitText;
      var cta = document.createElement('a'); cta.className = 'btn btn-primary mt-3'; cta.href = item.apply_url; cta.textContent = 'تقديم طلب لدى الشركة';
      body.appendChild(img); body.appendChild(title); if (limitText) body.appendChild(limit); body.appendChild(cta);
      card.appendChild(body); col.appendChild(card); grid.appendChild(col);
    });
  }

  function fetchCompanies(){
    var amount = Number(ui.certAmount && ui.certAmount.value || 0);
    var bank = ui.certBank && ui.certBank.value;
    if (!bank || !isFinite(amount) || amount <= 0) { ui.companiesGrid.innerHTML = ''; ui.companiesEmpty.style.display = 'block'; return; }
    ui.companiesEmpty.style.display = 'none';
    ui.companiesLoading.style.display = 'block';
    var url = '/client/filter_companies?bank_slug=' + encodeURIComponent(bank) + '&amount=' + encodeURIComponent(amount);
    if (state.applicantType) url += '&applicant_type=' + encodeURIComponent(state.applicantType);
    if (state.purpose) url += '&purpose=' + encodeURIComponent(state.purpose);
    fetch(url, { credentials: 'same-origin' })
      .then(function(r){ return r.json(); })
      .then(function(res){
        ui.companiesLoading.style.display = 'none';
        var items = (res && res.items) || [];
        if (!items.length) { ui.companiesGrid.innerHTML=''; ui.companiesEmpty.style.display='block'; return; }
        renderCompanies(items);
      })
      .catch(function(){ ui.companiesLoading.style.display='none'; ui.companiesEmpty.style.display='block'; });
  }

  function attach(){
    ui.btnInstant = byId('btnInstant');
    ui.btnCertified = byId('btnCertified');
    ui.instantSection = byId('instantValuationSection');
    ui.certifiedSection = byId('certifiedValuationSection');

    ui.landArea = byId('landArea');
    ui.locationSelect = byId('locationSelect');
    ui.buildingAge = byId('buildingAge');
    ui.builtArea = byId('builtArea');
    ui.instantValue = byId('instantValuationValue');

    ui.applicantTiles = qsa('.choice-tile[data-applicant]');
    ui.purposeContainer = byId('purposeContainer');
    ui.individualPurposes = byId('individualPurposes');
    ui.companyPurposes = byId('companyPurposes');

    ui.certAmount = byId('certAmount');
    ui.certBank = byId('certBankSelect');
    ui.btnFindCompanies = byId('btnFindCompanies');
    ui.companiesGrid = byId('companiesGrid');
    ui.companiesEmpty = byId('companiesEmpty');
    ui.companiesLoading = byId('companiesLoading');

    if (ui.btnInstant) ui.btnInstant.addEventListener('click', function(){
      ui.instantSection.style.display = '';
      ui.certifiedSection.style.display = 'none';
    });
    if (ui.btnCertified) ui.btnCertified.addEventListener('click', function(){
      ui.instantSection.style.display = 'none';
      ui.certifiedSection.style.display = '';
    });

    ;['input','change'].forEach(function(evt){
      if (ui.landArea) ui.landArea.addEventListener(evt, updateInstantValuation);
      if (ui.locationSelect) ui.locationSelect.addEventListener(evt, updateInstantValuation);
      if (ui.buildingAge) ui.buildingAge.addEventListener(evt, updateInstantValuation);
      if (ui.builtArea) ui.builtArea.addEventListener(evt, updateInstantValuation);
    });

    ui.applicantTiles.forEach(function(el){
      el.addEventListener('click', function(){
        state.applicantType = el.getAttribute('data-applicant');
        markActiveTile(document, 'data-applicant', state.applicantType);
        ui.purposeContainer.style.display = '';
        ui.individualPurposes.style.display = state.applicantType==='individual' ? '' : 'none';
        ui.companyPurposes.style.display = state.applicantType==='company' ? '' : 'none';
        state.purpose = null; // reset purpose until selected
        qsa('.choice-tile[data-purpose]').forEach(function(p){ p.classList.remove('active'); });
      });
    });

    qsa('.choice-tile[data-purpose]').forEach(function(el){
      el.addEventListener('click', function(){
        state.purpose = el.getAttribute('data-purpose');
        markActiveTile(document, 'data-purpose', state.purpose);
      });
    });

    if (ui.btnFindCompanies) ui.btnFindCompanies.addEventListener('click', function(e){ e.preventDefault(); fetchCompanies(); });
    if (ui.certAmount) ui.certAmount.addEventListener('input', function(){ /* debounce could be added */ });
    if (ui.certBank) ui.certBank.addEventListener('change', function(){ /* wait for explicit click */ });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
  else attach();
})();
