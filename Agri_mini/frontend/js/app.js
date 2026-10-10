/**
 * Agri_mini - Agricultural Decision-Support & Price Prediction Client
 * Communicates with FastAPI backend:
 *   - POST /api/v1/predict/price  (Workflow 1: Price Prediction — preserved)
 *   - POST /api/recommend/ceda    (Workflow 2: CEDA TOPSIS Multi-Market Recommendation)
 *   - GET /health (Backend Health Check)
 */

// -----------------------------------------------------------------------------
// 1. Configuration & API Base URL Detection
// -----------------------------------------------------------------------------
const API_BASE_URL = (function () {
  const origin = window.location.origin;
  if (origin && (origin.startsWith('http://') || origin.startsWith('https://')) && !origin.includes('file://')) {
    if (window.location.port === '8001') {
      return '';
    }
  }
  return 'http://127.0.0.1:8001';
})();

// -----------------------------------------------------------------------------
// 2. Presets Dictionary
// -----------------------------------------------------------------------------
const PREDICTION_PRESETS = {
  tomato_thrissur: {
    commodity: 'Tomato',
    market: 'Thrissur APMC (Sakthan Market)',
    district: 'Thrissur',
    state: 'Kerala',
    variety: 'Hybrid',
    prediction_date: '2026-08-28',
  },
  onion_chalakudy: {
    commodity: 'Onion',
    market: 'Chalakudy Wholesale Market',
    district: 'Thrissur',
    state: 'Kerala',
    variety: 'Red / Nasik',
    prediction_date: '2026-08-28',
  },
  banana_kunnamkulam: {
    commodity: 'Banana',
    market: 'Kunnamkulam Market',
    district: 'Thrissur',
    state: 'Kerala',
    variety: 'Robusta',
    prediction_date: '2026-08-28',
  },
  potato_kodungallur: {
    commodity: 'Potato',
    market: 'Kodungallur Market',
    district: 'Thrissur',
    state: 'Kerala',
    variety: 'Jyoti',
    prediction_date: '2026-08-28',
  },
};

const DEFAULT_CANDIDATE_MARKETS = [
  { market: 'Thrissur APMC (Sakthan Market)', district: 'Thrissur', state: 'Kerala', destination_name: 'Thrissur, Kerala', destination_lat: 10.5276, destination_lon: 76.2144 },
  { market: 'Chalakudy Wholesale Market', district: 'Thrissur', state: 'Kerala', destination_name: 'Chalakudy, Kerala', destination_lat: 10.3070, destination_lon: 76.3335 },
  { market: 'Kunnamkulam Market', district: 'Thrissur', state: 'Kerala', destination_name: 'Kunnamkulam, Kerala', destination_lat: 10.6508, destination_lon: 76.0711 },
  { market: 'Kodungallur Market', district: 'Thrissur', state: 'Kerala', destination_name: 'Kodungallur, Kerala', destination_lat: 10.2216, destination_lon: 76.1953 },
];

// Verified Model-Supported Candidate Mandis Catalog
// Only mandis with verified CEDA history and verified GPS coordinates are included.
// Unverified / missing-coordinate mandis are excluded from route-based recommendations.
const CANDIDATE_MARKETS_CATALOG = [
  {
    market_id: 147,
    district_id: 594,
    market_name: 'Thrissur APMC (Sakthan Market)',
    district_name: 'Thrissur',
    lat: 10.5276,
    lon: 76.2144,
    is_thrissur: true,
    supported_commodities: [19, 23, 24, 35, 78, 87, 90, 153, 154],
  },
  {
    market_id: 2152,
    district_id: 594,
    market_name: 'Chalakudy Wholesale Market',
    district_name: 'Thrissur',
    lat: 10.3070,
    lon: 76.3335,
    is_thrissur: true,
    supported_commodities: [23, 24, 35, 78, 87, 90, 153, 154], // Excludes 19 (Banana) and 152 (Sweet Potato)
  },
  {
    market_id: 2366,
    district_id: 594,
    market_name: 'Kunnamkulam Market',
    district_name: 'Thrissur',
    lat: 10.6508,
    lon: 76.0711,
    is_thrissur: true,
    supported_commodities: [19, 23, 24, 35, 78, 87, 90, 153, 154],
  },
  {
    market_id: 2364,
    district_id: 594,
    market_name: 'Kodungallur Market',
    district_name: 'Thrissur',
    lat: 10.2216,
    lon: 76.1953,
    is_thrissur: true,
    supported_commodities: [19, 23, 24, 35, 78, 87, 90, 153, 154],
  }
];

