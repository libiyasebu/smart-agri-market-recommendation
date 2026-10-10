# Agri_mini CEDA Market Coverage & Prediction Eligibility Report

**Generated**: October 2026  
**Project**: `D:\Agri_mini`  
**Focus**: Current CEDA Random Forest Price-Prediction System Market Coverage Analysis  

---

## 1. Exact Training Dataset Identification

The current machine learning model artifact in production is **`models/agri_price_model.joblib`**, accompanied by its metadata in **`models/model_metrics.json`**. 

Inspection of `backend/scripts/train_price_model_ceda.py`, `models/model_metrics.json`, and the pipeline object confirms:

* **Exact Training Dataset File**: `data/processed/ml_price_features.csv`
* **Total Rows in Dataset**: **22,657**
  * **Training Split** (`date < 2025-08-15`): **19,561 rows** (86.33%)
  * **Chronological Test Split** (`date >= 2025-08-15`): **3,096 rows** (13.67%)
  * *(Matches `models/model_metrics.json` lines 52–53: `train_rows: 19561`, `test_rows: 3096`)*
* **Date Range**: **2024-10-01 to 2025-10-30** (13 months)
  * Train period: `2024-10-01` to `2025-08-14`
  * Test period: `2025-08-15` to `2025-10-30`
* **Target Variable**: `modal_price` (INR per quintal)
* **Number of Active Commodities**: **10**
* **Number of Districts**: **11**
* **Number of Unique Markets in Training Pipeline**: **84**
* **Model Type & Hyperparameters**: `RandomForestRegressor(n_estimators=200, max_features='sqrt', min_samples_leaf=5, random_state=42)` fitted inside an sklearn `Pipeline` with `ColumnTransformer` (OrdinalEncoder for categorical features + passthrough for 23 numerical features).

> **Important Data Evolution Note**:
> On `2026-10-04`, an additional data collection batch (`thrissur_discovery_batch.py`) downloaded historical data for Thrissur markets, updating `data/processed/ceda_prices_clean.csv` and `data/processed/ceda_prices_weather.csv` to **27,265 rows** and **104 markets**. However, **`models/agri_price_model.joblib` has NOT been retrained** since `2026-10-03`, and `data/processed/ml_price_features.csv` remains at **22,657 rows and 84 markets**.

---

## 2. Directory of All Actual Markets in the Training Dataset

All 84 unique markets extracted from the verified training dataset (`data/processed/ml_price_features.csv`):

