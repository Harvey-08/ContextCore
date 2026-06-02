import json
import os
from pathlib import Path
from dotenv import load_dotenv
import pdfplumber
from jsonschema import validate, ValidationError

load_dotenv()
from backend.core.schemas import BookMetadata, CurriculumTopicList


# CONFIGURATION - Load from config file

# Get script directory (where this file is located)
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Centralized folder structure in generated_contents
GENERATED_DIR = ROOT_DIR.parent / "generated_contents"
# Base directory for global/fallback/manual processing
BASE_DIR = GENERATED_DIR / "content" / "general"
OUTPUT_DIR = BASE_DIR / "text_output"
TEXT_DIR = BASE_DIR / "text_output"
JSON_DIR = BASE_DIR / "json_output"
SCHEMA_FILE = SCRIPT_DIR / "curriculum_schema.json"

# Model and processing configuration
MODEL = "gemini-2.5-flash"
CHUNK_SIZE = 3000  # Characters per chunk for processing large texts

# Curriculum configuration (fully dynamic defaults)
GRADE_LEVEL = "Unknown"
SUBJECT = "General"
CURRICULUM_TYPE = "General"

# Default values for fallback
DEFAULT_LEARNING_OBJECTIVE = "Understand the curriculum concepts presented"
DEFAULT_ALLOWED_CONCEPT = "Core topic concepts"
DEFAULT_DISALLOWED_CONCEPTS = ["Advanced graduate level concepts"]

# Initialize Groq client (requires GROQ_API_KEY from .env)
api_key = os.getenv("GROQ_API_KEY")
if api_key:
    from groq import Groq
    groq_client = Groq(api_key=api_key)
    MODEL_NAME = "llama-3.1-8b-instant"
else:
    print("WARNING: GROQ_API_KEY not found in .env file")
    groq_client = None


def identify_book_metadata(pdf_path):
    """
    Identifies Grade, Subject, and Book Title from the first few pages of a PDF.
    Returns a dictionary with the metadata.
    """
    print(f"Identifying metadata for: {os.path.basename(pdf_path)}")
    text_preview = ""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            # Read first 5 pages for metadata (often found in title or preface)
            for i in range(min(5, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    text_preview += page_text + "\n"
        
        if not text_preview.strip():
            return {"grade": "Unknown", "subject": "General", "title": "Untitled", "curriculum": "Unknown"}

        prompt = f"""
        Analyze the following text from the beginning of a textbook and extract metadata:
        
        Text Preview:
        {text_preview[:4000]}
        """

        import instructor
        instructor_client = instructor.from_groq(groq_client)
        meta = instructor_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a specialized AI that extracts textbook metadata."},
                {"role": "user", "content": prompt}
            ],
            model=MODEL_NAME,
            response_model=BookMetadata,
            temperature=0.1,
            max_retries=2
        )
        metadata = meta.model_dump()
        print(f"Extracted Metadata: {metadata}")
        return metadata
    except Exception as e:
        print(f"Error identifying metadata: {e}")
        return {"grade": "Unknown", "subject": "General", "title": "Untitled", "curriculum": "Unknown"}


# SCHEMA LOADING AND PROMPT GENERATION

def load_schema():
    """Load the curriculum schema from file."""
    try:
        # Convert Path to string for open()
        schema_path = str(SCHEMA_FILE)
        
        # Check if file exists
        if not SCHEMA_FILE.exists():
            print(f"Schema file not found: {schema_path}")
            print(f"   Please ensure the file exists at the specified path.")
            return None
        
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        print(f"Loaded schema from: {SCHEMA_FILE.name}")
        print(f"   Path: {schema_path}")
        return schema
    except json.JSONDecodeError as e:
        print(f"Error parsing schema JSON: {str(e)}")
        print(f"   File: {SCHEMA_FILE}")
        return None
    except Exception as e:
        print(f"Error loading schema: {str(e)}")
        print(f"   File path: {SCHEMA_FILE}")
        print(f"   File exists: {SCHEMA_FILE.exists()}")
        return None


