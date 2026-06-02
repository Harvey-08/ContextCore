from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional, Union


# Question Models

class MCQQuestion(BaseModel):
    type: Literal["mcq"]
    question: str = Field(..., min_length=10)
    options: List[str] = Field(..., min_items=4, max_items=4)
    correct: str
    blooms_level: str
    learning_objective: str
    hint_1: str = Field(default="Think about the core concepts of this lesson.")
    hint_2: str = Field(default="Recall the primary context rules discussed in this section.")

    @validator("correct")
    def correct_must_be_in_options(cls, v, values):
        if "options" in values and v not in values["options"]:
            raise ValueError("Correct answer must be one of the options")
        return v

    @validator("options")
    def validate_options(cls, v):
        if len(v) != 4:
            raise ValueError("MCQ must have exactly 4 options")
        if len(set(v)) != len(v):
            raise ValueError("Options must not contain duplicate values")
        if any(not opt.strip() for opt in v):
            raise ValueError("Options must not contain empty or whitespace-only strings")
        return v


class ShortAnswerQuestion(BaseModel):
    type: Literal["short"]
    question: str = Field(..., min_length=10)
    answer: str
    blooms_level: str
    learning_objective: str


Question = Union[MCQQuestion, ShortAnswerQuestion]


# Quiz Model

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

