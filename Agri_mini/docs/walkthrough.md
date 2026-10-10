# Agri_mini - Complete Project Walkthrough (Phases 1 to 12)

This document provides a comprehensive, chronological engineering walkthrough of the entire development lifecycle of the **Agri_mini** platform.

---

## Phase 1 — Project Initialization, Environment & Base Structure
- **Objective**: Establish the development workspace, virtual environment, and initial directory structure.
- **Key Actions**:
  - Configured Python 3.10+ virtual environment (`.venv`).
  - Created standardized directory layout (`backend/app`, `backend/artifacts`, `backend/scripts`, `backend/tests`, `frontend`, `docs`).
  - Initialized `backend/app/config.py` using Pydantic Settings for type-safe environment configuration.
- **Verification**: Base FastAPI test instance returning HTTP 200 on root.

---

## Phase 2 — Multi-Source External Data Ingestion
- **Objective**: Build resilient connectors to acquire data across market, weather, macro-economic, and routing domains.
- **Modules Created**:
  - `backend/app/services/weather_service.py`: Open-Meteo connector for temperature, humidity, and rainfall forecasts.
  - `backend/app/services/faostat_service.py`: UN FAOSTAT connector for national crop production, yield (hg/ha), and harvested area.
  - `backend/app/services/routing_service.py`: OSRM connector for road driving distance and duration calculations.
- **Key Decisions**: Integrated robust fallback mechanisms to ensure system resilience when external APIs experience rate limits or network downtime.

---

## Phase 3 — PostgreSQL Relational Database & ORM Layer
- **Objective**: Design and establish normalized relational schemas in PostgreSQL (`agri_mini_db`).
- **Models Created**:
  - `MarketPrice` (`market_prices`): Stores historical commodity prices across mandis.
  - `WeatherRecord` (`weather_records`): Stores regional agro-meteorological metrics.
  - `FAOSTATIndicator` (`faostat_indicators`): Stores national macro crop statistics.
  - `RouteRecord` (`route_records`): Caches pairwise driving routes.
- **Database Engine**: SQLAlchemy 2.0 with `psycopg2-binary` connection pooling.

---