def generate_schema_description(schema):
    """Generate a human-readable description of the schema for the prompt."""
    if not schema or "properties" not in schema:
        return ""
    
    props = schema["properties"]
    required = schema.get("required", [])
    
    description = "Required fields and their types:\n"
    
    for field_name in required:
        if field_name in props:
            field_prop = props[field_name]
            field_type = field_prop.get("type", "unknown")
            
            if field_type == "string":
                description += f"- {field_name}: string\n"
            elif field_type == "array":
                items = field_prop.get("items", {})
                if isinstance(items, dict) and items.get("type") == "string":
                    description += f"- {field_name}: array of strings\n"
                elif isinstance(items, dict) and items.get("type") == "object":
                    # Handle nested objects like content_blocks
                    nested_props = items.get("properties", {})
                    nested_req = items.get("required", [])
                    description += f"- {field_name}: array of objects with fields: {', '.join(nested_req)}\n"
                    for nested_field in nested_req:
                        if nested_field in nested_props:
                            nested_type = nested_props[nested_field].get("type", "unknown")
                            if nested_type == "string":
                                enum = nested_props[nested_field].get("enum")
                                if enum:
                                    description += f"  - {nested_field}: string (must be one of: {', '.join(enum)})\n"
                                else:
                                    description += f"  - {nested_field}: string\n"
    
    return description


def generate_prompt_from_schema(schema, unit_name, chunk_text, chunk_index, total_chunks, metadata=None):
    """Generate the extraction prompt based on the schema and dynamically identified metadata."""
    schema_desc = generate_schema_description(schema)
    
    # Get content block type enum from schema
    content_block_type_enum = []
    if "properties" in schema and "content_blocks" in schema["properties"]:
        content_blocks_prop = schema["properties"]["content_blocks"]
        if "items" in content_blocks_prop and "properties" in content_blocks_prop["items"]:
            type_prop = content_blocks_prop["items"]["properties"].get("type", {})
            content_block_type_enum = type_prop.get("enum", ["definition", "explanation", "example"])
    
    # Use dynamically identified metadata from the uploaded PDF; fall back to neutral generics
    if metadata:
        curriculum_type = metadata.get("curriculum", CURRICULUM_TYPE) or "General"
        grade_level = metadata.get("grade", GRADE_LEVEL) or "Unknown"
        subject = metadata.get("subject", SUBJECT) or "General"
    else:
        curriculum_type = CURRICULUM_TYPE
        grade_level = GRADE_LEVEL
        subject = SUBJECT
    subject_lower = subject.lower()
    
    prompt = f"""
You are extracting structured curriculum data from a {curriculum_type} Grade {grade_level} {subject} textbook.

CRITICAL REQUIREMENTS:
1. You MUST extract all required fields according to the schema - these CANNOT be empty
2. Identify {subject_lower} topics, concepts, and learning goals from the text
3. Extract ALL {subject_lower} concepts mentioned or implied
4. Identify what concepts are appropriate for Grade {grade_level} level (allowed_concepts)
5. Identify what advanced concepts should NOT be introduced yet (disallowed_concepts)

SCHEMA REQUIREMENTS:
{schema_desc}

Extraction Rules:
- learning_objectives: Extract what students should learn/achieve. Look for phrases like "students will", "learn to", "understand", "be able to", learning goals, outcomes
- allowed_concepts: Extract ALL {subject_lower} concepts, topics, formulas, methods mentioned that are appropriate for Grade {grade_level}. Include relevant concepts for this grade level.
- disallowed_concepts: Identify advanced concepts that are beyond Grade {grade_level} level - these should NOT be taught yet
- content_blocks: Break down the text into logical blocks (definitions, explanations, examples)

For each topic found, extract according to the schema:
1. topic_id: A unique identifier (e.g., "topic_1", "topic_2")
2. topic_name: The specific topic name from the textbook
3. unit: The unit name (use: "{unit_name}")
4. learning_objectives: Array of specific learning objectives - MUST extract at least 2-3 objectives per topic
5. allowed_concepts: Array of concepts taught/mentioned - MUST include all relevant concepts (minimum 3-5 per topic)
6. disallowed_concepts: Array of advanced concepts that should NOT be introduced - include concepts beyond current level
7. content_blocks: Array of content blocks, each with:
   - block_id: Unique identifier starting from "block_1", "block_2", etc. (sequential)
   - type: One of {content_block_type_enum}
   - text: The actual content text (preserve original text, don't paraphrase)

Content block types:
- "definition": Formal definitions, theorems, formulas, mathematical statements
- "explanation": Explanatory text, step-by-step procedures, concept descriptions, methodology
- "example": Worked examples, sample problems, solved exercises, illustrations with solutions

IMPORTANT: 
- All required fields MUST be present and non-empty
- Extract actual learning goals and concepts from the text
- If a topic doesn't have explicit objectives, infer reasonable learning objectives based on the content
- The output MUST strictly conform to the schema structure

Return format (JSON array):
[
  {{
    "topic_id": "topic_1",
    "topic_name": "Specific Topic Name",
    "unit": "{unit_name}",
    "learning_objectives": ["Students will understand...", "Students will be able to..."],
    "allowed_concepts": ["concept1", "concept2", "concept3"],
    "disallowed_concepts": ["advanced_concept1"],
    "content_blocks": [
      {{"block_id": "block_1", "type": "definition", "text": "Exact definition text"}},
      {{"block_id": "block_2", "type": "explanation", "text": "Exact explanation text"}},
      {{"block_id": "block_3", "type": "example", "text": "Exact example text"}}
    ]
  }}
]

Chunk {chunk_index + 1} of {total_chunks}:

Text:
{chunk_text}
"""
    return prompt


