import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Path patching for standalone run
BASE_DIR = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend" / "core" / "schemas"))

load_dotenv()

# Configuration
# Removed global hardcoded paths
# JSON_PATH = "class7/json_output/gegp105.json"
# TOPIC_INDEX = 0


def generate_cards(json_data, topic_index=0):
    """Generate high-quality flashcards using Groq (Llama 3) with retries"""
    print(" Synthesizing flashcards with Groq...")
    
    topic = json_data[topic_index]
    topic_name = topic['topic_name']
    content_text = "\n".join([b['text'] for b in topic['content_blocks']])
    
    prompt = f"""
    Create a set of educational flashcards for the topic: {json.dumps(topic_name)}.
    
    SOURCE MATERIAL:
    {content_text[:4000]}
    
    REQUIREMENTS:
    1. Create 10-15 cards based on the depth of the material.
    2. Include a mix of:
       - Definitions (Q: What is X? A: ...)
       - Concepts (Q: Why does Y happen? A: ...)
       - Examples (Q: Solve this example... A: Solution)
    3. Keep answers concise (under 2 sentences).
    
    OUTPUT JSON FORMAT ONLY:
    {{
        "topic": {json.dumps(topic_name)},
        "cards": [
            {{"front": "Question or Term", "back": "Answer or Definition", "type": "definition"}},
            {{"front": "Problem...", "back": "Solution", "type": "problem"}}
        ]
    }}
    """
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found in .env file")
        
    from groq import Groq
    client = Groq(api_key=api_key)
    
    for attempt in range(3):
        try:
            print(f" Attempt {attempt+1}/3 with Groq...")
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert curriculum developer. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            clean_text = response.choices[0].message.content.strip()
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            print(f" Attempt {attempt+1} failed: JSON Decode Error ({str(e)}). Retrying...")
            if attempt == 2:
                raise RuntimeError(f"Flashcard Generation failed: {str(e)}")
        except Exception as e:
            print(f" Attempt {attempt+1} failed: {str(e)}. Retrying...")
            if attempt == 2:
                raise e

def run_flashcard_generator(json_path, output_path=None, topic_index=0):
    print("="*60)
    print(" FLASHCARD GENERATOR")
    print("="*60)
    
    # 1. Load Data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        data = [data]
        
    # 2. Generate with Active Prevention Loop
    from backend.verifier import ContentVerifier
    verifier = ContentVerifier()
    source_context = "\n".join([b['text'] for b in data[topic_index]['content_blocks']])
    
    max_retries = 3
    result = None
    
    for attempt in range(max_retries):
        print(f"\n--- Flashcard Generation Attempt {attempt + 1}/{max_retries} ---")
        result = generate_cards(data, topic_index)
        
        # 3. VERIFY (The Bias/Truth Layer)
        verification_result = verifier.verify(source_context, result, "Flashcards")
        
        if verification_result.get('score', 0) >= 85 and not verification_result.get('hallucination_found') and not verification_result.get('bias_found'):
            print("[SUCCESS] Flashcards passed strict verification!")
            break
        else:
            print("[FAILED] Verification failed. Retrying flashcard generation to prevent bad content...")
            if attempt == max_retries - 1:
                print("[WARNING] Max retries reached. Proceeding with best attempt.")
                
    result['verification_status'] = verification_result
    
    cards = result.get('cards', [])
    print(f" Generated {len(cards)} cards.")
    
    # 4. Save
    if not output_path:
        input_stem = os.path.splitext(os.path.basename(json_path))[0]
        output_path = f"{input_stem}_flashcards.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        
    print(f"\n Saved to {output_path}")
    return output_path

if __name__ == "__main__":
    # Test with default if exists
    default_json = "backend/core/content/class7/json_output/gegp105.json"
    if os.path.exists(default_json):
        run_flashcard_generator(default_json)
    else:
        print("Default file not found.")
