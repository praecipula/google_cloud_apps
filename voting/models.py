import datetime
import json
from google.cloud import firestore
from google.oauth2.service_account import Credentials

class Storage():
    @classmethod
    def load_credentials(cls):
        credentials=None
        with open("/Users/matt/Development/google_cloud_apps/credentials/google_cloud_apps_manager.json") as f:
            cred_info=json.loads(f.read())
            credentials = Credentials.from_service_account_info(cred_info)
        return credentials
        
    @classmethod
    def db(cls):
        if not hasattr(cls, '_db'):
            cls._db = firestore.Client(credentials=cls.load_credentials())
        return cls._db

#doc_ref = Storage.db().collection('users').document('alovelace')
#doc_ref.set({
#    'first': 'Ada',
#    'last': 'Lovelace',
#    'born': 1815
#})

class ModelBase:

    @classmethod
    def collection_name(cls):
        raise "Subclasses should implement"

    @classmethod
    def collection(cls):
        return Storage.db().collection(cls.collection_name())

    def __init__(self, document_id, *args, **kwargs): 
        self._document_id = document_id
        # There are some fields that should only be set on creation, like creation time.
        self._snapshot = None
        # Any attributes that aren't mapped to class properties
        self._additional_attributes = {}


    ## Writing / persistence methods

    def before_serialize(self, d = {}):
        '''
        Always returns a copy of the input dict.
        '''
        if not self._snapshot:
            # New document
            new_d = d.copy()
            new_d.update({"t_crte": firestore.SERVER_TIMESTAMP})
            return new_d
        return d.copy()

    def after_serialize(self, d):
        '''
        Always returns a copy of the input dict.
        '''
        return d.copy()

    def serialize(self):
        '''
        Serialize, including before and after callbacks.
        '''
        d = self.before_serialize()
        # Delegated method to subclass implementers
        d = self.to_dict(d)
        d = self.after_serialize(d)
        return d

    def to_dict(self, d):
        '''
        This is the method subclasses should implement in order to convert their properties to a dictionary.
        '''
        raise "Subclasses must implement"

    def save(self):
        dictionary = self.serialize()
        if not self._snapshot:
            # If this raises it's because we think we're inserting a new document but it exists.
            # IMPORTANT TODO: there can be a race condition where we check the DB for existance, and
            # then between that check and creation a new document gets made; that will cause create
            # to throw.
            # To handle that we should merge the trying-to-create-now doc onto the existing one, including
            # not overwriting the creation time, for instance, and then do an update.
            returnval = self.__class__.collection().document(self._document_id).create(dictionary)
            # TODO: check this for errors?

            # Firestore returns metadata about the operation, but, unhelpfully, not the document itself.
            # This means every write will need to get a re-read, unfortunately - there's no other way I know
            # of to get e.g. server side values like server timestamps.
            self.read()
        else:
            # Updating existing doc
            returnval = self.__class__.collection().document(self._document_id).update(dictionary)

            # Firestore returns metadata about the operation, but, unhelpfully, not the document itself.
            # This means every write will need to get a re-read, unfortunately - there's no other way I know
            # of to get e.g. server side values like server timestamps.
            self.read()
        # TODO: put is used to delete items (create and update will only append keys). How to handle
        # this semantic, where put should only be used for, well, PUT-http-like semantics where the
        # whole current state of the doc in memory is the canonical one?
        return True


    ## Reading methods

    def before_deserialize(self, d = {}):
        return d

    def after_deserialize(self, d):
        # TODO: Should this return a copy of dict or the modified dict?
        # should we get or pop?

        # It should always be true that t_crte exists, at least for all subclasses
        # of this class.
        self.creation_timestamp = d.pop("t_crte")
        self._additional_attributes = d.copy()
        return d

    def deserialize(self, d = {}):
        '''
        Serialize, including before and after callbacks.
        '''
        self.before_deserialize(d)
        # Delegated method to subclass implementers
        self.from_dict(d)
        self.after_deserialize(d)
        return self

    def from_dict(self, d):
        '''
        This is the method subclasses should implement in order to convert their properties from a dictionary.
        '''
        raise "Subclasses must implement"

    def read(self):
        '''
        Read data for this instance to the DB.
        This can (will probably) destroy any local data to get up to date with the DB.
        '''
        doc_ref = self.__class__.collection().document(self._document_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return None
        self.deserialize(snapshot.to_dict())
        self._snapshot = snapshot
        return self



class Candidate(ModelBase):
    @classmethod
    def collection_name(cls):
        return "candidates"

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.name = name
        self.num_votes = 0

    def to_dict(self, d = {}):
        d.update({
            "test": "Not really a very useful piece of data",
            "num_votes": self.num_votes
                 })
        return d

    def from_dict(self, d):
        # Pull out self attributes and return the remaining attrs
        self.num_votes = d.pop("num_votes")

    def __repr__(self):
        return f"Candidate: {self.name}, num_votes: {self.num_votes} || add_at: {self._additional_attributes}"

c = Candidate("7-11")
print(c)
c.read()
print(c)
c.save()
print(c)
c.num_votes = 5
print(c)
c.save()
print(c)
