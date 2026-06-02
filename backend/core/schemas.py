from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# 1. Ingestion Metadata Schema
class BookMetadata(BaseModel):
    grade: str = Field(..., description="Extract only the grade/class number, e.g. '7' from Class VII or Grade 7")
    subject: str = Field(..., description="The academic subject, e.g., 'Mathematics', 'Science', 'History'")
    title: str = Field(..., description="The official textbook title")
    curriculum: str = Field("Unknown", description="Curriculum type, e.g. 'NCERT', 'CBSE'")

# 2. Curriculum Chunk Extraction Schemas
class ContentBlock(BaseModel):
    block_id: str = Field(..., description="Unique sequential block identifier, e.g. 'block_1', 'block_2'")
    type: Literal["definition", "explanation", "example"] = Field(..., description="Type of block content")
    text: str = Field(..., description="The raw, un-paraphrased text from the textbook")

class PedagogicalProfile(BaseModel):
    reasoning_style: Literal["Analytical", "Procedural", "Narrative", "Comparative", "Symbolic", "Causal", "Interpretive"] = Field(..., description="Logical deduction style of the text")
    pedagogy_style: List[Literal["Example-Driven", "Visual", "Conceptual", "Stepwise", "Exploratory", "Debate-Oriented", "Case-Based"]] = Field(..., min_items=1, max_items=3, description="Recommended teaching approaches")
    assessment_style: Literal["Problem Solving", "Conceptual Recall", "Comparative Analysis", "Execution Tracing", "Argument Evaluation", "Process Understanding"] = Field(..., description="Optimal method to assess understanding")
    content_nature: Literal["Technical", "Theoretical", "Descriptive", "Abstract", "Sequential", "Structural"] = Field(..., description="Characteristics of textbook text")

class CurriculumTopic(BaseModel):
    topic_id: str = Field(..., description="Unique identifier for the topic, e.g. 'topic_1'")
    topic_name: str = Field(..., description="Name of the specific topic")
    unit: str = Field(..., description="Name of the chapter/unit")
    learning_objectives: List[str] = Field(..., min_items=2, description="Factual learning goals")
    allowed_concepts: List[str] = Field(..., min_items=3, description="Concepts taught appropriate for this grade level")
    disallowed_concepts: List[str] = Field(..., description="Advanced concepts that should NOT be taught yet")
    content_blocks: List[ContentBlock] = Field(..., min_items=1, description="Sequential content chunks")
    pedagogical_profile: Optional[PedagogicalProfile] = None

class CurriculumTopicList(BaseModel):
    topics: List[CurriculumTopic] = Field(..., description="List of curriculum topics parsed from the text")

# 3. Flashcards Schema
class FlashcardItem(BaseModel):
    front: str = Field(..., description="Question or term printed on the front of the flashcard")
    back: str = Field(..., description="Answer or definition printed on the back of the flashcard (keep under 2 sentences)")
    type: Literal["definition", "problem", "fact", "conceptual"] = Field(..., description="Category of flashcard item")

class Flashcards(BaseModel):
    topic: str = Field(..., description="Subject or topic of the flashcard set")
    cards: List[FlashcardItem] = Field(..., min_items=5, max_items=15, description="Collection of individual flashcards")

# 4. Teaching Plan / Roadmap Schema
class StudyPlan(BaseModel):
    overview: str = Field(..., description="Brief summary of what this topic covers (2-3 sentences)")
    prerequisites: str = Field(..., description="Detailed list of concepts students should master before this lesson")
    teaching_plan: str = Field(..., description="HTML-formatted timeline. e.g. '<b>5 mins:</b> Intro<br><b>20 mins:</b> Activity'")
    explanation: str = Field(..., description="Clear explanation of the core concept strictly adapted to the difficulty level")
    worked_examples: str = Field(..., description="At least two worked-out textbook examples with detailed solutions")
    questions: List[str] = Field(..., min_items=3, max_items=5, description="Reflective questions to ask in class")
    homework: str = Field(..., description="Homework exercises and practice problems")
    assessment: List[str] = Field(..., min_items=4, max_items=6, description="Criteria check-list items to assess understanding")

# 5. Grounding and Citation Audit Schema
class CitationReport(BaseModel):
    is_grounded: bool = Field(..., description="True if ALL claims are supported by textbook context, False otherwise")
    hallucinations: List[str] = Field(..., description="List of unsupported, hallucinated, or unmentioned claims found in the answer")
    refusal_reason: str = Field("", description="Detailed explanation of what was hallucinated and why, or empty if grounded")

# 6. Worksheet and Quiz Schema
class QuestionItem(BaseModel):
    id: int = Field(..., description="Unique 1-indexed sequential question identifier")
    question: str = Field(..., min_length=10, description="The test question text")
    options: Optional[List[str]] = Field(None, min_items=4, max_items=4, description="Four distinct options for MCQs. Must be None for short answers")
    correct_answer: str = Field(..., description="For MCQ, must be one of options. For short answer, must be the exact correct solution with explanation")

class WorksheetSection(BaseModel):
    section_name: str = Field(..., description="e.g. 'Section A: Multiple Choice', 'Section B: Short Answer'")
    questions: List[QuestionItem] = Field(..., min_items=3, max_items=5, description="Worksheet questions in this section")

class WorksheetAnswerItem(BaseModel):
    id: int = Field(..., description="Question number matching the worksheet ID")
    answer: str = Field(..., description="Answer sheet solution with key explanation details")

class Worksheet(BaseModel):
    worksheet_title: str = Field(..., description="Worksheet title with topic name and difficulty tier")
    sections: List[WorksheetSection] = Field(..., min_items=3, max_items=3, description="MCQ, Short Answer, and Word Problem sections")
    answer_key: List[WorksheetAnswerItem] = Field(..., description="Accompanying answer sheet matching all worksheet questions")
