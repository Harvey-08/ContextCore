# ContextCore: AI-Powered Teaching Assistant

ContextCore is an advanced AI-powered Teaching Assistant designed to transform raw curriculum documents (like NCERT PDFs) into high-quality, structured educational materials.

## System Architecture

ContextCore's architecture is a closed-loop, learning-aware system combining high-performance retrieval, structural verification, and adaptive student profiling.

```mermaid
flowchart TD
    subgraph INGESTION ["1. Curriculum Ingestion"]
        PDF["Raw Textbook (PDF)"] --> EP["extract_pipeline.py<br/>(AI Extraction)"]
        EP --> JSON["Structured Curriculum JSON"]
        EP --> CDB["ChromaDB Vector Store"]
    end

    subgraph ENGINE ["2. Dynamic Learning Engines"]
        JSON --> PE["prerequisites.py<br/>(Dependency Mapping)"]
        JSON --> AP["adaptive_prompts.py<br/>(Pedagogical Profiling)"]
        PE --> ROAD["Roadmap Generator"]
    end

    subgraph INTERFACE ["3. Active Generative Pipelines"]
        CDB --> MB["MathBuddy RAG Chatbot"]
        AP --> MB
        JSON --> GEN["Resource Generators<br/>(Quiz, Flashcards, Worksheets)"]
    end

    subgraph GUARDRAILS ["4. Validation & Safety (Truth Layer)"]
        MB --> CV["citation_validator.py<br/>(Self-Healing Loop)"]
        CV -- "Failed (Unsupported/Out of Bounds)" --> CV_HEAL["Critique & Auto-Regenerate<br/>(Up to 3 Retries)"]
        CV_HEAL --> MB
        
        GEN --> Pyd["quiz_schema.py<br/>(Pydantic Validation)"]
        Pyd --> V["verifier.py<br/>(Groq Llama-3.3-70b Auditor)"]
        V -- "Audit Report" --> V_LOG["Score, Bias, & Factual Logs"]
    end

    subgraph COGNITIVE ["5. Database & Memory Engine"]
        CV -- "Passed" --> DB["PostgreSQL Database<br/>(SQLAlchemy models)"]
        V_LOG --> DB
        DB --> SE["spaced_engine.py<br/>(Stepped Mastery-Aware Confidence Caps & Ebbinghaus Forgetting Curves)"]
        SE --> |"Retention < 50%"| REV["Today's Spaced Revision Queue"]
        REV --> MB
        SE -.-> VAL["validate_model_cases.py<br/>(Programmatic Math Auditor)"]
    end

    style INGESTION fill:#f9fafb,stroke:#e5e7eb,stroke-width:2px
    style ENGINE fill:#f0fdfa,stroke:#5eead4,stroke-width:2px
    style INTERFACE fill:#f5f3ff,stroke:#c084fc,stroke-width:2px
    style GUARDRAILS fill:#fff1f2,stroke:#fda4af,stroke-width:2px
    style COGNITIVE fill:#eff6ff,stroke:#93c5fd,stroke-width:2px
```

## Features

| Feature | Description |
|---|---|
| **PDF Upload & Extraction** | Upload textbook PDFs; AI extracts topics, objectives, and content blocks. |
| **Teaching Plan** | Generates a step-by-step lesson plan with timing, examples, and homework. |
| **Quiz Generator** | Creates interactive quizzes with instant feedback and PDF exports. |
| **Flashcards** | Smart concept review cards with flip animations. |
| **Practice Exercises** | Generates structured PDF worksheets with application questions. |
| **Video Lesson** | AI-generated animated video with synchronized narration (Manim + TTS). |
| **RAG Chatbot (MathBuddy)** | Conversational AI that answers questions strictly from the uploaded curriculum. |
| **Analytics Dashboard** | Tracks performance and identifies weak topics with AI recommendations. |
| **User Authentication** | Secure user login and registration system using JWT tokens. |
| **Prerequisite Engine** | Dynamic prerequisite engine checking sequencing of learning paths and preventing advanced topics without foundational mastery. |
| **Spaced Repetition Scheduler** | Adapts review schedules using dynamic Ebbinghaus Forgetting Curves and stepped Mastery-Aware Confidence Caps. |
| **Learner Model Validation Suite** | Programmatically executes assertion checks for student profiling (Expert, Beginner, Inactive, Struggling cases). |
| **Hybrid Search (BM25 + RRF)** | Fuses vector embedding retrieval with exact-keyword search via Reciprocal Rank Fusion. |
| **Self-Healing Citation Validator** | Instructs Groq to analyze generated answers for strict grounding and auto-heals citations. |