// -----------------------------------------------------------------------------
// 3. DOM Elements Registry
// -----------------------------------------------------------------------------
const elements = {
  // Navigation Tabs
  tabPrediction: document.getElementById('tab-prediction'),
  tabRecommendation: document.getElementById('tab-recommendation'),
  viewPrediction: document.getElementById('prediction-view'),
  viewRecommendation: document.getElementById('recommendation-view'),

  // Status & Global Alerts
  statusPill: document.getElementById('backend-status-pill'),
  statusText: document.getElementById('status-text'),
  alertBanner: document.getElementById('alert-banner'),
  alertTitle: document.getElementById('alert-title'),
  alertMessage: document.getElementById('alert-message'),
  alertIcon: document.getElementById('alert-icon'),
  alertClose: document.getElementById('alert-close'),

  // Workflow 1: Prediction Form & Outputs
  formPrediction: document.getElementById('prediction-form'),
  commodityInput: document.getElementById('commodity-input'),
  varietyInput: document.getElementById('variety-input'),
  marketInput: document.getElementById('market-input'),
  districtInput: document.getElementById('district-input'),
  stateInput: document.getElementById('state-input'),
  dateInput: document.getElementById('prediction-date-input'),
  predictBtn: document.getElementById('predict-btn'),
  btnSpinner: document.getElementById('btn-spinner'),
  btnIcon: document.getElementById('btn-icon'),
  btnLabel: document.getElementById('btn-label'),
  resetFormBtn: document.getElementById('reset-form-btn'),
  presetBtns: document.querySelectorAll('#prediction-view .preset-btn'),

  emptyStatePred: document.getElementById('empty-state'),
  loadingStatePred: document.getElementById('loading-state'),
  resultsCardPred: document.getElementById('results-card'),

  resPredictedPrice: document.getElementById('res-predicted-price'),
  resHeroPriceKg: document.getElementById('res-hero-price-kg'),
  resPricePerKg: document.getElementById('res-price-per-kg'),
  resLatestPrice: document.getElementById('res-latest-price'),
  resLatestPriceKg: document.getElementById('res-latest-price-kg'),
  resModelUsed: document.getElementById('res-model-used'),
  resFeaturesCount: document.getElementById('res-features-count'),
  resHistPoints: document.getElementById('res-hist-points'),
  resTimestamp: document.getElementById('res-timestamp'),
  resCommodityVariety: document.getElementById('res-commodity-variety'),
  resArrivalDate: document.getElementById('res-arrival-date'),
  resMarket: document.getElementById('res-market'),
  resDistrictState: document.getElementById('res-district-state'),

  weatherCard: document.getElementById('context-weather-card'),
  badgeWeather: document.getElementById('badge-weather'),
  faostatCard: document.getElementById('context-faostat-card'),
  badgeFaostat: document.getElementById('badge-faostat'),
  routeCard: document.getElementById('context-route-card'),
  badgeRoute: document.getElementById('badge-route'),

  // Workflow 2: Recommendation Form & Outputs
  formRecommendation: document.getElementById('recommendation-form'),
  recCommoditySelect: document.getElementById('rec-commodity-select'),
  recDateInput: document.getElementById('rec-date-input'),
  recOriginNameInput: document.getElementById('rec-origin-name-input'),
  recOriginLatInput: document.getElementById('rec-origin-lat-input'),
  recOriginLonInput: document.getElementById('rec-origin-lon-input'),
  recQuantityInput: document.getElementById('rec-quantity-input'),
  recQuintalsHint: document.getElementById('rec-quintals-hint'),
  recVehicleInput: document.getElementById('rec-vehicle-input'),
  recVehicleHint: document.getElementById('rec-vehicle-hint'),
  recFuelPriceInput: document.getElementById('rec-fuel-price-input'),
  recProductionCostInput: document.getElementById('rec-production-cost-input'),

  selectedMarketsCountBadge: document.getElementById('selected-markets-count'),
  candidateMarketsList: document.getElementById('candidate-markets-list'),
  candidateCheckboxes: document.querySelectorAll('.candidate-market-checkbox'),
  candidateCards: document.querySelectorAll('.candidate-market-card'),

  // Collapsible Weights
  toggleWeightsBtn: document.getElementById('toggle-weights-btn'),
  weightsBody: document.getElementById('weights-body'),
  weightProfitInput: document.getElementById('weight-profit-input'),
  weightPriceInput: document.getElementById('weight-price-input'),
  weightCostInput: document.getElementById('weight-cost-input'),
  weightTimeInput: document.getElementById('weight-time-input'),
  weightSpoilInput: document.getElementById('weight-spoil-input'),
  weightProfitVal: document.getElementById('weight-profit-val'),
  weightPriceVal: document.getElementById('weight-price-val'),
  weightCostVal: document.getElementById('weight-cost-val'),
  weightTimeVal: document.getElementById('weight-time-val'),
  weightSpoilVal: document.getElementById('weight-spoil-val'),
  weightsTotalBadge: document.getElementById('weights-total-badge'),
  resetWeightsBtn: document.getElementById('reset-weights-btn'),

  recBtn: document.getElementById('recommend-btn'),
  recBtnSpinner: document.getElementById('rec-btn-spinner'),
  recBtnIcon: document.getElementById('rec-btn-icon'),
  recBtnLabel: document.getElementById('rec-btn-label'),
  resetRecFormBtn: document.getElementById('reset-rec-form-btn'),
  recPresetTomato: document.getElementById('rec-preset-tomato-thrissur'),
  recPresetBanana: document.getElementById('rec-preset-banana-thrissur'),

  recEmptyState: document.getElementById('rec-empty-state'),
  recLoadingState: document.getElementById('rec-loading-state'),
  recResultsContainer: document.getElementById('rec-results-container'),

  // Hero Recommendation Card Fields
  recHeroTopsisScore: document.getElementById('rec-hero-topsis-score'),
  recHeroMarketName: document.getElementById('rec-hero-market-name'),
  recHeroLocation: document.getElementById('rec-hero-location'),
  recHeroProfitLabel: document.getElementById('rec-hero-profit-label'),
  recHeroProfitVal: document.getElementById('rec-hero-profit-val'),
  recHeroPriceVal: document.getElementById('rec-hero-price-val'),
  recHeroPriceKgVal: document.getElementById('rec-hero-price-kg-val'),
  recHeroFreightVal: document.getElementById('rec-hero-freight-val'),
  recHeroDist: document.getElementById('rec-hero-dist'),
  recHeroTime: document.getElementById('rec-hero-time'),
  recHeroSpoil: document.getElementById('rec-hero-spoil'),
  recHeroSellable: document.getElementById('rec-hero-sellable'),
  recHeroRationale: document.getElementById('rec-hero-rationale'),

  // Table & Criteria Elements
  rankingsTableBody: document.getElementById('rankings-table-body'),
  criteriaTableBody: document.getElementById('criteria-table-body'),
  failedCandidatesBox: document.getElementById('rec-failed-candidates-box'),
  failedCandidatesList: document.getElementById('rec-failed-candidates-list'),
};

