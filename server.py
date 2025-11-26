import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt

app = Flask(__name__)

# ---------------- DATABASE CONFIG ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'sunitha80'
app.config['MYSQL_DB'] = 'project'

# ---------------- JWT CONFIG ----------------
# IMPORTANT: real secret key
app.config['JWT_SECRET_KEY'] = "bd2e83a03a7ef2b53cf018a58f1b59d1470c8fd07f5c4b5c497ad1c903b812c1"

# accept tokens from headers only (Tkinter doesn't use cookies)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

mysql = MySQL(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# ---------------- REGISTER ----------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = data['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
    if cur.fetchone():
        return jsonify({'message': 'User already exists'}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    cur.execute("INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (username, email, pw_hash, 'customer'))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'User registered successfully'}), 201

# ---------------- LOGIN ----------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, password_hash, role FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()

    if user and bcrypt.check_password_hash(user[1], password):
        # Use a string identity; put role into additional claims to avoid 422 on protected routes
        token = create_access_token(identity=str(user[0]), additional_claims={'role': user[2]})
        return jsonify({'token': token, 'role': user[2]}), 200

    return jsonify({'message': 'Invalid credentials'}), 401

# ---------------- MANAGER LOGIN ----------------
@app.route('/manager_login', methods=['POST'])
def manager_login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, password_hash, role FROM users WHERE username=%s AND role='manager'", (username,))
    user = cur.fetchone()
    cur.close()

    if user and bcrypt.check_password_hash(user[1], password):
        token = create_access_token(identity=str(user[0]), additional_claims={'role': 'manager'})
        return jsonify({'token': token}), 200

    return jsonify({'message': 'Invalid manager credentials'}), 401

# ---------------- VIEW ALL ORDERS (MANAGER ONLY) ----------------
@app.route('/view_all_orders', methods=['GET'])
@jwt_required()
def view_all_orders():
    claims = get_jwt()
    if claims.get('role') != 'manager':
        return jsonify({'message': 'Access denied. Manager privileges required.'}), 403

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.id, u.username, o.order_date, o.status, o.total_amount
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.order_date DESC
    """)
    orders = cur.fetchall()
    
    order_list = []
    for order in orders:
        cur.execute("""
            SELECT b.title, oi.type, oi.price
            FROM order_items oi
            JOIN books b ON oi.book_id = b.id
            WHERE oi.order_id = %s
        """, (order[0],))
        items = cur.fetchall()
        
        order_list.append({
            'order_id': order[0],
            'username': order[1],
            'order_date': order[2].strftime('%Y-%m-%d %H:%M:%S'),
            'status': order[3],
            'total_amount': float(order[4]),
            'items': [{'title': item[0], 'type': item[1], 'price': float(item[2])} for item in items]
        })
    
    cur.close()
    return jsonify({'orders': order_list}), 200

# ---------------- UPDATE ORDER STATUS (MANAGER ONLY) ----------------
@app.route('/update_order_status', methods=['POST'])
@jwt_required()
def update_order_status():
    claims = get_jwt()
    if claims.get('role') != 'manager':
        return jsonify({'message': 'Access denied. Manager privileges required.'}), 403

    data = request.get_json()
    order_id = data.get('order_id')
    new_status = data.get('status')

    if new_status not in ('Pending', 'Paid'):
        return jsonify({'message': 'Invalid status. Must be "Pending" or "Paid".'}), 400

    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
    mysql.connection.commit()
    
    if cur.rowcount == 0:
        cur.close()
        return jsonify({'message': 'Order not found'}), 404
    
    cur.close()
    return jsonify({'message': f'Order {order_id} status updated to {new_status}'}), 200

# ---------------- ADD NEW BOOK (MANAGER ONLY) ----------------
@app.route('/add_book', methods=['POST'])
@jwt_required()
def add_book():
    claims = get_jwt()
    if claims.get('role') != 'manager':
        return jsonify({'message': 'Access denied. Manager privileges required.'}), 403

    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    price_buy = data.get('price_buy')
    price_rent = data.get('price_rent')
    availability = data.get('availability', 1)

    if not all([title, author, price_buy, price_rent]):
        return jsonify({'message': 'All fields are required'}), 400

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO books (title, author, price_buy, price_rent, availability)
        VALUES (%s, %s, %s, %s, %s)
    """, (title, author, price_buy, price_rent, availability))
    mysql.connection.commit()
    cur.close()

    return jsonify({'message': 'Book added successfully'}), 201

# ---------------- UPDATE BOOK (MANAGER ONLY) ----------------
@app.route('/update_book', methods=['POST'])
@jwt_required()
def update_book():
    claims = get_jwt()
    if claims.get('role') != 'manager':
        return jsonify({'message': 'Access denied. Manager privileges required.'}), 403

    data = request.get_json()
    book_id = data.get('book_id')
    
    if not book_id:
        return jsonify({'message': 'Book ID is required'}), 400

    # Build dynamic update query based on provided fields
    update_fields = []
    params = []
    
    if 'title' in data:
        update_fields.append("title=%s")
        params.append(data['title'])
    if 'author' in data:
        update_fields.append("author=%s")
        params.append(data['author'])
    if 'price_buy' in data:
        update_fields.append("price_buy=%s")
        params.append(data['price_buy'])
    if 'price_rent' in data:
        update_fields.append("price_rent=%s")
        params.append(data['price_rent'])
    if 'availability' in data:
        update_fields.append("availability=%s")
        params.append(data['availability'])
    
    if not update_fields:
        return jsonify({'message': 'No fields to update'}), 400
    
    params.append(book_id)
    query = f"UPDATE books SET {', '.join(update_fields)} WHERE id=%s"
    
    cur = mysql.connection.cursor()
    cur.execute(query, params)
    mysql.connection.commit()
    
    if cur.rowcount == 0:
        cur.close()
        return jsonify({'message': 'Book not found'}), 404
    
    cur.close()
    return jsonify({'message': 'Book updated successfully'}), 200

# ---------------- SEARCH BOOKS ----------------
@app.route('/search_books', methods=['GET'])
def search_books():
    keyword = request.args.get('keyword', '')
    cur = mysql.connection.cursor()
    query = """
        SELECT id, title, author, price_buy, price_rent, availability
        FROM books
        WHERE title LIKE %s OR author LIKE %s
    """
    like_keyword = f"%{keyword}%"
    cur.execute(query, (like_keyword, like_keyword))
    results = cur.fetchall()
    cur.close()

    books = [
        {"id": r[0], "title": r[1], "author": r[2], "price_buy": r[3], "price_rent": r[4], "availability": r[5]}
        for r in results
    ]
    return jsonify({"books": books})

# ---------------- GET BOOK ----------------
@app.route('/get_book', methods=['GET'])
def get_book():
    title = request.args.get('title')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, price_buy, price_rent FROM books WHERE title=%s", (title,))
    result = cur.fetchone()
    cur.close()

    if result:
        return jsonify({"book_id": result[0], "price_buy": result[1], "price_rent": result[2]})
    return jsonify({"message": "Book not found"}), 404

# ---------------- PLACE ORDER ----------------

def send_bill_email(to_email, subject, html_body):
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_user = 'sshreyan9@gmail.com'
    smtp_password = 'haqyumnyzkkhftjz'  

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject 
    msg['From'] = smtp_user
    msg['To'] = to_email

    msg.attach(MIMEText(html_body, 'html'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_password)
    server.sendmail(smtp_user, to_email, msg.as_string())
    server.quit()

def build_html_bill(order_id, order_date, items, total):
    rows = ""
    for item in items:
        rows += f"<tr><td>{item['title']}</td><td>{item['type'].capitalize()}</td><td>${item['price']:.2f}</td></tr>"
    html = f"""
    <html>
    <body>
        <h2 style="color:#2c3e50;">Your Bookstore Receipt</h2>
        <p><strong>Order ID: </strong>{order_id}</p>
        <p><strong>Date: </strong>{order_date}</p>
        <table style="border-collapse:collapse;width:70%;">
            <thead>
                <tr>
                    <th style="border:1px solid #ddd;padding:8px;">Title</th>
                    <th style="border:1px solid #ddd;padding:8px;">Type</th>
                    <th style="border:1px solid #ddd;padding:8px;">Price</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <h3 style="color:#16a085;">Total: ${total:.2f}</h3>
    </body>
    </html>
    """
    return html


@app.route('/place_order', methods=['POST'])
@jwt_required()
def place_order():
    data = request.get_json(silent=True) or {}
    items = data.get('items')
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Invalid request: 'items' must be a non-empty list"}), 400

    user_id = int(get_jwt_identity())
    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO orders (user_id, status, total_amount) VALUES (%s, 'Pending', 0)", (user_id,))
        order_id = cur.lastrowid

        total = 0
        bill_items = []
        for item in items:
            book_id = item.get("book_id")
            order_type = item.get("type")
            if not book_id or order_type not in ("buy", "rent"):
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": "Each item must include 'book_id' and 'type'"}), 400

            price_field = "price_buy" if order_type == "buy" else "price_rent"
            cur.execute(f"SELECT title, {price_field}, availability FROM books WHERE id=%s", (book_id,))
            row = cur.fetchone()
            if not row:
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": f"Book id {book_id} not found"}), 404
            title, price, availability = row
            if not availability:
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": f"Book id {book_id} is not available"}), 409

            total += price
            bill_items.append({
                "title": title,
                "type": order_type,
                "price": float(price)
            })

            cur.execute("""
                INSERT INTO order_items (order_id, book_id, type, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, book_id, order_type, price))

        cur.execute("UPDATE orders SET total_amount=%s WHERE id=%s", (total, order_id))
        mysql.connection.commit()

        # Get order date and user email for the receipt
        cur.execute("SELECT order_date FROM orders WHERE id=%s", (order_id,))
        order_date = cur.fetchone()[0].strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("SELECT email FROM users WHERE id=%s", (user_id,))
        user_email = cur.fetchone()[0]
        cur.close()

        # Generate bill HTML and send email
        html_bill = build_html_bill(order_id, order_date, bill_items, total)
        subject = f"Your Bookstore Receipt (Order #{order_id})"
        send_bill_email(user_email, subject, html_bill)

        return jsonify({
            "message": "Order placed and bill emailed successfully",
            "order_id": order_id,
            "total": float(total)
        }), 200

    except Exception as e:
        mysql.connection.rollback()
        cur.close()
        return jsonify({"error": "Failed to place order", "details": str(e)}), 500


# ---------------- RUN SERVER ----------------

if __name__ == '__main__':
    print("✅ Flask server running with JWT header auth")
    app.run(debug=True)