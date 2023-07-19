import datetime
from flask import Flask, render_template

import models

app = Flask(__name__)

@app.route('/')
def serve_app():
    return render_template('index.html' , utc_dt=datetime.datetime.utcnow())

@app.route('/hello')
def hello_world():
    return 'Hello, World!'

@app.route('/init_db')
def initialize_database():
    return "Done!"

