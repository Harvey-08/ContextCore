# ContextCore: AI-Powered Teaching Assistant

ContextCore is an advanced AI-powered Teaching Assistant designed to transform raw curriculum documents (like NCERT PDFs) into high-quality, structured educational materials.

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

## Accuracy & Hallucination Prevention

To ensure the AI generates factual, curriculum-aligned content without hallucinations, ContextCore implements a strict multi-layered validation system:

1. **Grounding via RAG**: The system never generates content from pre-trained memory. It uses ChromaDB to retrieve exact paragraphs from the uploaded PDFs and forces the LLM to answer using *only* that context.
2. **Direct Source Extraction**: When generating Teaching Plans, the AI does not invent examples. The system explicitly parses the extracted JSON for `type: "example"` blocks and injects raw textbook text directly into the final output.
3. **Strict Schema Validation**: All structured outputs (like Quizzes) are strictly validated using Pydantic (`quiz_schema.py`). The system mathematically enforces logic, such as validating that the designated "correct answer" actually exists within the generated multiple-choice options.
4. **The "Truth Layer"**: The `verifier.py` module acts as an automated auditor. It cross-references newly generated content against the original source text to score for hallucinations, bias, and accuracy before approving the output.


## Tech Stack

- **Frontend**: React, Vite, TailwindCSS, Framer Motion
- **Backend**: FastAPI, Manim, FFmpeg
- **AI & ML**:
  - Groq (Llama 3.3 & 3.1 LLM Agents)
  - Sentence Transformers (Embeddings)
  - ChromaDB (Vector Database)
  - Retrieval-Augmented Generation (RAG)

## Project Structure

```text
ContextCore/
├── backend/
│   ├── core/
│   │   ├── chatbot_rag.py        # RAG Chatbot logic 
│   │   ├── extract_pipeline.py   # PDF extraction and JSON structuring
│   │   ├── qa.py                 # Vector search and context retrieval
│   │   ├── quiz_schema.py        # Pydantic models for quiz validation
│   │   └── curriculum_schema.json# Standard schema for extracted data
│   ├── generators/
│   │   ├── generate_flashcards.py# Flashcard generation
│   │   ├── generate_plan.py      # PDF teaching plan generation
│   │   ├── generate_quiz.py      # Validated quiz generation
│   │   ├── get_youtube_links.py  # YouTube API integration
│   │   └── practice_questions.py # Worksheet PDF generation
│   ├── video_engine/
│   │   ├── tts_generator.py      # Audio and timing generation
│   │   ├── manim_engine_synchronized.py # Manim animation logic
│   │   ├── video_audio_merger.py # FFmpeg merging logic
│   │   └── generate_animations_synchronized.py # Video pipeline orchestrator
│   ├── analytics_engine.py      # Performance tracking and metrics
│   ├── verifier.py              # Hallucination detection
│   └── main.py                  # FastAPI server entry point
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    # Main user dashboard and controls
│   │   │   ├── LandingPage.jsx  # Initial welcome and upload screen
│   │   │   └── QuizTaker.jsx    # Interactive quiz interface
│   │   ├── App.jsx              # Global state and component routing
│   │   ├── index.css            # Global styles and design system
│   │   └── main.jsx             # Vite entry point
│   ├── index.html               # Main HTML template
│   ├── vite.config.js           # Vite configuration
│   ├── tailwind.config.js       # Tailwind CSS configuration
│   ├── postcss.config.js        # PostCSS configuration
│   ├── eslint.config.js         # Linting configuration
│   └── package.json             # Frontend dependencies
├── generated_contents/          # AI-generated output storage
└── requirements.txt             # Backend dependencies
```

## Generated Content Structure

When you use the application, it automatically organizes all generated assets into the following structure:

```text
generated_contents/
├── audio_segments/          # Individual TTS audio clips for lessons
├── content/                 # Extracted curriculum Text and JSON 
├── media/                   # Temporary Manim animation frames
├── outputs/                 # Final generated PDF teaching plans and worksheets
├── quiz_assets/             # Quiz performance history and JSON data
├── uploads/                 # Uploaded PDFs
└── video_assets/            # Final merged MP4 video lessons and specifications
```

## Prerequisites (Windows)

- **Python 3.11**
- **Node.js 18+**
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
   ```

   **Frontend `.env`**:
   ```env
   VITE_API_BASE=http://localhost:8000
   ```

3. **Launch the App**:
   Run the following commands in separate terminals:
   - Terminal 1 (Backend): `py -3.11 -m uvicorn backend.main:app --reload`
   - Terminal 2 (Frontend): `cd frontend && npm run dev`