# PDF TO TEXT FUNCTIONS (from pdf_to_text.py)

def extract_text(pdf_path, output_txt):
    """Extract text from a PDF file and save to text file."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_txt), exist_ok=True)
        
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"Extracted: {os.path.basename(pdf_path)} -> {os.path.basename(output_txt)}")
        return True
    except Exception as e:
        print(f"Error extracting {pdf_path}: {str(e)}")
        return False




# TEXT TO JSON FUNCTIONS (from ai_text_to_json.py)

def load_file(path):
    """Load text from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_text_into_chunks(text, chunk_size=CHUNK_SIZE):
    """Split text into chunks of specified size."""
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        if current_length + word_length > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def call_llm_structured(prompt, metadata=None):
    """Call LLM with instructor and return CurriculumTopicList object."""
    if metadata:
        curriculum_type = metadata.get("curriculum", CURRICULUM_TYPE) or "General"
        subject = metadata.get("subject", SUBJECT) or "General"
    else:
        curriculum_type = CURRICULUM_TYPE
        subject = SUBJECT

    system_instruction = (
        f"You are an information extraction system for {curriculum_type} {subject.lower()} curriculum. "
        "Extract topics, learning objectives, allowed concepts, disallowed concepts, and content blocks strictly matching the schema."
    )

    import instructor
    instructor_client = instructor.from_groq(groq_client)
    try:
        topic_list = instructor_client.chat.completions.create(
            model=MODEL_NAME,
            response_model=CurriculumTopicList,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_retries=2
        )
        return topic_list
    except Exception as e:
        print(f"[Instructor Ingestion Warning] Ingestion extraction failed: {e}")
        return None


def process_text_chunk(chunk_text, chunk_index, total_chunks, unit_name, schema, metadata=None):
    """Process a single text chunk and extract curriculum data."""
    prompt = generate_prompt_from_schema(schema, unit_name, chunk_text, chunk_index, total_chunks, metadata=metadata)
    
    topic_list = call_llm_structured(prompt, metadata=metadata)
    if not topic_list or not topic_list.topics:
        return []
        
    # Convert Pydantic models back to dictionaries for backward compatibility with downstream functions
    topics_dicts = []
    for topic in topic_list.topics:
        topics_dicts.append(topic.model_dump())
    return topics_dicts


