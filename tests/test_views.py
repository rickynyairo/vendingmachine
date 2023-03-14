import json
import pytest
from ..app import create_app, db
from models import User, Product


@pytest.fixture(scope='module')
def test_client():
    flask_app = create_app('testing')
    with flask_app.test_client() as testing_client:
        with flask_app.app_context():
            db.create_all()
            yield testing_client
            db.drop_all()


def test_create_user(test_client):
    response = test_client.post('/user', json={
        'username': 'testuser',
        'password': 'testpassword',
        'deposit': 0,
        'role': 'buyer'
    })
    data = json.loads(response.data)
    assert response.status_code == 201
    assert data['message'] == 'User created successfully'
    assert data['user']['username'] == 'testuser'


def test_create_product(test_client):
    seller = User(username='seller', password='password', deposit=0, role='seller')
    db.session.add(seller)
    db.session.commit()
    response = test_client.post('/product', json={
        'product_name': 'Test product',
        'amount_available': 10,
        'cost': 50,
        'seller_id': seller.id
    }, headers={'Authorization': 'Bearer ' + seller.get_token()})
    data = json.loads(response.data)
    assert response.status_code == 201
    assert data['message'] == 'Product created successfully'
    assert data['product']['product_name'] == 'Test product'


def test_get_products(test_client):
    response = test_client.get('/product')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert len(data['products']) == 1


def test_get_product(test_client):
    product = Product.query.first()
    response = test_client.get(f'/product/{product.id}')
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['product']['product_name'] == product.product_name


def test_update_product(test_client):
    product = Product.query.first()
    seller = User.query.filter_by(id=product.seller_id).first()
    response = test_client.put(f'/product/{product.id}', json={
        'amount_available': 5
    }, headers={'Authorization': 'Bearer ' + seller.get_token()})
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['message'] == 'Product updated successfully'
    assert data['product']['amount_available'] == 5


def test_delete_product(test_client):
    product = Product.query.first()
    seller = User.query.filter_by(id=product.seller_id).first()
    response = test_client.delete(f'/product/{product.id}', headers={'Authorization': 'Bearer ' + seller.get_token()})
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['message'] == 'Product deleted successfully'


def test_deposit(test_client):
    user = User.query.filter_by(role='buyer').first()
    response = test_client.post('/deposit', json={
        'user_id': user.id,
        'coin_value': 10
    })
    data = json.loads(response.data)
    assert response.status_code == 200
    assert data['message'] == 'Deposit successful'
    assert data['user']['deposit'] == 10


def test_buy(test_client):
    user = User.query.filter_by(role='buyer').first()
    product = Product.query.first()
    product.amount_available = 2
    db.session.commit()
    response = test_client.post('/buy', json={
        'user_id': user.id,
        'product_id': product.id
    })