// -----------------------------------------------------------------------------
// 4. Initialization
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Load default price prediction preset
  loadPredictionPreset('tomato_thrissur');

  // Check backend service availability
  checkBackendHealth();

  // Setup tab switches, form listeners, and weight bindings
  setupEventListeners();

  // Render initial candidate markets for default commodity (Tomato = 78)
  renderCandidateMarketsForCommodity(78);

  // Initialize vehicle suggestion for default load
  updateVehicleSuggestion(elements.recQuantityInput?.value || 1000);
});

// -----------------------------------------------------------------------------
// 5. Event Listeners Setup
// -----------------------------------------------------------------------------
function setupEventListeners() {
  // 1. Workflow Tab Switcher
  elements.tabPrediction?.addEventListener('click', () => switchWorkflowTab('prediction'));
  elements.tabRecommendation?.addEventListener('click', () => switchWorkflowTab('recommendation'));

  // 2. Price Prediction Preset Buttons
  elements.presetBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const key = e.currentTarget.getAttribute('data-preset');
      if (key && PREDICTION_PRESETS[key]) {
        elements.presetBtns.forEach((b) => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        loadPredictionPreset(key);
      }
    });
  });

  // 3. Price Prediction Form Submit & Reset
  elements.formPrediction?.addEventListener('submit', handlePredictionSubmit);
  elements.resetFormBtn?.addEventListener('click', () => {
    loadPredictionPreset('tomato_thrissur');
    elements.presetBtns.forEach((b) => b.classList.remove('active'));
    document.querySelector('#prediction-view .preset-btn[data-preset="tomato_thrissur"]')?.classList.add('active');
    hideAlert();
  });

  // 4. Recommendation Candidate Checkboxes (Delegated on container)
  elements.candidateMarketsList?.addEventListener('change', (e) => {
    if (e.target.matches('.candidate-market-checkbox')) {
      const card = e.target.closest('.candidate-market-card');
      if (e.target.checked) {
        card?.classList.add('selected');
      } else {
        card?.classList.remove('selected');
      }
      updateSelectedCandidateCount();
    }
  });

  // 4b. Dynamically update candidate markets when selected commodity changes
  elements.recCommoditySelect?.addEventListener('change', (e) => {
    const commId = parseInt(e.target.value, 10);
    renderCandidateMarketsForCommodity(commId);
  });

  // 5. Quantity Input Live Hint & Automatic Vehicle Recommendation
  elements.recQuantityInput?.addEventListener('input', (e) => {
    updateVehicleSuggestion(e.target.value);
  });

  // 5b. Farmer Manual Vehicle Selection Tracking
  elements.recVehicleInput?.addEventListener('change', () => {
    userManuallySelectedVehicle = true;
    const kg = parseFloat(elements.recQuantityInput?.value) || 0;
    if (elements.recVehicleHint && kg > 0) {
      const selected = elements.recVehicleInput.options[elements.recVehicleInput.selectedIndex]?.text || '';
      elements.recVehicleHint.textContent = `Manual selection: ${selected}`;
    }
  });

  // 6. Collapsible Decision Priorities
  elements.toggleWeightsBtn?.addEventListener('click', () => {
    const isExpanded = elements.toggleWeightsBtn.getAttribute('aria-expanded') === 'true';
    elements.toggleWeightsBtn.setAttribute('aria-expanded', !isExpanded);
    elements.weightsBody?.classList.toggle('hidden', isExpanded);
  });

  // 7. Weight Sliders Live Updates
  const weightSliders = [
    { input: elements.weightProfitInput, label: elements.weightProfitVal },
    { input: elements.weightPriceInput, label: elements.weightPriceVal },
    { input: elements.weightCostInput, label: elements.weightCostVal },
    { input: elements.weightTimeInput, label: elements.weightTimeVal },
    { input: elements.weightSpoilInput, label: elements.weightSpoilVal },
  ];

  weightSliders.forEach(({ input, label }) => {
    input?.addEventListener('input', () => {
      if (label) label.textContent = `${input.value}%`;
      updateWeightsTotal();
    });
  });

  elements.resetWeightsBtn?.addEventListener('click', resetDefaultWeights);

  // 8. Recommendation Demo Presets
  elements.recPresetTomato?.addEventListener('click', () => loadRecommendationPreset('tomato'));
  elements.recPresetBanana?.addEventListener('click', () => loadRecommendationPreset('banana'));

  // 9. Recommendation Form Submit & Reset
  elements.formRecommendation?.addEventListener('submit', handleRecommendationSubmit);
  elements.resetRecFormBtn?.addEventListener('click', () => loadRecommendationPreset('tomato'));

  // 10. Alert close
  elements.alertClose?.addEventListener('click', hideAlert);
}

// -----------------------------------------------------------------------------
// 6. Tab Switcher
// -----------------------------------------------------------------------------
function switchWorkflowTab(target) {
  hideAlert();
  if (target === 'prediction') {
    elements.tabPrediction?.classList.add('active');
    elements.tabPrediction?.setAttribute('aria-selected', 'true');
    elements.tabRecommendation?.classList.remove('active');
    elements.tabRecommendation?.setAttribute('aria-selected', 'false');

    elements.viewPrediction?.classList.add('active');
    elements.viewPrediction?.classList.remove('hidden');
    elements.viewRecommendation?.classList.remove('active');
    elements.viewRecommendation?.classList.add('hidden');
  } else {
    elements.tabRecommendation?.classList.add('active');
    elements.tabRecommendation?.setAttribute('aria-selected', 'true');
    elements.tabPrediction?.classList.remove('active');
    elements.tabPrediction?.setAttribute('aria-selected', 'false');

    elements.viewRecommendation?.classList.add('active');
    elements.viewRecommendation?.classList.remove('hidden');
    elements.viewPrediction?.classList.remove('active');
    elements.viewPrediction?.classList.add('hidden');
  }
}

