from flask import Blueprint,render_template,request
from storage_service.store import get_app_credentials

all_credentials = Blueprint('all_credentials', __name__, template_folder='templates')

@all_credentials.route("/credential_info", methods=['GET'])
def show():
    return get_asana_credentials()

@all_credentials.route("/asana_oauth_redirect", methods=['GET'])
def create():

    task_id = request.get["task_url"]
    return render_template("post_follow_up.html", source_task_url = request.form['task_url'])

# NOT a flask route.
# Helper method to get and store credentials from Asana


#https://app.asana.com/-/oauth_authorize?response_type=code&client_id=1163630087121140&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fasana_oauth_redirect&state=<STATE_PARAM>
def get_asana_credentials():
    return f"Gonna get em: " + str(get_app_credentials())