| Market ID | Market Name | District ID | District Name | Total Records | Earliest Date | Latest Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **4391** | Market 4391 (Ernakulam) | 595 | Ernakulam | 64 | 2024-10-03 | 2024-12-31 |
| **2153** | Market 2153 (Idukki) | 596 | Idukki | 2 | 2024-12-08 | 2024-12-29 |
| **2158** | Market 2158 (Kannur) | 589 | Kannur | 898 | 2024-10-03 | 2025-10-30 |
| **136** | Market 136 (Kannur) | 589 | Kannur | 897 | 2024-10-02 | 2025-10-30 |
| **138** | Kannur Market | 589 | Kannur | 717 | 2024-10-02 | 2025-10-30 |
| **2373** | Market 2373 (Kannur) | 589 | Kannur | 644 | 2024-10-03 | 2025-10-29 |
| **3092** | Market 3092 (Kannur) | 589 | Kannur | 272 | 2024-10-03 | 2025-10-30 |
| **10461** | Market 10461 (Kannur) | 589 | Kannur | 269 | 2024-10-02 | 2025-10-30 |
| **10462** | Market 10462 (Kannur) | 589 | Kannur | 240 | 2024-10-02 | 2025-10-30 |
| **137** | Market 137 (Kannur) | 589 | Kannur | 146 | 2024-10-02 | 2024-12-31 |
| **10752** | Market 10752 (Kannur) | 589 | Kannur | 114 | 2025-05-27 | 2025-10-30 |
| **10750** | Market 10750 (Kannur) | 589 | Kannur | 102 | 2025-06-02 | 2025-10-30 |
| **4388** | Market 4388 (Kannur) | 589 | Kannur | 98 | 2024-10-11 | 2025-08-13 |
| **10747** | Market 10747 (Kannur) | 589 | Kannur | 98 | 2025-06-03 | 2025-10-30 |
| **10748** | Market 10748 (Kannur) | 589 | Kannur | 97 | 2025-06-02 | 2025-10-30 |
| **10749** | Market 10749 (Kannur) | 589 | Kannur | 64 | 2025-06-02 | 2025-10-30 |
| **10751** | Market 10751 (Kannur) | 589 | Kannur | 54 | 2025-06-05 | 2025-10-30 |
| **2371** | Market 2371 (Kannur) | 589 | Kannur | 37 | 2024-10-02 | 2024-12-13 |
| **10463** | Market 10463 (Kannur) | 589 | Kannur | 1 | 2024-10-02 | 2024-10-02 |
| **10460** | Market 10460 (Kannur) | 589 | Kannur | 1 | 2024-10-03 | 2024-10-03 |
| **2376** | Market 2376 (Kasaragod) | 588 | Kasaragod | 2,202 | 2024-10-01 | 2025-10-25 |
| **2375** | Market 2375 (Kasaragod) | 588 | Kasaragod | 1,773 | 2024-10-03 | 2025-09-30 |
| **2159** | Market 2159 (Kasaragod) | 588 | Kasaragod | 1,625 | 2024-10-03 | 2025-10-25 |
| **540** | Market 540 (Kasaragod) | 588 | Kasaragod | 587 | 2024-10-01 | 2025-10-30 |
| **10476** | Market 10476 (Kasaragod) | 588 | Kasaragod | 504 | 2024-10-10 | 2025-10-29 |
| **10477** | Market 10477 (Kasaragod) | 588 | Kasaragod | 302 | 2024-10-29 | 2025-10-29 |
| **2354** | Market 2354 (Kollam) | 600 | Kollam | 1 | 2024-12-30 | 2024-12-30 |
| **2157** | Kozhikode Market | 591 | Kozhikode | 1,311 | 2024-10-01 | 2025-10-29 |
| **3094** | Market 3094 (Kozhikode) | 591 | Kozhikode | 760 | 2024-10-02 | 2025-10-29 |
| **10464** | Market 10464 (Kozhikode) | 591 | Kozhikode | 565 | 2024-10-01 | 2025-10-30 |
| **539** | Market 539 (Kozhikode) | 591 | Kozhikode | 529 | 2024-10-02 | 2024-12-31 |
| **3093** | Market 3093 (Kozhikode) | 591 | Kozhikode | 432 | 2024-10-02 | 2024-12-31 |
| **3095** | Market 3095 (Kozhikode) | 591 | Kozhikode | 425 | 2024-10-02 | 2024-12-31 |
| **10468** | Market 10468 (Kozhikode) | 591 | Kozhikode | 324 | 2024-10-02 | 2025-10-30 |
| **3096** | Market 3096 (Kozhikode) | 591 | Kozhikode | 305 | 2024-10-03 | 2024-12-31 |
| **132** | Market 132 (Kozhikode) | 591 | Kozhikode | 242 | 2024-10-02 | 2024-12-31 |
| **10465** | Market 10465 (Kozhikode) | 591 | Kozhikode | 156 | 2024-10-07 | 2025-10-29 |
| **10467** | Market 10467 (Kozhikode) | 591 | Kozhikode | 128 | 2024-10-02 | 2025-10-27 |
| **10729** | Market 10729 (Kozhikode) | 591 | Kozhikode | 125 | 2025-05-27 | 2025-10-29 |
| **10466** | Market 10466 (Kozhikode) | 591 | Kozhikode | 113 | 2024-10-27 | 2025-10-30 |
| **10724** | Market 10724 (Kozhikode) | 591 | Kozhikode | 111 | 2025-05-27 | 2025-10-27 |
| **10725** | Market 10725 (Kozhikode) | 591 | Kozhikode | 106 | 2025-06-04 | 2025-10-30 |
| **10728** | Market 10728 (Kozhikode) | 591 | Kozhikode | 98 | 2025-06-04 | 2025-10-27 |
| **10726** | Market 10726 (Kozhikode) | 591 | Kozhikode | 94 | 2025-06-04 | 2025-10-27 |
| **10727** | Market 10727 (Kozhikode) | 591 | Kozhikode | 88 | 2025-05-28 | 2025-10-15 |
| **2155** | Market 2155 (Malappuram) | 592 | Malappuram | 300 | 2024-10-02 | 2025-03-17 |
| **3089** | Perinthalmanna Market | 592 | Malappuram | 225 | 2024-11-26 | 2025-03-29 |
| **142** | Market 142 (Malappuram) | 592 | Malappuram | 201 | 2024-10-02 | 2024-12-31 |
| **3090** | Market 3090 (Malappuram) | 592 | Malappuram | 169 | 2024-10-01 | 2024-12-31 |
| **3088** | Market 3088 (Malappuram) | 592 | Malappuram | 159 | 2024-10-03 | 2024-12-31 |
| **3091** | Market 3091 (Malappuram) | 592 | Malappuram | 118 | 2024-10-02 | 2024-12-31 |
| **10463** | Market 10463 (Malappuram) | 592 | Malappuram | 63 | 2024-10-02 | 2024-12-31 |
| **10503** | Market 10503 (Malappuram) | 592 | Malappuram | 62 | 2024-10-14 | 2024-12-31 |
| **10458** | Market 10458 (Malappuram) | 592 | Malappuram | 61 | 2024-10-04 | 2024-12-31 |
| **10457** | Market 10457 (Malappuram) | 592 | Malappuram | 43 | 2024-10-03 | 2024-12-30 |
| **10460** | Market 10460 (Malappuram) | 592 | Malappuram | 32 | 2024-10-01 | 2024-12-30 |
| **10461** | Market 10461 (Malappuram) | 592 | Malappuram | 25 | 2024-10-07 | 2024-12-30 |
| **10462** | Market 10462 (Malappuram) | 592 | Malappuram | 15 | 2024-12-03 | 2024-12-31 |
| **10459** | Market 10459 (Malappuram) | 592 | Malappuram | 9 | 2024-10-09 | 2024-12-29 |
| **144** | Market 144 (Palakkad) | 593 | Palakkad | 278 | 2024-10-01 | 2024-12-31 |
| **2368** | Market 2368 (Palakkad) | 593 | Palakkad | 260 | 2024-10-02 | 2024-12-31 |
| **143** | Market 143 (Palakkad) | 593 | Palakkad | 234 | 2024-10-01 | 2024-12-31 |
| **2531** | Market 2531 (Palakkad) | 593 | Palakkad | 196 | 2024-10-01 | 2024-12-31 |
| **3087** | Market 3087 (Palakkad) | 593 | Palakkad | 179 | 2024-10-01 | 2024-12-31 |
| **8305** | Market 8305 (Palakkad) | 593 | Palakkad | 72 | 2024-10-04 | 2024-12-12 |
| **10453** | Market 10453 (Palakkad) | 593 | Palakkad | 37 | 2024-10-02 | 2024-12-07 |
| **10452** | Market 10452 (Palakkad) | 593 | Palakkad | 27 | 2024-10-09 | 2024-12-26 |
| **8304** | Market 8304 (Palakkad) | 593 | Palakkad | 1 | 2024-12-01 | 2024-12-01 |
| **10329** | Market 10329 (Thiruvananthapuram) | 601 | Thiruvananthapuram | 13 | 2024-11-17 | 2024-11-29 |
| **148** | Thrissur Market 148 | 594 | Thrissur | 16 | 2024-10-14 | 2024-12-26 |
| **2154** | Market 2154 (Wayanad) | 590 | Wayanad | 353 | 2024-10-02 | 2025-10-27 |
| **2374** | Market 2374 (Wayanad) | 590 | Wayanad | 335 | 2024-10-03 | 2025-10-30 |
| **10471** | Market 10471 (Wayanad) | 590 | Wayanad | 243 | 2024-10-03 | 2025-10-29 |
| **150** | Market 150 (Wayanad) | 590 | Wayanad | 192 | 2024-10-03 | 2024-12-31 |
| **10469** | Market 10469 (Wayanad) | 590 | Wayanad | 191 | 2024-10-08 | 2025-10-24 |
| **10472** | Market 10472 (Wayanad) | 590 | Wayanad | 144 | 2024-10-03 | 2025-10-14 |
| **10740** | Market 10740 (Wayanad) | 590 | Wayanad | 123 | 2025-06-01 | 2025-10-29 |
| **10743** | Market 10743 (Wayanad) | 590 | Wayanad | 120 | 2025-06-02 | 2025-10-29 |
| **10744** | Market 10744 (Wayanad) | 590 | Wayanad | 116 | 2025-05-28 | 2025-10-24 |
| **10746** | Market 10746 (Wayanad) | 590 | Wayanad | 76 | 2025-07-16 | 2025-10-24 |
| **10742** | Market 10742 (Wayanad) | 590 | Wayanad | 74 | 2025-06-08 | 2025-10-14 |
| **10745** | Market 10745 (Wayanad) | 590 | Wayanad | 74 | 2025-06-08 | 2025-10-14 |
| **10741** | Market 10741 (Wayanad) | 590 | Wayanad | 70 | 2025-06-09 | 2025-10-14 |
| **149** | Market 149 (Wayanad) | 590 | Wayanad | 32 | 2024-11-08 | 2024-12-30 |

