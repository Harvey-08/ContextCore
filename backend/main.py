
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import shutil
import os
import sys
import io
import json
from pathlib import Path
from typing import List, Optional
import uuid

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

# Import existing core modules
try:
    from extract_pipeline import process_single_file, validate_json_file
    from generate_plan import run_teaching_plan_generator
    from generate_quiz import run_quiz_generator
    from generate_flashcards import run_flashcard_generator
    from practice_questions import generate_questions_from_json, create_pdf
    from generate_animations_synchronized import run_video_generator
    from chatbot_rag import MathBuddyChatbot
    from analytics_engine import save_quiz_result, get_analytics_dash_data, get_recommendations, QuizResult
    from get_youtube_links import search_youtube
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
UPLOAD_DIR = GENERATED_DIR / "uploads"
CONTENT_DIR = GENERATED_DIR / "content"
OUTPUT_DIR = GENERATED_DIR / "outputs"
QUIZ_ASSETS_DIR = GENERATED_DIR / "quiz_assets"
VIDEO_ASSETS_DIR = GENERATED_DIR / "video_assets"
AUDIO_ASSETS_DIR = GENERATED_DIR / "audio_segments"
MEDIA_DIR = GENERATED_DIR / "media"

# Directory creation will happen "Just-in-Time" in specific endpoints

# Initialize Chatbot
chatbot_instance = None
try:
    # Check if we are in the correct directory for relative paths in chatbot
    # chatbot_rag now correctly expects mapping inside content/class7/
    # We might need to change CWD or pass path needed. 
    # For now, let's assume server is run from root.
    chatbot_instance = MathBuddyChatbot()
except Exception as e:
    print(f"ERROR: Chatbot initialization failed: {e}")

class ChatRequest(BaseModel):
    message: str

class GenerateRequest(BaseModel):
    filename: str
    topic_index: int = 0

class FileInfo(BaseModel):
    filename: str
    display_name: str
    topics: List[str]
    topic_count: int

class FolderInfo(BaseModel):
    folder: str
    files: List[FileInfo]

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {"status": "System Online", "message": "Teaching Assistant API is running"}

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Serve files from the outputs directory for download"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        # Fallback for video assets if needed
        video_path = VIDEO_ASSETS_DIR / filename
        if video_path.exists():
            return FileResponse(path=video_path, filename=filename, media_type='video/mp4')
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    
    return FileResponse(path=file_path, filename=filename)

# Mount static directories (Ensure they exist first to prevent startup crash)
from fastapi.staticfiles import StaticFiles
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory="generated_contents/outputs"), name="outputs")
app.mount("/video_assets", StaticFiles(directory="generated_contents/video_assets"), name="video_assets")

