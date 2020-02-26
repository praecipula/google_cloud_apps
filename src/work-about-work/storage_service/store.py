from google.cloud import datastore
import google.cloud.exceptions

# This is a safe number to expose;
# it's the entrypoint for all successive loads from the datastore.
APP_ID=1163630087121140

def _datastore_client():
    return datastore.Client.from_service_account_json("/Users/mattbramlage/sandbox/google_cloud_apps/credentials_not_tracked/work_about_work_creds.json", namespace="credentials")

def get_entity_by_key(data_kind, key):
    client = _datastore_client()
    query = client.query(kind=data_kind)
    app_key = client.key(data_kind, key)
    query.key_filter(app_key, '=')
    matches = list(query.fetch())
    assert len(matches) == 1, "Expected to fetch single value by key"
    return matches[0]


def get_app_credentials():
    print("hi")
    entity = get_entity_by_key("OauthCredentials", f"app_credentials_{APP_ID}")
    return {'client_id': APP_ID, 'client_secret': entity['client_secret'], 'redirect_urls': entity['redirect_urls']}

def store_user_refresh_token(user, refresh_token):
    client = _datastore_client()
    user_credentials_entity = datastore.Entity(key=client.key('OauthCredentials', f"user_credentials_{user}"))
    user_credentials_entity.update({'refresh_token': refresh_token})
    client.put(user_credentials_entity)
    return True
