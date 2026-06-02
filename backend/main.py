
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import shutil
import os
import sys
import io
import json
from pathlib import Path
from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.orm import Session


# Force UTF-8 encoding for stdout and stderr to prevent UnicodeEncodeError with emojis on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory and subfolders to sys.path to import modules
# Add parent directory and subfolders to sys.path to import modules
BACKEND_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = BACKEND_DIR.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BACKEND_DIR / "core"))
sys.path.append(str(BACKEND_DIR / "generators"))
sys.path.append(str(BACKEND_DIR / "video_engine"))
sys.path.append(str(BACKEND_DIR)) # For analytics

from backend.cache.redis_client import redis_client

# Import existing core modules
try:
    from backend.core.extract_pipeline import process_single_file, validate_json_file
    from backend.generators.generate_plan import run_teaching_plan_generator
    from backend.generators.generate_quiz import run_quiz_generator
    from backend.generators.generate_flashcards import run_flashcard_generator
    from backend.generators.practice_questions import generate_questions_from_json, create_pdf
    from backend.video_engine.generate_animations_synchronized import run_video_generator
    from backend.core.chatbot_rag import MathBuddyChatbot
    from backend.analytics_engine import get_recommendations
    from backend.generators.get_youtube_links import search_youtube
    from backend.core.database import (
        get_db, get_or_create_profile, get_or_create_topic_mastery,
        LearnerProfile, QuizResultHistory, TopicMastery, LearningLog
    )
    from backend.core.prerequisites import check_prerequisites, get_personalized_roadmap
    from backend.core.spaced_engine import get_revision_schedule, calculate_learning_velocity, calculate_retention, calculate_dynamic_confidence
except ImportError as e:
    print(f"Server Startup Error: Could not import modules. {e}")
    pass

app = FastAPI(title="Teaching Assistant API", version="1.0.0")

# CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Centralized Data Directories
GENERATED_DIR = BASE_DIR / "generated_contents"

def get_user_dirs(user_name: str):
    # Sanitize user name to be safe for directory naming (letters, numbers, underscores, hyphens only)
    import re
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_name.strip())
    if not safe_name:
        safe_name = "default_user"
    user_base = GENERATED_DIR / safe_name
    dirs = {
        "uploads": user_base / "uploads",
        "content": user_base / "content",
        "outputs": user_base / "outputs",
        "video_assets": user_base / "video_assets",
        "audio_segments": user_base / "audio_segments",
        "media": user_base / "media"
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs

# Initialize Chatbot
chatbot_instance = None
try:
    # Check if we are in the correct directory for relative paths in chatbot
    # Chatbot uses dynamic content discovery from generated_contents/
    # For now, let's assume server is run from root.
    chatbot_instance = MathBuddyChatbot()
except Exception as e:
    print(f"ERROR: Chatbot initialization failed: {e}")

class ChatRequest(BaseModel):
    message: str
    difficulty: str = "Beginner"
    session_id: str = "default"

class GenerateRequest(BaseModel):
    filename: str
    topic_index: int = 0
    difficulty: str = "Beginner"

class FileInfo(BaseModel):
    filename: str
    display_name: str
    topics: List[str]
    topic_count: int

class FolderInfo(BaseModel):
    folder: str
    files: List[FileInfo]

from backend.core.auth_utils import verify_password, get_password_hash, create_access_token, decode_access_token
from backend.core.database import User, RetrievalLog

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

class AuthRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

# ENDPOINTS

@app.post("/auth/signup")
async def signup(request: AuthRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    name = request.name.strip() if request.name else ""
    if not name:
        raise HTTPException(status_code=400, detail="Name is required for registration")
    
    # Check if user already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")
    
    # Hash password and save
    hashed = get_password_hash(request.password)
    user = User(email=email, name=name, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Provision learner profile
    profile = get_or_create_profile(db, user_id=user.id)
    
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "name": user.name})
    return {
        "status": "success",
        "token": token,
        "email": user.email,
        "name": user.name,
        "current_level": profile.current_level
    }

@app.post("/auth/login")
async def login(request: AuthRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    profile = get_or_create_profile(db, user_id=user.id)
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "name": user.name})
    return {
        "status": "success",
        "token": token,
        "email": user.email,
        "name": user.name,
        "current_level": profile.current_level
    }


@app.get("/")
async def root():
    return {"status": "System Online", "message": "Teaching Assistant API is running"}

