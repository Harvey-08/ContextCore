from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional, Union


# ---------------------------
# Question Models
# ---------------------------

class MCQQuestion(BaseModel):
    type: Literal["mcq"]
    question: str = Field(..., min_length=10)
    options: List[str] = Field(..., min_items=3, max_items=5)
    correct: str
    blooms_level: str
    learning_objective: str

    @validator("correct")
    def correct_must_be_in_options(cls, v, values):
        if "options" in values and v not in values["options"]:
            raise ValueError("Correct answer must be one of the options")
        return v


class ShortAnswerQuestion(BaseModel):
    type: Literal["short"]
    question: str = Field(..., min_length=10)
    answer: str
    blooms_level: str
    learning_objective: str


Question = Union[MCQQuestion, ShortAnswerQuestion]


# ---------------------------
# Quiz Model
# ---------------------------

class Quiz(BaseModel):
    topic: str
    class_level: str
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    duration_minutes: int = Field(..., ge=10, le=90)
    questions: List[MCQQuestion]

    @validator("questions")
    def min_questions(cls, v):
        if len(v) < 3:
            raise ValueError("Quiz must have at least 3 questions")
        return v
