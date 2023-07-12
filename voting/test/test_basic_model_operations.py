import pytest
import models

class TestModelWhichDidntOverrideCollectionName(models.ModelBase):
    pass

class TestModelWhichDidntOverrideDictMethods(models.ModelBase, models.CollectionDeleteable):
    @classmethod
    def collection_name(cls):
        return "test_failing_models_collection"

@pytest.fixture
def test_model_which_didnt_override_dict_methods():
    model = TestModelWhichDidntOverrideDictMethods("test_model_which_should_fail")
    yield model
    # This probably should never fail, but we're including it as a teardown just in case.
    TestModelWhichDidntOverrideDictMethods.delete_all_documents_in_collection()

class TestModel(models.ModelBase, models.CollectionDeleteable):
    @classmethod
    def collection_name(cls):
        return "test_collection"

    def __init__(self, document_id, *args, **kwargs):
        super().__init__(document_id, *args, **kwargs)
        self.to_dict_called = False
        self.from_dict_called = False
        self.before_serialize_called = False
        self.after_serialize_called = False
        self._some_key = "Initialized data"

    @property 
    def some_key(self):
        return self._some_key

    @some_key.setter
    def some_key(self, value):
        self._some_key = value

    def before_serialize(self, d={}):
        self.before_serialize_called = True
        return super().before_serialize(d)

    def after_serialize(self, d):
        self.after_serialize_called = True
        return super().after_serialize(d)

    def to_dict(self, d):
        self.to_dict_called = True
        d["some_key"] = self._some_key
        return d

    def before_deserialize(self, d={}):
        self.before_deserialize_called = True
        return super().before_deserialize(d)

    def after_deserialize(self, d):
        self.after_deserialize_called = True
        return super().after_deserialize(d)

    def from_dict(self, d):
        self.from_dict_called = True
        self._some_key = d.get("some_key", None)

@pytest.fixture
def test_model_unsaved():
    model = TestModel("test_model_unsaved")
    yield model
    # This probably should never be needed, but we're including it as a teardown just in case.
    TestModel.delete_all_documents_in_collection()

@pytest.fixture
def test_model_saved():
    model = TestModel("test_model_saved")
    model.sync()
    yield model
    # This probably should never be needed, but we're including it as a teardown just in case.
    TestModel.delete_all_documents_in_collection()

#------

class TestBasicModelRequirements:

    def test_load_creds(self):
        creds = models.Storage.load_credentials()
        assert creds is not None

    def test_classes_must_override_collection_name(self):
        with pytest.raises(Exception):
            c = TestModelWhichDidntOverrideCollectionName.collection()
        c = TestModel.collection()

    def test_classes_must_implement_to_and_from_dict(self, test_model_which_didnt_override_dict_methods):
        with pytest.raises(models.ModelBase.RequiredMethodNotImplemented):
            test_model_which_didnt_override_dict_methods.serialize()

class TestModelSerialization:

    def test_classes_have_serialize_lifecycle_methods_called(self, test_model_unsaved):
        d = test_model_unsaved.serialize()
        assert test_model_unsaved.to_dict_called == True
        assert test_model_unsaved.before_serialize_called == True
        assert test_model_unsaved.after_serialize_called == True

class TestModelDeserialization:

    def test_classes_must_have_a_snapshot_to_deserialize_from(self, test_model_unsaved):
        # This is typically done with ModelBase.read() to get the snapshot from the DB.
        # Note that this makes the construction of the *model* a 2-step process:
        # Read from the database into the snapshot then marshal into the model from the snapshot.
        # This is also used for "dirty tracking", i.e. if the snapshot differs from the db (which we
        # must unfortunately track with a read operation from the DB) then we're locally dirty / not
        # up to date with the db.
        with pytest.raises(AttributeError): #NoneType for the snapshot fails when the Firebase-expected "to_dict" method is called.
            d = test_model_unsaved.deserialize()

    def test_classes_have_deserialize_lifecycle_methods_called(self, test_model_saved):
        d = test_model_saved.deserialize()
        assert test_model_saved.from_dict_called == True
        assert test_model_saved.before_deserialize_called == True
        assert test_model_saved.after_deserialize_called == True