---

## 3. Commodity × Market Coverage

Across the **10 active commodities**, coverage is highly concentrated in **Banana (commodity_id: 19)**, while high-demand vegetables (Tomato, Onion, Potato) have much smaller market footprints:

| Commodity | ID | Records | Districts | Markets | Market Breakdown (Market ID: Observations) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Banana** | 19 | 11,778 | 6 | 66 | Market 136 (828), Kannur Market 138 (717), Market 142 (132), Market 143 (139), Market 144 (184), Market 540 (587), Market 2154 (283), Market 2155 (151), Kozhikode Market 2157 (829), Market 2158 (828), Market 2368 (166), Market 2371 (37), Market 2373 (575), Market 2374 (265), Market 2375 (693), Market 2376 (1,154), Market 2531 (102), Market 3087 (85), Market 3088 (65), Perinthalmanna Market 3089 (83), Market 3090 (75), Market 3091 (24), Market 3092 (272), Market 3094 (328), Market 4388 (98), Market 8305 (72), Market 10452 (27), Market 10453 (37), Market 10457 (43), Market 10458 (61), Market 10459 (9), Market 10460 (32), Market 10461 (25), Market 10462 (15), Market 10463 (63), Market 10464 (242), Market 10465 (156), Market 10466 (113), Market 10467 (128), Market 10468 (324), Market 10469 (191), Market 10471 (243), Market 10472 (144), Market 10476 (504), Market 10477 (301), Market 10503 (62), Market 10724 (111), Market 10725 (106), Market 10726 (94), Market 10727 (88), Market 10728 (98), Market 10729 (125), Market 10740 (123), Market 10741 (70), Market 10742 (74), Market 10743 (120), Market 10744 (116), Market 10745 (74), Market 10746 (76), Market 10747 (98), Market 10748 (97), Market 10749 (64), Market 10750 (102), Market 10751 (54), Market 10752 (114), Market 10461 (244), Market 10462 (225) |
| **Onion** | 23 | 1,100 | 3 | 12 | Market 132 (68), Market 136 (69), Market 137 (73), Market 539 (69), Kozhikode Market 2157 (69), Market 2158 (70), Market 2159 (301), Market 2376 (193), Market 3093 (68), Market 3094 (72), Market 3095 (75), Market 3096 (73) |
| **Potato** | 24 | 1,201 | 3 | 12 | Market 132 (70), Market 136 (69), Market 539 (70), Kozhikode Market 2157 (69), Market 2158 (70), Market 2159 (295), Market 2375 (175), Market 2376 (240), Market 3093 (71), Market 3094 (72), Market 3095 (70), Market 3096 (70) |
| **Brinjal** | 35 | 1,326 | 4 | 15 | Market 132 (35), Market 150 (64), Market 539 (70), Kozhikode Market 2157 (69), Market 2158 (70), Market 2159 (201), Market 2373 (69), Market 2375 (166), Market 2376 (173), Market 3093 (70), Market 3094 (72), Market 3095 (70), Market 3096 (70), Market 10460 (1), Market 10464 (81) |
| **Tomato** | 78 | 1,255 | 4 | 14 | Market 132 (69), Market 136 (69), Market 539 (70), Kozhikode Market 2157 (69), Market 2158 (70), Market 2373 (69), Market 2375 (174), Market 2376 (173), Market 3093 (71), Market 3094 (72), Market 3095 (70), Market 3096 (70), Market 10464 (84), Market 10463 (1) |
| **Green Chilli** | 87 | 1,405 | 4 | 15 | Market 150 (64), Market 539 (70), Market 2154 (70), Kozhikode Market 2157 (69), Market 2158 (70), Market 2373 (69), Market 2374 (70), Market 2375 (173), Market 2376 (269), Market 3093 (70), Market 3094 (72), Market 3095 (70), Market 3096 (70), Market 10461 (25), Market 10464 (84) |
| **Banana-Green** | 90 | 1,273 | 4 | 14 | Market 137 (73), Market 149 (32), Market 150 (64), Market 539 (70), Market 2159 (301), Market 2373 (69), Market 2375 (175), Market 2376 (170), Market 3094 (72), Market 3095 (70), Market 3096 (22), Market 10461 (25), Market 10462 (15), Market 10464 (76) |
| **Sweet Potato** | 152 | 736 | 8 | 14 | Market 143 (95), Market 144 (94), Thrissur Market 148 (16), Market 2153 (2), Market 2155 (149), Market 2354 (1), Market 2368 (94), Market 2375 (36), Market 2531 (94), Perinthalmanna Market 3089 (94), Market 3087 (94), Market 8304 (1), Market 10329 (13), Market 10477 (1) |
| **Carrot** | 153 | 1,288 | 4 | 17 | Market 132 (68), Market 136 (69), Market 142 (69), Market 539 (70), Market 2155 (69), Kozhikode Market 2157 (69), Market 2159 (267), Market 2375 (173), Market 3088 (94), Perinthalmanna Market 3089 (24), Market 3090 (94), Market 3091 (94), Market 3093 (72), Market 3094 (72), Market 3095 (70), Market 3096 (70), Market 10464 (82) |
| **Cabbage** | 154 | 1,295 | 3 | 15 | Market 142 (69), Market 539 (70), Market 2155 (69), Kozhikode Market 2157 (68), Market 2159 (261), Market 2375 (184), Market 2376 (244), Market 3088 (94), Perinthalmanna Market 3089 (24), Market 3090 (94), Market 3091 (94), Market 3093 (72), Market 3094 (72), Market 3095 (70), Market 3096 (22) |

