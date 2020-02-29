# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python37_app]
from flask import Flask
import google.cloud.logging
import logging, logging.config
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from storage_service import store
from environment_service.environment import Environment,get_environment
import os

if get_environment() == Environment.PRODUCTION:
    client = google.cloud.logging.Client()
    client.setup_logging()

logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d|| %(message)s',
            }
        },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'stream': 'ext://sys.stdout',
            }
        },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console'],
        }
    })

logging.getLogger('root').info("Logging init!")

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)
auth = HTTPBasicAuth()


from auth_credentials_store.all_credentials import all_credentials
app.register_blueprint(all_credentials)
from quick_follow_up.follow_up import follow_up
app.register_blueprint(follow_up, url_prefix="/follow_up")


@auth.verify_password
def verify_password(username, password):
    # 1 salt for the app. Yes, I understand this is a bad salting scheme and it should be per user :)
    app_random_salt="16bea2eea75b1dcaf49f2760d526646b9f9b89f9"
    if not username:
        return False
    return check_password_hash(store.get_basic_auth_hash(username), password + app_random_salt)

@app.route('/')
@auth.login_required
def index():
    return f"Hello, {auth.username()}!"


@app.route('/ping')
def info():
    return str(get_environment())

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