# Authenticated helper to get user from token (either in header or query param)
async def get_current_user_for_serving(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> User:
    actual_token = credentials.credentials if credentials else token
    if not actual_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required"
        )
    payload = decode_access_token(actual_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@app.get("/download/{filename}")
async def download_file(filename: str, current_user: User = Depends(get_current_user_for_serving)):
    """Serve files from the outputs or video_assets directory for download, scoped by user_name"""
    user_dirs = get_user_dirs(current_user.name)
    file_path = user_dirs["outputs"] / filename
    if not file_path.exists():
        video_path = user_dirs["video_assets"] / filename
        if video_path.exists():
            return FileResponse(path=video_path, filename=filename, media_type='video/mp4')
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    return FileResponse(path=file_path, filename=filename)

@app.get("/outputs/{filename}")
async def serve_output_file(filename: str, current_user: User = Depends(get_current_user_for_serving)):
    """Serve PDF and output assets dynamically with authentication"""
    user_dirs = get_user_dirs(current_user.name)
    file_path = user_dirs["outputs"] / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/video_assets/{filename}")
async def serve_video_asset(filename: str, current_user: User = Depends(get_current_user_for_serving)):
    """Serve video assets dynamically with authentication"""
    user_dirs = get_user_dirs(current_user.name)
    file_path = user_dirs["video_assets"] / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4")

@app.get("/files", response_model=List[FolderInfo])
async def list_files(current_user: User = Depends(get_current_user)):
    """List all processed JSON files recursively from content directory, scoped by user_name"""
    results_map = {} # folder_path -> List[FileInfo]
    
    user_dirs = get_user_dirs(current_user.name)
    user_content_dir = user_dirs["content"]
    
    if not user_content_dir.exists():
        return []

    # Recursively find all .json files inside user_content_dir
    for f in user_content_dir.rglob("*.json"):
        # FILTER: Skip backend mapping files and text_output directories
        if f.name.startswith("chapter_mapping") or "text_output" in str(f.parent):
            continue

        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, dict):
                    data = [data]
                
                topics = [item.get('topic_name', 'Unknown') for item in data]
                
                if topics and topics[0] != 'Unknown':
                    display_name = topics[0]
                else:
                    display_name = f.stem.replace('_', ' ').title()

                rel_path = f.relative_to(user_content_dir)
                
                # Group by top-level or mid-level folder?
                folder_parts = rel_path.parts[:-2] # Skip filename and its immediate parent (usually json_output)
                if not folder_parts:
                    folder_name = "Root"
                else:
                    folder_name = " > ".join(folder_parts)

                if folder_name not in results_map:
                    results_map[folder_name] = []
                
                results_map[folder_name].append({
                    "filename": str(rel_path).replace("\\", "/"),
                    "display_name": display_name,
                    "topics": topics,
                    "topic_count": len(topics)
                })
        except Exception as e:
            print(f"Error reading {f}: {e}")

    # Convert map to FolderInfo list
    results = []
    for folder, files in results_map.items():
        results.append({
            "folder": folder,
            "files": files
        })
            
    return results

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user)
):
    """Upload a PDF, identify metadata, and process it into the correct folder, scoped by user_name"""
    user_dirs = get_user_dirs(current_user.name)
    user_upload_dir = user_dirs["uploads"]
    user_content_dir = user_dirs["content"]
    
    file_path = user_upload_dir / file.filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        from backend.core.extract_pipeline import identify_book_metadata, process_specific_pdf, load_schema
        
        # 1. Identify Metadata
        metadata = identify_book_metadata(file_path)
        
        # 2. Process with Metadata
        schema = load_schema()
        if not schema:
            return JSONResponse(status_code=500, content={"error": "Schema not found"})
            
        json_output = process_specific_pdf(file_path, schema, custom_output_base=user_content_dir, metadata=metadata)
        
        if json_output:
            # Create a display string for the folder
            grade = metadata.get('grade', 'Unknown')
            subject = metadata.get('subject', 'General')
            folder_display = f"Grade {grade} > {subject}"
            
            return {
                "status": "success", 
                "message": f"Processed into {folder_display}", 
                "json_file": str(json_output.relative_to(user_content_dir)).replace("\\", "/"),
                "metadata": metadata
            }
        else:
            return JSONResponse(status_code=500, content={"error": "Processing failed"})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# Helper to resolve path
def get_json_path(filename: str, user_name: str) -> Path:
    user_dirs = get_user_dirs(user_name)
    return user_dirs["content"] / filename

