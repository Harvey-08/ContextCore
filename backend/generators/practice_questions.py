
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.units import inch

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
# Allow flexibility for class6 or class7 based on existing folders, default to class7 as per recent changes
BASE_DIR = SCRIPT_DIR / "class7" 
INPUT_DIR = BASE_DIR / "json_output"
OUTPUT_DIR = BASE_DIR / "practice_questions"

# Model configuration
MODEL = "gemini-2.5-flash"

# ============================================================================
# LLM GENERATION
# ============================================================================

def generate_questions_from_json(json_content, filename):
    """
    Generate practice questions based on the curriculum JSON content.
    """
    
    # Extract relevant content to keep context minimal/relevant
    # Flatten structure if it's a list of topics
    topics_context = []
    
    data_list = json_content if isinstance(json_content, list) else [json_content]
    
    for item in data_list:
        topic_info = {
            "topic": item.get("topic_name", "General Match"),
            "objectives": item.get("learning_objectives", []),
            "concepts": item.get("allowed_concepts", []),
        }
        # Add a snippet of content blocks if available? 
        # Might be too long, but let's take definition blocks to ensure accuracy
        blocks = item.get("content_blocks", [])
        definitions = [b["text"] for b in blocks if b.get("type") == "definition"]
        if definitions:
            topic_info["key_definitions"] = definitions[:3] # Limit to top 3
            
        topics_context.append(topic_info)

    prompt = f"""
    You are a mathematics teacher creating a practice worksheet for Grade 7 students.
    Based on the following curriculum topics and concepts, generate 15 high-quality practice questions.
    
    Source Material:
    {json.dumps(topics_context, indent=2)}
    
    REQUIREMENTS:
    1. Generate exactly 15 questions total.
    2. Section A: 5 Multiple Choice Questions (MCQs) with 4 options (A, B, C, D).
    3. Section B: 5 Short Answer Questions (conceptual or simple calculation).
    4. Section C: 5 Word Problems / Application Questions (requires higher order thinking).
    5. Include an Answer Key at the end.
    
    OUTPUT FORMAT:
    Return ONLY a valid JSON object with this structure:
    {{
      "worksheet_title": "Practice Worksheet: [Topic Name]",
      "sections": [
        {{
          "section_name": "Section A: Multiple Choice",
          "questions": [
            {{
              "id": 1,
              "question": "Question text here...",
              "options": ["Option A", "Option B", "Option C", "Option D"],
              "correct_answer": "Option A - [Explanation]"
            }}
          ]
        }},
        {{
            "section_name": "Section B: Short Answer",
            "questions": [ ... (no options here) ]
        }},
         {{
            "section_name": "Section C: Application Problems",
            "questions": [ ... ]
        }}
      ],
      "answer_key": [
        {{"id": 1, "answer": "..."}},
        ...
      ]
    }}
    """
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found in .env file")
        
    from groq import Groq
    client = Groq(api_key=api_key)
    
    for attempt in range(3):
        print(f" Attempt {attempt+1}/3 with Groq...")
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful education assistant. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            clean_text = response.choices[0].message.content.strip()
            return json.loads(clean_text)
            
        except json.JSONDecodeError as e:
            print(f"   JSON Decode Error: {e}. Retrying...")
            if attempt == 2:
                return None
        except Exception as e:
            print(f"   Error: {e}. Retrying...")
            if attempt == 2:
                return None
    
    return None

# ============================================================================
# PDF GENERATION
# ============================================================================

def create_pdf(data, output_path):
    """
    Create a formatted PDF from the generated question data.
    """
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = styles['Title']
    story.append(Paragraph(data.get("worksheet_title", "Practice Worksheet"), title_style))
    story.append(Spacer(1, 0.5 * inch))

    # General Styles
    normal_style = styles['Normal']
    heading_style = styles['Heading2']
    question_style = ParagraphStyle(
        'Question',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=10,
        leading=14
    )
    option_style = ParagraphStyle(
        'Option',
        parent=styles['Normal'],
        leftIndent=20,
        fontSize=11,
        spaceAfter=5
    )


    # Sections
    for section in data.get("sections", []):
        # Section Header
        story.append(Paragraph(section.get("section_name", "Section"), heading_style))
        story.append(Spacer(1, 0.1 * inch))
        
        for q in section.get("questions", []):
            # Question Text
            q_text = f"<b>{q.get('id', '-')}.</b> {q.get('question', '')}"
            story.append(Paragraph(q_text, question_style))
            
            # Options (if MCQ)
            options = q.get("options", [])
            if options:
                # Label options A, B, C, D if they aren't already
                labels = ['A)', 'B)', 'C)', 'D)']
                for i, opt in enumerate(options):
                    label = labels[i] if i < len(labels) else "-"
                    # Check if option already has a label
                    if opt.strip().startswith(('A)', 'A.', 'a)', '(a)')):
                         story.append(Paragraph(f"{opt}", option_style))
                    else:
                        story.append(Paragraph(f"{label} {opt}", option_style))
            
            story.append(Spacer(1, 0.15 * inch))
        
        story.append(Spacer(1, 0.2 * inch))

    # Page Break for Answer Key
    story.append(PageBreak())
    story.append(Paragraph("Answer Key", title_style))
    story.append(Spacer(1, 0.3 * inch))
    
    # Process Answer Key
    # It might be in the 'answer_key' list or embedded in questions
    
    # If we have a separate answer key list
    if "answer_key" in data and data["answer_key"]:
        for ans in data["answer_key"]:
            ans_text = f"<b>{ans.get('id', '-')}:</b> {ans.get('answer', '')}"
            story.append(Paragraph(ans_text, normal_style))
            story.append(Spacer(1, 0.1 * inch))
    else:
        # Fallback: try to find answers in the question objects if not in separate list
        for section in data.get("sections", []):
             story.append(Paragraph(f"<b>{section.get('section_name')}</b>", heading_style))
             for q in section.get("questions", []):
                 if "correct_answer" in q:
                     ans_text = f"<b>{q.get('id')}:</b> {q.get('correct_answer')}"
                     story.append(Paragraph(ans_text, normal_style))
                     story.append(Spacer(1, 0.05 * inch))

    try:
        doc.build(story)
        return True
    except Exception as e:
        print(f" Error building PDF: {e}")
        return False

