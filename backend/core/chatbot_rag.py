import os
import sys
from dotenv import load_dotenv
from qa import SmartQA
import textwrap

# Load environment variables (for GEMINI_API_KEY)
load_dotenv()

class MathBuddyChatbot:
    """
    Standalone RAG Chatbot for Curriculum
    Uses SmartQA (Vector DB) for context retrieval and Google Gemini LLM for answer generation.
    """
    
    def __init__(self):
        print("Initializing MathBuddy Chatbot with Groq...")
        
        # 1. Initialize RAG System (SmartQA) - Now Dynamic!
        try:
            self.qa_system = SmartQA(
                content_dir="generated_contents/content"
            )
        except Exception as e:
            print(f"Error initializing SmartQA: {e}")
            raise Exception(f"Error initializing SmartQA: {e}")
            
        # 2. Initialize LLM (Groq)
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY not found in .env file")
            raise Exception("GROQ_API_KEY not found in .env file")
            
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.1-8b-instant"
        self.chat_history = []  # List of {"role":Str, "content":Str}
        
        print("System Ready! Context loaded from your dynamic curriculum folders.")

    def _rewrite_query(self, user_question):
        """
        Rewrite follow-up questions to be standalone using chat history via Groq.
        """
        if not self.chat_history:
            return user_question
            
        recent_history = self.chat_history[-4:] 
        
        system_prompt = """You are a query rewriter. 
        Your task is to rewrite the last user question to be a STANDALONE search query based on the conversation history.
        Do NOT answer the question. Just rewrite it for a search engine.
        """
        
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history])
        
        prompt = f"""
        CONVERSATION HISTORY:
        {history_text}
        
        LAST USER QUESTION:
        {user_question}
        
        REWRITTEN STANDALONE QUERY:
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model=self.model_name,
                temperature=0.1
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten.replace('"', '')
        except:
            return user_question

    def get_response(self, user_question):
        """
        Query Groq with context + history
        """
        try:
            # Step 0: Contextualize Query
            search_query = self._rewrite_query(user_question)
            
            # Step 1: Retrieve Context using RAG
            print(f"\n Searching textbooks for: '{search_query}'...")
            search_result = self.qa_system.ask(search_query, n_results=5)
            
            context_text = search_result['context']
            chapter_name = search_result['chapter']
            relevance = search_result['chapter_relevance']

            # Relevance Threshold
            if relevance < 0.45:
                 return {
                    'answer': "I'm sorry, I couldn't find any relevant information in the current curriculum to answer your question.",
                    'chapter': 'None',
                    'relevance': relevance,
                    'sources': []
                }
            
            # Step 2: Prepare Prompt for LLM
            system_prompt = """You are a specialized AI assistant for the uploaded curriculum.
            Answer ONLY based on the provided "CONTEXT FROM CURRICULUM".
            """
            
            history_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in self.chat_history[-6:]])
            
            user_prompt = f"""
            CONTEXT FROM CURRICULUM (Chapter: {chapter_name}):
            {context_text}
            
            CONVERSATION HISTORY:
            {history_context}
            
            CURRENT QUESTION:
            {user_question}
            """
            
            # Step 3: Call LLM (Groq)
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model_name,
                temperature=0.3,
                max_tokens=800
            )
            
            response_text = response.choices[0].message.content
            
            # Step 4: Update Memory
            self.chat_history.append({"role": "user", "content": user_question})
            self.chat_history.append({"role": "assistant", "content": response_text})
            
            return {
                'answer': response_text,
                'chapter': chapter_name,
                'relevance': relevance,
                'sources': search_result['chunks'][:3]
            }
            
        except Exception as e:
            return {'error': str(e)}

    def start_interactive_session(self):
        """Run the interactive command-line chat loop"""
        print("\n" + "="*60)
        print(" MathBuddy CLI - Dynamic Curriculum Assistant (With Memory )")
        print("Type 'quit', 'exit', or 'q' to stop.")
        print("="*60 + "\n")
        
        while True:
            question = input("You: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("\n Goodbye! Happy Learning!")
                break
                
            if not question:
                continue
                
            result = self.get_response(question)
            
            if 'error' in result:
                print(f"\n Error: {result['error']}\n")
                continue
                
            print("\n" + "-"*60)
            print(f" MathBuddy (Focus: {result['chapter']})")
            print("-"*60)
            print(result['answer'])
            print("\n" + "."*30)
            if result.get('sources'):
                print("Sources found in:")
                for i, chunk in enumerate(result['sources']):
                    doctype = chunk['type'].replace('content_', '').upper()
                    print(f"- [{doctype}] {chunk['topic']}")
            print("."*30 + "\n")

if __name__ == "__main__":
    chatbot = MathBuddyChatbot()
    chatbot.start_interactive_session()