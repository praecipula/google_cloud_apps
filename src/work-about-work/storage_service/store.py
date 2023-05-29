import logging
from google.cloud import datastore
import google.cloud.exceptions
from environment_service.environment import Environment,get_environment
import os

# This is a safe number to expose;
# it's the entrypoint for all successive loads from the datastore.
APP_ID=1163630087121140

def _datastore_client():

    environment = get_environment()
    if environment == Environment.DEVELOPMENT:
        return datastore.Client.from_service_account_json("/Users/mattbramlage/sandbox/google_cloud_apps/credentials_not_tracked/work_about_work_creds.json", namespace="credentials")
    elif environment == Environment.PRODUCTION:
        client = datastore.Client(namespace="credentials")
        return client

def _app_credentials_key():
    return f"app_credentials_{APP_ID}"

def _user_credentials_key_for_id(user_id):
    return f"user_credentials_{user_id}"

def get_entity_by_key(data_kind, key):
    client = _datastore_client()
    query = client.query(kind=data_kind)
    app_key = client.key(data_kind, key)
    query.key_filter(app_key, '=')
    matches = list(query.fetch())
    assert len(matches) <= 1, "Expected to fetch at most a single value by key"
    if len(matches) == 0:
        logging.getLogger('root').warn(f"Fetch witk kind {data_kind} and key {key} returned no results")
        return None
    return matches[0]


def get_app_credentials():
    entity = get_entity_by_key("OauthCredentials", _app_credentials_key())
    assert entity != None, "You need to bootstrap the app credentials in the datastore: https://console.cloud.google.com/datastore/entities"
    return {'client_id': APP_ID, 'client_secret': entity['client_secret'], 'redirect_urls': entity['redirect_urls']}

def get_or_construct_user_credentials(user):
    entity = get_entity_by_key("OauthCredentials", _user_credentials_key_for_id(user))
    if not entity:
        entity = datastore.Entity(key=_datastore_client().key('OauthCredentials', _user_credentials_key_for_id(user)))
    return entity

def store_user_refresh_token(user, refresh_token):
    client = _datastore_client()
    user_credentials_entity = get_or_construct_user_credentials(user)
    user_credentials_entity.update({'refresh_token': refresh_token})
    client.put(user_credentials_entity)
    return user_credentials_entity

def get_user_access_token(user):
    client = _datastore_client()
    user_credentials_entity = get_entity_by_key("OauthCredentials", _user_credentials_key_for_id(user))
    return user_credentials_entity

def store_user_access_token(user, access_token, expire_epoch_time):
    client = _datastore_client()
    user_credentials_entity = get_or_construct_user_credentials(user)
    user_credentials_entity.update({'access_token': access_token, 'expire_time': expire_epoch_time})
    client.put(user_credentials_entity)
    return user_credentials_entity

def get_basic_auth_hash(username):
    logging.getLogger('root').info(f"Getting auth credentials for {username} from store")
    entity = get_entity_by_key("BasicAuthCredentials", username)
    return entity['salted_hash']
