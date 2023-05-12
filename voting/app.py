import models
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/init_db')
def initialize_database():
    models.Storage.initialize_db()
    return "Done!"

@app.route('/categories')
def get_categories():
    c = models.Storage.session().query(models.CandidateCategory).all()
    return str(c)
