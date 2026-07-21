# 📊 Low‑Level Store Management System

A **data‑science‑powered** retail management application designed for **small local stores** (kirana, mom‑and‑pop shops).  
It uses demand forecasting, customer segmentation, basket analysis, and vendor performance tracking to help the **store owner**, **customers**, and **suppliers** all benefit from a single smart system.

---

## 🎯 Who is this for?

| Stakeholder | Benefits |
|-------------|----------|
| 🏪 **Store Owner** | Reduce waste, never run out of stock, increase sales, save time, understand customers |
| 🧑‍🤝‍🧑 **Customer** | Personalised offers, loyalty rewards, faster service |
| 🚚 **Vendor / Supplier** | Clear demand signals, fair performance scorecard, better relationship |

---

## ✨ Key Features

- **Real‑time Dashboard** – Total sales, transaction count, customer count, low‑stock alerts
- **Sales Recording** – Add items, select customer, payment mode (Cash/UPI/Card), dynamic “Add Item” button
- **Smart Inventory**  
  - Daily demand forecasting (Exponential Smoothing)  
  - Safety stock & reorder point calculation  
  - Auto‑generated restock suggestions with quantity
- **Customer Segmentation (RFM)** – VIP, Regular, At‑Risk, New/Occasional – all computed from transaction history
- **Market Basket Analysis** – Finds frequently bought‑together product pairs (association rules) for combos & shelf placement
- **Vendor Portal**  
  - Vendor login (phone + PIN)  
  - See restock requests *only* for their own products  
  - View their performance scorecard (on‑time delivery %, fill rate, quality score)
- **Master Data Management** – Add new products, customers, and vendors directly from the UI
- **Mobile‑friendly** – Responsive Bootstrap interface

---

## 🧠 Data Science Techniques Used

| Technique | Library | Application |
|-----------|---------|--------------|
| Time‑series forecasting | `statsmodels` (Holt‑Winters) | Predict 7‑day demand for each product |
| Safety stock & reorder point | `numpy` / `pandas` | Determine when and how much to order |
| RFM analysis | `pandas` (quantile binning) | Segment customers based on Recency, Frequency, Monetary value |
| Association rule mining | Custom co‑occurrence matrix | Find product pairs with high support & confidence |
| Vendor scorecard | Aggregation on historical deliveries | On‑time %, fill rate, quality score |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask |
| Database | SQLite (lightweight, zero‑config) |
| Frontend | HTML5, Bootstrap 5, Vanilla JS |
| Analytics | pandas, statsmodels, scikit‑learn |
| Visualisation | (Optional) Matplotlib, but dashboard uses raw HTML tables |

---

