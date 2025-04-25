from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
import os

# Connect to the PostgreSQL database
DATABASE_URL = os.getenv("DATABASE_URL")  # Make sure this is set in your environment
print("Connecting to database with URL:", DATABASE_URL)  # Debugging line

# Initialize FastAPI
app = FastAPI()

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Model
class Note(Base):
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index('notes_search_idx', search_vector, postgresql_using='gin'),
    )

# Create the database tables (only needed once)
Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoint to get all notes
@app.get("/notes")
def get_notes(db: Session = Depends(get_db)):
    notes = db.query(Note).all()
    return notes

# Endpoint to get a single note's content by ID
@app.get("/notes/{note_id}")
def get_note_content(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        return {"error": "Note not found"}
    return {"content": note.content}

# Search notes by query
@app.get("/search")
def search_notes(q: str, db: Session = Depends(get_db)):
    query = f"SELECT * FROM notes WHERE search_vector @@ to_tsquery(:q)"
    result = db.execute(query, {'q': q}).fetchall()
    return {"results": result}