def merge_topics(all_topics):
    """Merge topics from different chunks, combining content blocks."""
    topic_map = {}
    global_block_counter = 1
    
    for topic in all_topics:
        topic_name = topic.get("topic_name", "")
        topic_id = topic.get("topic_id", "")
        
        # Create a unique key for the topic
        key = topic_name.lower().strip() if topic_name else topic_id
        
        if key not in topic_map:
            # New topic
            topic_map[key] = {
                "topic_id": topic_id or f"topic_{len(topic_map) + 1}",
                "topic_name": topic_name,
                "unit": topic.get("unit", ""),
                "learning_objectives": [],
                "allowed_concepts": [],
                "disallowed_concepts": [],
                "content_blocks": []
            }
        
        # Merge learning objectives and concepts
        existing = topic_map[key]
        
        # Add learning objectives (filter out empty strings)
        new_objectives = [obj for obj in topic.get("learning_objectives", []) if obj and obj.strip()]
        existing["learning_objectives"].extend(new_objectives)
        
        # Add allowed concepts (filter out empty strings)
        new_allowed = [concept for concept in topic.get("allowed_concepts", []) if concept and concept.strip()]
        existing["allowed_concepts"].extend(new_allowed)
        
        # Add disallowed concepts (filter out empty strings)
        new_disallowed = [concept for concept in topic.get("disallowed_concepts", []) if concept and concept.strip()]
        existing["disallowed_concepts"].extend(new_disallowed)
        
        # Add content blocks with sequential block_ids
        for block in topic.get("content_blocks", []):
            # Ensure block has required fields
            if "text" in block and block["text"].strip():
                block_copy = {
                    "block_id": f"block_{global_block_counter}",
                    "type": block.get("type", "explanation"),
                    "text": block["text"].strip()
                }
                # Validate type - get valid types from schema if available
                valid_types = ["definition", "explanation", "example"]
                # Try to get from config or use defaults
                if block_copy["type"] not in valid_types:
                    block_copy["type"] = "explanation"  # Default fallback
                
                existing["content_blocks"].append(block_copy)
                global_block_counter += 1
    
    # Remove duplicates and empty values, ensure arrays are not empty
    final_topics = []
    for topic in topic_map.values():
        # Remove duplicates while preserving order
        seen_objs = set()
        unique_objectives = []
        for obj in topic["learning_objectives"]:
            obj_lower = obj.lower().strip()
            if obj_lower and obj_lower not in seen_objs:
                seen_objs.add(obj_lower)
                unique_objectives.append(obj)
        default_objective = DEFAULT_LEARNING_OBJECTIVE
        topic["learning_objectives"] = unique_objectives if unique_objectives else [default_objective]
        
        seen_concepts = set()
        unique_allowed = []
        for concept in topic["allowed_concepts"]:
            concept_lower = concept.lower().strip()
            if concept_lower and concept_lower not in seen_concepts:
                seen_concepts.add(concept_lower)
                unique_allowed.append(concept)
        default_allowed = DEFAULT_ALLOWED_CONCEPT
        topic["allowed_concepts"] = unique_allowed if unique_allowed else [default_allowed]
        
        seen_disallowed = set()
        unique_disallowed = []
        for concept in topic["disallowed_concepts"]:
            concept_lower = concept.lower().strip()
            if concept_lower and concept_lower not in seen_disallowed:
                seen_disallowed.add(concept_lower)
                unique_disallowed.append(concept)
        default_disallowed = DEFAULT_DISALLOWED_CONCEPTS
        topic["disallowed_concepts"] = unique_disallowed if unique_disallowed else default_disallowed
        
        # Ensure content_blocks have sequential block_ids
        for idx, block in enumerate(topic["content_blocks"], 1):
            block["block_id"] = f"block_{idx}"
        
        final_topics.append(topic)
    
    return final_topics


def build_final_json(all_topics, pdf_filename):
    """Build the final JSON structure according to schema."""
    # Since schema requires a single topic object, we'll create one per topic
    # But if user wants all in one file, we'll return array of topics
    # Based on schema, it seems like each JSON should be one topic
    
    # For now, return array of topics (user can split later if needed)
    merged_topics = merge_topics(all_topics)
    
    # If only one topic, return it directly; otherwise return array
    if len(merged_topics) == 1:
        return merged_topics[0]
    else:
        # Return array of topics - user can process each separately
        return merged_topics