# ============================================================================
# MAIN
# ============================================================================

def run_practice_generator(json_path, output_path, topic_index=0):
    print("="*60)
    print(" Mathematical Practice Question Generator")
    print("="*60)
    
    # 1. Load Data
    print(f" Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if isinstance(data, dict):
        data = [data]
        
    target_data = data[topic_index:topic_index+1]
    
    # 2. Generate Content with Active Prevention Loop
    print("   Generating questions with AI...")
    
    from backend.verifier import ContentVerifier
    verifier = ContentVerifier()
    source_context = str(target_data)
    
    max_retries = 3
    question_data = None
    
    for attempt in range(max_retries):
        print(f"\n--- Practice Questions Generation Attempt {attempt + 1}/{max_retries} ---")
        question_data = generate_questions_from_json(target_data, os.path.basename(json_path))
        
        if not question_data:
            print("   [FAILED] AI generation failed to return data.")
            continue
            
        # VERIFY (The Bias/Truth Layer)
        verification_result = verifier.verify(source_context, question_data, "Practice Questions")
        
        if verification_result.get('score', 0) >= 85 and not verification_result.get('hallucination_found') and not verification_result.get('bias_found'):
            print("   [SUCCESS] Practice questions passed strict verification!")
            break
        else:
            print("   [FAILED] Verification failed. Retrying to prevent bad content...")
            if attempt == max_retries - 1:
                print("   [WARNING] Max retries reached. Proceeding with best attempt.")
                
    if not question_data:
        print("   [FATAL] AI generation completely failed after retries.")
        return False
        
    # 3. Save PDF
    print(f"   Rendering PDF: {output_path}")
    success = create_pdf(question_data, Path(output_path))
    
    if success:
        print(f"   Complete! Saved to: {output_path}")
        return output_path
    else:
        print("   PDF Creation failed.")
        return False


def main():
    print("="*60)
    print(" Mathematical Practice Question Generator")
    print("="*60)

    if not INPUT_DIR.exists():
        print(f" Input directory not found: {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    json_files = list(INPUT_DIR.glob("*.json"))
    if not json_files:
        print(f" No JSON files found in {INPUT_DIR}")
        return

    print(f"found {len(json_files)} curriculum files to process.\n")

    for idx, json_file in enumerate(json_files, 1):
        print(f"Processing {idx}/{len(json_files)}: {json_file.name}...")
        
        # 1. Load JSON
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            print(f"   Error reading file: {e}")
            continue

        # 2. Generate Content with Active Prevention Loop
        print("   Generating questions with AI...")
        
        from backend.verifier import ContentVerifier
        verifier = ContentVerifier()
        source_context = str(content)
        
        max_retries = 3
        question_data = None
        
        for attempt in range(max_retries):
            print(f"\n--- Practice Questions Generation Attempt {attempt + 1}/{max_retries} ---")
            question_data = generate_questions_from_json(content, json_file.name)
            
            if not question_data:
                print("   [FAILED] AI generation failed to return data.")
                continue
                
            # VERIFY (The Bias/Truth Layer)
            verification_result = verifier.verify(source_context, question_data, "Practice Questions")
            
            if verification_result.get('score', 0) >= 85 and not verification_result.get('hallucination_found') and not verification_result.get('bias_found'):
                print("   [SUCCESS] Practice questions passed strict verification!")
                break
            else:
                print("   [FAILED] Verification failed. Retrying to prevent bad content...")
                if attempt == max_retries - 1:
                    print("   [WARNING] Max retries reached. Proceeding with best attempt.")
                    
        if not question_data:
            print("   [FATAL] AI generation completely failed after retries.")
            continue
        # 3. Save PDF
        output_filename = f"Practice_Questions_{json_file.stem}.pdf"
        output_path = OUTPUT_DIR / output_filename
        
        print(f"   Rendering PDF: {output_filename}")
        success = create_pdf(question_data, output_path)
        
        if success:
            print(f"   Complete! Saved to: {output_path}")
        else:
            print("   PDF Creation failed.")

    print("\n" + "="*60)
    print(" All tasks completed!")

if __name__ == "__main__":
    main()
