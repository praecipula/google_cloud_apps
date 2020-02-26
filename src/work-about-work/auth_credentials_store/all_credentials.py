from flask import Blueprint,render_template,request
from storage_service.store import get_app_credentials,store_user_refresh_token,store_user_access_token
from environment_service.environment import Environment,get_request_environment
from environment_service.utilities import utc_from_epoch_ms
import asana

all_credentials = Blueprint('all_credentials', __name__, template_folder='templates')

@all_credentials.route("/credential_info", methods=['GET'])
def show_credentials_summary():
    client = get_asana_client()
    return client.users.me()

@all_credentials.route("/asana_oauth_redirect", methods=['GET'])
def exchange_authorization_code():
    client = get_asana_client()
    authorization_code = request.args.get("code")
    # TODO: should verify the state parameter
    token = client.session.fetch_token(code=authorization_code)
    store_user_refresh_token(token['data']['gid'], token['refresh_token'])
    store_user_access_token(token['data']['gid'], token['access_token'], utc_from_epoch_ms(token['expires_at']))
    return "Got an authorized client!"
    

# NOT a flask route.
# Helper method to get and store credentials from Asana


#https://app.asana.com/-/oauth_authorize?response_type=code&client_id=1163630087121140&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fasana_oauth_redirect&state=<STATE_PARAM>
# Memoize this; I think there's a better way, but for now this will be the same client for each full request.
_client = None
def get_asana_client():
    global _client
    if _client:
        return _client
    my_credentials = get_app_credentials()
    # TODO: this is reauthing every time. Store this per user.
    creds = get_app_credentials()
    environment = get_request_environment(request)
    redirect_uri = None
    # TODO: brittle. Don't make this dependent on the ordering.
    # We could match on the base url in the redirect list, which might be better, but we need to have the env service anyway...
    if environment == Environment.DEVELOPMENT:
        redirect_uri = creds['redirect_urls'][0]
    _client = asana.Client.oauth(client_id = creds['client_id'], client_secret = creds['client_secret'], redirect_uri=redirect_uri)
    (url, state) = _client.session.authorization_url()
    # TODO: this works, but isn't complete.
    import webbrowser; webbrowser.open(url)
    return _client

