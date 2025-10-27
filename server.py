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


if __name__ == '__main__':
    app.run(debug=True)