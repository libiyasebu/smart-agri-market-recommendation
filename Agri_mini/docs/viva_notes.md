# Agri_mini - Academic Viva & Examination Q&A Preparation Notes

This document provides clear, concise, and academically rigorous answers to potential questions during project evaluation, viva voce, or technical demonstrations.

---

### 1. What core problem does the Agri_mini system solve?
Smallholder farmers suffer from **informational asymmetry and multi-dimensional decision complexity** when marketing produce. While one mandi may offer a nominally higher price, higher road distance may lead to increased fuel freight and transit spoilage that wipes out the profit premium. Agri_mini unifies price forecasting, logistics costing, spoilage modeling, and multi-criteria TOPSIS ranking to recommend the objectively most profitable market destination.

---

### 2. Why was FastAPI selected over Flask or Django?
- **Asynchronous Performance**: Native `async`/`await` support on ASGI (Uvicorn) ensures high concurrent throughput.
- **Type Safety & Automatic Validation**: Powered by Pydantic v2, eliminating manual schema validation errors.
- **Automatic OpenAPI Documentation**: Automatically generates interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) without third-party plugins.
- **Lightweight Architecture**: Provides clean modularity without the unnecessary ORM or session overhead of Django.

---

### 3. Why was PostgreSQL chosen as the database?
- **Relational Integrity**: Enforces foreign keys, data types, and non-null constraints across market, weather, and routing tables.
- **Time-Series Query Efficiency**: Fast indexing on composite keys `(commodity, market, arrival_date)` enables instant retrieval of preceding historical lags.
- **ACID Compliance**: Ensures robust data ingestion and concurrent querying without database locking issues.

---

### 4. Why was Random Forest Regressor selected as the production model?
- **Non-Linear Relationships**: Accurately captures non-linear interactions between historical prices, weather parameters, and macro-economic factors.
- **Robustness to Overfitting**: Ensemble averaging across multiple decision trees reduces prediction variance compared to single trees.
- **Empirical Superiority**: In benchmark evaluations against Ridge, Decision Trees, and XGBoost, the tuned Random Forest achieved the lowest error metrics (**MAE: ₹ 21.20/qtl**, **$R^2: 0.9990$**).

---

### 5. Why is a chronological train/test split mandatory instead of random shuffling?
In time-series agricultural forecasting, random k-fold shuffling causes **lookahead data leakage** by training the model on future observations to predict past prices. A strictly chronological split ($80\%$ historical training, $20\%$ future testing) accurately simulates real-world forecasting conditions where only past data is available.

---

### 6. What is target leakage and how was it prevented?
- **Target Leakage**: Occurs when features contain information that would not be available at inference time.
- **Prevention in Agri_mini**: All engineered features (lags $t-1 \dots t-14$, 7-day rolling means, volatility) are derived strictly from records where `arrival_date < prediction_date`. Same-day or future prices are strictly excluded from the feature space.

---

### 7. Why include weather data (Open-Meteo) in price and spoilage models?
- **Price Forecasting**: Ambient weather (heat waves, heavy rainfall) disrupts harvesting and regional supply arrivals at mandis, causing price volatility.
- **Spoilage Estimation**: Elevated temperatures and relative humidity accelerate microbial respiration and post-harvest decay during road transit.

---

### 8. Why include FAOSTAT macro indicators?
FAOSTAT data provides national-level macro context on annual crop production volumes, yields (hg/ha), and harvested area. This allows the model to differentiate between national bumper harvest years (which depress baseline prices) and deficit years.

---

### 9. Why use OSRM (Open Source Routing Machine) instead of straight-line distance?
Straight-line (Euclidean) distance ignores actual road networks, ghat terrains, river crossings, and speed constraints. OSRM uses real OpenStreetMap road networks to compute actual drivable road distance (km) and driving travel time (minutes).

---

### 10. How is transportation cost calculated?
$$\text{Required Trips} = \left\lceil \frac{\text{Quantity (kg)}}{\text{Vehicle Capacity (kg)}} \right\rceil$$
$$\text{Fuel Expense} = \left( \frac{\text{Distance (km)}}{\text{Fuel Economy (km/L)}} \right) \times \text{Fuel Price (₹/L)}$$
$$\text{Total Cost} = \text{Trips} \times \Big( \text{Fuel Expense} + (\text{Distance} \times \text{Maintenance/km}) + \text{Driver Wage} + \text{Tolls} + \text{Misc} \Big)$$

---

### 11. Why is spoilage modeled as a rule-based heuristic rather than a machine learning model?
There is no publicly available, large-scale empirical dataset linking daily road shipments to physical spoilage percentages across Indian mandis. Using an agro-meteorological heuristic calibrated to verified post-harvest literature parameters (thermal thresholds, humidity sensitivity, transit hours) provides transparent, explainable, and scientifically grounded loss estimates.

---

### 12. What is the difference between Expected Net Return and Expected Profit?
- **Expected Net Return**: Realized revenue from sellable produce minus transportation freight costs:
  $$\text{Net Return} = (\text{Sellable Quintals} \times P_{\text{predicted}}) - \text{Transportation Cost}$$
- **Expected Profit**: True accounting profit after also subtracting the farmer's cultivation and harvest production costs:
  $$\text{Expected Profit} = \text{Expected Net Return} - \text{Production Cost}$$

---

### 13. What is TOPSIS and why was it chosen for market recommendation?
- **TOPSIS** stands for *Technique for Order Preference by Similarity to Ideal Solution*.
- It selects the alternative that is **closest to the Ideal Best Solution ($A^+$)** and **farthest from the Ideal Worst Solution ($A^-$)** in Euclidean geometric space.
- It provides a compensatory multi-criteria framework that balances conflicting objectives (maximizing profit/price while minimizing transport cost, duration, and spoilage risk).

---

### 14. What do Benefit and Cost criteria mean in TOPSIS?
- **Benefit Criteria** (Higher is better): e.g., Expected Profit, Predicted Modal Price.
- **Cost Criteria** (Lower is better): e.g., Transportation Cost, Transit Duration, Spoilage Risk Score.

---

### 15. Why can changing priority weights alter the recommended market?
TOPSIS normalizes and multiplies criteria values by user-defined weights $w_j$. If a farmer assigns a higher weight to *Transit Duration* (e.g. for highly fragile produce), closer mandis are favored over distant mandis even if the distant mandi has a slightly higher profit margin.

---

### 16. What are the known limitations of the system?
1. **Model Dataset Scope**: The price forecasting model is calibrated to the historical training dataset; periodic retraining is required.
2. **Dynamic Traffic**: OSRM routes represent standard driving profiles without live congestion tracking.
3. **Spoilage Formulation**: It is a calibrated heuristic rather than an empirical sensor-tracked ML model.

---

### 17. What are the recommended future enhancements?
- Live vehicle IoT temperature & humidity sensor streaming during transit.
- Farmer SMS/WhatsApp recommendation alerts in vernacular languages.
- Integration of live FASTag toll charges and real-time traffic APIs.
- Multi-crop load consolidation algorithms for smallholder farmer cooperatives.