---

## 4. Actual Prediction Eligibility Analysis

### Requirement Verification from Code
Inspection of `backend/app/services/price_prediction_service.py` (lines 121–153):
1. **Commodity Validity**: `commodity_id` must exist in `ACTIVE_COMMODITIES` (all 10 are registered).
2. **District History Validity**: `district_id` must have weather history in the cache `<= prediction_date`.
3. **Market Series History**: The strictly prior historical series `hist[(hist["commodity_id"] == commodity_id) & (hist["market_id"] == market_id) & (hist["date"] < pred_ts)]` must satisfy:
   $$\text{len(series)} \ge \text{MIN\_LAG\_ROWS} \quad (\text{MIN\_LAG\_ROWS} = 2)$$
   If $\text{len(series)} == 0$, raises: `ValueError("market_id has no historical records for commodity_id")`.
   If $\text{len(series)} < 2$, raises: `ValueError("Insufficient historical records: found {n} prior observations... Minimum required: 2")`.

### Eligibility Calculation Matrix
Across the theoretical space of $10 \text{ commodities} \times 84 \text{ markets} = 840$ combinations in the model feature space:
* **Eligible Combinations** ($\ge 2$ records): **191 combinations** (22.7%)
* **Ineligible Combinations with Sparse Data** ($1$ record): **3 combinations** (0.4%)
  * Sweet Potato at Market 2354 (Kollam): 1 record $\rightarrow$ **INELIGIBLE**
  * Sweet Potato at Market 8304 (Palakkad): 1 record $\rightarrow$ **INELIGIBLE**
  * Sweet Potato at Market 10477 (Kasaragod): 1 record $\rightarrow$ **INELIGIBLE**