// -----------------------------------------------------------------------------
// 7. Load Presets
// -----------------------------------------------------------------------------
function loadPredictionPreset(key) {
  const p = PREDICTION_PRESETS[key];
  if (!p) return;
  if (elements.commodityInput) elements.commodityInput.value = p.commodity;
  if (elements.varietyInput) elements.varietyInput.value = p.variety;
  if (elements.marketInput) elements.marketInput.value = p.market;
  if (elements.districtInput) elements.districtInput.value = p.district;
  if (elements.stateInput) elements.stateInput.value = p.state;
  if (elements.dateInput) elements.dateInput.value = p.prediction_date;
}

function getCandidateCheckboxes() {
  return elements.candidateMarketsList
    ? Array.from(elements.candidateMarketsList.querySelectorAll('.candidate-market-checkbox'))
    : Array.from(document.querySelectorAll('.candidate-market-checkbox'));
}

function renderCandidateMarketsForCommodity(commodityId, forcedCheckedIds = null) {
  if (!elements.candidateMarketsList) return;

  const supported = CANDIDATE_MARKETS_CATALOG.filter((m) =>
    m.supported_commodities.includes(commodityId)
  );

  if (supported.length === 0) {
    elements.candidateMarketsList.innerHTML = `
      <div style="padding: 1rem; color: var(--text-muted); font-size: 0.875rem;">
        ⚠️ No verified markets currently contain sufficient historical records for this commodity in the retrained model.
      </div>
    `;
    updateSelectedCandidateCount();
    return;
  }

  // Sort: Thrissur markets first, then regional
  supported.sort((a, b) => {
    if (a.is_thrissur && !b.is_thrissur) return -1;
    if (!a.is_thrissur && b.is_thrissur) return 1;
    return a.market_name.localeCompare(b.market_name);
  });

  const cardsHtml = supported.map((m) => {
    let isChecked = false;
    if (forcedCheckedIds !== null) {
      isChecked = forcedCheckedIds.includes(m.market_id);
    } else {
      // Prioritize eligible Thrissur district mandis by auto-selecting them
      isChecked = m.is_thrissur;
      // If no Thrissur markets support this commodity, check available regional mandis
      const thrissurCount = supported.filter((x) => x.is_thrissur).length;
      if (thrissurCount === 0) {
        isChecked = true;
      }
    }

    const selectedClass = isChecked ? 'selected' : '';
    const checkedAttr = isChecked ? 'checked' : '';

    return `
      <label class="candidate-market-card ${selectedClass}">
        <input type="checkbox" class="candidate-market-checkbox" ${checkedAttr}
          data-market-id="${m.market_id}" data-district-id="${m.district_id}"
          data-market-name="${m.market_name}"
          data-lat="${m.lat}" data-lon="${m.lon}">
        <div class="candidate-market-details">
          <div class="candidate-name">${m.market_name}</div>
          <div class="candidate-meta">📍 ${m.district_name} District (ID ${m.district_id}) &bull; market_id ${m.market_id}</div>
        </div>
        <span class="candidate-check-icon">✓</span>
      </label>
    `;
  }).join('');

  elements.candidateMarketsList.innerHTML = cardsHtml;
  updateSelectedCandidateCount();
}

let userManuallySelectedVehicle = false;

function updateVehicleSuggestion(quantityKg) {
  const kg = parseFloat(quantityKg) || 0;
  const qtl = kg / 100.0;
  const qtlStr = qtl % 1 === 0 ? qtl.toFixed(1) : qtl.toFixed(2);
  const unitStr = qtl === 1.0 ? 'quintal' : 'quintals';

  if (elements.recQuintalsHint) {
    elements.recQuintalsHint.textContent = `${qtlStr} ${unitStr}`;
  }

  // Determine ideal vehicle based on weight capacity
  let idealVehicle = 'three_wheeler';
  let idealLabel = 'Three-Wheeler Cargo Auto';
  if (kg > 7500) {
    idealVehicle = 'large_truck';
    idealLabel = 'Large Truck';
  } else if (kg > 2500) {
    idealVehicle = 'medium_truck';
    idealLabel = 'Medium Truck';
  } else if (kg > 1500) {
    idealVehicle = 'pickup';
    idealLabel = 'Pickup';
  } else if (kg > 500) {
    idealVehicle = 'mini_truck';
    idealLabel = 'Mini Truck';
  } else {
    idealVehicle = 'three_wheeler';
    idealLabel = 'Three-Wheeler Cargo Auto';
  }

  // If farmer has not manually overridden vehicle choice, cleanly recommend and set the ideal vehicle
  if (!userManuallySelectedVehicle && elements.recVehicleInput && kg > 0) {
    elements.recVehicleInput.value = idealVehicle;
  }

  if (elements.recVehicleHint) {
    if (kg > 0) {
      elements.recVehicleHint.textContent = `Suggested for ${kg} kg: ${idealLabel}`;
    } else {
      elements.recVehicleHint.textContent = 'Select cargo vehicle';
    }
  }
}

