import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, JSON, Text, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# Database Connection Logic: STRICTLY PostgreSQL ONLY
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError(
        "DATABASE_URL not configured properly in .env! "
        "A valid PostgreSQL connection string starting with 'postgresql://' is required."
    )

print("Connecting to PostgreSQL database...")
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)

# Automated migration: Drop old tables if this is the first authentication upgrade or name column is missing
try:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users');")
        )
        users_table_exists = result.scalar()
        
        name_column_exists = False
        if users_table_exists:
            result_col = conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'name');")
            )
            name_column_exists = result_col.scalar()
            
        # Check if retrieval_logs table needs new trace columns
        retrieval_table_exists = conn.execute(
            text("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'retrieval_logs');")
        ).scalar()
        
        trace_column_exists = False
        if retrieval_table_exists:
            trace_column_exists = conn.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'retrieval_logs' AND column_name = 'retrieval_trace');")
            ).scalar()
            
        if not users_table_exists or not name_column_exists:
            print("Upgrading database schema for JWT Authentication and Name Column: dropping old tables...")
            conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS quiz_result_history CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS learner_profiles CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS retrieval_logs CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS evaluation_logs CASCADE;"))
            conn.commit()
            print("Old tables dropped successfully.")
        elif retrieval_table_exists and not trace_column_exists:
            print("Upgrading database schema for Retrieval Observability: dropping old logs tables...")
            conn.execute(text("DROP TABLE IF EXISTS retrieval_logs CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS evaluation_logs CASCADE;"))
            conn.commit()
            print("Old logs tables dropped for trace addition.")
except Exception as e:
    print(f"Skipped schema drop pre-check: {e}")

try:
    # Test connection
    with engine.connect() as conn:
        pass
    print("PostgreSQL connection successfully established.")
except Exception as e:
    print(f"Failed to connect to PostgreSQL database at {DATABASE_URL}: {e}")
    raise RuntimeError(f"Strict PostgreSQL Database Connection Failed: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# MODELS

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    current_level = Column(String(50), default="Beginner") # Beginner, Intermediate, Advanced
    weak_topics = Column(JSON, default=list) # List of weak topic names
    strong_topics = Column(JSON, default=list) # List of mastered topic names
    completed_topics = Column(JSON, default=list) # List of completed topic names
    quiz_history = Column(JSON, default=list) # Summary list of quiz attempt structures
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class QuizResultHistory(Base):
    __tablename__ = "quiz_result_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    topic = Column(String(255), nullable=False)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    difficulty = Column(String(50), nullable=False) # Beginner, Intermediate, Advanced
    date = Column(DateTime, default=datetime.utcnow)
    weak_subtopics = Column(JSON, default=list)
    response_duration = Column(Float, default=0.0)
    hints_used = Column(Integer, default=0)
    answer_changes_before_submit = Column(Integer, default=0)


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    query = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(JSON, default=list)
    rerank_scores = Column(JSON, default=list)
    selected_chunk_ids = Column(JSON, default=list)
    learner_level = Column(String(50), nullable=False)
    retrieval_latency = Column(Float, nullable=False) # in milliseconds
    retrieval_trace = Column(JSON, nullable=True) # vector similarities, BM25 scores, RRF ranks
    pedagogical_trace = Column(JSON, nullable=True) # learner level, active modes, boost reasons
    timestamp = Column(DateTime, default=datetime.utcnow)

class EvaluationLog(Base):
    __tablename__ = "evaluation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    faithfulness = Column(Float, nullable=False)
    answer_relevancy = Column(Float, nullable=False)
    context_precision = Column(Float, nullable=False)
    context_recall = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    topic_name = Column(String(255), nullable=False)
    mastery_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    attempt_count = Column(Integer, default=0)
    average_quiz_score = Column(Float, default=0.0)
    current_estimated_level = Column(String(50), default="Beginner") # Beginner, Intermediate, Advanced
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confidence_evidence = Column(JSON, default=dict)
    clarification_requests = Column(Integer, default=0)
    topic_repetition = Column(Integer, default=0)


class LearningLog(Base):
    __tablename__ = "learning_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type = Column(String(100), nullable=False) # quiz_submit, mastery_update, prereq_warning, spaced_repetition
    topic_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Dynamic Automated Migration Block
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE quiz_result_history ADD COLUMN IF NOT EXISTS response_duration FLOAT DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE quiz_result_history ADD COLUMN IF NOT EXISTS hints_used INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE quiz_result_history ADD COLUMN IF NOT EXISTS answer_changes_before_submit INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE topic_mastery ADD COLUMN IF NOT EXISTS confidence_evidence JSON DEFAULT '{}';"))
        conn.execute(text("ALTER TABLE topic_mastery ADD COLUMN IF NOT EXISTS clarification_requests INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE topic_mastery ADD COLUMN IF NOT EXISTS topic_repetition INTEGER DEFAULT 0;"))
        print("[Database Migration] Schema tracking columns updated successfully.")
except Exception as migration_err:
    print(f"[Database Migration Warning] Automatic ALTER TABLE migration skipped: {migration_err}")


# Dependency to get db session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# HELPER FUNCTIONS FOR INITIALIZING AND MANAGING DATA

def get_or_create_profile(db_session, user_id: int) -> LearnerProfile:
    """Retrieve the learner profile, or create a default one if it does not exist."""
    profile = db_session.query(LearnerProfile).filter(LearnerProfile.user_id == user_id).first()
    if not profile:
        profile = LearnerProfile(
            user_id=user_id,
            current_level="Beginner",
            weak_topics=[],
            strong_topics=[],
            completed_topics=[],
            quiz_history=[]
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)
    return profile

def get_or_create_topic_mastery(db_session, user_id: int, topic_name: str) -> TopicMastery:
    """Retrieve the topic mastery, or create a default one if it does not exist."""
    record = db_session.query(TopicMastery).filter(
        TopicMastery.user_id == user_id,
        TopicMastery.topic_name == topic_name
    ).first()
    if not record:
        record = TopicMastery(
            user_id=user_id,
            topic_name=topic_name,
            mastery_score=0.0,
            confidence_score=0.0,
            attempt_count=0,
            average_quiz_score=0.0,
            current_estimated_level="Beginner"
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
    return record