* **Ineligible Combinations with Zero Data** ($0$ records): **646 combinations** (76.9%)

### Sample Commodity × Market Eligibility Table

| Commodity | Market ID | Genuine Market Name | District | Historical Records | Prediction Eligible? | Reason |
| :--- | :---: | :--- | :--- | :---: | :---: | :--- |
| **Banana** | 2157 | Kozhikode Market | Kozhikode | 829 | **YES** | Meets minimum 2 historical records requirement (829 records) |
| **Banana** | 3089 | Perinthalmanna Market | Malappuram | 83 | **YES** | Meets minimum 2 historical records requirement (83 records) |
| **Banana** | 147 | Thrissur APMC (Sakthan Market) | Thrissur | 0 *(in ml_features)* | **NO** | Zero records in RF training dataset *(out-of-vocabulary in model)* |
| **Banana** | 2152 | Chalakudy Wholesale Market | Thrissur | 0 | **NO** | Zero records in RF training dataset |
| **Banana** | 2366 | Kunnamkulam Market | Thrissur | 0 | **NO** | Zero records in RF training dataset |
| **Banana** | 2364 | Kodungallur Market | Thrissur | 0 | **NO** | Zero records in RF training dataset |
| **Tomato** | 2157 | Kozhikode Market | Kozhikode | 69 | **YES** | Meets minimum 2 historical records requirement (69 records) |
| **Tomato** | 3089 | Perinthalmanna Market | Malappuram | 0 | **NO** | Zero records for Tomato in this market |
| **Tomato** | 2376 | Market 2376 (Kasaragod) | Kasaragod | 173 | **YES** | Meets minimum 2 historical records requirement (173 records) |
| **Onion** | 2157 | Kozhikode Market | Kozhikode | 69 | **YES** | Meets minimum 2 historical records requirement (69 records) |
| **Onion** | 136 | Market 136 (Kannur) | Kannur | 69 | **YES** | Meets minimum 2 historical records requirement (69 records) |
| **Sweet Potato** | 3089 | Perinthalmanna Market | Malappuram | 94 | **YES** | Meets minimum 2 historical records requirement (94 records) |
| **Sweet Potato** | 2354 | Market 2354 (Kollam) | Kollam | 1 | **NO** | Insufficient historical records (only 1 record, < 2 required) |
| **Sweet Potato** | 8304 | Market 8304 (Palakkad) | Palakkad | 1 | **NO** | Insufficient historical records (only 1 record, < 2 required) |
| **Sweet Potato** | 148 | Thrissur Market 148 | Thrissur | 16 | **YES** | Meets minimum 2 historical records requirement (16 records) |