## Phase 4 — Leakage-Safe Preprocessing & Feature Engineering
- **Objective**: Construct a leakage-safe ML dataset from PostgreSQL records.
- **Engineering Strategy**:
  - **Temporal Lags**: Derived $t-1, t-3, t-7, t-14$ historical price lags strictly from preceding dates ($t' < t_{\text{pred}}$).
  - **Rolling Statistics**: 7-day and 14-day rolling means, standard deviations, and price volatilities.
  - **Temporal Encodings**: Day-of-week, month-of-year, and seasonal sine/cosine cyclical features.
  - **Context Merging**: Left-joined weather variables and FAOSTAT indicators.
- **Total Features**: 54 engineered features.

---

## Phase 5 — Machine Learning Model Training & Hyperparameter Tuning
- **Objective**: Train, benchmark, validate, and select the best production regression model.
- **Methodology**:
  - Strictly chronological 80/20 train/test split to mirror live deployment conditions.
  - Benchmarked Linear Regression, Ridge, Decision Tree, XGBoost, and Random Forest.
  - Conducted 4-fold expanding-window time-series cross-validation.
- **Selected Model**: **Random Forest Regressor (Tuned)**
  - Hyperparameters: `n_estimators=50, max_depth=10, min_samples_split=2, min_samples_leaf=1, max_features=1.0`.
  - Metrics: **MAE = ₹ 21.20/qtl**, **RMSE = ₹ 29.55/qtl**, **$R^2 = 0.9990$**, **MAPE = 0.93%**.
- **Artifacts Saved**: `best_price_model.joblib`, `preprocessor.joblib`, `model_metadata.json`.

---

## Phase 6 — Production Price Prediction REST API
- **Objective**: Expose the trained Random Forest model via high-performance REST endpoint.
- **API Endpoint**: `POST /api/v1/predict/price`
- **Behavior**: Accepts produce, mandi, district, variety, and target date. Dynamically queries PostgreSQL for historical lags, transforms features via preprocessor, and returns predicted modal price with context match badges.

---

## Phase 7 — Agricultural Transportation Cost & Logistics Module
- **Objective**: Calculate physical freight expenses for moving harvest from farm to mandi.
- **Service Created**: `backend/app/services/transport_service.py`
- **Supported Vehicles**: `mini_truck` (1.5T), `pickup` (2.5T), `medium_truck` (7.5T), `large_truck` (16.0T).
- **Logistics Logic**: Computes required round-trip runs $\lceil Q / C_{\text{veh}} \rceil$, fuel requirements based on OSRM distance and fuel economy, vehicle maintenance, driver wages, tolls, and loading charges.
- **API Endpoint**: `POST /api/v1/transport/estimate`

---

## Phase 8 — Weather-Aware Spoilage Risk Estimation Module
- **Objective**: Quantify transit crop quality deterioration and physical volume loss.
- **Service Created**: `backend/app/services/spoilage_service.py`
- **Methodology**: Heuristic agro-meteorological model combining:
  - Commodity base perishability index ($[0, 100]$).
  - Thermal stress index based on corridor temperature versus optimal crop range.
  - Moisture stress index based on relative humidity.
  - Transit time exposure stress index.
- **API Endpoint**: `POST /api/v1/spoilage/estimate`

---

## Phase 9 — Expected Profit & Net Return Evaluation Engine
- **Objective**: Unify price forecasting, freight costing, and spoilage loss into transparent financial accounting.
- **Service Created**: `backend/app/services/profit_service.py`
- **Calculations**:
  - $\text{Gross Revenue} = \text{Sellable Quintals} \times P_{\text{predicted}}$
  - $\text{Expected Net Return} = \text{Gross Revenue} - \text{Total Freight Cost}$
  - $\text{Expected Profit} = \text{Expected Net Return} - \text{Production Cost}$ (if supplied)
- **API Endpoint**: `POST /api/v1/profit/evaluate`

---

## Phase 10 — TOPSIS Multi-Market Recommendation Engine
- **Objective**: Objectively rank multiple candidate mandis using multi-criteria decision analysis.
- **Service Created**: `backend/app/services/recommendation_service.py`
- **Algorithm**:
  - Vector normalization of decision matrix $X_{m \times n}$.
  - Weight application: Profit ($40\%$), Price ($20\%$), Freight ($15\%$), Duration ($10\%$), Spoilage ($15\%$).
  - Euclidean distance to Ideal Best ($A^+$) and Ideal Worst ($A^-$).
  - Relative closeness scoring: $C_i = S_i^- / (S_i^+ + S_i^-) \in [0.0, 1.0]$.
- **API Endpoint**: `POST /api/v1/recommend/markets`

---

## Phase 11 — Full Decision-Support Frontend Integration
- **Objective**: Upgrade the web dashboard to support both standalone price forecasting and multi-market recommendation.
- **Key Enhancements**:
  - Sticky tab navigation: `[ Price Forecast ]` and `[ Smart Market Recommendation ]`.
  - Candidate mandi selection cards with live count validation ($\ge 2$).
  - Collapsible decision priority sliders with real-time weight summation.
  - Hero card for Rank #1 Recommended Market with decision rationale narrative.
  - Full multi-market comparison table and criteria transparency breakdown.

---

## Phase 12 — Final System Validation, Documentation & Deployment Preparation
- **Objective**: Complete codebase audit, comprehensive health checking, end-to-end smoke testing, and full academic documentation.
- **Key Deliverables**:
  - `backend/scripts/system_check.py`: Complete diagnostic tool.
  - `backend/scripts/test_full_system.py`: End-to-end API smoke test suite.
  - `start_project.ps1`: One-command PowerShell launcher.
  - Comprehensive documentation (`README.md`, `architecture.md`, `walkthrough.md`, `viva_notes.md`, `demo_script.md`).
  - **136 automated regression tests passing (100%)**.
