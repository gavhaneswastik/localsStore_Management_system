from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
from database import init_db, seed_data, get_db
from analytics import get_restock_suggestions, compute_rfm, basket_analysis, vendor_performance

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize DB and seed data on first run
with app.app_context():
    init_db()
    seed_data()

# Helper to execute queries
def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.execute(query, args)
    conn.commit()
    conn.close()

# ---------- Routes ----------
@app.route('/')
def dashboard():
    # Basic stats
    total_sales = query_db("SELECT SUM(total_amount) FROM sales")[0][0] or 0
    sales_count = query_db("SELECT COUNT(*) FROM sales")[0][0]
    cust_count = query_db("SELECT COUNT(*) FROM customers")[0][0]
    products = query_db("SELECT * FROM products")
    low_stock = [p for p in products if p['stock'] <= p['reorder_level']]
    
    return render_template('dashboard.html', total_sales=total_sales,
                           sales_count=sales_count, cust_count=cust_count,
                           products=products, low_stock=low_stock)

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if request.method == 'POST':
        date = request.form['date']
        customer_id = request.form.get('customer_id') or None
        payment_mode = request.form['payment_mode']
        # Process items: product_id[] and quantity[]
        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')
        
        total = 0
        # Validate stock
        for pid, qty in zip(product_ids, quantities):
            if not qty: continue
            qty = int(qty)
            stock = query_db("SELECT stock FROM products WHERE id=?", [pid], one=True)[0]
            if qty > stock:
                flash(f"Insufficient stock for product ID {pid}", "danger")
                return redirect(url_for('sales'))
        
        # Insert sale
        conn = get_db()
        cur = conn.execute("INSERT INTO sales (date, customer_id, total_amount, payment_mode) VALUES (?,?,?,?)",
                          (date, customer_id, 0, payment_mode))
        sale_id = cur.lastrowid
        for pid, qty in zip(product_ids, quantities):
            if not qty: continue
            qty = int(qty)
            price = query_db("SELECT selling_price FROM products WHERE id=?", [pid], one=True)[0]
            total += qty * price
            conn.execute("INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?,?,?,?)",
                        (sale_id, pid, qty, price))
            conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, pid))
        conn.execute("UPDATE sales SET total_amount = ? WHERE id = ?", (total, sale_id))
        conn.commit()
        conn.close()
        
        flash("Sale recorded successfully!", "success")
        return redirect(url_for('sales'))
    
    products = query_db("SELECT * FROM products WHERE stock > 0")
    customers = query_db("SELECT id, name FROM customers")
    return render_template('sales.html', products=products, customers=customers)

@app.route('/inventory')
def inventory():
    products = query_db("SELECT * FROM products")
    suggestions = get_restock_suggestions()
    return render_template('inventory.html', products=products, suggestions=suggestions)

@app.route('/restock', methods=['POST'])
def restock():
    product_id = request.form['product_id']
    quantity = request.form['quantity']
    vendor_id = request.form['vendor_id']
    cost = request.form.get('cost_per_unit') or 0
    date = datetime.now().strftime('%Y-%m-%d')
    execute_db("INSERT INTO restocks (date, vendor_id, product_id, quantity, cost_per_unit) VALUES (?,?,?,?,?)",
              (date, vendor_id, product_id, quantity, cost))
    execute_db("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
    flash("Restock recorded", "success")
    return redirect(url_for('inventory'))

@app.route('/customers')
def customers():
    rfm_df = compute_rfm()
    return render_template('customers.html', customers=rfm_df.to_dict('records'))

@app.route('/vendors')
def vendors():
    perf = vendor_performance()
    return render_template('vendors.html', vendors=perf.to_dict('records'))

@app.route('/basket')
def basket():
    pairs = basket_analysis()
    return render_template('basket.html', pairs=pairs)

# ---------- Add New Product ----------
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    vendors = query_db("SELECT id, name FROM vendors")
    if request.method == 'POST':
        name = request.form['name']
        category = request.form.get('category', '')
        cost_price = float(request.form['cost_price'])
        selling_price = float(request.form['selling_price'])
        stock = int(request.form['stock'])
        reorder_level = int(request.form['reorder_level'])
        vendor_id = request.form.get('vendor_id') or None

        execute_db(
            "INSERT INTO products (name, category, cost_price, selling_price, stock, reorder_level, vendor_id) VALUES (?,?,?,?,?,?,?)",
            (name, category, cost_price, selling_price, stock, reorder_level, vendor_id)
        )
        flash("Product added successfully!", "success")
        return redirect(url_for('inventory'))
    return render_template('add_product.html', vendors=vendors)

# ---------- Add New Customer ----------
@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        join_date = request.form.get('join_date', datetime.now().strftime('%Y-%m-%d'))
        try:
            execute_db("INSERT INTO customers (name, phone, join_date) VALUES (?,?,?)",
                       (name, phone, join_date))
            flash("Customer added!", "success")
            return redirect(url_for('customers'))
        except sqlite3.IntegrityError:
            flash("Phone number already exists.", "danger")
    return render_template('add_customer.html')

# ---------- Add New Vendor ----------
@app.route('/add_vendor', methods=['GET', 'POST'])
def add_vendor():
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        lead_time = int(request.form['lead_time_days'])
        pin = request.form.get('pin', '1234')
        execute_db("INSERT INTO vendors (name, contact, lead_time_days, pin) VALUES (?,?,?,?)",
                   (name, contact, lead_time, pin))
        flash("Vendor added!", "success")
        return redirect(url_for('vendors'))
    return render_template('add_vendor.html')
# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)