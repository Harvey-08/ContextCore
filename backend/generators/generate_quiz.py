import sys
from pathlib import Path
import json
import os
import requests
from dotenv import load_dotenv

# Path patching for standalone run
BASE_DIR = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend" / "core"))

from backend.core.quiz_schema import Quiz
from pydantic import ValidationError
from backend.core.adaptive_prompts import get_generator_instructions

load_dotenv()

# Configuration
# JSON_PATH and TOPIC_INDEX removed for API usage
# API keys will be loaded from environment within functions

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{class_level}} Quiz</title>
    <style>
        body { font-family: 'Helvetica', 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 40px; }
        .header { text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px; }
        h1 { color: #2c3e50; margin: 0; font-size: 28px; }
        .meta { margin-top: 10px; color: #7f8c8d; font-size: 14px; }
        .question { margin-bottom: 25px; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .question-meta { font-size: 12px; color: #999; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
        .q-text { font-size: 16px; font-weight: bold; margin-bottom: 15px; }
        .options { list-style-type: none; padding: 0; }
        .options li { margin-bottom: 8px; padding: 8px 12px; background: #f8f9fa; border-radius: 4px; border: 1px solid #e9ecef; }
        .answer-key { margin-top: 50px; page-break-before: always; }
        .key-item { font-size: 14px; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{topic}}</h1>
        <div class="meta">
            Class: {{class_level}} &bull; Difficulty: {{difficulty}} &bull; Time: {{duration}} mins
        </div>
    </div>

    {{questions_html}}

    <div class="answer-key">
        <div class="header">
            <h1>Answer Key</h1>
        </div>
        {{answer_key_html}}
    </div>
</body>
</html>
"""

def generate_quiz_json(topic_data, difficulty="Beginner", class_level="7", subject="General"):
    """Generate and validate quiz JSON"""
    topic_name = topic_data['topic_name']
    objectives = "\n".join([f"- {obj}" for obj in topic_data['learning_objectives']])
    # Use only first 2000 chars of content to avoid context limit
    content_context = "\n".join([b['text'] for b in topic_data['content_blocks']])[:2000]

    top_schema = json.dumps(Quiz.model_json_schema(), indent=2)
    
    # Get level-aware guidance
    profile = topic_data.get("pedagogical_profile")
    level_guidance = get_generator_instructions(difficulty, "quiz", profile=profile)

    system_instruction = "You are a curriculum expert that generates valid JSON quizzes strictly following a provided schema."

    prompt = f"""
    Generate a valid JSON object for a quiz aligned with the curriculum.
    Do NOT return the schema itself. Return an INSTANCE of the schema.

    TOPIC: {topic_name}
    CLASS LEVEL: Class {class_level}
    SUBJECT: {subject}
    DIFFICULTY: {difficulty}

    LEARNING OBJECTIVES:
    {objectives}

    CONTEXT (from textbook):
    {content_context}

    PEDAGOGICAL DIFFICULTY INSTRUCTIONS:
    {level_guidance}

    Required Fields:
    - topic: "{topic_name}"
    - class_level: "Class {class_level}"
    - difficulty: "{difficulty}"
    - duration_minutes: (integer 10-20)
    - questions: List of at least 5 MCQs.
      * Each MCQ must have exactly 4 options (1 correct answer and 3 plausible distractors).
      * Do not include duplicate options or empty options.
      * Each question must include hint_1 and hint_2 as progressive, helpful conceptual clues to guide the student.

    Return JSON strictly matching this schema:
    {top_schema}
    """

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found in .env file")
        
    import instructor
    from groq import Groq
    client = instructor.from_groq(Groq(api_key=api_key))
    
    print("Generating quiz with Groq and Instructor...")
    try:
        quiz = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=Quiz,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_retries=2
        )
        print("Validation Successful!")
        return quiz
    except Exception as e:
        print(f"Instructor Generation/Validation Failed: {e}")
        raise RuntimeError(f"Failed to generate valid quiz after retries: {e}")

def create_html(quiz: Quiz):
    """Render quiz HTML"""
    questions_html = []
    answer_key_html = []
    
    for i, q in enumerate(quiz.questions, 1):
        # Render Question
        q_html = f"""
        <div class="question">
            <div class="question-meta">
                Q{i} &bull; {q.blooms_level} &bull; {q.type.upper()}
            </div>
            <div class="q-text">{q.question}</div>
        """
        
        if q.type == "mcq":
            opts = "".join([f"<li>{opt}</li>" for opt in q.options])
            q_html += f'<ul class="options">{opts}</ul>'
            ans_text = q.correct
            
        q_html += "</div>"
        questions_html.append(q_html)
        
        # Render Answer Key
        answer_key_html.append(f'<div class="key-item"><b>Q{i}:</b> {ans_text}</div>')

    html = HTML_TEMPLATE.replace("{{topic}}", quiz.topic)
    html = html.replace("{{class_level}}", quiz.class_level)
    html = html.replace("{{difficulty}}", quiz.difficulty)
    html = html.replace("{{duration}}", str(quiz.duration_minutes))
    html = html.replace("{{questions_html}}", "\n".join(questions_html))
    html = html.replace("{{answer_key_html}}", "\n".join(answer_key_html))
    
    return html

def convert_to_pdf(html_content, output_path="quiz.pdf"):
    """Convert to PDF"""
    api_key = os.getenv("PDFSHIFT_API_KEY")
    
    if not api_key:
        print("PDFSHIFT_API_KEY not found. Saving as HTML.")
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Saved to {html_path}")
        return html_path

    print("Converting to PDF via PDFShift...")
    response = requests.post(
        "https://api.pdfshift.io/v3/convert/pdf",
        auth=("api", api_key),
        json={"source": html_content, "landscape": False}
    )

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Success! Saved to {output_path}")
        return output_path
    else:
        print(f"PDF Generation Failed: {response.text}")
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_path

def run_quiz_generator(json_path, output_path, topic_index=0, difficulty="Beginner"):
    print("="*60)
    print("STRICT QUIZ GENERATOR (Pydantic Validated)")
    print("="*60)
    
    # 1. Load Data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if isinstance(data, dict):
        data = [data]
    
    # Extract dynamic class level and subject from folder path structure
    grade_str = "Unknown"
    subject_str = "General"
    path_parts = Path(json_path).resolve().parts
    system_folders = {"json_output", "text_output", "content", "uploads", "outputs", "generated_contents"}
    for i, part in enumerate(path_parts):
        if part.lower().startswith("grade_"):
            grade_str = part.replace("Grade_", "").replace("grade_", "")
            # The folder immediately after Grade_X is typically the subject
            if i + 1 < len(path_parts) and path_parts[i + 1].lower() not in system_folders:
                subject_str = path_parts[i + 1]

    # 2. Generate Valid Quiz with Active Prevention Loop
    try:
        from backend.verifier import ContentVerifier
        verifier = ContentVerifier()
        source_context = "\n".join([b['text'] for b in data[topic_index]['content_blocks']])
        
        max_retries = 3
        quiz = None
        
        for attempt in range(max_retries):
            print(f"\n--- Quiz Generation Attempt {attempt + 1}/{max_retries} ---")
            quiz = generate_quiz_json(data[topic_index], difficulty, grade_str, subject_str)
            
            # VERIFY (The Bias/Truth Layer)
            verification_result = verifier.verify(source_context, quiz.model_dump(), "Quiz")
            
            if verification_result.get('score', 0) >= 85 and not verification_result.get('hallucination_found') and not verification_result.get('bias_found'):
                print("[SUCCESS] Quiz passed strict verification!")
                break
            else:
                print("[FAILED] Verification failed. Retrying quiz generation to prevent bad content...")
                if attempt == max_retries - 1:
                    print("[WARNING] Max retries reached. Proceeding with best attempt.")
        
        # Save validation JSON
        json_output_path = output_path.replace('.pdf', '.json')
        with open(json_output_path, 'w', encoding='utf-8') as f:
            f.write(quiz.model_dump_json())

        # 3. Create HTML
        html = create_html(quiz)
        
        # 4. Generate PDF
        pdf_path = convert_to_pdf(html, output_path)
        
        return {
            "pdf_path": pdf_path,
            "json_path": json_output_path,
            "data": quiz.model_dump()  # Return raw data for frontend
        }
        
    except Exception as e:
        print(f"\nFATAL: {e}")
        return None

if __name__ == "__main__":
    # CLI usage: python generate_quiz.py <path_to_json> [output_pdf_name]
    if len(sys.argv) < 2:
        print("Usage: python generate_quiz.py <path_to_json> [output_pdf_name]")
        print("Example: python generate_quiz.py generated_contents/user1/content/Grade_7/Math/json_output/chapter1.json quiz_output.pdf")
        sys.exit(1)

    json_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else "test_quiz_output.pdf"

    if os.path.exists(json_path):
        print(f"Testing Quiz Generation for: {json_path}")
        run_quiz_generator(json_path, output_name)
    else:
        print(f"File not found: {json_path}")