## Bias & Hallucination Prevention

To ensure the AI generates factual, unbiased, and curriculum-aligned content, ContextCore implements a strict multi-layered validation system:

1. **Hybrid Retrieval-Augmented Generation (BM25 + RRF)**: The system never generates content from pre-trained memory. It uses local Sentence-Transformers combined with exact-keyword Rank-BM25 indices, fused via Reciprocal Rank Fusion (RRF), to retrieve exact textbook paragraphs from ChromaDB and forces the LLM to answer using *only* that grounded context.
2. **Self-Healing Grounding Agent (`citation_validator.py`)**: All live RAG conversational responses undergo a strict verification and self-healing loop:
   - **Citation Boundary Check**: Automatically parses index-based citation markers (e.g., `[1]`, `[#2]`) and verifies that they map to valid, existing source contexts.
   - **Post-Generation Grounding Verification**: Employs `Instructor` structured JSON validators to execute strict factual audits on Groq (`llama-3.1-8b-instant`), identifying any unsupported claims.
   - **Self-Healing Critique Loop**: If citation bounds or factual grounding checks fail, the system automatically provides a feedback critique to the generator and triggers up to **3 healing retry attempts** to correct the response.
3. **Structured Schema & Logic Enforcement (`quiz_schema.py`)**: All structured learning materials (like Quizzes and Worksheets) are strictly validated using Pydantic models. The schema mathematically guarantees logical constraints—for example, verifying that the designated "correct answer" actually exists within the generated multiple-choice options.
4. **Automated Auditor "Truth Layer" (`verifier.py`)**: The `ContentVerifier` module acts as a final automated quality gateway. It runs a deep audit of newly generated structured materials against original textbook text using the powerful `llama-3.3-70b-versatile` model. It computes an exact 0-100 Trust Score, flags potential political/cultural/gender bias, and details structural issues before approving the output.


## Tech Stack

- **Frontend**: React, Vite, TailwindCSS, Framer Motion, Recharts, Lucide React, Axios
- **Backend**: FastAPI, Manim, FFmpeg, PostgreSQL, SQLAlchemy
- **AI & ML**:
  - Groq (Llama 3.3 & 3.1 LLM Agents)
  - Sentence Transformers (Embeddings)
  - ChromaDB (Vector Database)
  - Retrieval-Augmented Generation (RAG)
  - LangGraph (Agentic Workflows)
  - Instructor (Structured Data Extraction)
  - Ragas (RAG Evaluation Framework)
  - Rank-BM25 (Lexical Keyword Indexing)

## Project Structure

```text
ContextCore/
├── backend/
│   ├── cache/
│   │   └── redis_client.py                                 # Redis connection pooling and caching client
│   ├── core/
│   │   ├── chatbot_rag.py                                  # RAG Chatbot logic 
│   │   ├── extract_pipeline.py                             # PDF extraction and JSON structuring
│   │   ├── qa.py                                           # Vector search and context retrieval
│   │   ├── quiz_schema.py                                  # Pydantic models for quiz validation
│   │   ├── curriculum_schema.json                          # Standard schema for extracted data
│   │   ├── adaptive_prompts.py                             # Difficulty-aware prompt templates and user profiles
│   │   ├── auth_utils.py                                   # JWT authentication, hashing, and user sign-in security
│   │   ├── database.py                                     # SQLAlchemy session setup and PostgreSQL schema models
│   │   ├── prerequisites.py                                # Prerequisite checker and topic flow dependency analyzer
│   │   ├── schemas.py                                      # Pydantic models for authentication, verifications, and logs
│   │   └── spaced_engine.py                                # Spaced repetition scheduler algorithms for interval reviews
│   ├── generators/
│   │   ├── generate_flashcards.py                          # Flashcard generation
│   │   ├── generate_plan.py                                # PDF teaching plan generation
│   │   ├── generate_quiz.py                                # Validated quiz generation
│   │   ├── get_youtube_links.py                            # YouTube API integration
│   │   └── practice_questions.py                           # Worksheet PDF generation
│   ├── retrieval/                                          # Multi-engine retrieval components for blended context matching
│   │   ├── bm25_engine.py                                  # Rank-BM25 exact-keyword lexical index matching
│   │   └── rrf.py                                          # Reciprocal Rank Fusion blending vectors with lexical search results
│   ├── validation/                                         # Factual grounding and citation verifiers
│   │   ├── citation_validator.py                           # Real-time citation range verifier and LLM grounding self-healer
│   │   └── validate_model_cases.py                         # Offline learner model validation suite 
│   ├── video_engine/
│   │   ├── tts_generator.py                                # Audio and timing generation
│   │   ├── manim_engine_synchronized.py                    # Manim animation logic
│   │   ├── video_audio_merger.py                           # FFmpeg merging logic
│   │   └── generate_animations_synchronized.py             # Video pipeline orchestrator
│   ├── analytics_engine.py                                 # Performance tracking and metrics
│   ├── verifier.py                                         # Hallucination detection
│   └── main.py                                             # FastAPI server entry point
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx                               # Main user dashboard and controls
│   │   │   ├── LandingPage.jsx                             # Initial welcome and upload screen
│   │   │   └── QuizTaker.jsx                               # Interactive quiz interface
│   │   ├── App.jsx                                         # Global state and component routing
│   │   ├── index.css                                       # Global styles and design system
│   │   └── main.jsx                                        # Vite entry point
│   ├── index.html                                          # Main HTML template
│   ├── vite.config.js                                      # Vite configuration
│   ├── tailwind.config.js                                  # Tailwind CSS configuration
│   ├── postcss.config.js                                   # PostCSS configuration
│   ├── eslint.config.js                                    # Linting configuration
│   └── package.json                                        # Frontend dependencies
├── generated_contents/                                     # AI-generated output storage
├── vector_store/                                           # ChromaDB semantic search vector embedding store
└── requirements.txt                                        # Backend dependencies
```

