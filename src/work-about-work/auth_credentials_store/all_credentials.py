from flask import Blueprint,render_template,request,make_response
from flask import current_app as app
from storage_service import store
from environment_service.environment import Environment,get_request_environment
from environment_service.utilities import utc_from_epoch_ms,utc_now
from datetime import datetime
import asana

all_credentials = Blueprint('all_credentials', __name__, template_folder='templates')

@all_credentials.route("/credential_info", methods=['GET'])
def show_credentials_summary():
    user_id = request.cookies.get('asana_user_id')
    client = get_asana_client_for_user(user_id)
    return client.users.me()

@all_credentials.route("/asana_oauth_redirect", methods=['GET'])
def exchange_authorization_code():
    app.logger.info("Landed from oauth code redirect")
    # TODO: refactor this "partial" code-only client out
    authorization_code = request.args.get("code")
    # TODO: should verify the state parameter
    client = get_asana_client_for_code(authorization_code)
    # After the exchange we can introspect the token for some useful data.
    # TODO: this isn't very law-of-demeter-y
    import pdb; pdb.set_trace()
    user_id = client.session.token['data']['gid']
    resp = make_response("Got an authorized client!")
    resp.set_cookie("asana_user_id", user_id)
    return resp

def exchange_refresh_token(client):
    user_id = request.cookies.get('asana_user_id')
    client = get_asana_client_for_user(user_id)
    token = client.session.refresh_token()
    store.store_user_refresh_token(user_id, token['refresh_token'])
    store.store_user_access_token(user_id, token['access_token'], utc_from_epoch_ms(token['expires_at']))
    

# NOT a flask route.
# Helper method to get and store credentials from Asana
def get_asana_client_for_code(authorization_code):
    app.logger.info("Exchanging authorization code for a token")
    application_credentials = store.get_app_credentials()
    environment = get_request_environment(request)
    if environment == Environment.DEVELOPMENT:
        redirect_uri = application_credentials['redirect_urls'][0]
    client = asana.Client.oauth(client_id = application_credentials['client_id'], client_secret = application_credentials['client_secret'], redirect_uri=redirect_uri)
    token = client.session.fetch_token(code=authorization_code)
    user_id = client.session.token['data']['gid']
    store.store_user_refresh_token(user_id, token['refresh_token'])
    store.store_user_access_token(user_id, token['access_token'], utc_from_epoch_ms(token['expires_at']))
    return client

def get_asana_client_for_user(user_id):
    # TODO: this is reauthing every time. Store this per user.
    application_credentials = store.get_app_credentials()
    environment = get_request_environment(request)
    redirect_uri = None
    client = None
    if environment == Environment.DEVELOPMENT:
        redirect_uri = application_credentials['redirect_urls'][0]
    # TODO: brittle. Don't make this dependent on the ordering.
    # We could match on the base url in the redirect list, which might be better, but we need to have the env service anyway...
    user_credentials = store.get_or_construct_user_credentials(user_id)
    if 'access_token' in user_credentials:
        if 'expire_time' in user_credentials and user_credentials['expire_time'] > utc_from_epoch_ms(utc_now().timestamp() + 3 * 60):
            app.logger.debug("Valid access token found--logged in")
            # Access token is present and will be valid for some time
            client = asana.Client.oauth(client_id = application_credentials['client_id'],
                    client_secret = application_credentials['client_secret'],
                    redirect_uri=redirect_uri,
                    token = {
                        "access_token": user_credentials['access_token'],
                        "refresh_token": user_credentials['refresh_token'],
                        "type": "bearer"
                        }
                    )
        else:
            # Exchange the refresh token again, then return
            app.logger.debug("Access token expired, exchanging refresh token")
            application_credentials = exchange_refresh_token()
            client = asana.Client.oauth(client_id = application_credentials['client_id'],
                    client_secret = application_credentials['client_secret'],
                    redirect_uri=redirect_uri,
                    token = {
                        "refresh_token": user_credentials['refresh_token'],
                        "type": "bearer"
                        }
                    )
            _client.refresh_token()
    else:
        app.logger.info("Full refresh of credentials from code: initial auth or previous auth token deleted")
        # This will start a second request that we want to be able to get the global variable for.
        client = asana.Client.oauth(client_id = application_credentials['client_id'], client_secret = application_credentials['client_secret'], redirect_uri=redirect_uri)
        (url, state) = client.session.authorization_url()
        # TODO: this works, but isn't complete.
        import webbrowser; webbrowser.open(url)
    return client