---

## 5. Answers to Mandatory Analysis Questions

### A. How many unique markets exist in the Random Forest training dataset?
**84 unique markets.**  
All 84 markets are present in `data/processed/ml_price_features.csv`, and all 84 markets appear in the training split (`train_df`, 19,561 rows) fitted into the Random Forest `OrdinalEncoder`.

### B. How many markets are actually eligible for prediction for at least one commodity?
**82 markets.**  
Of the 84 markets, 82 have at least $\ge 2$ historical observations for at least one commodity. Exactly 2 markets (Market ID 2354 in Kollam and Market ID 8304 in Palakkad) have only 1 total observation in the entire dataset and therefore cannot meet the `MIN_LAG_ROWS = 2` requirement.

### C. Does every market support all 10 commodities?
**NO.** Not a single market supports all 10 commodities.
* Maximum commodities supported by any market: **9 commodities** (only Market 2375 in Kasaragod supports 9 commodities).
* **0 markets** support 10 commodities.
* **51 markets** support ONLY 1 commodity (predominantly Banana).
* 10 markets support 2 commodities, 5 support 3, 2 support 4, 4 support 5, 1 supports 6, 2 support 7, and 6 support 8.

### D. Which commodity supports the largest number of markets?
**Banana (commodity_id: 19)** supports the largest number of markets: **66 markets**.

