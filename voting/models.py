import json
import sqlalchemy
from typing import Set, List
from sqlalchemy import Table, Column, Integer, String, DateTime, Boolean, ForeignKey, Index, event, select
from sqlalchemy.orm import relationship, backref, declarative_base, sessionmaker
from sqlalchemy.sql import func, expression

Base = declarative_base()

class Storage():
    @classmethod
    def load_credentials(cls):
        credentials=None
        with open("/Users/matt/Development/google_cloud_apps/credentials/google_cloud_apps_manager.json") as f:
            credentials=json.loads(f.read())
        return credentials
        
    @classmethod
    def initialize_db(cls):
        cls._engine = sqlalchemy.engine.create_engine('bigquery://', credentials_info=Storage.load_credentials())
        Session = sessionmaker()
        Session.configure(bind=cls._engine)
        cls._session = Session()
        # Is this idempotent with BigQuery or do we have to check for migrations?
        Base.metadata.create_all(cls._engine)

    @classmethod
    def session(cls):
        if not hasattr(cls, "_session"):
            print("Calling initialize()")
            Storage.initialize_db()
        return cls._session



class Queryable():
    @classmethod
    def query(cls):
        return Storage.session().query(cls)

class Trashable():
    trashed = Column(Boolean, server_default=expression.false())
    def trash(self):
        # This is abstract because subclasses might need to trash relationship classes in a business-logicy way
        # (e.g. an Election being trashed should also trash votes but not Candidates).
        raise "Subclasses must implement"

class CreationTimeable():
    time_created = Column(DateTime(timezone=True), server_default=func.current_datetime())

class Upsertable(Queryable):
    _upsert_key = None
    @classmethod
    def upsert(cls, value):
        '''
        For now, this is implemented in Python logic, which is race-condition-y, but I don't care because that's edge casey enough
        to accept. I don't even know if sqlite has an upsert...

        Also, page doesn't have much data to update, but it might in the future.
        '''

        instance = cls.query().filter(getattr(cls, cls._upsert_key) == value).one_or_none()
        if not instance:
            instance = cls()
            setter = setattr(instance, cls._upsert_key, value)
            Storage.session().add(instance)
            Storage.session().commit()
        return instance

'''
This is a "regular" many-to-many join in sqlalchemy (https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#setting-bi-directional-many-to-many)
Each candidate can be in multiple elections and each election has multiple candidates.
'''
candidate_election_join_table = Table(
        "voting.candidate_election",
        Base.metadata,
        Column("candidate_id", ForeignKey("voting.candidates.id"), primary_key=True),
        Column("election_id", ForeignKey("voting.elections.id"), primary_key=True)
        )

class Candidate(Base, Upsertable, Trashable, CreationTimeable):
    '''
    An option to vote on; for instance, if voting on food genera, this could be e.g. "Italian"
    '''
    __tablename__ = "voting.candidates"
    id = Column(String, primary_key=True, server_default=func.generate_uuid())
    name = Column(String, nullable=False, unique=True)
    elections = relationship("Election", secondary=candidate_election_join_table, back_populates="candidates")
    votes = relationship("Vote", back_populates="candidate")


class ElectionState(Base, Upsertable, Trashable, CreationTimeable):
    '''
    Basically an enum for the state of the election process.
    We could have this be a simple string, but eh. It's nicer to have this configurable.
    '''

    _upsert_key = "name"
    __tablename__ = "voting.election_state"
    id = Column(String, primary_key=True, server_default=func.generate_uuid())
    name = Column(String, nullable = False)

class Election(Base, Queryable, Trashable, CreationTimeable):
    '''
    The overarching model for a series of votes.

    An Election contains a number of Candidates, then a Ballot for deciding outcomes is given to each User. At the end of the Election,
    the net result of all Ballots will dictate the ordering of the Choices for that election.

    Basically, the start of every Voter sequence is creation of a new Election.
    '''
    __tablename__ = "voting.elections"
    id = Column(String, primary_key=True, server_default=func.generate_uuid())
    name = Column(String, nullable=False)
    # stores the process of the election; i.e. "created" vs. "populated" vs. "running" vs. "closed", what have you.
    process_state = Column(String, nullable=False)
    candidates = relationship(Candidate, secondary=candidate_election_join_table, back_populates="elections")
    votes = relationship("Vote", back_populates="election")


class CandidateCategory(Base, Upsertable, Trashable, CreationTimeable):
    '''
    To simplify creating a new Election each Candidate is mapped to a CandidateCategory. We can just therefore ask to
    instantiate a new "Restaurant" category, say, and a new Election will be created with all Candidates that are in that
    category.
    '''

    _upsert_key = "name"
    __tablename__ = "voting.candidate_category"

    id = Column(String, primary_key=True, server_default=func.generate_uuid())
    name = Column(String, nullable=False)

class Vote(Base, Queryable, Trashable, CreationTimeable):
    '''
    A collection of voting choices that is assigned to a user and represents a vote of their choices.
    Essentially a join model between Election and Candidate and User that scores a Candidate in that Election for that User.
    '''
    __tablename__ = "voting.votes"
    id = Column(String, primary_key=True, server_default=func.generate_uuid())
    candidate_id = Column(ForeignKey("voting.candidates.id"), primary_key=True)
    candidate = relationship(Candidate, back_populates="votes")
    election_id = Column(ForeignKey("voting.elections.id"), primary_key=True)
    election = relationship(Election, back_populates="votes")
    # For comparison counted sort this is essentially a 0 or 1, but keep it flexible as an int.
    score = Column(Integer, default=0)