def infer_pedagogical_profile(topics_data: list, metadata: dict = None) -> dict:
    """
    Analyzes the extracted curriculum topics and infers their pedagogical profile
    using LLM reasoning.
    """
    if not groq_client:
        return {
            "reasoning_style": "Analytical",
            "pedagogy_style": ["Conceptual"],
            "assessment_style": "Conceptual Recall",
            "content_nature": "Theoretical"
        }
        
    print("\nInferring Pedagogical Profile for curriculum...")
    
    # Create sample context
    sample_context = []
    for topic in topics_data[:3]:
        sample_context.append(f"Topic: {topic.get('topic_name')}")
        sample_context.append(f"Objectives: {', '.join(topic.get('learning_objectives', []))}")
        sample_context.append(f"Allowed Concepts: {', '.join(topic.get('allowed_concepts', []))}")
        blocks = topic.get("content_blocks", [])
        if blocks:
            sample_context.append(f"Sample Content: {blocks[0].get('text')[:300]}...")
            
    sample_text = "\n".join(sample_context)
    subject = metadata.get("subject", "General") if metadata else "General"
    grade = metadata.get("grade", "Unknown") if metadata else "Unknown"
    
    prompt = f"""
    You are an expert cognitive learning scientist and curriculum analyst.
    Your task is to analyze the following curriculum sample of Grade {grade} {subject} and infer its underlying pedagogical profile.
    
    CURRICULUM SAMPLE:
    {sample_text[:4000]}
    
    INSTRUCTIONS:
    Classify the curriculum sample along the following four axes:
    
    1. reasoning_style: The primary style of logical deduction or description. Must be ONE of:
       - "Analytical" (critical analysis, logic, classification)
       - "Procedural" (steps, code execution, algorithms, procedures)
       - "Narrative" (chronological, stories, historical sequences)
       - "Comparative" (comparing cases, laws, precedents, structures)
       - "Symbolic" (equations, formulas, proofs, symbolic logic)
       - "Causal" (cause-and-effect, science mechanisms, cycles)
       - "Interpretive" (textual explanation, hermeneutics, legal rules)
       
    2. pedagogy_style: The recommended teaching approaches. Select a list of 1-3 from:
       - "Example-Driven" (focus on worked examples or cases)
       - "Visual" (visualize graphs, diagrams, maps, code trees)
       - "Conceptual" (focus on definitions and theory)
       - "Stepwise" (micro-steps, chronological flow)
       - "Exploratory" (investigating variations, inquiry)
       - "Debate-Oriented" (exploring opposing viewpoints)
       - "Case-Based" (analyzing specific clinical, law, or real cases)
       
    3. assessment_style: The optimal way to test this knowledge. Must be ONE of:
       - "Problem Solving" (calculations, equations, exercises)
       - "Conceptual Recall" (identifying definitions, rules, facts)
       - "Comparative Analysis" (contrast systems, cases, arguments)
       - "Execution Tracing" (tracing code flow, debugging bugs)
       - "Argument Evaluation" (evaluating positions, laws, historical reviews)
       - "Process Understanding" (explaining cause-and-effect sequences)
       
    4. content_nature: The native characteristics of the text. Must be ONE of:
       - "Technical" (code, math syntax, engineering specifications)
       - "Theoretical" (laws, math theorems, abstract definitions)
       - "Descriptive" (history narrations, literature themes, descriptive science)
       - "Abstract" (philosophical arguments, high-level theories)
       - "Sequential" (chronologies, algorithms, workflows)
       - "Structural" (anatomy, physical maps, architecture)

    OUTPUT FORMAT (JSON ONLY):
    {{
        "reasoning_style": "...",
        "pedagogy_style": ["...", "..."],
        "assessment_style": "...",
        "content_nature": "..."
    }}
    """
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a specialized Cognitive Science AI. Output ONLY valid JSON matching the format requested."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        profile_raw = response.choices[0].message.content.strip()
        profile = json.loads(profile_raw)
        print(f"Inferred Pedagogical Profile: {profile}")
        return profile
    except Exception as e:
        print(f"Error inferring pedagogical profile: {e}. Using fallback.")
        return {
            "reasoning_style": "Analytical",
            "pedagogy_style": ["Conceptual"],
            "assessment_style": "Conceptual Recall",
            "content_nature": "Theoretical"
        }

