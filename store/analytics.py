import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import sqlite3
import warnings
warnings.filterwarnings('ignore')

DB_NAME = 'store.db'

def get_sales_history(product_id, days=60):
    """Fetch daily sales quantity for a product."""
    conn = sqlite3.connect(DB_NAME)
    query = """
    SELECT s.date, SUM(si.quantity) as qty
    FROM sales s
    JOIN sale_items si ON s.id = si.sale_id
    WHERE si.product_id = ?
    GROUP BY s.date
    ORDER BY s.date
    """
    df = pd.read_sql_query(query, conn, params=(product_id,))
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=['date', 'qty'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').asfreq('D', fill_value=0).reset_index()
    return df

def forecast_demand(product_id, periods=7):
    """Generate weekly forecast for a product using Exponential Smoothing."""
    df = get_sales_history(product_id, days=60)
    if len(df) < 14:  # Not enough data
        return None
    try:
        model = ExponentialSmoothing(df['qty'], trend='add', seasonal='add', seasonal_periods=7)
        fitted = model.fit()
        forecast = fitted.forecast(periods)
        return forecast.tolist()
    except:
        # Fallback: simple moving average
        return [df['qty'].mean()] * periods

def get_restock_suggestions():
    """Return list of products needing restock, with suggested order quantities."""
    conn = sqlite3.connect(DB_NAME)
    products = pd.read_sql_query("SELECT * FROM products", conn)
    vendors = pd.read_sql_query("SELECT * FROM vendors", conn)
    conn.close()
    
    suggestions = []
    for _, prod in products.iterrows():
        forecast = forecast_demand(prod['id'], periods=7)
        if forecast is None:
            continue
        lead_time = vendors[vendors['id'] == 2]['lead_time_days'].values[0]  # simplified: assume vendor id 2 for all
        # Safety stock: 1.65 * std of demand over lead time
        hist = get_sales_history(prod['id'], days=lead_time*3)  # get recent data
        if len(hist) < lead_time:
            std_demand = 0
        else:
            std_demand = hist['qty'].std()
        safety_stock = 1.65 * std_demand * np.sqrt(lead_time)
        demand_lead = sum(forecast[:lead_time])
        reorder_point = demand_lead + safety_stock
        if prod['stock'] <= reorder_point:
            order_qty = sum(forecast) + safety_stock - prod['stock']
            suggestions.append({
                'product_id': prod['id'],
                'name': prod['name'],
                'current_stock': prod['stock'],
                'forecast_7day': sum(forecast),
                'reorder_point': round(reorder_point),
                'suggested_order': max(0, round(order_qty))
            })
    return suggestions

def compute_rfm():
    """Calculate Recency, Frequency, Monetary values per customer."""
    conn = sqlite3.connect(DB_NAME)
    customers = pd.read_sql_query("SELECT * FROM customers", conn)
    sales = pd.read_sql_query("SELECT * FROM sales WHERE customer_id IS NOT NULL", conn)
    conn.close()
    
    if sales.empty:
        customers['segment'] = 'No Data'
        return customers[['id', 'name', 'phone', 'recency', 'frequency', 'monetary', 'segment', 'loyalty_points']]
    
    sales['date'] = pd.to_datetime(sales['date'])
    now = datetime.now()
    
    rfm = sales.groupby('customer_id').agg(
        recency=('date', lambda x: (now - x.max()).days),
        frequency=('id', 'count'),
        monetary=('total_amount', 'sum')
    ).reset_index()
    
    # Merge with customer info
    rfm = customers.merge(rfm, left_on='id', right_on='customer_id', how='left')
    rfm[['recency', 'frequency', 'monetary']] = rfm[['recency', 'frequency', 'monetary']].fillna(0)
    
    # Function to assign quartile scores (1-4) even with ties
    def assign_quartile(series, ascending=True):
        """Assign 1 to 4 based on quartile ranks. 
           ascending=True means smaller values get lower scores (for recency, lower recency is better, we want high score for low recency).
        """
        if len(series.dropna()) == 0:
            return pd.Series(1, index=series.index)
        # Rank the series
        ranks = series.rank(ascending=ascending, method='first')
        # Divide into 4 quantiles based on rank
        max_rank = ranks.max()
        if max_rank <= 4:
            # Not enough distinct values, assign scores 1..max_rank based on rank
            return ranks.astype(int)
        else:
            # Calculate quartile boundaries
            quartile_size = max_rank / 4.0
            scores = pd.cut(ranks, bins=[0, quartile_size, 2*quartile_size, 3*quartile_size, max_rank],
                            labels=[1, 2, 3, 4], include_lowest=True)
            return scores.astype(int)
    
    # For recency, lower is better -> ascending=True (rank 1 = best -> score 4)
    # We'll map the final scores so that lower recency gets higher score
    rfm['R_score'] = assign_quartile(rfm['recency'], ascending=True)
    # Invert: rank 1 -> score 4, rank 2 -> score 3, etc.
    rfm['R_score'] = 5 - rfm['R_score']
    
    rfm['F_score'] = assign_quartile(rfm['frequency'], ascending=False)  # higher frequency is better
    rfm['M_score'] = assign_quartile(rfm['monetary'], ascending=False)   # higher monetary is better
    
    # Segment definitions based on R, F, M scores (simplified)
    def segment(row):
        if row['R_score'] >= 3 and row['F_score'] >= 3:
            return 'VIP'
        elif row['R_score'] >= 2:
            return 'Regular'
        elif row['recency'] > 30:
            return 'At Risk'
        else:
            return 'New/Occasional'
    
    rfm['segment'] = rfm.apply(segment, axis=1)
    return rfm[['id', 'name', 'phone', 'recency', 'frequency', 'monetary', 'segment', 'loyalty_points']]

def basket_analysis(min_support=0.05):
    """Simple frequent itemset mining using co-occurrence matrix."""
    conn = sqlite3.connect(DB_NAME)
    # Get all sales with items
    sales = pd.read_sql_query("""
        SELECT si.sale_id, p.name as product_name
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
    """, conn)
    conn.close()
    
    # Create basket matrix
    basket = sales.groupby(['sale_id', 'product_name']).size().unstack(fill_value=0)
    basket = basket.applymap(lambda x: 1 if x > 0 else 0)
    
    # Calculate support for single items
    n_transactions = len(basket)
    item_support = basket.sum() / n_transactions
    
    # Find frequent pairs
    frequent_items = item_support[item_support >= min_support].index.tolist()
    pairs = []
    for i, item1 in enumerate(frequent_items):
        for item2 in frequent_items[i+1:]:
            support_pair = (basket[item1] & basket[item2]).sum() / n_transactions
            if support_pair >= min_support:
                confidence_1_2 = support_pair / item_support[item1] if item_support[item1] else 0
                confidence_2_1 = support_pair / item_support[item2] if item_support[item2] else 0
                pairs.append({
                    'items': f"{item1} + {item2}",
                    'support': round(support_pair, 3),
                    'confidence_1->2': round(confidence_1_2, 3),
                    'confidence_2->1': round(confidence_2_1, 3)
                })
    return pairs

def vendor_performance():
    """Calculate on-time delivery %, fill rate, avg quality per vendor."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM vendor_perf", conn)
    vendors = pd.read_sql_query("SELECT * FROM vendors", conn)
    conn.close()
    
    if df.empty:
        return vendors[['id','name']].assign(on_time_pct=0, fill_rate=0, quality_score=0)
    
    perf = df.groupby('vendor_id').agg(
        on_time_pct=('on_time_delivery', 'mean'),
        fill_rate=('fill_rate', 'mean'),
        quality_score=('quality_score', 'mean')
    ).reset_index()
    perf = vendors.merge(perf, left_on='id', right_on='vendor_id', how='left')
    perf = perf.fillna(0)
    perf['on_time_pct'] = (perf['on_time_pct'] * 100).round(1)
    perf['fill_rate'] = (perf['fill_rate'] * 100).round(1)
    perf['quality_score'] = perf['quality_score'].round(1)
    return perf[['id', 'name', 'on_time_pct', 'fill_rate', 'quality_score']]