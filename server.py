from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token

app = Flask(__name__)

# Configure database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'sunitha80'
app.config['MYSQL_DB'] = 'project'

# JWT Configuration
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'

mysql = MySQL(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# User Registration
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

# User Login
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
        token = create_access_token(identity={'id': user[0], 'role': user[2]})
        return jsonify({'token': token}), 200
    return jsonify({'message': 'Invalid credentials'}), 401

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
    # Return as list of dicts
    books = [
        {"title": r[0], "author": r[1], "price_buy": r[2], "price_rent": r[3], "availability": r[4]}
        for r in results
    ]
    return jsonify({"books": books})

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


from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/place_order', methods=['POST'])
@jwt_required()
def place_order():
    data = request.get_json()
    items = data['items']  # list of { book_id, type }
    
    user = get_jwt_identity()
    user_id = user['id']

    cur = mysql.connection.cursor()

    # Create order entry
    cur.execute("INSERT INTO orders (user_id, status, total_amount) VALUES (%s, 'Pending', 0)", (user_id,))
    order_id = cur.lastrowid

    total = 0
    for item in items:
        book_id = item["book_id"]
        order_type = item["type"]  # buy/rent

        # Get correct price
        price_field = "price_buy" if order_type == "buy" else "price_rent"
        cur.execute(f"SELECT {price_field} FROM books WHERE id=%s", (book_id,))
        price = cur.fetchone()[0]

        total += price

        # Add order item row
        cur.execute("""
            INSERT INTO order_items (order_id, book_id, type, price)
            VALUES (%s, %s, %s, %s)
        """, (order_id, book_id, order_type, price))
    
    # Update order total
    cur.execute("UPDATE orders SET total_amount=%s WHERE id=%s", (total, order_id))

    mysql.connection.commit()
    cur.close()

    return jsonify({"message": "Order placed successfully", "order_id": order_id})



if __name__ == '__main__':
    app.run(debug=True)