### E. Which commodity supports the smallest number of markets?
**Onion (commodity_id: 23)** and **Potato (commodity_id: 24)** support the smallest number of markets: tied at **12 markets each**.

### F. Which districts currently have prediction coverage?
**10 districts** have prediction coverage (at least one prediction-eligible market):
1. **Kannur** (District ID 589): 18 eligible markets
2. **Kozhikode** (District ID 591): 18 eligible markets
3. **Wayanad** (District ID 590): 14 eligible markets
4. **Malappuram** (District ID 592): 14 eligible markets
5. **Palakkad** (District ID 593): 8 eligible markets (out of 9; market 8304 has only 1 row)
6. **Kasaragod** (District ID 588): 6 eligible markets
7. **Ernakulam** (District ID 595): 1 eligible market (Market 4391)
8. **Thrissur** (District ID 594): 1 eligible market (Market 148)
9. **Thiruvananthapuram** (District ID 601): 1 eligible market (Market 10329)
10. **Idukki** (District ID 596): 1 eligible market (Market 2153)

*(Kollam district 600 has 0 eligible markets because its sole market, 2354, has only 1 record. Kottayam 597, Alappuzha 598, and Pathanamthitta 599 currently have 0 records in CEDA).*

### G. Are the 6 markets currently shown in the frontend the complete model coverage or only frontend/demo candidate markets?
They are **ONLY frontend/demo candidate markets**. They represent a curated sample of 6 markets, not the 84 markets present in the model training data.

### H. Are there model-supported markets that are currently missing from the frontend?
**YES, 80 model-supported markets are missing from the frontend.**  
Out of 82 eligible markets in the training dataset, only 2 (Kozhikode ID 2157 and Perinthalmanna ID 3089) are currently exposed in the frontend.

---

## 6. Frontend vs. Model Coverage Discrepancy & Audit

### Comparison Table

