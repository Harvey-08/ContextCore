import json
import os
import subprocess
import sys
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Path patching for standalone run
BASE_DIR = Path(__file__).parent.parent.absolute()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "video_engine"))

from cache.redis_client import redis_client
from tts_generator import TTSGenerator
from video_audio_merger import merge_video_audio

load_dotenv()

# LLM GENERATION

def generate_spec_with_llm(json_data, topic_index=0):
    """Generate visual spec for Manim using Gemini"""
    print("Designing animation storyboard...")
    
    topic = json_data[topic_index]
    topic_name = topic['topic_name']
    objectives = "\n".join([f"- {obj}" for obj in topic['learning_objectives']])
    content = "\n".join([b['text'] for b in topic['content_blocks']])[:2000]
    
    prompt = f"""
    Create a Manim animation specification for the topic: "{topic_name}".
    
    CONTEXT:
    {content}
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "title": "Short Title",
        "subtitle": "Short Subtitle",
        "sections": [
            {{
                "type": "definition",
                "term": "Key Term",
                "text": "Simple definition (max 10 words)"
            }},
            {{
                "type": "bullet_list",
                "heading": "Key Properties",
                "items": ["Point 1", "Point 2", "Point 3"]
            }},
            {{
                "type": "analogy",
                "concept": "Abstract Concept",
                "analogy": "Real world object"
            }},
            {{
                "type": "process",
                "steps": ["Step 1", "Step 2", "Step 3"]
            }},
            {{
                "type": "statement",
                "text": "Concluding thought"
            }}
        ]
    }}
    
    Make it visual, simple, and educational. Use 3-5 sections max.
    """
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not found in .env file")
        
    client = Groq(api_key=api_key)
    
    full_prompt = f"{prompt}\n\nSTRICTLY return only a JSON object matching the requested format."
    
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a specialized AI that outputs ONLY valid JSON."
            },
            {
                "role": "user",
                "content": full_prompt
            }
        ],
        model="llama-3.1-8b-instant",
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    
    return response.choices[0].message.content


def generate_narration_audio(user_name="default_user"):
    """Generate TTS narration from lesson spec - THIS HAPPENS FIRST"""
    print("\n" + "="*60)
    print(" STEP 1: GENERATING NARRATION AUDIO")
    print("="*60)
    print("  This creates audio segments with precise timing data")
    print("  The video will sync to these audio timings!")
    
    try:
        # CENTRALIZED DIRECTORIES DYNAMICALLY NESTED IN USER FOLDER
        video_assets_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "video_assets"
        outputs_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "outputs"
        audio_segments_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "audio_segments"
        
        os.makedirs(video_assets_dir, exist_ok=True)
        os.makedirs(outputs_dir, exist_ok=True)
        os.makedirs(audio_segments_dir, exist_ok=True)
        
        spec_path = video_assets_dir / "lesson_spec.json"
        merged_output_path = video_assets_dir / "narration_full.mp3"
        
        tts_gen = TTSGenerator(spec_path=str(spec_path), output_dir=str(audio_segments_dir))

        audio_path, duration = tts_gen.generate_full_narration(use_edge_tts=True, merged_output_path=str(merged_output_path))
        
        # Sync files to video_assets
        import shutil
        src_audio = Path(audio_path)
        src_timing = src_audio.with_name("narration_full_timing.json")
        
        dest_audio = video_assets_dir / "narration_full.mp3"
        dest_timing = video_assets_dir / "narration_full_timing.json"
        
        if str(src_audio) != str(dest_audio):
            shutil.copy(str(src_audio), str(dest_audio))
        
        if src_timing.exists() and str(src_timing) != str(dest_timing):
            shutil.copy(str(src_timing), str(dest_timing))
            print(f"   [OK] Audio and timing stored in video_assets.")
        
        print(f"\nNarration audio generated: {audio_path}")
        print(f"   Duration: {duration:.2f} seconds")
        return audio_path, duration
    except Exception as e:
        print(f"\n TTS generation failed: {e}")
        print("   Falling back to gTTS...")
        try:
            video_assets_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "video_assets"
            audio_segments_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "audio_segments"
            spec_path = video_assets_dir / "lesson_spec.json"
            merged_output_path = video_assets_dir / "narration_full.mp3"
            
            tts_gen = TTSGenerator(spec_path=str(spec_path), output_dir=str(audio_segments_dir))
            audio_path, duration = tts_gen.generate_full_narration(use_edge_tts=False, merged_output_path=str(merged_output_path))
            print(f"    Narration audio generated (gTTS): {audio_path}")
            return audio_path, duration
        except Exception as e2:
            print(f"    All TTS methods failed: {e2}")
            return None, None