def process_single_file(text_file_path, pdf_path=None, schema=None, custom_output_base=None, metadata=None):
    """Process a single text file and convert to JSON, using dynamically identified PDF metadata."""
    if schema is None:
        print("Schema not provided")
        return None
    
    if pdf_path is None:
        pdf_filename = text_file_path.stem + ".pdf"
        pdf_path = BASE_DIR / pdf_filename
    else:
        pdf_filename = os.path.basename(pdf_path)
    
    text = load_file(str(text_file_path))
    unit_name = text_file_path.stem  # Use filename as unit name
    
    # Log which metadata is driving this extraction
    if metadata:
        print(f"\nProcessing: {text_file_path.name} | Grade {metadata.get('grade','?')} {metadata.get('subject','?')} [{metadata.get('curriculum','?')}]")
    else:
        print(f"\nProcessing: {text_file_path.name} (no metadata - using generic extraction)")
    print(f"   Text length: {len(text)} characters")
    print(f"   Unit: {unit_name}")
    
    # Split text into manageable chunks
    text_chunks = split_text_into_chunks(text, CHUNK_SIZE)
    print(f"   Split into {len(text_chunks)} chunk(s) for processing")
    
    all_topics = []
    for i, chunk in enumerate(text_chunks):
        print(f"   Processing chunk {i + 1}/{len(text_chunks)}...", end=" ")
        topics = process_text_chunk(chunk, i, len(text_chunks), unit_name, schema, metadata=metadata)
        all_topics.extend(topics)
        print(f"Extracted {len(topics)} topic(s)")
    
    # Build final JSON
    final_json = build_final_json(all_topics, pdf_filename)
    
    # Ingest pedagogical profile inferred directly from the topics list
    topics_list = final_json if isinstance(final_json, list) else [final_json]
    ped_profile = infer_pedagogical_profile(topics_list, metadata)
    for topic in topics_list:
        topic["pedagogical_profile"] = ped_profile
        
    # Save output - single JSON file
    if custom_output_base:
         target_dir = Path(custom_output_base) / "json_output"
    else:
         target_dir = JSON_DIR
 
    output_file = target_dir / f"{text_file_path.stem}.json"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Save as array of topics (single file)
    if isinstance(final_json, list):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
        print(f"Saved: {output_file.name} ({len(final_json)} topic(s))")
    else:
        # Single topic object - wrap in array for consistency
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([final_json], f, indent=2, ensure_ascii=False)
        print(f"Saved: {output_file.name} (1 topic)")
    
    # Trigger Persistent ChromaDB indexing
    try:
        from backend.core.qa import SmartQA
        qa = SmartQA(content_dir="generated_contents")
        qa.index_curriculum_to_chroma(str(output_file), metadata=metadata)
        print(f"[Persistent Vector Ingestion] Successfully indexed {output_file.name} into Persistent ChromaDB.")
    except Exception as index_err:
        print(f"[Persistent Vector Ingestion Warning] Failed to index on-the-fly during PDF upload: {index_err}")
        
    return output_file


def process_specific_pdf(pdf_path, schema, custom_output_base=None, metadata=None):
    """Process the specific PDF file and convert to JSON."""
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return None
    
    # Dynamically identify metadata if not passed to prevent any hardcoded class/subject structures
    if metadata is None:
        metadata = identify_book_metadata(pdf_path)
    
    # Determine the directory structure based on metadata
    if metadata:
        grade = f"Grade_{metadata.get('grade', 'Unknown')}"
        subject = metadata.get('subject', 'General').replace(" ", "_")
        
        # Simplified: Nest directly inside Subject, skipping the Title folder
        if custom_output_base:
            output_dir = Path(custom_output_base) / grade / subject
        else:
            output_dir = GENERATED_DIR / "content" / grade / subject
    else:
        # Extreme fallback to general content dir
        output_dir = GENERATED_DIR / "content" / "Grade_Unknown" / "General"

    text_dir = output_dir / "text_output"
    json_dir = output_dir / "json_output"
    
    text_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if text file exists, if not extract it
    text_file = text_dir / f"{pdf_path.stem}.txt"
    
    if not text_file.exists():
        print(f"Text file not found. Extracting from PDF...")
        # Extract text from PDF
        text = ""
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Extracted text from PDF")
        except Exception as e:
            print(f"Error extracting text from PDF: {str(e)}")
            return None
    
    try:
        # Pass the calculated json_dir as custom_output_base to process_single_file
        # but process_single_file expects the PARENT of json_output.
        return process_single_file(text_file, pdf_path, schema, custom_output_base=output_dir, metadata=metadata)
    except Exception as e:
        print(f"Error processing {pdf_path.name}: {str(e)}")
        raise


# JSON VALIDATION FUNCTIONS (from validate_json.py)

