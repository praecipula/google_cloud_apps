import sqlalchemy
from typing import Set, List
from sqlalchemy import Table, Column, Integer, String, DateTime, Boolean, ForeignKey, Index, event, select
from sqlalchemy.orm import relationship, backref, declarative_base, sessionmaker, mapped_column, Mapped
from sqlalchemy.sql import func, expression

Base = declarative_base()

class Storage():
    @classmethod
    def initialize_db(cls):
        cls._engine = sqlalchemy.create_engine('bigquery://future-medley-249022/voting', credentials_path="../credentials/google_cloud_apps_manager.json")
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

class Trashable():
    trashed = Column(Boolean, server_default=expression.true())

'''
This is a "regular" many-to-many join in sqlalchemy (https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#setting-bi-directional-many-to-many)
Each candidate can be in multiple elections and each election has multiple candidates.
'''
candidate_election_join_table = Table(
        "candidate_election",
        Base.metadata,
        Column("candidate_id", ForeignKey("candidates.id"), primary_key=True),
        Column("election_id", ForeignKey("elections.id"), primary_key=True)
        )

class Candidate(Base, Trashable):
    '''
    An option to vote on; for instance, if voting on food genera, this could be e.g. "Italian"
    '''

    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    name = Column(String, nullable=False, unique=True)
    elections : Mapped[Set["Election"]] = relationship(secondary=candidate_election_join_table, back_populates="candidates")
    votes: Mapped[List["Vote"]] = relationship(back_populates="candidates")

class Election(Base, Trashable):
    '''
    The overarching model for a series of votes.

    An Election contains a number of Candidates, then a Ballot for deciding outcomes is given to each User. At the end of the Election,
    the net result of all Ballots will dictate the ordering of the Choices for that election.
    '''

    __tablename__ = "elections"
    id: Mapped[int] = mapped_column(primary_key=True)
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    name = Column(String, nullable=False)
    # stores the process of the election; i.e. "created" vs. "populated" vs. "running" vs. "closed", what have you.
    process_state = Column(String, nullable=False)
    candidates: Mapped[Set[Candidate]] = relationship(secondary=candidate_election_join_table, back_populates="elections")
    votes: Mapped[List["Vote"]] = relationship(back_populates="elections")

class Vote(Base, Trashable):
    '''
    A collection of voting choices that is assigned to a user and represents a vote of their choices.
    Essentially a join model between Election and Candidate and User that scores a Candidate in that Election for that User.
    '''
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    # For comparison counted sort this is essentially a 0 or 1, but keep it flexible.
    score = Column(Integer, default=0)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), primary_key = True)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), primary_key = True)
    # user_id => similar when we have a user model.