def run_manim_synchronized(user_name="default_user"):
    """Run Manim with synchronized timing in YouTube Shorts format"""
    print("\n" + "="*60)
    print("STEP 2: RENDERING SYNCHRONIZED ANIMATION")
    print("="*60)
    print("  Resolution: 1920x1080 (16:9 Landscape)")
    print("  Syncing: Animation timing matches audio segments")
    print("(This might take a minute)")
    
    media_dir = os.path.join("generated_contents", user_name, "media")
    os.makedirs(media_dir, exist_ok=True)
    
    # Landscape dimensions with synchronized engine
    cmd = [
        sys.executable, "-m", "manim",
        "--resolution", "1920,1080",  # Landscape mode
        "--fps", "30",  # Smooth 30fps
        "--media_dir", media_dir, # Scoped media dir
        os.path.join("backend", "video_engine", "manim_engine_synchronized.py"),  # Use synchronized version
        "SynchronizedLesson"
    ]
    
    try:
        # Pass user_name as an env variable so the subprocess scene knows where to read timed spec from
        env = os.environ.copy()
        env["USER_NAME"] = user_name
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        print("\n Synchronized Animation Rendered!")
        video_path = os.path.join("generated_contents", user_name, "media", "videos", "manim_engine_synchronized", "1080p30", "SynchronizedLesson.mp4")
        print(f"Video saved to: {video_path}")
        print("  Format: Landscape 16:9 ready!")
        print("  Timing: Perfectly synced with audio!")
        return video_path
    except subprocess.CalledProcessError as e:
        print(f"Manim Failed: {e}")
        print("--- STDERR ---")
        print(e.stderr)
        if "ffmpeg" in e.stderr.lower():
            if "dll load failed" in e.stderr.lower():
                print("\nCRITICAL: A required DLL failed to load (likely PyAV).")
                print("This often happens on Windows due to 'Smart App Control'.")
                print("Try: pip install av==16.1.0")
            else:
                print("\nCRITICAL: FFmpeg is missing!")
                print("To fix: Install FFmpeg from https://ffmpeg.org/download.html and add it to your PATH.")
        return None
    except FileNotFoundError:
        print("Command not found.")
        return None

def merge_video_and_audio(video_path, audio_path, output_path="final_video_with_narration.mp4"):
    """Merge synchronized video with narration audio"""
    print("\n" + "="*60)
    print(" STEP 3: MERGING VIDEO AND AUDIO")
    print("="*60)
    print(" Combining synchronized video with narration track")
    
    success = merge_video_audio(
        video_path=video_path,
        audio_path=audio_path,
        output_path=output_path,
        adjust_speed=False  # No speed adjustment needed - already synced!
    )
    
    if success:
        print(f"\nFINAL SYNCHRONIZED VIDEO READY: {output_path}")
        print("  Format: YouTube Shorts (1080x1920)")
        print("  Audio-Visual Sync: Perfect!")
        return output_path
    else:
        print("\nMerge failed")
        return None

def run_video_generator(json_path, output_dir, topic_index=0, custom_filename=None):
    print("="*60)
    print("  AI EDUCATIONAL ANIMATOR WITH SYNCHRONIZED NARRATION")
    print("="*60)
    
    # Update Redis status to PROCESSING if custom_filename (job_id) is provided
    status_key = None
    if custom_filename:
        status_key = f"video_job:{custom_filename}"
        redis_client.set_status(status_key, "PROCESSING", ex_seconds=86400)
        
    # 1. Resolve user_name from json_path to create user-scoped folders
    path_parts = Path(json_path).resolve().parts
    user_name = "default_user"
    for i, part in enumerate(path_parts):
        if part == "generated_contents" and i + 1 < len(path_parts):
            user_name = path_parts[i+1]
            break
            
    print(f"Dynamic User Context Detected: {user_name}")
    
    # Centralized directories dynamically nested in user folder
    user_video_assets_dir = Path(__file__).parent.parent.parent / "generated_contents" / user_name / "video_assets"
    os.makedirs(user_video_assets_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 1. Load Data
        print("    Loading curriculum data...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            data = [data]
            
        print(f"[OK] Loaded: {json_path}")
            
        # 2. Generate Spec
        print("\n" + "="*60)
        print("  GENERATING ANIMATION SPECIFICATION")
        print("="*60)
        spec_json = generate_spec_with_llm(data, topic_index)
        
        spec_file_path = user_video_assets_dir / "lesson_spec.json"
        with open(spec_file_path, "w", encoding="utf-8") as f:
            f.write(spec_json)
        print(f"  Saved storyboard to {spec_file_path}")
        
        # 3. Generate Narration Audio (Scoped by user_name)
        audio_path, audio_duration = generate_narration_audio(user_name)
        
        if not audio_path:
            raise Exception("Cannot proceed without audio")
        
        # 4. Render Synchronized Video (Scoped by user_name)
        video_path = run_manim_synchronized(user_name)
        
        if not video_path:
            raise Exception("Video rendering failed")
        
        # 5. Merge
        if custom_filename:
            final_video_name = custom_filename
        else:
            final_video_name = f"Video_{os.path.basename(json_path).replace('.json','')}_{topic_index}.mp4"
            
        final_video_dest = os.path.join(output_dir, final_video_name)
        
        # Safe temp merge path inside the user's video assets directory
        temp_merged_path = str(user_video_assets_dir / f"temp_merge_{final_video_name}")
        merged_path = merge_video_and_audio(video_path, audio_path, output_path=temp_merged_path)
        
        if merged_path and os.path.exists(merged_path):
            import shutil
            shutil.move(merged_path, final_video_dest)
            print(f" Moved final video to: {final_video_dest}")
            if status_key:
                redis_client.set_status(status_key, "COMPLETED", ex_seconds=86400)
            return final_video_dest
        else:
            raise Exception("Merge returned no path")
            
    except Exception as e:
        print(f"Video Generation Failed: {e}")
        if status_key:
            redis_client.set_status(status_key, "FAILED", ex_seconds=86400)
        return None

if __name__ == "__main__":
    # CLI usage: python generate_animations_synchronized.py <path_to_json> [output_dir]
    if len(sys.argv) < 2:
        print("Usage: python generate_animations_synchronized.py <path_to_json> [output_dir]")
        print("Example: python generate_animations_synchronized.py generated_contents/user1/content/Grade_7/Math/json_output/chapter1.json output/")
        sys.exit(1)

    json_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "generated_contents"

    if os.path.exists(json_path):
        run_video_generator(json_path, out_dir)
    else:
        print(f"File not found: {json_path}")