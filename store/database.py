import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import random

DB_NAME = 'store.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # Products (now includes vendor_id)
    cur.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        cost_price REAL,
        selling_price REAL,
        stock INTEGER DEFAULT 0,
        reorder_level INTEGER DEFAULT 10,
        vendor_id INTEGER,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id)
    )''')
    
    # Sales transactions
    cur.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        customer_id INTEGER,
        total_amount REAL,
        payment_mode TEXT
    )''')
    
    # Sale line items
    cur.execute('''CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY,
        sale_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price REAL,
        FOREIGN KEY(sale_id) REFERENCES sales(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')
    
    # Customers
    cur.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT UNIQUE,
        loyalty_points INTEGER DEFAULT 0,
        join_date TEXT
    )''')
    
    # Vendors (now includes pin)
    cur.execute('''CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        contact TEXT,
        lead_time_days INTEGER DEFAULT 2,
        pin TEXT DEFAULT '1234'
    )''')
    
    # Inventory restocks
    cur.execute('''CREATE TABLE IF NOT EXISTS restocks (
        id INTEGER PRIMARY KEY,
        date TEXT,
        vendor_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        cost_per_unit REAL,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )''')
    
    # Vendor performance records
    cur.execute('''CREATE TABLE IF NOT EXISTS vendor_perf (
        id INTEGER PRIMARY KEY,
        vendor_id INTEGER,
        date TEXT,
        on_time_delivery BOOLEAN,
        fill_rate REAL,
        quality_score REAL,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id)
    )''')
    
    conn.commit()
    conn.close()

def seed_data():
    """Populate DB with sample data for demonstration."""
    conn = get_db()
    cur = conn.cursor()
    
    # Only seed if tables are empty
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        conn.close()
        return
    
    # Products (8 columns: id, name, category, cost_price, selling_price, stock, reorder_level, vendor_id)
    products = [
        (1, 'Rice (1kg)', 'Grains', 45, 55, 50, 20, 2),
        (2, 'Wheat Flour (1kg)', 'Grains', 30, 38, 40, 15, 2),
        (3, 'Milk (500ml)', 'Dairy', 20, 25, 30, 10, 1),
        (4, 'Bread', 'Bakery', 15, 20, 25, 10, 1),
        (5, 'Eggs (dozen)', 'Dairy', 60, 75, 15, 5, 1),
        (6, 'Cooking Oil (1L)', 'Groceries', 120, 145, 20, 8, 2),
        (7, 'Toothpaste', 'Personal Care', 35, 45, 40, 15, 3),
        (8, 'Soap Bar', 'Personal Care', 18, 25, 60, 20, 3),
    ]
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?)", products)
    
    # Vendors (5 columns: id, name, contact, lead_time_days, pin)
    vendors = [
        (1, 'FreshFarm Dairy', '9876543210', 1, '1111'),
        (2, 'GrainHouse Ltd.', '9876543211', 2, '2222'),
        (3, 'General Supplies Co.', '9876543212', 3, '3333'),
    ]
    cur.executemany("INSERT INTO vendors VALUES (?,?,?,?,?)", vendors)
    
    # Customers (5 columns: id, name, phone, loyalty_points, join_date)
    customers = [
        (1, 'Ravi Kumar', '9999900001', 120, '2025-01-10'),
        (2, 'Anita Sharma', '9999900002', 85, '2025-02-15'),
        (3, 'Vikram Singh', '9999900003', 40, '2025-03-20'),
        (4, 'Priya Patel', '9999900004', 200, '2025-01-05'),
        (5, 'Suresh Reddy', '9999900005', 10, '2025-04-01'),
    ]
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)
    
    # Generate 60 days of sales
    today = datetime.now().date()
    for i in range(60):
        date = (today - timedelta(days=i)).isoformat()
        for _ in range(random.randint(3, 8)):
            cust_id = random.choice(customers)[0] if random.random() < 0.7 else None
            total = 0
            cur.execute("INSERT INTO sales (date, customer_id, total_amount, payment_mode) VALUES (?,?,?,?)",
                       (date, cust_id, 0, random.choice(['Cash', 'UPI', 'Card'])))
            sale_id = cur.lastrowid
            for _ in range(random.randint(1, 4)):
                prod = random.choice(products)
                qty = random.randint(1, 4)
                price = prod[4]  # selling_price is index 4
                total += qty * price
                cur.execute("INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?,?,?,?)",
                           (sale_id, prod[0], qty, price))
                cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, prod[0]))
            cur.execute("UPDATE sales SET total_amount = ? WHERE id = ?", (total, sale_id))
    
    # Ensure stocks don't go negative
    cur.execute("UPDATE products SET stock = 0 WHERE stock < 0")
    
    # Some restocks (30 days ago)
    for prod in products:
        cur.execute("INSERT INTO restocks (date, vendor_id, product_id, quantity, cost_per_unit) VALUES (?,?,?,?,?)",
                   ((today - timedelta(days=30)).isoformat(), prod[7], prod[0], 30, prod[3]))  # use product's vendor_id
    
    # Vendor performance records (random)
    for v in vendors:
        for _ in range(5):
            date = (today - timedelta(days=random.randint(1, 60))).isoformat()
            cur.execute("INSERT INTO vendor_perf (vendor_id, date, on_time_delivery, fill_rate, quality_score) VALUES (?,?,?,?,?)",
                       (v[0], date, random.choice([0,1]), round(random.uniform(0.7,1.0),2), round(random.uniform(3,5),1)))
    
    conn.commit()
    conn.close()