import os
import json
from dotenv import load_dotenv
import warnings

# Suppress warnings from google.generativeai deprecation
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)

load_dotenv()

class ContentVerifier:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Warning: GROQ_API_KEY not found. Verification layer is disabled.")
            self.enabled = False
        else:
            from groq import Groq
            self.client = Groq(api_key=api_key)
            self.model_name = "llama-3.3-70b-versatile"
            self.enabled = True

    def verify(self, source_context: str, generated_content: str | dict, context_name: str = "Content"):
        """
        Verifies generated content against source context using Groq.
        """
        if not self.enabled:
            return {"score": 100, "status": "SKIPPED", "feedback": "Verifier disabled (no API key)"}

        print(f"\nVerifying {context_name} with Groq Probe ({self.model_name})...")

        # Convert dict to string if needed
        content_str = json.dumps(generated_content, indent=2) if isinstance(generated_content, dict) else str(generated_content)
        
        prompt = f"""
        SOURCE TEXTBOOK CONTEXT:
        {source_context[:4000]}
        
        GENERATED CONTENT TO AUDIT:
        {content_str[:4000]}
        
        TASK:
        1. Check for HALLUCINATIONS: Are there facts in the content that directly contradict or are completely absent from the source?
        2. Check for BIAS: Is there any political, gender, or cultural bias?
        3. Check for RELEVANCE: Is it actually teaching the topic?
        
        OUTPUT JSON ONLY:
        {{
            "score": <0-100 integer>,
            "hallucination_found": <bool>,
            "bias_found": <bool>,
            "reason": "Short explanation",
            "flagged_issues": ["List", "of", "errors"]
        }}
        """

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a specialized AI Auditor. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_name,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            text = response.choices[0].message.content.strip()
            result = json.loads(text)
            self._print_report(result, context_name)
            return result
            
        except Exception as e:
            print(f" Verification Error with {self.model_name}: {e}")
            return {"score": 0, "status": "ERROR", "feedback": str(e)}

    def _print_report(self, result, context_name):
        score = result.get('score', 0)
        color = "" if score >= 85 else "" if score >= 70 else ""
        
        print("\n" + "="*40)
        print(f"  VERIFICATION REPORT: {context_name}")
        print(f"{color} Trust Score: {score}/100")
        
        if result.get('hallucination_found'):
            print(" HALLUCINATION DETECTED")
        if result.get('bias_found'):
            print("BIAS DETECTED")
            
        print(f"Reason: {result.get('reason')}")
        
        if result.get('flagged_issues'):
            print("Issues:")
            for issue in result['flagged_issues']:
                print(f"   - {issue}")
        print("="*40 + "\n")

if __name__ == "__main__":
    # Test run
    v = ContentVerifier()
    v.verify("The sky is blue.", "The sky is green.", "Test Check")
