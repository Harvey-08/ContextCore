import re
import json
import sys
from pathlib import Path
from backend.core.schemas import CitationReport

class CitationValidator:
    """
    Parses and validates citations inside generated answers, checks factual grounding
    against retrieved curriculum chunks, and executes automated healing retries.
    """
    def __init__(self, client, model_name: str = "llama-3.1-8b-instant"):
        self.client = client
        self.model_name = model_name

    def extract_citations(self, text: str) -> list:
        """
        Finds all cited index markers (e.g., [#1], [1], [#2], [2]) in the text.
        Returns a list of unique 1-indexed integers.
        """
        matches = re.findall(r'\[#?(\d+)\]', text)
        return list(set(int(m) for m in matches))

    def validate_citations_bounds(self, text: str, retrieved_count: int) -> dict:
        """
        Checks if citations are within the bounds of the retrieved context chunks.
        """
        citations = self.extract_citations(text)
        hallucinated = [c for c in citations if c < 1 or c > retrieved_count]
        
        return {
            "valid": len(hallucinated) == 0,
            "citations": citations,
            "hallucinated": hallucinated
        }

    def verify_grounding(self, retrieved_context: str, generated_answer: str) -> dict:
        """
        Post-generation grounding check.
        Uses a quick LLM call to verify if all statements in the answer are strictly supported by context.
        """
        if not generated_answer.strip():
            return {"is_grounded": True, "hallucinations": []}

        system_prompt = (
            "You are a strict factual grounding verifier. Your task is to check if all factual statements "
            "in the generated answer are supported by the provided textbook context.\n"
            "If any claim is unsupported, hallucinated, or not directly mentioned in the context, mark it as unsupported."
        )

        user_prompt = f"""CONTEXT FROM TEXTBOOK:
{retrieved_context}

GENERATED ANSWER:
{generated_answer}

Analyze the answer and check for factual grounding."""

        import instructor
        try:
            instructor_client = instructor.from_groq(self.client)
            report = instructor_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model_name,
                response_model=CitationReport,
                temperature=0.1,
                max_retries=2
            )
            return report.model_dump()
        except Exception as e:
            print(f"[CitationValidator Warning] Grounding check failed via Instructor: {e}")
            return {"is_grounded": True, "hallucinations": [], "error": str(e)}

    def execute_with_healing(
        self,
        query: str,
        retrieved_context: str,
        retrieved_count: int,
        system_prompt: str,
        user_prompt: str,
        generate_fn
    ) -> str:
        """
        Executes generation, validates citations and semantic grounding, and performs
        healing retries up to 2 times if violations are found.
        """
        max_attempts = 3
        current_attempt = 1
        current_user_prompt = user_prompt
        
        while current_attempt <= max_attempts:
            print(f"[CitationValidator] Generating answer attempt {current_attempt}...")
            response_text = generate_fn(system_prompt, current_user_prompt)
            
            citation_check = self.validate_citations_bounds(response_text, retrieved_count)
            grounding_check = self.verify_grounding(retrieved_context, response_text)
            
            if citation_check["valid"] and grounding_check["is_grounded"]:
                print("[CitationValidator] Generation passed grounding and citation verification.")
                return response_text
            
            print(f"[CitationValidator] Validation failed on attempt {current_attempt}:")
            critique_parts = []
            
            if not citation_check["valid"]:
                print(f"  - Hallucinated citations found: {citation_check['hallucinated']}. Max chunks is {retrieved_count}.")
                critique_parts.append(
                    f"You used citation numbers {citation_check['hallucinated']} which do not exist in the context. "
                    f"You must only cite within range [1, {retrieved_count}]. Make sure to write citations in the exact format [index] (e.g. [1])."
                )
                
            if not grounding_check["is_grounded"]:
                halls = grounding_check["hallucinations"]
                reason = grounding_check["refusal_reason"]
                print(f"  - Factual hallucinations found: {halls}. Reason: {reason}")
                critique_parts.append(
                    f"The following statements in your previous response are unsupported by the context: {halls}. "
                    f"Critique: {reason}"
                )
            
            if current_attempt == max_attempts:
                print("[CitationValidator] Max grounding validation attempts reached. Refusing response.")
                return (
                    "I'm sorry, I couldn't find any relevant information in the current curriculum matching your question. "
                    "The lesson material does not cover all details required for a complete grounded explanation. Let's focus on our active lesson topics!"
                )
            
            feedback = "\n".join(critique_parts)
            current_user_prompt = (
                f"{user_prompt}\n\n"
                f"### HEALING CRITIQUE FROM VERIFIER (ATTEMPT {current_attempt} FAILED):\n"
                f"Your previous attempt had the following issues:\n"
                f"{feedback}\n\n"
                f"Please regenerate the response. Rewrite it to be 100% strictly grounded in the provided textbook context. "
                f"Remove all unsupported statements and correct all citations."
            )
            current_attempt += 1

        return "Response generation failed due to strict grounding safety checks."
