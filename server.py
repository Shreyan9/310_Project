
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
        return jsonify({'token': token}), 200

    return jsonify({'message': 'Invalid credentials'}), 401

# ---------------- SEARCH BOOKS ----------------
@app.route('/search_books', methods=['GET'])
def search_books():
    keyword = request.args.get('keyword', '')
    cur = mysql.connection.cursor()
    query = """
        SELECT title, author, price_buy, price_rent, availability
        FROM books
        WHERE title LIKE %s OR author LIKE %s
    """
    like_keyword = f"%{keyword}%"
    cur.execute(query, (like_keyword, like_keyword))
    results = cur.fetchall()
    cur.close()

    books = [
        {"title": r[0], "author": r[1], "price_buy": r[2], "price_rent": r[3], "availability": r[4]}
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