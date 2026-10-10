# Technical Architecture & System Design Documentation

## 1. System Overview

The **Agri_mini** platform is a multi-tier, data-driven agricultural decision-support system. It integrates multi-source geospatial and market telemetry with a machine learning price forecasting engine, a physical logistics calculation module, an agro-meteorological spoilage heuristic, and a multi-criteria decision solver (TOPSIS).

---

## 2. High-Level Component Architecture

```mermaid
flowchart TD
    subgraph UI ["User Layer (Client Tier)"]
        Browser["Farmer Web Browser\n(HTML5, CSS3, Vanilla JS SPA)"]
        Swagger["FastAPI Swagger OpenAPI UI\n(/docs)"]
    end

    subgraph API ["Application Server Tier (FastAPI)"]
        RouterMain["FastAPI App Router\n(app.main)"]
        Cors["CORS Middleware"]
        StaticM["StaticFiles Mount\n(/dashboard)"]
        
        R_Pred["POST /api/v1/predict/price"]
        R_Trans["POST /api/v1/transport/estimate"]
        R_Spoil["POST /api/v1/spoilage/estimate"]
        R_Profit["POST /api/v1/profit/evaluate"]
        R_Rec["POST /api/v1/recommend/markets"]
    end

    subgraph Service ["Business Logic & Decision Engines"]
        S_Pred["PredictionService\n(Random Forest + Preprocessor)"]
        S_Trans["TransportService\n(Vehicle Specs + Fleet Physics)"]
        S_Spoil["SpoilageService\n(Perishability Index + Weather Heuristic)"]
        S_Profit["ProfitService\n(Financial Aggregator Engine)"]
        S_Rec["RecommendationService\n(TOPSIS Multi-Criteria Solver)"]
        
        S_Route["RoutingService\n(OSRM Connector)"]
        S_Weath["WeatherService\n(Open-Meteo Connector)"]
        S_Fao["FAOSTATService\n(FAOSTAT API Connector)"]
    end

    subgraph External ["External Services & APIs"]
        Ext_OSRM["OSRM / OpenStreetMap Engine\n(router.project-osrm.org)"]
        Ext_Meteo["Open-Meteo Weather API\n(api.open-meteo.com)"]
        Ext_DataGov["data.gov.in (Agmarknet)"]
        Ext_FAO["FAOSTAT Data Portal"]
    end

    subgraph DB ["Data Persistence Tier"]
        PG["PostgreSQL Database (agri_mini_db)"]
        T_Prices["market_prices (Historical Lags & Mandi Rates)"]
        T_Weather["weather_records (Daily Agro-Weather)"]
        T_FAO["faostat_indicators (National Macro Yield/Prod)"]
        T_Routes["route_records (Cached Road Distance/Time)"]
    end

    Browser --> RouterMain
    Swagger --> RouterMain
    RouterMain --> R_Pred & R_Trans & R_Spoil & R_Profit & R_Rec

    R_Pred --> S_Pred
    R_Trans --> S_Trans
    R_Spoil --> S_Spoil
    R_Profit --> S_Profit
    R_Rec --> S_Rec

    S_Profit --> S_Pred & S_Trans & S_Spoil
    S_Rec --> S_Profit

    S_Trans --> S_Route
    S_Spoil --> S_Route & S_Weath
    S_Pred --> PG

    S_Route --> Ext_OSRM
    S_Weath --> Ext_Meteo

    PG --> T_Prices & T_Weather & T_FAO & T_Routes
```

---

## 3. Data Pipeline & Ingestion Architecture

```
[ Agmarknet / data.gov.in ] ---> [ Ingestion Pipeline ] ---> [ market_prices Table ]
[ Open-Meteo Weather API ]  ---> [ Weather Service   ] ---> [ weather_records Table ]
[ FAOSTAT Macro Data     ]  ---> [ FAOSTAT Service   ] ---> [ faostat_indicators Table ]
[ OSRM Road Routing      ]  ---> [ Routing Service   ] ---> [ route_records Table ]
```

### Key Schemas in PostgreSQL:
1. **`market_prices`**: Daily mandi prices ($N = 588$ rows in benchmark dataset) covering commodity, variety, market, district, state, modal price, min price, max price, arrival date.
2. **`weather_records`**: District-level agro-meteorological records (temperature mean/max, relative humidity, precipitation).
3. **`faostat_indicators`**: National macro production indicators (annual crop production, yield in hg/ha, harvested area).
4. **`route_records`**: Cached pairwise driving routes (origin lat/lon, destination lat/lon, distance in km, travel duration in minutes).

---

## 4. Multi-Market TOPSIS Decision Flow

```mermaid
sequenceDiagram
    autonumber
    actor Farmer as Farmer / Web Dashboard
    participant RecRouter as Recommendation Route
    participant RecSvc as Recommendation Service
    participant ProfitSvc as Profit Service
    participant PredSvc as Price Prediction Service
    participant TransSvc as Transport Service
    participant SpoilSvc as Spoilage Service

    Farmer->>RecRouter: POST /api/v1/recommend/markets (Origin, Qty, Crop, Mandis)
    RecRouter->>RecSvc: recommend_markets(request, db)
    
    loop For Each Candidate Mandi
        RecSvc->>ProfitSvc: evaluate_profit(candidate_req, db)
        ProfitSvc->>PredSvc: predict_price(market, crop, date)
        PredSvc-->>ProfitSvc: Predicted Price (INR/qtl)
        ProfitSvc->>TransSvc: estimate_cost(origin, destination, qty)
        TransSvc-->>ProfitSvc: Road Distance, Time, Freight Cost (INR)
        ProfitSvc->>SpoilSvc: estimate_spoilage(crop, route, weather)
        SpoilSvc-->>ProfitSvc: Spoilage Risk Score, Loss %
        ProfitSvc-->>RecSvc: Financial Metrics (Gross Rev, Net Return, Net Profit)
    end

    Note over RecSvc: Construct Decision Matrix X (m x n)<br/>Apply Vector Normalization (r_ij)<br/>Compute Weighted Matrix (v_ij)<br/>Calculate Ideal Best (A+) & Worst (A-)<br/>Compute Euclidean Distances (S+, S-)<br/>Calculate Closeness Coefficient (Ci)

    RecSvc-->>RecRouter: Sorted Rankings, Hero Recommended Mandi & Rationale
    RecRouter-->>Farmer: HTTP 200 JSON Response
```

---

## 5. Security & Deployment Architecture

- **Stateless Application Server**: FastAPI server runs as an independent stateless process, easily horizontally scalable behind NGINX or reverse proxies.
- **Strict Environment Isolation**: All database passwords and configuration parameters are loaded via `app.config.Settings` (Pydantic Settings) reading `.env` files. No credentials or secrets are committed to version control.
- **Fail-Safe Downstream Handling**: Isolated candidate market evaluation prevents network or data errors in a single market from crashing the entire batch recommendation.
- **Client-Side Security**: Frontend communicates purely via standardized JSON REST APIs without exposing database connections or server secrets.
