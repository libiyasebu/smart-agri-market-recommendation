# Agri_mini - Project Demonstration Script (5-10 Minutes)

This script outlines a structured, professional demonstration flow for presenting the **Agri_mini** platform to evaluators, stakeholders, or examiners.

---

## Preparation Checklist
- [x] PostgreSQL service running (`agri_mini_db` on port `5432`).
- [x] Terminal open in `D:\Agri_mini`.
- [x] Web browser ready at `http://127.0.0.1:8000/dashboard/`.

---

## Step 1: System Startup (1 Minute)

### Command:
```powershell
.\start_project.ps1
```
*Or manual launch:*
```powershell
d:\Agri_mini\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Verbal Commentary:
> *"The backend starts on Uvicorn serving FastAPI at port 8000. It connects to our local PostgreSQL database `agri_mini_db` and loads our pre-trained Random Forest model and preprocessor artifacts into memory for low-latency inference."*

---

## Step 2: System Health & OpenAPI Swagger Inspection (1 Minute)

1. Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) in browser.
   - Show status: `{"status": "healthy", "service": "agri-price-transport-optimization-api", "version": "1.0.0"}`.
2. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
   - Point out the 5 core modules:
     - `POST /api/v1/predict/price` (Price Prediction)
     - `POST /api/v1/transport/estimate` (Transportation & Logistics)
     - `POST /api/v1/spoilage/estimate` (Spoilage Risk)
     - `POST /api/v1/profit/evaluate` (Profit Evaluation)
     - `POST /api/v1/recommend/markets` (Market Recommendation)

---

## Step 3: Workflow 1 — Agricultural Price Forecasting (2 Minutes)

1. Open the interactive dashboard: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
2. Ensure the **"Price Forecast"** tab is selected.
3. Click the quick preset button: **"🍅 Tomato (Thrissur APMC)"**.
4. Point out the input fields: Produce (`Tomato`), Variety (`Hybrid`), Mandi (`Thrissur APMC`), District (`Thrissur`), State (`Kerala`), Date (`2026-08-28`).
5. Click **"Predict Expected Modal Price"**.
6. **Walkthrough Results**:
   - Highlight the predicted modal price: **₹ 2,333.12 / quintal** (₹ 23.33 / kg).
   - Show the 54 features evaluated and historical lag points.
   - Show the green status badges verifying **Live Weather Matched**, **FAOSTAT Matched**, and **Road Route Matched**.

### Verbal Commentary:
> *"Our model derives historical lags strictly before the target date to ensure zero target leakage, combining recent market velocity with agro-weather and FAOSTAT macro indicators."*

---

## Step 4: Workflow 2 — TOPSIS Smart Market Recommendation (3 Minutes)

1. Switch to the **"Smart Market Recommendation"** tab.
2. Click the preset: **"🍅 Tomato (Thrissur Farm • 4 Mandis • 1000 kg)"**.
3. Point out the configuration:
   - **Farm Origin**: Thrissur ($10.5276, 76.2144$).
   - **Shipment**: $1000\text{ kg}$ loaded in a `mini_truck`.
   - **Cultivation Cost**: ₹ 12,000.
   - **Candidate Mandis Selected**: Palakkad Mandi, Kochi Market, Kozhikode Mandi, Trivandrum APMC.
4. Expand **"Adjust Decision Priorities (TOPSIS Weights)"** to demonstrate customizable multi-criteria weights (Profit $40\%$, Price $20\%$, Freight $15\%$, Time $10\%$, Spoilage $15\%$).
5. Click **"Evaluate & Recommend Best Market"**.

---

## Step 5: Explain the Recommendation Insights & Trade-Offs (2 Minutes)

### Highlight the Hero Recommendation Card:
- **Rank #1 Destination**: **Palakkad Wholesale Mandi**
- **TOPSIS Closeness Score**: **0.9864**
- **Expected Net Profit**: **₹ 8,542.46**
- **Decision Rationale**: Lowest freight cost (₹ 1,305.33), minimal transit loss ($6.84\%$), and highest net profit over a $67.6\text{ km}$ route.

### Highlight the Multi-Market Comparison Table:
Point out the crucial trade-off:
- **Trivandrum APMC** offered the highest nominal price (₹ 2,388.40/qtl).
- **However**, due to its $278.2\text{ km}$ distance, freight jumped to ₹ 3,815.57 and transit spoilage reached $11.12\%$.
- This caused Trivandrum's net profit to drop to ₹ 5,424.47 (Rank #4, TOPSIS score 0.0190).

### Verbal Commentary:
> *"This demonstrates the core value of our platform: maximizing price alone is deceptive. By factoring in freight physics and transit spoilage through TOPSIS vector normalization, the system protects the farmer from sub-optimal shipping choices."*

---

## Step 6: Automated Test Suite & Health Check (1 Minute)

In a separate terminal, show system health and test suite execution:
```powershell
d:\Agri_mini\.venv\Scripts\python.exe backend\scripts\system_check.py
```
```powershell
d:\Agri_mini\.venv\Scripts\python.exe backend\scripts\test_full_system.py
```
```powershell
d:\Agri_mini\.venv\Scripts\pytest.exe backend\tests -v
```
- Show all **136 automated regression tests passing**.

---

## Step 7: Conclusion & Q&A
Summarize:
- Modular, production-grade architecture in FastAPI & PostgreSQL.
- Tuned ML price model with zero data leakage ($R^2 = 0.9990$).
- Transparent mathematical accounting for transport and spoilage.
- Objective decision support powered by TOPSIS.