@app.get("/files", response_model=List[FolderInfo])
async def list_files():
    """List all processed JSON files recursively from content directory"""
    results_map = {} # folder_path -> List[FileInfo]
    
    if not CONTENT_DIR.exists():
        return []

    # Recursively find all .json files inside CONTENT_DIR
    for f in CONTENT_DIR.rglob("*.json"):
        # FILTER: Skip backend mapping files and text_output directories
        if f.name.startswith("chapter_mapping") or "text_output" in str(f.parent):
            continue
        
        # Only include if inside a 'json_output' folder (optional, depends on your preference)
        # if "json_output" not in str(f.parent): continue

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

                rel_path = f.relative_to(CONTENT_DIR)
                
                # Group by top-level or mid-level folder?
                # Let's group by the "Grade/Subject/Title" string
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
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload a PDF, identify metadata, and process it into the correct folder"""
    # Ensure the directory exists right before saving
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    file_path = UPLOAD_DIR / file.filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        from extract_pipeline import identify_book_metadata, process_specific_pdf, load_schema
        
        # 1. Identify Metadata
        metadata = identify_book_metadata(file_path)
        
        # 2. Process with Metadata
        schema = load_schema()
        if not schema:
            return JSONResponse(status_code=500, content={"error": "Schema not found"})
            
        json_output = process_specific_pdf(file_path, schema, custom_output_base=CONTENT_DIR, metadata=metadata)
        
        if json_output:
            # Create a display string for the folder
            grade = metadata.get('grade', 'Unknown')
            subject = metadata.get('subject', 'General')
            folder_display = f"Grade {grade} > {subject}"
            
            return {
                "status": "success", 
                "message": f"Processed into {folder_display}", 
                "json_file": str(json_output.relative_to(CONTENT_DIR)).replace("\\", "/"),
                "metadata": metadata
            }
        else:
            return JSONResponse(status_code=500, content={"error": "Processing failed"})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# Helper to resolve path
def get_json_path(filename: str) -> Path:
    # filename includes folder relative to content dir (e.g. class7/json_output/abc.json)
    return CONTENT_DIR / filename

@app.post("/generate/plan")
async def generate_plan(request: GenerateRequest):
    """Generate Teaching Plan PDF"""
    json_path = get_json_path(request.filename)
    if not json_path.exists():
        # Fallback for legacy calls (flat filename)
        # Search recursively? No, let's enforce path.
        raise HTTPException(status_code=404, detail=f"File not found at {json_path}")
        
    output_filename = f"Plan_{json_path.stem}_{request.topic_index}.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_filename
    
    try:
        final_path = run_teaching_plan_generator(str(json_path), str(output_path), request.topic_index)
        if final_path:
            # Determine correct filename based on return path (pdf or html)
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
async def generate_quiz(request: GenerateRequest):
    """Generate Quiz PDF"""
    json_path = get_json_path(request.filename)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    output_filename = f"Quiz_{json_path.stem}_{request.topic_index}.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_filename
    
    try:
        result = run_quiz_generator(str(json_path), str(output_path), request.topic_index)
        
        if not result:
            raise HTTPException(status_code=500, detail="Generation failed. The AI might be rate-limited or failed to output correct format.")
            
        return {
            "status": "success", 
            "file_url": f"/download/{output_filename}", 
            "filename": output_filename,
            "data": result['data'] 
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/flashcards")
async def generate_flashcards(request: GenerateRequest):
    """Generate Flashcards JSON"""
    json_path = get_json_path(request.filename)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    output_filename = f"Flashcards_{json_path.stem}_{request.topic_index}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_filename
    
    try:
        final_path = run_flashcard_generator(str(json_path), str(output_path), request.topic_index)
        
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
async def generate_practice(request: GenerateRequest):
    """Generate Practice Questions PDF"""
    json_path = get_json_path(request.filename)
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            data = [data]
            
        from practice_questions import run_practice_generator
        
        output_filename = f"Practice_{json_path.stem}_{request.topic_index}.pdf"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / output_filename
        
        final_path = run_practice_generator(str(json_path), str(output_path), request.topic_index)
        
        if final_path:
            return {"status": "success", "file_url": f"/download/{output_filename}", "filename": output_filename}
        else:
            raise HTTPException(status_code=500, detail="PDF Creation failed")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/resources")
async def generate_resources(request: GenerateRequest):
    """Fetch YouTube Resources"""
    json_path = get_json_path(request.filename)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, dict):
            data = [data]
            
        topic = data[request.topic_index]
        topic_name = topic.get('topic_name', 'Mathematics')
        
        # Import dynamically to avoid top-level issues if env missing
        from get_youtube_links import search_youtube
        
        query = f"{topic_name} mathematics explanation for students"
        videos = search_youtube(query, max_results=6)
        
        return {"status": "success", "data": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """RAG Chatbot Endpoint"""
    if not chatbot_instance:
        return {"answer": "Chatbot is offline (Check API Keys or Init).", "chapter": "System", "relevance": 0}
    
    response = chatbot_instance.get_response(request.message)
    if "error" in response:
        # FIX: Return error as a chat message so frontend can display it
        # raise HTTPException(status_code=500, detail=response["error"])
        return {
            "answer": f" Chatbot Error: {response['error']}",
            "chapter": "System Error",
            "relevance": 0,
            "sources": []
        }
        
    return response

@app.post("/generate/video")
async def generate_video(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate Shortform Video (Background Task) with Unique Filename"""
    json_path = get_json_path(request.filename)
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {json_path}")
        
    # UNIQUE FILENAME LOGIC
    import uuid
    import time
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:6]
    output_filename = f"Video_{json_path.stem}_{request.topic_index}_{timestamp}_{unique_id}.mp4"
    output_path = OUTPUT_DIR / output_filename
    
    # Define the background task wrapper
    def _run_gen():
        try:
            # PASS unique filename to generator
            run_video_generator(str(json_path), str(OUTPUT_DIR), request.topic_index, custom_filename=output_filename)
        except Exception as e:
            print(f"Background Video Gen Failed: {e}")

    background_tasks.add_task(_run_gen)
    
    return {
        "status": "processing", 
        "message": "Video generation started in background", 
        "filename": output_filename, # Frontend polls this UNIQUE key
        "check_url": f"/download/{output_filename}"
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    return HTTPException(status_code=404, detail="File not found")

# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@app.post("/quiz/submit")
async def submit_quiz(result: QuizResult):
    """Save quiz result to history"""
    try:
        saved_record = save_quiz_result(result)
        return {"status": "success", "record": saved_record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/analytics")
async def get_dashboard_data():
    """Get processed data for dashboard"""
    try:
        data = get_analytics_dash_data()
        
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

@app.post("/generate/youtube")
async def generate_youtube_links(request: YouTubeRequest):
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
                json_path = get_json_path(request.filename)
                
                # If path exists, read it
                if json_path.exists():
                    import json
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # Handle list vs dict structure
                    topics = data if isinstance(data, list) else data.get('topics', [])
                    
                    if topics and 0 <= request.topic_index < len(topics):
                        topic_name = topics[request.topic_index]['topic_name']
                        query = f"Class 7 Math {topic_name} explanation"
            except Exception as e:
                print(f"Warning: Failed to infer topic from filename {request.filename}: {e}")
                # Fallthrough to error if query still None
            
        if not query:
            return {"error": "Could not determine search query"}
            
        # Pass the API key explicitly as search_youtube expects it
        from get_youtube_links import YOUTUBE_API_KEY
        videos = search_youtube(query, YOUTUBE_API_KEY)
        return {"query": query, "videos": videos}
        
    except Exception as e:
        print(f"YouTube Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("Starting Backend Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