## Generated Content Structure

When you use the application, it automatically organizes all generated assets into the following structure:

```text
generated_contents/
├── audio_segments/          # Individual TTS audio clips for lessons
├── content/                 # Extracted curriculum Text and JSON 
├── media/                   # Temporary Manim animation frames
├── outputs/                 # Final generated PDF teaching plans and worksheets
├── uploads/                 # Uploaded PDFs
└── video_assets/            # Final merged MP4 video lessons and specifications
```

## Prerequisites (Windows)

- **Python 3.11**
- **Node.js 18+**
- **PostgreSQL**: Relational database for storing user accounts, spaced repetition logs, and RAG evaluations.
  - **Quick Setup**: Install PostgreSQL, start the service, and create a database named `contextcore`.
- **Redis**: High-performance key-value cache store for dashboard data sessions.
  - **Quick Setup**: Install Redis (via WSL, Memurai for Windows, or WSL Docker), start the service on port `6379`.
- **FFmpeg**: Essential for video and audio processing.
  - **Quick Install**: Open terminal and run `winget install Gyan.FFmpeg`.
  - **Manual Install**: Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your System PATH.
- **API Keys**: 
  - **Groq API Key**: Powers the Llama 3 models for all generation.
  - **YouTube Data API**: For fetching relevant educational videos.
  - **PDFShift API**: For high-quality PDF generation.

## Setup & Installation

1. **Install Dependencies**:
   ```bash
   py -3.11 -m pip install -r requirements.txt
   cd frontend && npm install
   ```

2. **Configure Environment**:
   Create a root `.env` file for the backend and a `frontend/.env` for the client.
   
   **Root `.env`**:
   ```env
   GROQ_API_KEY=your_key_here
   PDFSHIFT_API_KEY=your_key_here
   YOUTUBE_API_KEY=your_key_here
   DATABASE_URL=postgresql://postgres:password@localhost:5432/contextcore
   JWT_SECRET_KEY=your_jwt_secret_key_here
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   ```

   **Frontend `.env`**:
   ```env
   VITE_API_BASE=http://localhost:8000
   ```

3. **Start Redis Service (Required before running Backend & Frontend)**:
   You must start the Redis cache service before launching the applications. Run once to download and create the container:
   ```bash
   docker run -d --name redis -p 6379:6379 redis
   ```

4. **Launch the App**:
   Run the following commands in separate terminals:
   - Terminal 1 (Backend): `py -3.11 -m uvicorn backend.main:app --reload`
   - Terminal 2 (Frontend): `cd frontend && npm run dev`


## Future Improvements

- **Bayesian Knowledge Tracing (BKT)**: Replace heuristic mastery estimation with probabilistic concept-level knowledge tracking, enabling more accurate modeling of learner understanding and progression after each assessment interaction.
- **Item Response Theory (IRT)**: Introduce learner ability and question difficulty modeling to support adaptive assessments, personalized difficulty calibration, and more reliable evaluation of student performance.


