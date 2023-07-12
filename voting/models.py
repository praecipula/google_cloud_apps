import datetime
import json
import logging
import python_logging_base
from google.cloud import firestore
from google.oauth2.service_account import Credentials

LOG=logging.getLogger("models")
LOG.setLevel(logging.TRACE)

class Storage():
    @classmethod
    def load_credentials(cls):
        credentials=None
        with open("/Users/matt/Development/google_cloud_apps/credentials/google_cloud_apps_manager.json") as f:
            LOG.debug("Reading credentials...")
            cred_info=json.loads(f.read())
            credentials = Credentials.from_service_account_info(cred_info)
            LOG.debug("... credentials read.")
        return credentials
        
    @classmethod
    def db(cls):
        if not hasattr(cls, '_db'):
            cls._db = firestore.Client(credentials=cls.load_credentials())
        return cls._db

    @classmethod
    def transaction(cls):
        return cls.db().transaction()


class ModelBase:
    '''
    Base class for models saved in Firestore. This class handles the serialization / deserialization lifecycle
    for a model to and from a Firebase model-as-dictionary.
    '''

    class SyncTransactionFailed(Exception):
        pass

    class RequiredMethodNotImplemented(NotImplementedError):
        pass

    class SubclassRequirementsTypeError(TypeError):
        pass

    @classmethod
    def collection_name(cls):
        '''
        Subclasses should implement this. Then it can be used to do something like MyModel.collection() to
        get the Firebase collection.
        '''
        raise ModelBase.RequiredMethodNotImplemented("Subclasses should implement")

    @classmethod
    def collection(cls):
        '''
        Return the Firebase collection for this model.
        '''
        return Storage.db().collection(cls.collection_name())

    def __init__(self, document_id, *args, **kwargs):
        '''
        Initialize the model. This is initializing the local model and it may or may not be
        connected to the Firestore model.

        Given only the document_id, it's possible to instantiate the model with the database
        contents by calling read().
        '''
        # The ID of the document for fetching from / saving to Firestore
        self._document_id = document_id
        # The snapshot of the document as we last fetched it in the db
        self._snapshot = None
        # Any attributes that aren't mapped to class properties by subclasses are collected here.
        self._additional_attributes = {}

    def doc_ref(self):
        return self.__class__.collection().document(self._document_id)

    ## Writing / persistence methods
    def before_serialize(self, d = {}):
        '''
        Serialization methods handle the translation of model attributes to the dictionary for firebase.
        The distinction between serialization and to_dict is mostly semantic: the serialization path
        acts more as a library-level method to wrap e.g. creation time, trashed, etc... meta-information
        whereas to_dict is meant to be cleaner translation between attributes and dictionary methods.

        before_/after_serialize are used to keep intents cleaner in subclasses so subclasses
        don't have to always remember to do bookkeeping tasks.
        '''

        # Here's an example of a bookkeeping concern: creation and modification dates are stored on
        # all objects.
        if self._snapshot == None:
            # This is a new document, we think.
            # See #save() for how we handle if we're not actually new and this is a conflict.
            # Update the creation time. This should only happen on actual-create such that we don't
            # overwrite it with a put or update request on accident.
            # TODO: is there some way to enforce that this can not be updated, ever, using security rules?
            d.update({'t_cr': firestore.SERVER_TIMESTAMP})
        # Modified time.
        d.update({'t_md': firestore.SERVER_TIMESTAMP})
        return d

    def after_serialize(self, d):
        '''
        '''
        return d

    def serialize(self):
        '''
        The template method pattern for serialize, including before and after callbacks.
        '''
        LOG.trace("Serializing...")
        d = self.before_serialize()
        # Delegated method to subclass implementers
        d = self.to_dict(d)
        if not isinstance(d, dict):
            raise ModelBase.SubclassArgumentOrReturnError("to_dict override method must return a dict type")
        d = self.after_serialize(d)
        LOG.trace("...serialization complete")
        return d

    def to_dict(self, d):
        '''
        This is the method subclasses should implement in order to convert their properties to a dictionary.
        '''
        raise ModelBase.RequiredMethodNotImplemented("Subclasses should implement")

    def sync(self):
        '''
        Perform a full sync of the doc, reads and writes.
        This fails if *anything* has changed on the doc, so this is in effect
        an update-if-not-changed operation.
        For more granular control see sync_field()
        '''
        LOG.trace("Performing full model sync")
        in_mem_dictionary = self.serialize()
        t = Storage.transaction()
        # The case where a document is created "behind" this model.
        if self._snapshot == None:
            LOG.trace(f"Saving brand new model {self.doc_ref()}")
            @firestore.transactional
            def create(transaction):
                # Should be a new document.
                # Should new the document. Fails in Firestore if it exists. Easy-peasy.
                transaction.create(self.doc_ref(), in_mem_dictionary)
            create(t)
        else:
            LOG.trace(f"Updating existing model {self.doc_ref()}")
            @firestore.transactional
            def put(transaction):
                firestore_document = self.doc_ref().get(transaction=transaction)
                # Check expected state - here that means modified date fields are the same.
                # This is so we have a fairly reliable value if *any* of the fields on the model are stale
                # and can check in O(1) instead of O(n) where n is every piece of data that's comparable on the model.
                # Blanket and very blunt case for "if anything has changed don't sync" - other methods can do better.
                if self._snapshot.get('t_md') != firestore_document.get('t_md'):
                    LOG.warn(f"Update failed; database model has changed since in-memory instance was created.")
                    raise SyncTransactionFailed(f"Tried updating doc {self._document_id} but our modified timestamp is out of date.")
                # This is a straight-up put! That means it will delete anything not in memory!
                t.put(self.doc_ref(), in_mem_dictionary)
            put(t)

        # Unfortunately need immediate re-read for server-set fields like dates.
        # There is a race condition here if another write lands immediately after our transaction
        # or the transaction is delayed, but hopefully the catch on update / raise if modification
        # timestamp is out of date will catch this. It's a bit annoying that Firebase won't
        # let us read in a transaction, but replication has to happen etc...
        self._snapshot = self.doc_ref().get()
        self.deserialize()

    def sync_fields(self, fieldnames = []):

        LOG.trace(f"Syncing select fields: {fieldnames}")
        in_mem_dictionary = self.serialize()
        t = Storage.transaction()
        error_fields = []
        
        # TODO: delete can be handled this way maybe.
        @firestore.transactional
        def update_select_fields(transaction):

            # Freshly get the doc
            firebase_document = self.doc_ref().get(transaction=transaction)
            for field in fieldnames:
                # Get the fresh value of the one field. (Maybe this can be done with a targeted query for big docs?)
                current_field_on_db = firebase_document.get(field)
                # Get the possibly stale model on the old snapshot
                snapshot_field_on_model = self._snapshot.to_dict().get(field)
                # If the snapshot field is stale (has changed since this model was read from db)...
                if current_data_on_db != snapshot_data_on_model:
                    LOG.warn(f"Database value has changed relative to our snapshot: {field}")
                    error_fields.append(field)
                    # This means that something in the DB is different than the snapshot data we started with before
                    # modifying the model. This is a merge conflict.
                # This is an update of just the one field
            if len(error_fields) == 0:
                updating_fields = dict([(k, in_mem_dictionary[k]) for k in fieldnames])
                t.update(self.doc_ref(), updating_fields)
        
        update_select_fields(t)
        if len(failed_to_update_fields) > 0:
            raise SyncTransactionFailed(f"Tried updating {failed_to_update_fields} but server data is different than snapshot data")

        # Re-read the whole document again to get new server values.
        # This means that sync_field can update model state on other fields! This is (currently) intentional.
        self._snapshot = self.doc_ref().get()
        self.deserialize()
    
    ## Reading methods

    def before_deserialize(self, d = {}):
        return d

    def after_deserialize(self, d):
        # It should always be true that these timestamps exist, at least for all subclasses
        # of this class.
        self.creation_timestamp = d.pop('t_cr')
        self.modification_timestamp = d.pop('t_md')
        # By this point nothing has handled anything remaining in d; this is the last step
        # out of deserialization.
        self._additional_attributes = d.copy()
        return d

    def deserialize(self):
        '''
        Deserialize from the snapshot, including before and after callbacks.
        '''
        d = self._snapshot.to_dict()
        self.before_deserialize(d)
        # Delegated method to subclass implementers
        self.from_dict(d)
        self.after_deserialize(d)
        return self

    def from_dict(self, d):
        '''
        This is the method subclasses should implement in order to convert their properties from a dictionary.
        '''
        raise RequiredMethodNotImplemented("Subclasses should implement")

    def read(self):
        '''
        Read data for this instance from the DB.
        This can (will probably) destroy any local data to get up to date with the DB.
        '''
        doc_ref = self.__class__.collection().document(self._document_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return None
        self._snapshot = snapshot
        self.deserialize()
        return self

class CollectionDeleteable():
    """
    To delete an entire collection or subcollection in Cloud Firestore, retrieve (read) all the documents within the collection or subcollection and delete them.
    https://firebase.google.com/docs/firestore/manage-data/delete-data#collections

    So let's make this a mixin outside of non-delete-all-collection contexts.
    Must also be mixed in with ModelBase
    """

    @classmethod
    def delete_all_documents_in_collection(cls):
        """
        Making the name somewhat awkward on purpose to be really clear what is going to happen.
        """
        psize = 100
        # On the documentation page https://firebase.google.com/docs/firestore/manage-data/delete-data#collections
        # they do this recursively . It's not clear to me why; I think the generator will keep supplying documents
        # though the whole collection even if it's larger than page_size even if multiple fetches happen on the backend.
        # So we should just be able to stream through the whole thing.
        docs = cls.collection().list_documents(page_size=psize)
        for doc in docs:
            LOG.trace(f"Deleting doc {doc.id}")
            doc.delete()

class Candidate(ModelBase):
    '''
    * A candidate can participate in multiple Elections
    '''
    @classmethod
    def collection_name(cls):
        return "candidates"

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.name = name
        self.num_votes = 0

    def to_dict(self, d = {}):
        d.update({
            "test": "Not really a very useful piece of data, also unmapped to show that's possible",
            "num_votes": self.num_votes
                 })
        return d

    def from_dict(self, d):
        # Pull out self attributes and return the remaining attrs
        self.num_votes = d.pop("num_votes")

    def __repr__(self):
        return f"Candidate: {self.name}, num_votes: {self.num_votes} || add_at: {self._additional_attributes}"

class Election(ModelBase):
    '''
    * An Election is a concrete instance 
    '''
    @classmethod
    def collection_name(cls):
        return "elections"

    STATE_CREATED="Created"
    STATE_OPEN="Open"
    STATE_CLOSED="Closed"

    @classmethod
    def from_template(cls):
        return ElectionTemplate.create_election()

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.name = name
        self.state = Election.STATE_CREATED



class ElectionTemplate(ModelBase):

    @classmethod
    def collection_name(cls):
        return "election_templates"

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self._candidates = set()

    def to_dict(self, d = {}):
        candidates = set(map(lambda model: model.doc_ref(), self._candidates))
        d.update({
            "candidates": candidates
                 })
        return d

    def from_dict(self, d):
        # Pull out self attributes and return the remaining attrs
        self._candidates = set(map(lambda doc_ref: Candidate(doc_ref.id), d["candidates"]))


