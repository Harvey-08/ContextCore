import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Path patching for standalone run
BASE_DIR = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend" / "core"))
from backend.core.schemas import Flashcards
from backend.core.adaptive_prompts import get_generator_instructions

load_dotenv()

# Configuration
# Paths are provided dynamically via function arguments or CLI


def generate_cards(json_data, topic_index=0, difficulty="Beginner"):
    """Generate high-quality flashcards using Groq (Llama 3) with retries"""
    print(f" Synthesizing flashcards with Groq for level: {difficulty}...")
    
    topic = json_data[topic_index]
    topic_name = topic['topic_name']
    content_text = "\n".join([b['text'] for b in topic['content_blocks']])
    
    level_guidance = get_generator_instructions(difficulty, "flashcards")
    
    prompt = f"""
    Create a set of educational flashcards for the topic: {json.dumps(topic_name)}.
    
    TARGET STUDENT LEVEL: {difficulty}
    
    SOURCE MATERIAL:
    {content_text[:4000]}
    
    PEDAGOGICAL INSTRUCTIONS FOR THIS TIER:
    {level_guidance}
    
    REQUIREMENTS:
    1. Create 10-15 cards based on the depth of the material.
    2. Include a mix of card types matched strictly to the target student level instructions.
    3. Keep answers highly concise (under 2 sentences).
    
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
        
    import instructor
    from groq import Groq
    client = instructor.from_groq(Groq(api_key=api_key))
    
    print("Generating flashcards with Groq and Instructor...")
    try:
        cards = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=Flashcards,
            messages=[
                {"role": "system", "content": "You are an expert curriculum developer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_retries=2
        )
        return cards.model_dump()
    except Exception as e:
        print(f"Instructor Generation/Validation Failed: {e}")
        raise RuntimeError(f"Failed to generate flashcards: {e}")

def run_flashcard_generator(json_path, output_path=None, topic_index=0, difficulty="Beginner"):
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
        result = generate_cards(data, topic_index, difficulty)
        
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
    # CLI usage: python generate_flashcards.py <path_to_json> [output_json_name]
    if len(sys.argv) < 2:
        print("Usage: python generate_flashcards.py <path_to_json> [output_json_name]")
        print("Example: python generate_flashcards.py generated_contents/user1/content/Grade_7/Math/json_output/chapter1.json flashcards.json")
        sys.exit(1)

    json_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None

    if os.path.exists(json_path):
        run_flashcard_generator(json_path, output_name)
    else:
        print(f"File not found: {json_path}")