@app.post("/generate/plan")
async def generate_plan(request: GenerateRequest, current_user: User = Depends(get_current_user)):
    """Generate Teaching Plan PDF"""
    json_path = get_json_path(request.filename, current_user.name)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {json_path}")
        
    output_filename = f"Plan_{json_path.stem}_{request.topic_index}.pdf"
    user_dirs = get_user_dirs(current_user.name)
    output_path = user_dirs["outputs"] / output_filename
    
    try:
        final_path = run_teaching_plan_generator(str(json_path), str(output_path), request.topic_index, request.difficulty)
        if final_path:
            actual_filename = os.path.basename(final_path)
            return {"status": "success", "file_url": f"/download/{actual_filename}", "filename": actual_filename}
        else:
            raise HTTPException(status_code=500, detail="Generation failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class YouTubeRequest(BaseModel):
    query: str = None
    filename: str = None
    topic_index: int = 0

@app.post("/generate/quiz")
async def generate_quiz(request: GenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate Quiz PDF with Dynamic Difficulty Allocation based on Learner Model"""
    json_path = get_json_path(request.filename, current_user.name)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # -- DYNAMIC DIFFICULTY ALLOCATION --
    # Determine difficulty from learner's TopicMastery if not explicitly overridden
    effective_difficulty = request.difficulty
    auto_difficulty = False
    
    try:
        # Read the topic name from the JSON file to look up mastery
        with open(json_path, 'r', encoding='utf-8') as f:
            topic_data = json.load(f)
        if isinstance(topic_data, dict):
            topic_data = [topic_data]
        
        if 0 <= request.topic_index < len(topic_data):
            topic_name = topic_data[request.topic_index].get("topic_name", "")
            if topic_name:
                mastery_record = db.query(TopicMastery).filter(
                    TopicMastery.user_id == current_user.id,
                    TopicMastery.topic_name == topic_name
                ).first()
                
                if mastery_record and mastery_record.mastery_score is not None:
                    m_score = mastery_record.mastery_score
                    if m_score < 0.40:
                        effective_difficulty = "Beginner"
                    elif m_score < 0.75:
                        effective_difficulty = "Intermediate"
                    else:
                        effective_difficulty = "Advanced"
                    
                    if effective_difficulty != request.difficulty:
                        auto_difficulty = True
                        print(f"[Dynamic Difficulty] Auto-adjusted quiz difficulty to '{effective_difficulty}' "
                              f"based on mastery={m_score:.2f} for topic '{topic_name}'")
    except Exception as diff_err:
        print(f"[Dynamic Difficulty] Fallback to requested difficulty: {diff_err}")
        
    output_filename = f"Quiz_{json_path.stem}_{request.topic_index}.pdf"
    user_dirs = get_user_dirs(current_user.name)
    output_path = user_dirs["outputs"] / output_filename
    
    try:
        result = run_quiz_generator(str(json_path), str(output_path), request.topic_index, effective_difficulty)
        
        if not result:
            raise HTTPException(status_code=500, detail="Generation failed. The AI might be rate-limited or failed to output correct format.")
            
        return {
            "status": "success", 
            "file_url": f"/download/{output_filename}", 
            "filename": output_filename,
            "data": result['data'],
            "effective_difficulty": effective_difficulty,
            "auto_difficulty": auto_difficulty,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/flashcards")
async def generate_flashcards(request: GenerateRequest, current_user: User = Depends(get_current_user)):
    """Generate Flashcards JSON"""
    json_path = get_json_path(request.filename, current_user.name)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    output_filename = f"Flashcards_{json_path.stem}_{request.topic_index}.json"
    user_dirs = get_user_dirs(current_user.name)
    output_path = user_dirs["outputs"] / output_filename
    
    try:
        final_path = run_flashcard_generator(str(json_path), str(output_path), request.topic_index, request.difficulty)
        
        if not final_path:
             raise HTTPException(status_code=500, detail="Generation failed. The AI might be rate-limited.")
             
        with open(final_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
            
        return {"status": "success", "data": content}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/practice")
async def generate_practice(request: GenerateRequest, current_user: User = Depends(get_current_user)):
    """Generate Practice Questions PDF"""
    json_path = get_json_path(request.filename, current_user.name)
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            data = [data]
            
        from backend.generators.practice_questions import run_practice_generator
        
        output_filename = f"Practice_{json_path.stem}_{request.topic_index}.pdf"
        user_dirs = get_user_dirs(current_user.name)
        output_path = user_dirs["outputs"] / output_filename
        
        final_path = run_practice_generator(str(json_path), str(output_path), request.topic_index, request.difficulty)
        
        if final_path:
            return {"status": "success", "file_url": f"/download/{output_filename}", "filename": output_filename}
        else:
            raise HTTPException(status_code=500, detail="PDF Creation failed")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/resources")
async def generate_resources(request: GenerateRequest, current_user: User = Depends(get_current_user)):
    """Fetch YouTube Resources"""
    json_path = get_json_path(request.filename, current_user.name)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, dict):
            data = [data]
            
        topic = data[request.topic_index]
        topic_name = topic.get('topic_name', 'General Topic')
        
        # Import dynamically to avoid top-level issues if env missing
        from backend.generators.get_youtube_links import search_youtube
        
        query = f"{topic_name} educational explanation tutorial for students"
        videos = search_youtube(query, max_results=6)
        
        return {"status": "success", "data": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Clarification trigger phrases for behavioral detection
CLARIFICATION_TRIGGERS = [
    "explain again", "simplify this", "another example", "i don't understand",
    "give an example", "can you simplify", "what does that mean", "i'm confused",
    "break it down", "explain it differently", "say that again", "make it simpler",
    "can you explain", "help me understand", "i don't get it", "too complex",
    "in simple terms", "in simpler words", "elaborate", "clarify",
]

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """RAG Chatbot Endpoint with Clarification Scanning & Topic Repetition Tracking"""
    if not chatbot_instance:
        return {"answer": "Chatbot is offline (Check API Keys or Init).", "chapter": "System", "relevance": 0}
    
    # -- CLARIFICATION DETECTION --
    # Parse the incoming message for clarification trigger phrases
    message_lower = request.message.strip().lower()
    is_clarification = any(trigger in message_lower for trigger in CLARIFICATION_TRIGGERS)
    
    # Execute the chatbot response
    response = chatbot_instance.get_response(
        request.message,
        request.difficulty,
        user_id=current_user.id,
        session_id=request.session_id
    )
    
    # -- BEHAVIORAL TRACKING --
    # If a clarification was detected, update the active topic's mastery record
    if is_clarification and "error" not in response:
        try:
            chapter_name = response.get("chapter", "")
            if chapter_name and chapter_name not in ("System", "System Error", "None"):
                mastery_record = db.query(TopicMastery).filter(
                    TopicMastery.user_id == current_user.id,
                    TopicMastery.topic_name.ilike(f"%{chapter_name}%")
                ).first()
                
                if mastery_record:
                    mastery_record.clarification_requests = (mastery_record.clarification_requests or 0) + 1
                    mastery_record.topic_repetition = (mastery_record.topic_repetition or 0) + 1
                    
                    # Recalculate confidence with updated clarification count
                    if mastery_record.attempt_count and mastery_record.attempt_count > 0:
                        latest_quiz = db.query(QuizResultHistory).filter(
                            QuizResultHistory.user_id == current_user.id,
                            QuizResultHistory.topic.ilike(f"%{chapter_name}%")
                        ).order_by(QuizResultHistory.date.desc()).first()
                        
                        if latest_quiz:
                            conf_result = calculate_dynamic_confidence(
                                score=latest_quiz.score,
                                total_questions=latest_quiz.total_questions,
                                response_duration=latest_quiz.response_duration or 0.0,
                                hints_used=latest_quiz.hints_used or 0,
                                answer_changes_before_submit=latest_quiz.answer_changes_before_submit or 0,
                                clarification_requests=mastery_record.clarification_requests,
                            )
                            mastery_record.confidence_score = conf_result["confidence_score"]
                            mastery_record.confidence_evidence = conf_result["evidence"]
                    
                    # Log the clarification event
                    clarification_log = LearningLog(
                        user_id=current_user.id,
                        event_type="clarification_request",
                        topic_name=chapter_name,
                        description=f"Clarification requested: '{request.message[:100]}...' (Total clarifications for topic: {mastery_record.clarification_requests})"
                    )
                    db.add(clarification_log)
                    db.commit()
                    print(f"[Behavioral Tracker] Clarification detected for topic '{chapter_name}' (count: {mastery_record.clarification_requests})")
        except Exception as track_err:
            print(f"[Behavioral Tracker] Clarification tracking error: {track_err}")
            db.rollback()
    
    if "error" in response:
        return {
            "answer": f" Chatbot Error: {response['error']}",
            "chapter": "System Error",
            "relevance": 0,
            "sources": []
        }
        
    return response

@app.post("/generate/video")
async def generate_video(request: GenerateRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    """Generate Shortform Video (Background Task) with Unique Filename, scoped by user_name"""
    json_path = get_json_path(request.filename, current_user.name)
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {json_path}")
        
    # UNIQUE FILENAME LOGIC
    import uuid
    import time
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:6]
    output_filename = f"Video_{json_path.stem}_{request.topic_index}_{timestamp}_{unique_id}.mp4"
    user_dirs = get_user_dirs(current_user.name)
    output_path = user_dirs["outputs"] / output_filename
    
    # Initialize background status in Redis
    status_key = f"video_job:{output_filename}"
    redis_client.set_status(status_key, "PENDING", ex_seconds=86400) # 24 hours
    
    # Define the background task wrapper
    def _run_gen():
        try:
            # PASS unique filename to generator and use user specific output dir
            run_video_generator(str(json_path), str(user_dirs["outputs"]), request.topic_index, custom_filename=output_filename)
        except Exception as e:
            print(f"Background Video Gen Failed: {e}")
            redis_client.set_status(status_key, "FAILED", ex_seconds=86400)

    background_tasks.add_task(_run_gen)
    
    return {
        "status": "processing", 
        "message": "Video generation started in background", 
        "filename": output_filename, # Frontend polls this UNIQUE key
        "check_url": f"/download/{output_filename}"
    }

@app.get("/video/status/{job_id}")
async def get_video_status(job_id: str):
    """Check video generation job status in Redis"""
    status_key = f"video_job:{job_id}"
    status = redis_client.get_status(status_key)
    
    if status:
        return {"job_id": job_id, "status": status}
        
    return {"job_id": job_id, "status": "NOT_FOUND"}




# ANALYTICS ENDPOINTS

class QuizSubmitRequest(BaseModel):
    topic: str
    score: int
    total_questions: int
    difficulty: str
    weak_subtopics: List[str] = []
    response_duration: float = 0.0  # Total time in seconds for the quiz
    hints_used: int = 0             # Total hints consumed during quiz
    answer_changes_before_submit: int = 0  # Total answer modifications before final submit

class ProfileUpdateRequest(BaseModel):
    current_level: Optional[str] = None
    completed_topic: Optional[str] = None

@app.get("/learner/profile")
async def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        profile = get_or_create_profile(db, user_id=current_user.id)
        return {
            "status": "success",
            "current_level": profile.current_level,
            "weak_topics": profile.weak_topics,
            "strong_topics": profile.strong_topics,
            "completed_topics": profile.completed_topics,
            "quiz_history": profile.quiz_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/learner/profile")
async def update_profile(request: ProfileUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        profile = get_or_create_profile(db, user_id=current_user.id)
        if request.current_level:
            if request.current_level not in ["Beginner", "Intermediate", "Advanced"]:
                raise HTTPException(status_code=400, detail="Invalid difficulty level")
            profile.current_level = request.current_level
        if request.completed_topic:
            completed = list(profile.completed_topics or [])
            if request.completed_topic not in completed:
                completed.append(request.completed_topic)
                profile.completed_topics = completed
        db.commit()
        db.refresh(profile)
        return {"status": "success", "profile": {
            "current_level": profile.current_level,
            "weak_topics": profile.weak_topics,
            "strong_topics": profile.strong_topics,
            "completed_topics": profile.completed_topics
        }}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quiz/submit")
async def submit_quiz(result: QuizSubmitRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Save quiz result and update fine-grained topic mastery, confidence, and learning logs"""
    try:
        # 1. Save to QuizResultHistory table (now includes behavioral tracking columns)
        record = QuizResultHistory(
            user_id=current_user.id,
            topic=result.topic,
            score=result.score,
            total_questions=result.total_questions,
            difficulty=result.difficulty,
            weak_subtopics=result.weak_subtopics,
            response_duration=result.response_duration,
            hints_used=result.hints_used,
            answer_changes_before_submit=result.answer_changes_before_submit,
        )
        db.add(record)

        # 2. Update global Learner Profile (legacy weak/strong topic tracking)
        profile = get_or_create_profile(db, user_id=current_user.id)
        percentage = (result.score / result.total_questions) * 100 if result.total_questions > 0 else 0
        normalized_score = percentage / 100.0

        weak = list(profile.weak_topics or [])
        strong = list(profile.strong_topics or [])
        history = list(profile.quiz_history or [])

        attempt_entry = {
            "id": len(history) + 1,
            "topic": result.topic,
            "score": result.score,
            "total_questions": result.total_questions,
            "percentage": round(percentage, 1),
            "difficulty": result.difficulty,
            "date": datetime.utcnow().isoformat(),
            "weak_subtopics": result.weak_subtopics,
            "response_duration": result.response_duration,
            "hints_used": result.hints_used,
            "answer_changes": result.answer_changes_before_submit,
        }
        history.append(attempt_entry)
        profile.quiz_history = history

        if percentage < 40:
            if result.topic not in weak:
                weak.append(result.topic)
            if result.topic in strong:
                strong.remove(result.topic)
        elif percentage >= 80:
            if result.topic not in strong:
                strong.append(result.topic)
            if result.topic in weak:
                weak.remove(result.topic)

        profile.weak_topics = weak
        profile.strong_topics = strong

        # 3. --- SMOOTH TOPIC-WISE MASTERY UPDATE ---
        mastery_record = get_or_create_topic_mastery(db, user_id=current_user.id, topic_name=result.topic)

        old_mastery = mastery_record.mastery_score

        # Smooth exponential mastery update: M_new = M_old * 0.7 + score * 0.3
        new_mastery = round((old_mastery * 0.7) + (normalized_score * 0.3), 4)

        # 4. --- DYNAMIC CONFIDENCE CALCULATION (Multi-Signal Behavioral Formula) ---
        clarification_count = mastery_record.clarification_requests or 0
        confidence_result = calculate_dynamic_confidence(
            score=result.score,
            total_questions=result.total_questions,
            response_duration=result.response_duration,
            hints_used=result.hints_used,
            answer_changes_before_submit=result.answer_changes_before_submit,
            clarification_requests=clarification_count,
        )
        new_confidence = confidence_result["confidence_score"]
        confidence_evidence = confidence_result["evidence"]

        # Update running average quiz score
        total_attempts = mastery_record.attempt_count + 1
        new_avg_score = round(
            ((mastery_record.average_quiz_score * mastery_record.attempt_count) + percentage) / total_attempts, 2
        )

        # Derive topic-specific estimated level from mastery score
        if new_mastery >= 0.75:
            estimated_level = "Advanced"
        elif new_mastery >= 0.45:
            estimated_level = "Intermediate"
        else:
            estimated_level = "Beginner"

        # Increment topic repetition count
        mastery_record.topic_repetition = (mastery_record.topic_repetition or 0) + 1

        mastery_record.mastery_score = new_mastery
        mastery_record.confidence_score = new_confidence
        mastery_record.confidence_evidence = confidence_evidence
        mastery_record.attempt_count = total_attempts
        mastery_record.average_quiz_score = new_avg_score
        mastery_record.current_estimated_level = estimated_level

        # 5. --- PREREQUISITE GAP ANALYSIS ---
        prereq_gaps = check_prerequisites(db, current_user.id, result.topic)
        prereq_log_desc = None
        if prereq_gaps:
            gap_summary = ", ".join(
                [f"{g['prereq_topic']} ({g['score_percentage']}%)" for g in prereq_gaps]
            )
            prereq_log_desc = f"Prerequisite gaps detected for '{result.topic}': {gap_summary}"

        # 6. --- LEARNING LOG WRITES ---
        quiz_log = LearningLog(
            user_id=current_user.id,
            event_type="quiz_submit",
            topic_name=result.topic,
            description=f"Quiz completed: {result.score}/{result.total_questions} ({round(percentage,1)}%) at {result.difficulty} level. Duration: {result.response_duration}s, Hints: {result.hints_used}, Changes: {result.answer_changes_before_submit}"
        )
        db.add(quiz_log)

        mastery_log = LearningLog(
            user_id=current_user.id,
            event_type="mastery_update",
            topic_name=result.topic,
            description=f"Mastery updated: {round(old_mastery*100,1)}% -> {round(new_mastery*100,1)}% | Confidence: {round(new_confidence*100,1)}% (dynamic) | Level: {estimated_level}"
        )
        db.add(mastery_log)

        if prereq_log_desc:
            prereq_log = LearningLog(
                user_id=current_user.id,
                event_type="prereq_warning",
                topic_name=result.topic,
                description=prereq_log_desc
            )
            db.add(prereq_log)

        # 7. Global Auto-Difficulty Promotion check (legacy)
        auto_promoted = False
        current_level = profile.current_level
        if percentage >= 80 and current_level in ["Beginner", "Intermediate"]:
            level_attempts = [
                h for h in history
                if h.get("difficulty") == current_level and h.get("percentage", 0) >= 80
            ]
            if len(level_attempts) >= 3:
                new_level = "Intermediate" if current_level == "Beginner" else "Advanced"
                profile.current_level = new_level
                auto_promoted = True
                promotion_log = LearningLog(
                    user_id=current_user.id,
                    event_type="level_promotion",
                    topic_name=result.topic,
                    description=f"Global difficulty auto-promoted from {current_level} to {new_level} after 3 consecutive high-score attempts."
                )
                db.add(promotion_log)
                print(f"Auto-Promoting user from {current_level} to {new_level}!")

        db.commit()

        return {
            "status": "success",
            "record": attempt_entry,
            "auto_promoted": auto_promoted,
            "new_level": profile.current_level,
            "topic_mastery": {
                "topic": result.topic,
                "mastery_score": new_mastery,
                "confidence_score": new_confidence,
                "confidence_evidence": confidence_evidence,
                "estimated_level": estimated_level,
                "average_quiz_score": new_avg_score,
                "attempt_count": total_attempts
            },
            "prereq_gaps": prereq_gaps
        }
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/analytics")
async def get_dashboard_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get processed data for dashboard using user-specific PostgreSQL history"""
    try:
        # Query user-specific quiz history from PostgreSQL
        history_records = db.query(QuizResultHistory).filter(QuizResultHistory.user_id == current_user.id).order_by(QuizResultHistory.date.desc()).all()
        
        history = []
        for r in history_records:
            history.append({
                "topic": r.topic,
                "score": r.score,
                "total_questions": r.total_questions,
                "difficulty": r.difficulty,
                "date": r.date.isoformat(),
                "weak_subtopics": r.weak_subtopics or []
            })
            
        if not history:
            return {
                "spider_data": [],
                "recent_activity": [],
                "weakest_topics": [],
                "recommendations": []
            }
            
        # 1. Calculate Topic Scores
        topic_stats = {}
        for entry in history:
            t = entry['topic']
            score = entry['score']
            total = entry['total_questions']
            percentage = (score / total) * 100 if total > 0 else 0
            
            if t not in topic_stats:
                topic_stats[t] = {'sum_pct': 0, 'count': 0}
            
            topic_stats[t]['sum_pct'] += percentage
            topic_stats[t]['count'] += 1

        # Query TopicMastery to get real-time learning metrics
        mastery_records = db.query(TopicMastery).filter(TopicMastery.user_id == current_user.id).all()
        mastery_by_topic = {r.topic_name.lower(): r for r in mastery_records}

        spider_data = []
        weakest_list = []
        
        for topic, stats in topic_stats.items():
            avg_score = round(stats['sum_pct'] / stats['count'], 1)
            
            # Match by case-insensitive name
            m_record = mastery_by_topic.get(topic.lower())
            if m_record:
                m_score = m_record.mastery_score if m_record.mastery_score is not None else 0.0
                c_score = m_record.confidence_score if m_record.confidence_score is not None else 0.0
                attempts = m_record.attempt_count if m_record.attempt_count is not None else 1
                ret_val = calculate_retention(m_score, c_score, m_record.last_updated, attempts)
            else:
                m_score, c_score, ret_val = 0.0, 0.0, 0.0
                
            spider_data.append({
                "subject": topic,
                "A": avg_score,
                "mastery": round(m_score * 100, 1),
                "confidence": round(c_score * 100, 1),
                "retention": round(ret_val * 100, 1),
                "fullMark": 100
            })
            
            if avg_score < 70:  # Threshold for "Weak"
                weakest_list.append({"topic": topic, "score": avg_score})

        # Sort weakest
        weakest_list.sort(key=lambda x: x['score'])
        
        data = {
            "spider_data": spider_data,
            "recent_activity": history[:5], # First 5 in descending date order (most recent)
            "weakest_topics": weakest_list
        }
        
        if data['weakest_topics'] and chatbot_instance:
            weak_topic_names = [x['topic'] for x in data['weakest_topics']]
            # Limit to top 3 weakest to save time
            recs = get_recommendations(weak_topic_names[:3], chatbot_instance.qa_system, chatbot_instance.client, chatbot_instance.model_name)
            data['recommendations'] = recs
        else:
            data['recommendations'] = []
            
        return data
    except Exception as e:
        # Log error but return empty structure to avoid crashing UI
        print(f"Analytics Error: {e}")
        return {
            "spider_data": [],
            "recent_activity": [],
            "weakest_topics": [],
            "recommendations": [],
            "error": str(e)
        }


# LEARNER INTELLIGENCE ENDPOINTS

@app.get("/learner/mastery")
async def get_topic_mastery(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return per-topic mastery scores, confidence levels, retention, and estimated levels"""
    try:
        records = db.query(TopicMastery).filter(TopicMastery.user_id == current_user.id).all()
        mastery_list = []
        for r in records:
            m_score = r.mastery_score if r.mastery_score is not None else 0.0
            c_score = r.confidence_score if r.confidence_score is not None else 0.0
            attempts = r.attempt_count if r.attempt_count is not None else 1
            retention = calculate_retention(m_score, c_score, r.last_updated, attempts)
            mastery_list.append({
                "topic": r.topic_name,
                "mastery_score": m_score,
                "mastery_percentage": round(m_score * 100, 1),
                "confidence_score": c_score,
                "confidence_percentage": round(c_score * 100, 1),
                "estimated_level": r.current_estimated_level,
                "attempt_count": r.attempt_count,
                "average_quiz_score": r.average_quiz_score,
                "retention": retention,
                "retention_percentage": round(retention * 100, 1),
                "confidence_evidence": r.confidence_evidence or {},
                "last_updated": r.last_updated.isoformat() if r.last_updated else None
            })
        mastery_list.sort(key=lambda x: x["mastery_score"], reverse=True)
        return {"status": "success", "mastery": mastery_list}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/learner/timeline")
async def get_learning_timeline(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return chronological learning event log with velocity analytics and spaced revision schedule"""
    try:
        logs = db.query(LearningLog).filter(
            LearningLog.user_id == current_user.id
        ).order_by(LearningLog.timestamp.desc()).limit(50).all()

        timeline = []
        for log in logs:
            timeline.append({
                "event_type": log.event_type,
                "topic": log.topic_name,
                "description": log.description,
                "timestamp": log.timestamp.isoformat()
            })

        velocity = calculate_learning_velocity(db, current_user.id)
        revision_schedule = get_revision_schedule(db, current_user.id)

        return {
            "status": "success",
            "timeline": timeline,
            "velocity": velocity,
            "revision_schedule": revision_schedule[:5]  # Top 5 most urgent
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/learner/roadmap")
async def get_learning_roadmap(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Generate a personalized multi-step learning roadmap based on mastery and prerequisite graph"""
    try:
        # Collect all available topics from user's uploaded content
        user_dirs = get_user_dirs(current_user.name)
        user_content_dir = user_dirs["content"]
        available_topics = []

        if user_content_dir.exists():
            for f in user_content_dir.rglob("*.json"):
                if "text_output" in str(f.parent) or f.name.startswith("chapter_mapping"):
                    continue
                try:
                    with open(f, 'r', encoding='utf-8') as jf:
                        data = json.load(jf)
                        if isinstance(data, dict):
                            data = [data]
                        for item in data:
                            t = item.get("topic_name", "")
                            if t:
                                available_topics.append(t)
                except Exception:
                    pass

        roadmap = get_personalized_roadmap(db, current_user.id, available_topics)
        return {"status": "success", "roadmap": roadmap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/dashboard")
async def get_learner_analytics_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Comprehensive Learning-Aware Analytics Dashboard.
    
    Returns:
        - Topic-by-topic Mastery, Confidence, and Retention scores
        - Learning Velocity and Overall Growth patterns
        - Explainable confidence metrics (accuracy, speed, hint penalty, answer stability)
        - Sorted Priority Revision Queue
    """
    try:
        # 1. Topic-wise Mastery, Confidence, and Retention
        mastery_records = db.query(TopicMastery).filter(TopicMastery.user_id == current_user.id).all()
        
        topic_analytics = []
        for r in mastery_records:
            m_score = r.mastery_score if r.mastery_score is not None else 0.0
            c_score = r.confidence_score if r.confidence_score is not None else 0.0
            attempts = r.attempt_count if r.attempt_count is not None else 1
            retention = calculate_retention(m_score, c_score, r.last_updated, attempts)
            
            topic_analytics.append({
                "topic": r.topic_name,
                "mastery_score": m_score,
                "mastery_percentage": round(m_score * 100, 1),
                "confidence_score": c_score,
                "confidence_percentage": round(c_score * 100, 1),
                "retention_score": retention,
                "retention_percentage": round(retention * 100, 1),
                "estimated_level": r.current_estimated_level,
                "attempt_count": r.attempt_count or 0,
                "average_quiz_score": r.average_quiz_score or 0.0,
                "clarification_requests": r.clarification_requests or 0,
                "topic_repetition": r.topic_repetition or 0,
                "confidence_evidence": r.confidence_evidence or {},
                "last_updated": r.last_updated.isoformat() if r.last_updated else None,
            })
        
        topic_analytics.sort(key=lambda x: x["mastery_score"], reverse=True)
        
        # 2. Learning Velocity and Growth Patterns
        velocity = calculate_learning_velocity(db, current_user.id)
        
        # 3. Priority Revision Queue
        revision_queue = get_revision_schedule(db, current_user.id)
        
        # 4. Overall Summary Statistics
        total_topics = len(topic_analytics)
        avg_mastery = round(sum(t["mastery_score"] for t in topic_analytics) / total_topics, 3) if total_topics > 0 else 0.0
        avg_confidence = round(sum(t["confidence_score"] for t in topic_analytics) / total_topics, 3) if total_topics > 0 else 0.0
        avg_retention = round(sum(t["retention_score"] for t in topic_analytics) / total_topics, 3) if total_topics > 0 else 0.0
        
        topics_at_risk = [t for t in topic_analytics if t["retention_score"] < 0.50 or t["confidence_score"] < 0.50]
        
        return {
            "status": "success",
            "summary": {
                "total_topics_tracked": total_topics,
                "average_mastery": avg_mastery,
                "average_mastery_percentage": round(avg_mastery * 100, 1),
                "average_confidence": avg_confidence,
                "average_confidence_percentage": round(avg_confidence * 100, 1),
                "average_retention": avg_retention,
                "average_retention_percentage": round(avg_retention * 100, 1),
                "topics_at_risk_count": len(topics_at_risk),
            },
            "topic_analytics": topic_analytics,
            "learning_velocity": velocity,
            "revision_queue": revision_queue,
            "topics_at_risk": topics_at_risk,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/youtube")
async def generate_youtube_links(request: YouTubeRequest, current_user: User = Depends(get_current_user)):
    """
    Search for YouTube videos.
    Can accept a raw query OR a filename/topic_index to infer the topic.
    """
    try:
        query = request.query
        
        # If no explicit query, try to infer from loaded JSON (mock logic similar to other endpoints)
        if not query and request.filename:
            # infer logic
            try:
                # Use helper to get absolute path
                json_path = get_json_path(request.filename, current_user.name)
                
                # If path exists, read it
                if json_path.exists():
                    import json
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # Handle list vs dict structure
                    topics = data if isinstance(data, list) else data.get('topics', [])
                    
                    if topics and 0 <= request.topic_index < len(topics):
                        topic_name = topics[request.topic_index]['topic_name']
                        
                        # Dynamically extract grade and subject from folder path structure
                        grade_label = "General"
                        subject = "Education"
                        parts = json_path.resolve().parts
                        for i, part in enumerate(parts):
                            if part.lower().startswith("grade_"):
                                grade_label = part.replace("_", " ")
                                if i + 1 < len(parts) and parts[i + 1].lower() != "json_output":
                                    subject = parts[i + 1]
                                break
                        query = f"{grade_label} {subject} {topic_name} explanation"
            except Exception as e:
                print(f"Warning: Failed to infer topic from filename {request.filename}: {e}")
                # Fallthrough to error if query still None
            
        if not query:
            return {"error": "Could not determine search query"}
            
        # Pass the API key explicitly as search_youtube expects it
        from backend.generators.get_youtube_links import YOUTUBE_API_KEY
        videos = search_youtube(query, YOUTUBE_API_KEY)
        return {"query": query, "videos": videos}
        
    except Exception as e:
        print(f"YouTube Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("Starting Backend Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
