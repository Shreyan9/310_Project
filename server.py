

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
@app.route('/place_order', methods=['POST'])
@jwt_required()
def place_order():
    # Safely parse JSON and validate payload
    data = request.get_json(silent=True) or {}
    items = data.get('items')

    if not isinstance(items, list) or not items:
        return jsonify({"error": "Invalid request: 'items' must be a non-empty list"}), 400

    # get_jwt_identity() is a string (user id), convert to int
    user_id = int(get_jwt_identity())
    # If you need role for authorization:
    # role = get_jwt().get('role')

    cur = mysql.connection.cursor()
    try:
        # Create the order
        cur.execute("INSERT INTO orders (user_id, status, total_amount) VALUES (%s, 'Pending', 0)", (user_id,))
        order_id = cur.lastrowid

        total = 0
        for item in items:
            book_id = item.get("book_id")
            order_type = item.get("type")

            if not book_id or order_type not in ("buy", "rent"):
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": "Each item must include 'book_id' and 'type' ('buy' or 'rent')"}), 400

            price_field = "price_buy" if order_type == "buy" else "price_rent"
            cur.execute(f"SELECT {price_field}, availability FROM books WHERE id=%s", (book_id,))
            row = cur.fetchone()
            if not row:
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": f"Book id {book_id} not found"}), 404

            price, availability = row
            if not availability:
                mysql.connection.rollback()
                cur.close()
                return jsonify({"error": f"Book id {book_id} is not available"}), 409

            total += price

            cur.execute("""
                INSERT INTO order_items (order_id, book_id, type, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, book_id, order_type, price))

        # Update total and commit
        cur.execute("UPDATE orders SET total_amount=%s WHERE id=%s", (total, order_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Order placed successfully", "order_id": order_id, "total": float(total)}), 200

    except Exception as e:
        mysql.connection.rollback()
        cur.close()
        return jsonify({"error": "Failed to place order", "details": str(e)}), 500

# ---------------- RUN SERVER ----------------

# Debug handler to see why 422 is happening
import traceback

@app.errorhandler(422)
def handle_unprocessable_entity(err):
    print("---- 422 DEBUG ----")
    print("Request data:", request.get_data(as_text=True))
    print("Request headers:", dict(request.headers))
    traceback.print_exc()
    print("--------------------")

    try:
        exc = err.exc
        return jsonify({"error": str(exc)}), 422
    except:
        return jsonify({"error": "Invalid request or JWT"}), 422

if __name__ == '__main__':
    print("✅ Flask server running with JWT header auth")
    app.run(debug=True)