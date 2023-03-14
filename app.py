import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from passlib.hash import sha256_crypt
from tools import generate_token, auth_required
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    deposit = db.Column(db.Integer, default=0)
    role = db.Column(db.String(20), default="buyer")
    products = db.relationship("Product", backref="seller", lazy="dynamic")

    def serialize(self):
        return {
            "id": self.id,
            "username": self.username,
            "deposit": self.deposit,
            "role": self.role,
        }

    def __repr__(self):
        return f"User('{self.username}', '{self.deposit}', '{self.role}')"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    amount_available = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def serialize(self):
        return {
            "id": self.id,
            "amount_available": self.amount_available,
            "cost": self.cost,
            "name": self.name,
            "seller_id": self.seller_id,
        }


# Auth routes
@app.post("/register")
def register():
    username = request.json.get("username")
    password = request.json.get("password")
    role = request.json.get("role", "buyer")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"error": "Username is already taken"}), 400

    user = User(username=username, password=sha256_crypt.encrypt(password), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created"}), 201


@app.post("/login")
def login():
    username = request.json.get("username")
    password = request.json.get("password")
    user = User.query.filter_by(username=username).first()
    if not user or not sha256_crypt.verify(password, user.password):
        return jsonify({"error": "Invalid username or password"}), 400

    return (
        jsonify(
            {
                "message": "Logged in",
                "user": user.serialize(),
                "token": generate_token(user.id, user.role),
            }
        ),
        200,
    )


# User routes
@app.get("/users")
@auth_required(role="seller")
def list_users():
    users = User.query.all()
    return jsonify([user.serialize() for user in users]), 200


@app.get("/users/<int:user_id>")
@auth_required(role="seller|buyer")
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.serialize()), 200


@app.delete("/users/<int:user_id>")
@auth_required(role="seller|buyer")
def delete_user(user_id):
    if request.user_id != user_id:
        return jsonify({"error": "Cannot delete another user"}), 403
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200


# Product routes


@app.get("/products")
def list_products():
    products = Product.query.all()
    return jsonify([product.serialize() for product in products])


@app.route("/products/<int:product_id>")
@auth_required(role="buyer|seller")
def get_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product.serialize())


@app.post("/products")
@auth_required(role="seller")
def create_product():
    amount_available = request.json.get("amount_available", 0)
    cost = request.json.get("cost")
    product_name = request.json.get("name")
    seller_id = request.user_id
    if not all([amount_available, cost, product_name]):
        return jsonify({"error": "All fields are required"}), 404

    seller = User.query.get(seller_id)

    if not seller:
        return jsonify({"error": "Seller not found"}), 404

    product = Product(
        amount_available=amount_available, cost=cost, name=product_name, seller=seller
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({"message": "Product created", "product": product.serialize()}), 201


@app.put("/products/<int:product_id>")
@auth_required(role="seller")
def update_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.seller_id != request.user_id:
        return jsonify({"error": "Cannot update another seller's product"}), 403

    amount_available = request.json.get("amount_available", product.amount_available)
    cost = request.json.get("cost", product.cost)
    product_name = request.json.get("name", product.name)
    seller_id = request.user_id

    seller = User.query.get(seller_id)
    if not seller:
        return jsonify({"error": "Seller not found"}), 404

    product.amount_available = amount_available
    product.cost = cost
    product.name = product_name
    product.seller = seller
    db.session.commit()
    return jsonify({"message": "Product updated", "product": product.serialize()})


@app.delete("/products/<int:product_id>")
@auth_required(role="seller")
def delete_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if product.seller_id != request.user_id:
        return jsonify({"error": "Cannot delete another seller's product"}), 403

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted"})


# Buyer routes
@app.post("/deposit")
@auth_required(role="buyer")
def deposit():
    user_id = request.user_id
    coin = request.json.get("coin")
    if coin not in [5, 10, 20, 50, 100]:
        return jsonify({"error": "Invalid coin"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.deposit += coin
    db.session.commit()
    return jsonify({"message": "Deposit added", "user": user.serialize()})


@app.post("/buy")
@auth_required(role="buyer")
def buy():
    user_id = request.user_id
    product_id = request.json.get("product_id")
    amount = request.json.get("amount", 1)
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if product.amount_available < amount:
        return jsonify({"error": "Insufficient products available"}), 400

    if user.deposit < amount * product.cost:
        return jsonify({"error": "Insufficient funds"}), 400

    user.deposit -= amount * product.cost
    product.amount_available -= amount
    db.session.commit()
    change = []
    remaining = user.deposit
    coins = [100, 50, 20, 10, 5]
    for coin in coins:
        count = remaining // coin
        if count > 0:
            remaining -= count * coin
            change += [coin] * count
    return (
        jsonify(
            {
                "message": "Purchase successful",
                "product": product.serialize(),
                "change": change,
            }
        ),
        200,
    )


@app.post("/reset")
@auth_required(role="buyer")
def reset_deposit():
    user_id = request.user_id
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.deposit = 0
    db.session.commit()
    return jsonify({"message": "Deposit reset", "user": user.serialize()})


if __name__ == "__main__":
    app.run(debug=True)