def validate_json_file(json_file, schema_file):
    """Validate a single JSON file against the schema."""
    try:
        # Convert Path objects to strings
        json_path = str(json_file) if isinstance(json_file, Path) else json_file
        schema_path = str(schema_file) if isinstance(schema_file, Path) else schema_file
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        # Handle both single topic object and array of topics
        if isinstance(data, list):
            # Validate each topic in the array
            valid_count = 0
            for idx, topic in enumerate(data):
                try:
                    validate(instance=topic, schema=schema)
                    valid_count += 1
                except ValidationError as e:
                    print(f"Invalid topic {idx + 1} in {Path(json_file).name}")
                    print(f"   Error: {e.message}")
                    if e.path:
                        print(f"   Path: {' -> '.join(str(p) for p in e.path)}")
                    return False
            
            print(f"Valid: {Path(json_file).name} ({valid_count} topic(s))")
            return True
        else:
            # Single topic object
            validate(instance=data, schema=schema)
            print(f"Valid: {Path(json_file).name}")
            return True
    except ValidationError as e:
        print(f"Invalid: {Path(json_file).name}")
        print(f"   Error: {e.message}")
        if e.path:
            print(f"   Path: {' -> '.join(str(p) for p in e.path)}")
        return False
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {Path(json_file).name}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error validating {Path(json_file).name}: {str(e)}")
        return False


def validate_all_json_files():
    """Validate all JSON files in the output directory."""
    if not JSON_DIR.exists():
        print(f"JSON directory not found: {JSON_DIR}")
        print("   Please run ai_text_to_json.py first to generate JSON files.")
        return
    
    if not SCHEMA_FILE.exists():
        print(f"Schema file not found: {SCHEMA_FILE}")
        return
    
    json_files = list(JSON_DIR.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {JSON_DIR}")
        return
    
    print(f"Validating {len(json_files)} JSON file(s) against schema...\n")
    
    valid_count = 0
    for json_file in json_files:
        if validate_json_file(str(json_file), str(SCHEMA_FILE)):
            valid_count += 1
    
    print(f"\nValidation complete: {valid_count}/{len(json_files)} file(s) are valid")


# MAIN PIPELINE

def run_full_pipeline():
    """Run the complete pipeline for all PDFs: PDF  TXT  JSON  Validation"""
    print("=" * 70)
    print("Starting Full Pipeline: PDF -> TXT -> JSON -> Validation")
    print("=" * 70)
    
    # Load schema first
    print("\n" + "=" * 70)
    print("LOADING SCHEMA")
    print("=" * 70)
    schema = load_schema()
    if schema is None:
        print("Cannot proceed without schema")
        return
    
    # Find all PDF files in BASE_DIR
    if not BASE_DIR.exists():
        print(f"Base directory not found: {BASE_DIR}")
        return
    
    pdf_files = list(BASE_DIR.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {BASE_DIR}")
        return
    
    print(f"\nFound {len(pdf_files)} PDF file(s) to process")
    print(f" Directory: {BASE_DIR}\n")
    
    # Process each PDF
    successful_pdfs = []
    failed_pdfs = []
    
    for idx, pdf_file in enumerate(pdf_files, 1):
        print("\n" + "=" * 70)
        print(f"PROCESSING PDF {idx}/{len(pdf_files)}: {pdf_file.name}")
        print("=" * 70)
        
        # Step 1 & 2: Extract text from PDF and convert to JSON
        print(f"\nStep 1-2: Processing {pdf_file.name} (Extract text -> Convert to JSON)")
        json_output_file = process_specific_pdf(pdf_file, schema)
        
        if json_output_file is None:
            print(f"Failed to process {pdf_file.name}")
            failed_pdfs.append(pdf_file.name)
            continue
        
        # Step 3: Validate JSON file
        json_file = JSON_DIR / f"{pdf_file.stem}.json"
        if json_file.exists():
            print(f"\nStep 3: Validating {json_file.name}")
            is_valid = validate_json_file(str(json_file), str(SCHEMA_FILE))
            if is_valid:
                successful_pdfs.append(pdf_file.name)
            else:
                failed_pdfs.append(pdf_file.name)
        else:
            print(f"JSON file not found: {json_file.name}")
            failed_pdfs.append(pdf_file.name)
    
    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    print(f"Successfully processed: {len(successful_pdfs)}/{len(pdf_files)} PDF file(s)")
    if successful_pdfs:
        print("\nSuccessful files:")
        for pdf_name in successful_pdfs:
            print(f"  {pdf_name}")
    
    if failed_pdfs:
        print(f"\nFailed files: {len(failed_pdfs)}")
        for pdf_name in failed_pdfs:
            print(f"  {pdf_name}")
    
    print("\n" + "=" * 70)
    print("Pipeline Complete!")
    print("=" * 70)


if __name__ == "__main__":
    run_full_pipeline()