# AI-Based Agricultural Price Prediction and Smart Market Recommendation System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4+-F7931E.svg)](https://scikit-learn.org/)
[![TOPSIS](https://img.shields.io/badge/Decision%20Support-TOPSIS%20Engine-emerald.svg)]()
[![Tests Passing](https://img.shields.io/badge/tests-136%20passed-brightgreen.svg)]()

An end-to-end, production-ready agro-logistics platform that unifies **machine learning crop price forecasting**, **OSRM road logistics costing**, **Open-Meteo transit spoilage risk assessment**, **expected net profit evaluation**, and **TOPSIS multi-criteria market ranking** into an interactive farmer decision-support dashboard.

---

## 1. Problem Statement

Smallholder farmers and agricultural producers face severe informational asymmetry when marketing their harvest:
1. **Uncertain Selling Prices**: Crop market prices fluctuate heavily across regional APMC mandis due to supply spikes, historical seasonality, and weather shocks.
2. **Hidden Transportation Expenses**: A distant mandi offering higher nominal rates may incur freight costs exceeding the price premium.
3. **Transit Spoilage & Quality Loss**: Perishable produce deteriorates during transit due to travel duration, ambient heat, and humidity, eroding actual sellable volume.
4. **Sub-optimal Market Selection**: Farmers lack decision-support tools that simultaneously weigh predicted prices, road distances, transit times, fuel expenses, and spoilage losses to choose the most profitable mandi.

---

## 2. Objectives

- Construct a **leakage-safe, time-aware machine learning model** to forecast daily modal prices for agricultural commodities across regional mandis.
- Integrate **multi-source real-time context**: historical Agmarknet price series, Open-Meteo agro-weather forecasts, FAOSTAT national agricultural indicators, and OSRM road driving routes.
- Accurately calculate **freight and logistics expenses** based on road distances, vehicle payload capacities, fuel rates, driver wages, and required multi-trip runs.
- Model **perishability and transit spoilage risks** using commodity physiological traits and corridor temperature/humidity conditions.
- Implement an **objective multi-criteria decision solver using TOPSIS** (Technique for Order Preference by Similarity to Ideal Solution) to rank candidate markets.
- Deliver an intuitive, responsive **web dashboard** that empowers farmers with actionable insights.

---

## 3. System Features

- **Dual-Workflow Web Dashboard**:
  - *Workflow 1 (Price Forecast)*: Single-market modal price prediction with feature integration audit badges.
  - *Workflow 2 (Smart Market Recommendation)*: Multi-market comparison, Hero recommended destination card, full rankings table, and customizable priority weights.
- **Leakage-Safe Feature Engineering**: 54 engineered features including $t-1, t-3, t-7, t-14$ price lags, 7-day and 14-day rolling statistics, historical price volatility, weather variables, and macro indicators.
- **Transparent Cost & Revenue Accounting**: Explicit breakdown of gross revenue, spoilage value loss, realized sellable yield, freight charges, and true accounting profit.
- **Fail-Safe Multi-Market Processing**: Downstream isolation ensures that a failure in one candidate market does not crash the evaluation of remaining valid markets.
- **Interactive REST API**: FastAPI backend documented with interactive Swagger OpenAPI UI (`/docs`).

---

## 4. System Architecture

```
                               +-------------------------------------+
                               |     Farmer Web Client (HTML5/CSS)   |
                               |          /dashboard/ SPA            |
                               +------------------+------------------+
                                                  |
                                                  | HTTP / JSON REST
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                    FastAPI Production Backend (Port 8000)                          |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  +---------------------------+   +---------------------------+   +-------------------------------+ |
|  |     PredictionService     |   |     TransportService      |   |        SpoilageService        | |
|  | (Tuned Random Forest Reg) |   | (OSRM Road Routing Engine)|   | (Open-Meteo Decay Heuristic)  | |
|  +-------------+-------------+   +-------------+-------------+   +---------------+---------------+ |
|                |                               |                                 |                 |
|                +-----------------------+       |       +-------------------------+                 |
|                                        |       |       |                                           |
|                                        v       v       v                                           |
|                                  +---------------------------+                                     |
|                                  |       ProfitService       |                                     |
|                                  | (Financial Net Return)    |                                     |
|                                  +-------------+-------------+                                     |
|                                                |                                                   |
|                                                v                                                   |
|                                  +---------------------------+                                     |
|                                  |   RecommendationService   |                                     |
|                                  | (TOPSIS Decision Solver)  |                                     |
|                                  +---------------------------+                                     |
|                                                                                                    |
+--------------------------------------------------+-------------------------------------------------+
                                                   | SQLAlchemy ORM
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                   PostgreSQL Database (agri_mini_db)                               |
|   - market_prices (Agmarknet)             - weather_records (Open-Meteo)                          |
|   - faostat_indicators (FAOSTAT)          - route_records (OSRM Cache)                            |
+----------------------------------------------------------------------------------------------------+
```

---

## 5. Data Sources

1. **Agmarknet (data.gov.in)**: Historical daily mandi transaction prices (Modal, Min, Max prices in INR/quintal, commodity, variety, market, district, state).
2. **Open-Meteo**: Agro-meteorological metrics (daily mean/max temperatures, relative humidity, precipitation).
3. **FAOSTAT (UN Food and Agriculture Organization)**: National annual agricultural production metrics, crop yield (hg/ha), and harvested area.
4. **OSRM (OpenStreetMap)**: Exact road driving distances, transit travel durations, and corridor geometry between farm origins and mandi destinations.
5. **PostgreSQL (`agri_mini_db`)**: Central relational store with indexed queries for leakage-free feature retrieval.

---

## 6. Machine Learning Pipeline

- **Target Variable**: `modal_price` (INR per quintal).
- **Leakage Prevention**: Strictly chronological train-test split ($80\%$ train, $20\%$ test). Lag features ($t-1 \dots t-14$) and rolling windows strictly use preceding historical observations ($t' < t_{\text{pred}}$) to prevent lookahead contamination.
- **Models Compared**:
  - Linear Regression / Ridge
  - Decision Tree Regressor
  - XGBoost Regressor
  - **Random Forest Regressor (Tuned)** *(Selected Best Production Model)*
- **Tuned Hyperparameters**:
  - `n_estimators`: 50
  - `max_depth`: 10
  - `min_samples_split`: 2
  - `min_samples_leaf`: 1
  - `max_features`: 1.0
- **Validation Metrics**:
  - **Test MAE**: ₹ 21.20 / quintal
  - **Test RMSE**: ₹ 29.55 / quintal
  - **Test $R^2$ Score**: 0.9990
  - **Test MAPE**: 0.93%

---

## 7. Mathematical Formulations

### A. Road Logistics Cost Calculation
For a shipment of quantity $Q\text{ (kg)}$ with single-trip road distance $D\text{ (km)}$ using vehicle payload capacity $C_{\text{veh}}\text{ (kg)}$:

$$\text{Trips} = \left\lceil \frac{Q}{C_{\text{veh}}} \right\rceil$$

$$\text{Fuel Required (L)} = \frac{D}{\text{Efficiency (km/L)}}$$

$$\text{Single Trip Cost} = (\text{Fuel} \times P_{\text{fuel}}) + (D \times C_{\text{maint}}) + C_{\text{driver}} + \text{Toll} + \text{Other}$$

$$\text{Total Freight Cost} = \text{Trips} \times \text{Single Trip Cost}$$

### B. Weather-Aware Spoilage & Physical Loss
For commodity base perishability $B \in [0, 100]$, temperature stress $S_T$, humidity stress $S_H$, transit time stress $S_t$, and rain stress $S_R$:

$$\text{Risk Score} = 0.35 B + 0.25 S_T + 0.15 S_H + 0.20 S_t + 0.05 S_R \quad \in [0, 100]$$

$$\text{Loss \%} = \text{MaxLossPct} \times \left( \frac{\text{Risk Score}}{100} \right)^{1.35}$$

$$\text{Sellable Quantity (kg)} = Q \times \left( 1 - \frac{\text{Loss \%}}{100} \right)$$

### C. Financial Return & Accounting Profit

$$\text{Gross Revenue} = \left( \frac{\text{Sellable Qty (kg)}}{100} \right) \times P_{\text{predicted}}$$

$$\text{Expected Net Return} = \text{Gross Revenue} - \text{Total Freight Cost}$$

$$\text{Expected Profit} = \text{Expected Net Return} - \text{Production Cost}$$

### D. TOPSIS Multi-Criteria Decision Ranking
For $m$ candidate markets evaluated across $n$ decision criteria ($x_{ij}$):
1. **Vector Normalization**:
   $$r_{ij} = \frac{x_{ij}}{\sqrt{\sum_{k=1}^m x_{kj}^2}}$$
2. **Weighted Normalized Matrix**:
   $$v_{ij} = w_j \cdot r_{ij}, \quad \sum w_j = 1.0$$
3. **Ideal Best ($A^+$) & Worst ($A^-$) Solutions**:
   - Benefit criteria (Profit, Price): $A_j^+ = \max_i v_{ij}, \quad A_j^- = \min_i v_{ij}$
   - Cost criteria (Freight, Duration, Spoilage): $A_j^+ = \min_i v_{ij}, \quad A_j^- = \max_i v_{ij}$
4. **Euclidean Distances**:
   $$S_i^+ = \sqrt{\sum_{j=1}^n (v_{ij} - A_j^+)^2}, \quad S_i^- = \sqrt{\sum_{j=1}^n (v_{ij} - A_j^-)^2}$$
5. **Relative Closeness Coefficient ($C_i \in [0.0, 1.0]$)**:
   $$C_i = \frac{S_i^-}{S_i^+ + S_i^-}$$
   *Markets are ranked in descending order of $C_i$.*

---

## 8. API Endpoints

| Method | Endpoint | Tag | Summary |
| :---: | :--- | :--- | :--- |
| `GET` | `/` | General | Root API metadata, version info, and endpoint index |
| `GET` | `/health` | Monitoring | Liveness check and service health verification |
| `GET` | `/api/v1/system/info` | Monitoring | Detailed runtime information and ML model specifications |
| `GET` | `/dashboard/` | Static | Web decision-support user interface |
| `POST` | `/api/v1/predict/price` | Price Prediction | Forecasts expected modal market price (INR/qtl) |
| `POST` | `/api/v1/transport/estimate` | Transportation | Calculates road distance, duration, and freight cost |
| `POST` | `/api/v1/spoilage/estimate` | Spoilage Risk | Computes transit perishability risk score and loss % |
| `POST` | `/api/v1/profit/evaluate` | Profit Evaluation | Computes revenue, freight, and expected profit |
| `POST` | `/api/v1/recommend/markets` | Market Recommendation | TOPSIS multi-market comparison and optimal destination ranking |

---

## 9. Project Directory Structure

```
D:\Agri_mini
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore patterns
├── README.md                        # Complete project documentation
├── requirements.txt                 # Python package dependencies
├── start_project.ps1                # One-command PowerShell startup script
├── backend
│   ├── .env.example
│   ├── requirements.txt
│   ├── app
│   │   ├── config.py                # Pydantic v2 application settings
│   │   ├── database.py              # SQLAlchemy engine & session factory
│   │   ├── main.py                  # FastAPI application entrypoint & routing
│   │   ├── models/                  # SQLAlchemy ORM schemas
│   │   │   ├── __init__.py
│   │   │   ├── market_price.py
│   │   │   ├── weather_record.py
│   │   │   ├── faostat_indicator.py
│   │   │   └── route_record.py
│   │   ├── schemas/                 # Pydantic validation request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── prediction.py
│   │   │   ├── transport.py
│   │   │   ├── spoilage.py
│   │   │   ├── profit.py
│   │   │   └── recommendation.py
│   │   └── services/                # Core business logic & decision engines
│   │       ├── __init__.py
│   │       ├── routing_service.py
│   │       ├── weather_service.py
│   │       ├── faostat_service.py
│   │       ├── prediction_service.py
│   │       ├── transport_service.py
│   │       ├── spoilage_service.py
│   │       ├── profit_service.py
│   │       └── recommendation_service.py
│   ├── artifacts
│   │   ├── best_price_model.joblib   # Tuned Random Forest model binary
│   │   ├── preprocessor.joblib       # One-hot encoder & standard scaler
│   │   └── model_metadata.json       # Feature names, metrics, hyperparameters
│   ├── scripts
│   │   ├── system_check.py          # Comprehensive health verification script
│   │   ├── test_full_system.py      # End-to-end API smoke test suite
│   │   └── test_recommendation.py   # TOPSIS verification scenario
│   └── tests                        # Pytest automated test suite (136 tests)
│       ├── test_schema.py
│       ├── test_weather.py
│       ├── test_routing.py
│       ├── test_prediction_service.py
│       ├── test_prediction_api.py
│       ├── test_transport_service.py
│       ├── test_transport_api.py
│       ├── test_spoilage_service.py
│       ├── test_spoilage_api.py
│       ├── test_profit_service.py
│       ├── test_profit_api.py
│       ├── test_recommendation_service.py
│       ├── test_recommendation_api.py
│       └── test_frontend_dashboard.py
├── docs
│   ├── architecture.md              # Technical architecture & dataflow diagrams
│   ├── walkthrough.md               # Phases 1-12 complete project walkthrough
│   ├── viva_notes.md                # Comprehensive viva & presentation Q&A guide
│   └── demo_script.md               # 5-10 minute demonstration walkthrough
└── frontend
    ├── index.html                   # Dual-workflow decision dashboard
    ├── css
    │   └── style.css                # Agricultural emerald SaaS styling
    └── js
        └── app.js                   # Client controller for REST APIs
```

---

## 10. Installation & Setup

### Prerequisites
- **Python**: Version 3.10, 3.11, 3.12, or 3.13
- **PostgreSQL**: Version 14, 15, or 16
- **OS**: Windows, macOS, or Linux

### Step 1: Clone or Open Project
```powershell
cd D:\Agri_mini
```

### Step 2: Create & Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Configure PostgreSQL Database
1. Ensure PostgreSQL server is running on `localhost:5432`.
2. Create database `agri_mini_db`:
   ```sql
   CREATE DATABASE agri_mini_db;
   ```
3. Copy `.env.example` to `.env` and set your password:
   ```ini
   DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/agri_mini_db
   ```

---

## 11. How to Run the System

### Option A: Using One-Command PowerShell Launcher
```powershell
.\start_project.ps1
```

### Option B: Manual Uvicorn Launch
```powershell
d:\Agri_mini\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Accessing Interfaces:
- **Decision-Support Web Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Swagger Interactive API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 12. Verification & Testing

### 1. Run Complete Automated Regression Suite (136 Tests)
```powershell
d:\Agri_mini\.venv\Scripts\pytest.exe backend\tests -v
```

### 2. Run Comprehensive System Health Check
```powershell
d:\Agri_mini\.venv\Scripts\python.exe backend\scripts\system_check.py
```

### 3. Run End-to-End API Smoke Test
```powershell
d:\Agri_mini\.venv\Scripts\python.exe backend\scripts\test_full_system.py
```

---

## 13. Sample Demonstration Scenario

- **Farmer Origin**: Thrissur, Kerala ($10.5276, 76.2144$)
- **Commodity**: Tomato (Hybrid), Target Date: 2026-08-28
- **Shipment**: $1000\text{ kg}$ loaded on a `mini_truck`
- **Cultivation Cost**: ₹ 12,000

### Evaluation Summary:

```
=====================================================================================
 Rank | Candidate Market         | Price/Qtl   | Dist    | Freight    | Spoil%  | Net Profit  | TOPSIS Score
-------------------------------------------------------------------------------------
 #1   | Palakkad Wholesale Mandi | Rs 2345.19 |  67.6km | Rs 1305.33 |   6.8% |  Rs 8542.46 |   0.9864
 #2   | Kochi (Ernakulam) Market | Rs 2327.76 |  84.9km | Rs 1511.61 |   7.0% |  Rs 8134.23 |   0.9013
 #3   | Kozhikode Central Mandi  | Rs 2329.52 | 128.7km | Rs 2033.32 |   7.8% |  Rs 7437.87 |   0.6947
 #4   | Trivandrum APMC          | Rs 2388.40 | 278.2km | Rs 3815.57 |  11.1% |  Rs 5424.47 |   0.0190
=====================================================================================
```
*Key Insight*: Although Trivandrum APMC offered the highest nominal price (₹ 2,388/qtl), its $278.2\text{ km}$ transit distance resulted in higher freight (₹ 3,815) and transit spoilage ($11.1\%$), yielding the lowest net profit (₹ 5,424). **Palakkad Wholesale Mandi is recommended as Rank #1.**

---

## 14. Assumptions & Limitations

1. **Price Forecasting**: The ML model was trained and evaluated on historical Agmarknet records. Periodic model retraining is required as seasonal patterns evolve.
2. **Road Routing**: Transit distances and driving durations rely on OpenStreetMap/OSRM profiles. Severe road closures or live congestion may alter driving durations.
3. **Transit Spoilage**: Spoilage estimation is a rule-based agro-meteorological heuristic calibrated to physiological crop parameters. It is not an empirical ML classification model.
4. **Decision Ranking**: TOPSIS ranks options according to user-configured priority weights. It provides decision-support estimates rather than financial guarantees.

---

## 15. Future Scope

- Integration with live IoT cold-storage monitoring on transport vehicles.
- Farmer SMS / WhatsApp notification alerts with regional mandi recommendations.
- Multi-crop mixed shipment load optimization.
- Real-time road toll and dynamic traffic API integration.
- Deep reinforcement learning for multi-stop harvest collection routes.

---

## 16. License

Academic Project & Research Prototype — Agri_mini Platform.