function loadRecommendationPreset(type) {
  if (type === 'tomato') {
    elements.recPresetTomato?.classList.add('active');
    elements.recPresetBanana?.classList.remove('active');

    // Tomato = commodity_id 78
    if (elements.recCommoditySelect) elements.recCommoditySelect.value = '78';
    if (elements.recDateInput) elements.recDateInput.value = '2025-10-15';
    if (elements.recOriginNameInput) elements.recOriginNameInput.value = 'Thrissur Farm, Kerala';
    if (elements.recOriginLatInput) elements.recOriginLatInput.value = 10.5276;
    if (elements.recOriginLonInput) elements.recOriginLonInput.value = 76.2144;
    if (elements.recQuantityInput) {
      elements.recQuantityInput.value = 1000;
      elements.recQuintalsHint.textContent = '10.0 quintals';
    }
    if (elements.recVehicleInput) elements.recVehicleInput.value = 'mini_truck';
    if (elements.recFuelPriceInput) elements.recFuelPriceInput.value = 95.0;
    if (elements.recProductionCostInput) elements.recProductionCostInput.value = '';

    userManuallySelectedVehicle = false;
    updateVehicleSuggestion(1000);

    // Render candidate markets for Tomato (78) and preselect all 4 Thrissur markets
    renderCandidateMarketsForCommodity(78, [147, 2152, 2366, 2364]);
    resetDefaultWeights();
  } else if (type === 'banana') {
    elements.recPresetBanana?.classList.add('active');
    elements.recPresetTomato?.classList.remove('active');

    // Banana = commodity_id 19
    if (elements.recCommoditySelect) elements.recCommoditySelect.value = '19';
    if (elements.recDateInput) elements.recDateInput.value = '2025-10-15';
    if (elements.recOriginNameInput) elements.recOriginNameInput.value = 'Thrissur Farm, Kerala';
    if (elements.recOriginLatInput) elements.recOriginLatInput.value = 10.5276;
    if (elements.recOriginLonInput) elements.recOriginLonInput.value = 76.2144;
    if (elements.recQuantityInput) {
      elements.recQuantityInput.value = 1000;
      elements.recQuintalsHint.textContent = '10.0 quintals';
    }
    if (elements.recVehicleInput) elements.recVehicleInput.value = 'mini_truck';
    if (elements.recFuelPriceInput) elements.recFuelPriceInput.value = 95.0;
    if (elements.recProductionCostInput) elements.recProductionCostInput.value = '';

    userManuallySelectedVehicle = false;
    updateVehicleSuggestion(1000);

    // Render candidate markets for Banana (19) and preselect supported Thrissur markets (147, 2366, 2364)
    // Note: Chalakudy (2152) has no Banana history in CEDA and is cleanly excluded
    renderCandidateMarketsForCommodity(19, [147, 2366, 2364]);
    resetDefaultWeights();
  }
}

function updateSelectedCandidateCount() {
  const selected = getCandidateCheckboxes().filter((cb) => cb.checked);
  if (elements.selectedMarketsCountBadge) {
    elements.selectedMarketsCountBadge.textContent = `${selected.length} Selected`;
    if (selected.length < 2) {
      elements.selectedMarketsCountBadge.style.background = 'var(--danger-bg)';
      elements.selectedMarketsCountBadge.style.color = 'var(--danger-text)';
    } else {
      elements.selectedMarketsCountBadge.style.background = 'var(--primary-100)';
      elements.selectedMarketsCountBadge.style.color = 'var(--primary-800)';
    }
  }
}

function resetDefaultWeights() {
  if (elements.weightProfitInput) elements.weightProfitInput.value = 40;
  if (elements.weightPriceInput) elements.weightPriceInput.value = 20;
  if (elements.weightCostInput) elements.weightCostInput.value = 15;
  if (elements.weightTimeInput) elements.weightTimeInput.value = 10;
  if (elements.weightSpoilInput) elements.weightSpoilInput.value = 15;

  if (elements.weightProfitVal) elements.weightProfitVal.textContent = '40%';
  if (elements.weightPriceVal) elements.weightPriceVal.textContent = '20%';
  if (elements.weightCostVal) elements.weightCostVal.textContent = '15%';
  if (elements.weightTimeVal) elements.weightTimeVal.textContent = '10%';
  if (elements.weightSpoilVal) elements.weightSpoilVal.textContent = '15%';

  updateWeightsTotal();
}

function updateWeightsTotal() {
  const p = parseInt(elements.weightProfitInput?.value || 40, 10);
  const pr = parseInt(elements.weightPriceInput?.value || 20, 10);
  const c = parseInt(elements.weightCostInput?.value || 15, 10);
  const t = parseInt(elements.weightTimeInput?.value || 10, 10);
  const s = parseInt(elements.weightSpoilInput?.value || 15, 10);
  const total = p + pr + c + t + s;

  if (elements.weightsTotalBadge) {
    elements.weightsTotalBadge.textContent = `Total: ${total}%`;
    if (total === 100) {
      elements.weightsTotalBadge.className = 'badge badge-success';
    } else {
      elements.weightsTotalBadge.className = 'badge badge-primary';
    }
  }
}

// -----------------------------------------------------------------------------
// 8. Backend Health Check
// -----------------------------------------------------------------------------
async function checkBackendHealth() {
  if (!elements.statusPill || !elements.statusText) return;
  elements.statusPill.className = 'status-pill checking';
  elements.statusText.textContent = 'Connecting...';

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    if (response.ok) {
      const data = await response.json();
      elements.statusPill.className = 'status-pill online';
      elements.statusText.textContent = `Backend Online • ${data.version || 'v1.0.0'}`;
    } else {
      elements.statusPill.className = 'status-pill offline';
      elements.statusText.textContent = 'Backend Error';
    }
  } catch (err) {
    elements.statusPill.className = 'status-pill offline';
    elements.statusText.textContent = 'Backend Offline';
    console.warn('Backend connection failed:', err);
  }
}

