import models
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/init_db')
def initialize_database():
    return "Done!"