| Frontend Market Name | Market ID | District ID | In RF Training Set (`ml_price_features`)? | In Runtime History (`ceda_prices_weather`)? | Eligible Commodities ($\ge 2$ rows) | Ineligible Commodities |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **Thrissur APMC (Sakthan Market)** | 147 | 594 | ❌ NO (0 rows) | ✅ YES (641 rows) | Banana, Onion, Potato, Brinjal, Tomato, Chilli, Green-Banana, Carrot, Cabbage (9 crops) | Sweet Potato (0 rows) |
| **Chalakudy Wholesale Market** | 2152 | 594 | ❌ NO (0 rows) | ✅ YES (519 rows) | Onion, Potato, Brinjal, Tomato, Chilli, Green-Banana, Carrot, Cabbage (8 crops) | Banana (0 rows), Sweet Potato (0 rows) |
| **Kunnamkulam Market** | 2366 | 594 | ❌ NO (0 rows) | ✅ YES (482 rows) | Banana, Onion, Potato, Brinjal, Tomato, Chilli, Green-Banana, Carrot, Cabbage (9 crops) | Sweet Potato (0 rows) |
| **Kodungallur Market** | 2364 | 594 | ❌ NO (0 rows) | ✅ YES (306 rows) | Banana, Onion, Potato, Brinjal, Tomato, Chilli, Green-Banana, Carrot, Cabbage (9 crops) | Sweet Potato (0 rows) |
| **Kozhikode Market** | 2157 | 591 | ✅ YES (1,311 rows) | ✅ YES (1,319 rows) | Banana, Onion, Potato, Brinjal, Tomato, Chilli, Carrot, Cabbage (8 crops) | Green-Banana (0 rows), Sweet Potato (0 rows) |
| **Perinthalmanna Market** | 3089 | 592 | ✅ YES (225 rows) | ✅ YES (229 rows) | Banana, Sweet Potato, Carrot, Cabbage (4 crops) | Onion, Potato, Brinjal, Tomato, Chilli, Green-Banana (6 crops with 0 rows) |

### Key Architectural Finding
1. **Model vs. Runtime History Disconnect**:
   The Random Forest model (`models/agri_price_model.joblib`) was trained on `2026-10-03` using `ml_price_features.csv` (84 markets). The four Thrissur markets (147, 2152, 2366, 2364) were acquired on `2026-10-04` by `thrissur_discovery_batch.py` and merged into `ceda_prices_weather.csv` (104 markets), but the model was never retrained.
2. **How Inference Currently Behaves for Thrissur**:
   When the user selects Thrissur APMC (147) in the frontend, `PricePredictionService` successfully pulls historical lags from `ceda_prices_weather.csv` (where 147 has 641 rows). However, inside `agri_price_model.joblib`, the fitted `OrdinalEncoder` has never seen `market_id=147`, so it encodes it as `-1` (`unknown_value=-1`). The trees still produce a prediction based on lag prices, date, and weather features, but without market-specific embedding.
3. **Frontend Commodity Mismatches**:
   * **Chalakudy Market (2152)** has **0 historical records for Banana**. If a user selects Banana with Chalakudy, the backend correctly raises HTTP 400 (`market_id=2152 has no historical records for commodity_id=19`).
   * **Perinthalmanna Market (3089)** has **0 historical records for Tomato, Onion, Potato, Brinjal, Green Chilli**.
   * **Sweet Potato (152)** has 0 records across all 4 Thrissur markets and Kozhikode Market.

---

## 7. Conclusions & Next Steps

1. **Retraining Opportunity**:
   Retraining the Random Forest model on the updated `ceda_prices_weather.csv` (27,265 rows) will officially add Thrissur APMC, Chalakudy, Kunnamkulam, and Kodungallur (plus 16 other Thrissur markets) directly into the model's vocabulary, expanding official model coverage from **84 to 104 markets**.
2. **Frontend Expansion**:
   The frontend currently only presents 6 markets. Expanding the UI selection to include top volume markets across Kannur, Kozhikode, Wayanad, Palakkad, and Kasaragod will unlock the model's true multi-district coverage.
3. **Crop-Specific Validation**:
   Frontend market selectors should dynamically disable markets that do not have trading history for the selected crop (e.g. disabling Chalakudy when Banana is selected).