// -----------------------------------------------------------------------------
// 9. Workflow 1: Handle Price Prediction Submit
// -----------------------------------------------------------------------------
async function handlePredictionSubmit(e) {
  e.preventDefault();
  hideAlert();

  const payload = {
    commodity: elements.commodityInput.value.trim(),
    variety: elements.varietyInput.value.trim(),
    market: elements.marketInput.value.trim(),
    district: elements.districtInput.value.trim(),
    state: elements.stateInput.value.trim(),
    prediction_date: elements.dateInput.value.trim(),
  };

  if (!payload.commodity || !payload.market || !payload.district || !payload.state || !payload.variety || !payload.prediction_date) {
    showAlert('Validation Error', 'Please complete all required fields with valid values.', 'error');
    return;
  }

  setPredictionLoading(true);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/predict/price`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (response.ok && data.status === 'success') {
      renderPredictionResult(data);
      const modalQtl = Number(data.predicted_modal_price);
      const modalKg = modalQtl / 100.0;
      showAlert('Prediction Success', `Predicted modal price: ₹ ${modalQtl.toFixed(2)}/qtl (₹ ${modalKg.toFixed(2)}/kg) for ${data.commodity} at ${data.market}.`, 'success');
    } else {
      const errorMsg = data.detail || (Array.isArray(data) ? JSON.stringify(data) : 'Prediction service error.');
      showAlert('Prediction Failed', errorMsg, 'error');
      showPredictionEmptyState();
    }
  } catch (err) {
    console.error('Inference request failed:', err);
    showAlert('Network Error', `Failed to reach backend at ${API_BASE_URL || 'localhost:8000'}. Ensure the backend is running.`, 'error');
    showPredictionEmptyState();
  } finally {
    setPredictionLoading(false);
  }
}

function renderPredictionResult(data) {
  const modalPrice = Number(data.predicted_modal_price) || 0;
  const priceKg = modalPrice / 100.0;
  const latestPrice = Number(data.latest_known_price) || modalPrice;
  const latestPriceKg = latestPrice / 100.0;

  elements.resPredictedPrice.textContent = modalPrice.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (elements.resHeroPriceKg) {
    elements.resHeroPriceKg.textContent = priceKg.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  elements.resPricePerKg.textContent = `₹ ${priceKg.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} / kg`;

  elements.resLatestPrice.textContent = `₹ ${latestPrice.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} / qtl`;

  if (elements.resLatestPriceKg) {
    elements.resLatestPriceKg.textContent = `(₹ ${latestPriceKg.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} / kg)`;
  }

  elements.resModelUsed.textContent = data.model_used || 'Random Forest (Tuned)';
  elements.resFeaturesCount.textContent = `${data.features_used_count || 54} Features`;
  elements.resHistPoints.textContent = `${data.historical_data_points_used || 0} Records`;

  updateContextBadge(elements.weatherCard, elements.badgeWeather, data.weather_matched, 'Live Weather Matched', 'Default Weather Fallback');
  updateContextBadge(elements.faostatCard, elements.badgeFaostat, data.faostat_matched, 'FAOSTAT Matched', 'Default Macro Fallback');
  updateContextBadge(elements.routeCard, elements.badgeRoute, data.route_matched, 'Road Route Matched', 'Default Route Fallback');

  elements.resCommodityVariety.textContent = `${data.commodity} (${data.variety})`;
  elements.resArrivalDate.textContent = data.prediction_date;
  elements.resMarket.textContent = data.market;
  elements.resDistrictState.textContent = `${data.district}, ${data.state}`;

  if (data.prediction_timestamp) {
    const d = new Date(data.prediction_timestamp);
    elements.resTimestamp.textContent = `Generated: ${d.toLocaleTimeString()} (${d.toLocaleDateString()})`;
  } else {
    elements.resTimestamp.textContent = 'Generated just now';
  }

  elements.emptyStatePred?.classList.add('hidden');
  elements.loadingStatePred?.classList.add('hidden');
  elements.resultsCardPred?.classList.remove('hidden');
}

function updateContextBadge(cardEl, pillEl, isMatched, matchedText, fallbackText) {
  if (!cardEl || !pillEl) return;
  if (isMatched) {
    cardEl.classList.remove('unmatched');
    cardEl.classList.add('matched');
    pillEl.textContent = '✓ ' + matchedText;
  } else {
    cardEl.classList.remove('matched');
    cardEl.classList.add('unmatched');
    pillEl.textContent = '— ' + fallbackText;
  }
}

function setPredictionLoading(isLoading) {
  if (isLoading) {
    elements.predictBtn.disabled = true;
    elements.btnSpinner?.classList.remove('hidden');
    elements.btnIcon?.classList.add('hidden');
    elements.btnLabel.textContent = 'Running Inference...';

    elements.emptyStatePred?.classList.add('hidden');
    elements.resultsCardPred?.classList.add('hidden');
    elements.loadingStatePred?.classList.remove('hidden');
  } else {
    elements.predictBtn.disabled = false;
    elements.btnSpinner?.classList.add('hidden');
    elements.btnIcon?.classList.remove('hidden');
    elements.btnLabel.textContent = 'Predict Expected Modal Price';
    elements.loadingStatePred?.classList.add('hidden');
  }
}

function showPredictionEmptyState() {
  elements.resultsCardPred?.classList.add('hidden');
  elements.loadingStatePred?.classList.add('hidden');
  elements.emptyStatePred?.classList.remove('hidden');
}

// -----------------------------------------------------------------------------
// 10. Workflow 2: Handle CEDA Market Recommendation Submit
// Calls POST /api/recommend/ceda (CEDA RF model + OSRM + TOPSIS)
// -----------------------------------------------------------------------------
async function handleRecommendationSubmit(e) {
  e.preventDefault();
  hideAlert();

  // 1. Gather candidate markets from checkboxes (genuine AGMARKNET market_id/district_id)
  const candidateMarkets = [];
  getCandidateCheckboxes().forEach((cb) => {
    if (cb.checked) {
      const marketId   = parseInt(cb.getAttribute('data-market-id'), 10);
      const districtId = parseInt(cb.getAttribute('data-district-id'), 10);
      const marketName = cb.getAttribute('data-market-name') || '';
      const lat = parseFloat(cb.getAttribute('data-lat'));
      const lon = parseFloat(cb.getAttribute('data-lon'));
      if (marketId && districtId && !isNaN(lat) && !isNaN(lon)) {
        candidateMarkets.push({
          market_id:       marketId,
          district_id:     districtId,
          market_name:     marketName,
          destination_lat: lat,
          destination_lon: lon,
        });
      }
    }
  });

  if (candidateMarkets.length < 2) {
    showAlert('Selection Error', 'Please select at least 2 candidate markets for TOPSIS ranking.', 'error');
    return;
  }

  // 2. Build CEDA request payload
  const commodityId   = parseInt(elements.recCommoditySelect?.value || 78, 10);
  const predictionDate = elements.recDateInput?.value?.trim();
  const originLat     = parseFloat(elements.recOriginLatInput?.value);
  const originLon     = parseFloat(elements.recOriginLonInput?.value);
  const quantityKg    = parseFloat(elements.recQuantityInput?.value);
  const vehicleType   = elements.recVehicleInput?.value || 'mini_truck';
  const fuelPrice     = parseFloat(elements.recFuelPriceInput?.value) || 95.0;
  const prodCostVal   = elements.recProductionCostInput?.value?.trim();
  const productionCost = prodCostVal !== '' ? parseFloat(prodCostVal) : null;

  if (!predictionDate || isNaN(originLat) || isNaN(originLon) || isNaN(quantityKg) || quantityKg <= 0) {
    showAlert('Validation Error', 'Please fill in all required fields (date, coordinates, quantity).', 'error');
    return;
  }

  const payload = {
    commodity_id:       commodityId,
    quantity_kg:        quantityKg,
    source_latitude:    originLat,
    source_longitude:   originLon,
    prediction_date:    predictionDate,
    candidate_markets:  candidateMarkets,
    vehicle_type:       vehicleType,
    fuel_price_per_litre: fuelPrice,
    toll_charges:       0.0,
    other_charges:      0.0,
    production_cost:    productionCost,
  };

  setRecommendationLoading(true);

  try {
    const response = await fetch(`${API_BASE_URL}/api/recommend/ceda`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (response.ok && data.status === 'success') {
      renderRecommendationResult(data);
      const topMarket = data.recommended_market;
      showAlert(
        'Recommendation Complete',
        `Evaluated ${data.markets.length} markets. Recommended: ${topMarket.market_name} (TOPSIS: ${Number(topMarket.topsis_score).toFixed(4)}).`,
        'success'
      );
    } else {
      const errorMsg = data.detail || 'Recommendation service failed.';
      showAlert('Recommendation Error', errorMsg, 'error');
      showRecommendationEmptyState();
    }
  } catch (err) {
    console.error('Recommendation request failed:', err);
    showAlert('Network Error', `Cannot reach backend at ${API_BASE_URL || 'localhost:8000'}. Ensure backend is running.`, 'error');
    showRecommendationEmptyState();
  } finally {
    setRecommendationLoading(false);
  }
}

// -----------------------------------------------------------------------------
// 11. Render Recommendation Results
// Dual-compatible: CEDA schema (market_name, transport_cost_inr, data.markets[])
// and legacy schema (market, transportation_cost, data.rankings[]).
// -----------------------------------------------------------------------------
function renderRecommendationResult(data) {
  const rec = data.recommended_market;

  // CEDA field names with legacy fallbacks
  const heroName = rec.market_name || rec.market || '';
  const heroDistrict = rec.district_id
    ? ('District ID ' + rec.district_id + ', Kerala')
    : ((rec.district || '') + ' District, ' + (rec.state || ''));
  const heroFreight = rec.transport_cost_inr !== undefined ? rec.transport_cost_inr : (rec.transportation_cost || 0);
  const hasProdCost = (rec.expected_profit_inr !== null && rec.expected_profit_inr !== undefined)
    || (rec.expected_profit !== null && rec.expected_profit !== undefined);
  const profitVal = hasProdCost
    ? Number(rec.expected_profit_inr !== undefined ? rec.expected_profit_inr : rec.expected_profit)
    : Number(rec.expected_net_return_inr !== undefined ? rec.expected_net_return_inr : (rec.expected_net_return || 0));

  // 1. Hero Card
  elements.recHeroMarketName.textContent = heroName;
  elements.recHeroLocation.textContent = '\uD83D\uDCCD ' + heroDistrict;
  elements.recHeroTopsisScore.textContent = Number(rec.topsis_score).toFixed(4);
  elements.recHeroProfitLabel.textContent = hasProdCost ? 'Expected Net Profit' : 'Expected Net Return';
  elements.recHeroProfitVal.textContent = profitVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const heroPriceQtl = Number(rec.predicted_price_per_quintal) || 0;
  const heroPriceKg = heroPriceQtl / 100.0;
  elements.recHeroPriceVal.textContent = heroPriceQtl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (elements.recHeroPriceKgVal) {
    elements.recHeroPriceKgVal.textContent = heroPriceKg.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  elements.recHeroFreightVal.textContent = Number(heroFreight).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // Additional metrics from rankings list
  const rankingsList = data.markets || data.rankings || [];
  const topRankItem = rankingsList[0] || {};
  elements.recHeroDist.textContent = Number(topRankItem.distance_km || 0).toFixed(1) + ' km';
  elements.recHeroTime.textContent = Number(topRankItem.transit_duration_minutes || 0).toFixed(1) + ' min';
  elements.recHeroSpoil.textContent = Number(topRankItem.estimated_spoilage_pct || 0).toFixed(2) + '%';
  elements.recHeroSellable.textContent = Number(topRankItem.sellable_quantity_kg || 0).toFixed(1) + ' kg';
  elements.recHeroRationale.textContent = rec.reason_summary;

  // 2. Rankings Table
  elements.rankingsTableBody.innerHTML = '';
  rankingsList.forEach(function(item) {
    const tr = document.createElement('tr');
    if (item.rank === 1) tr.className = 'rank-row-top';
    const marketDisplay = item.market_name || item.market || '';
    const districtDisplay = item.district_id ? ('District ID ' + item.district_id) : (item.district || '');
    const freightCost = item.transport_cost_inr !== undefined ? item.transport_cost_inr : (item.transportation_cost || 0);
    const profitAmt = item.expected_profit_inr !== undefined ? item.expected_profit_inr
      : (item.expected_profit !== undefined ? item.expected_profit : null);
    const returnAmt = item.expected_net_return_inr !== undefined ? item.expected_net_return_inr
      : (item.expected_net_return !== undefined ? item.expected_net_return : 0);
    const priceQtl = Number(item.predicted_price_per_quintal) || 0;
    const priceKg = priceQtl / 100.0;
    const rupee = '\u20B9';
    const itemFinancial = profitAmt !== null
      ? (rupee + ' ' + Number(profitAmt).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
      : (rupee + ' ' + Number(returnAmt).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    tr.innerHTML = '<td class="text-center"><span class="rank-badge-pill ' + (item.rank === 1 ? 'top-1' : '') + '">#' + item.rank + '</span></td>'
      + '<td><strong>' + marketDisplay + '</strong><div style="font-size:0.75rem;color:var(--neutral-500);">' + districtDisplay + '</div></td>'
      + '<td class="text-right">'
      + '  <div style="font-weight:700;color:var(--neutral-800);">' + rupee + ' ' + priceQtl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' <span style="font-size:0.75rem;font-weight:500;color:var(--neutral-500);">/ qtl</span></div>'
      + '  <div style="font-size:0.8rem;font-weight:600;color:var(--primary-700);margin-top:2px;">' + rupee + ' ' + priceKg.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' <span style="font-size:0.75rem;font-weight:500;color:var(--neutral-500);">/ kg</span></div>'
      + '</td>'
      + '<td class="text-right">' + Number(item.distance_km).toFixed(1) + ' km</td>'
      + '<td class="text-right">' + rupee + ' ' + Number(freightCost).toFixed(2) + '</td>'
      + '<td class="text-right">' + Number(item.estimated_spoilage_pct).toFixed(2) + '%</td>'
      + '<td class="text-right" style="font-weight:700;color:' + (item.rank === 1 ? 'var(--primary-800)' : 'inherit') + ';">' + itemFinancial + '</td>'
      + '<td class="text-center"><strong style="color:' + (item.rank === 1 ? 'var(--primary-700)' : 'var(--neutral-700)') + ';">' + Number(item.topsis_score).toFixed(4) + '</strong></td>';
    elements.rankingsTableBody.appendChild(tr);
  });

  // 3. Criteria Table
  elements.criteriaTableBody.innerHTML = '';
  (data.criteria_used || []).forEach(function(crit) {
    const tr = document.createElement('tr');
    const typeStr = ((crit.criterion_type || crit.type) || '').toLowerCase();
    const isBenefit = typeStr === 'benefit';
    const displayName = crit.display_name || crit.name || '';
    const codeName = crit.name || '';
    const weightVal = crit.weight !== undefined ? crit.weight : 0;
    tr.innerHTML = '<td><strong>' + displayName + '</strong></td>'
      + '<td><span class="' + (isBenefit ? 'type-badge-benefit' : 'type-badge-cost') + '">' + (isBenefit ? 'Maximize (Benefit)' : 'Minimize (Cost)') + '</span></td>'
      + '<td class="text-right"><strong>' + (Number(weightVal) * 100).toFixed(1) + '%</strong></td>'
      + '<td><code style="font-family:var(--font-mono);font-size:0.75rem;color:var(--neutral-600);">' + codeName + '</code></td>';
    elements.criteriaTableBody.appendChild(tr);
  });

  // 4. Failed Markets
  const failedList = data.failed_markets || data.failed_candidates || [];
  if (failedList.length > 0) {
    elements.failedCandidatesList.innerHTML = '';
    failedList.forEach(function(f) {
      const li = document.createElement('li');
      li.textContent = (f.market_name || f.market || ('market_id ' + f.market_id)) + ': ' + (f.failure_reason || 'Evaluation failed');
      elements.failedCandidatesList.appendChild(li);
    });
    elements.failedCandidatesBox && elements.failedCandidatesBox.classList.remove('hidden');
  } else {
    elements.failedCandidatesBox && elements.failedCandidatesBox.classList.add('hidden');
  }

  // Show results
  elements.recEmptyState && elements.recEmptyState.classList.add('hidden');
  elements.recLoadingState && elements.recLoadingState.classList.add('hidden');
  elements.recResultsContainer && elements.recResultsContainer.classList.remove('hidden');
}
function setRecommendationLoading(isLoading) {
  if (isLoading) {
    elements.recBtn.disabled = true;
    elements.recBtnSpinner?.classList.remove('hidden');
    elements.recBtnIcon?.classList.add('hidden');
    elements.recBtnLabel.textContent = 'Evaluating & Ranking Mandis...';

    elements.recEmptyState?.classList.add('hidden');
    elements.recResultsContainer?.classList.add('hidden');
    elements.recLoadingState?.classList.remove('hidden');
  } else {
    elements.recBtn.disabled = false;
    elements.recBtnSpinner?.classList.add('hidden');
    elements.recBtnIcon?.classList.remove('hidden');
    elements.recBtnLabel.textContent = 'Evaluate & Recommend Best Market';
    elements.recLoadingState?.classList.add('hidden');
  }
}

function showRecommendationEmptyState() {
  elements.recResultsContainer?.classList.add('hidden');
  elements.recLoadingState?.classList.add('hidden');
  elements.recEmptyState?.classList.remove('hidden');
}

// -----------------------------------------------------------------------------
// 12. Alert Helpers
// -----------------------------------------------------------------------------
function showAlert(title, message, type = 'error') {
  if (!elements.alertBanner) return;
  elements.alertTitle.textContent = title;
  elements.alertMessage.textContent = message;
  elements.alertBanner.className = `alert-banner ${type}`;
  elements.alertIcon.textContent = type === 'success' ? '✅' : '⚠️';
  elements.alertBanner.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideAlert() {
  elements.alertBanner?.classList.add('hidden');
}
