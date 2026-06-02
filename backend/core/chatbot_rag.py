import os
import sys
from dotenv import load_dotenv
from backend.core.qa import SmartQA
import textwrap
from backend.core.adaptive_prompts import get_chatbot_system_prompt

# Ensure backend path is in sys.path
from pathlib import Path
backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)
from cache.redis_client import redis_client

# Load environment variables
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
            # Scan all users' content under generated_contents - works for any uploaded PDF
            self.qa_system = SmartQA(
                content_dir="generated_contents"
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
        
        # Compile LangGraph Orchestration Workflow Graph
        self.workflow = self._compile_graph()
        
        print("System Ready! Context loaded from your dynamic curriculum folders.")

    def _rewrite_query(self, user_question, chat_history):
        """
        Rewrite follow-up questions to be standalone using chat history via Groq.
        """
        if not chat_history:
            return user_question
            
        recent_history = chat_history[-4:] 
        
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

    def _compile_graph(self):
        from langgraph.graph import StateGraph, END
        from typing import TypedDict, List, Dict, Optional, Any
        
        class RAGState(TypedDict):
            query: str
            rewritten_query: str
            difficulty: str
            user_id: Optional[int]
            session_id: Optional[str]
            chapter_metadata: Optional[dict]
            chunks: List[dict]
            system_prompt: str
            user_prompt: str
            raw_answer: str
            validation_result: dict
            attempt_count: int
            error: Optional[str]
            chat_history: List[dict]
            
        g = StateGraph(RAGState)
        
        # Define workflow node executors
        g.add_node("query_rewrite", self._node_query_rewrite)
        g.add_node("retrieve", self._node_retrieve)
        g.add_node("rerank", self._node_rerank)
        g.add_node("adaptive_prompt", self._node_adaptive_prompt)
        g.add_node("generate", self._node_generate)
        g.add_node("citation_validate", self._node_citation_validate)
        g.add_node("refuse_generation", self._node_refuse_generation)
        g.add_node("persist_metrics", self._node_persist_metrics)
        
        # Define transitions and routing
        g.set_entry_point("query_rewrite")
        g.add_edge("query_rewrite", "retrieve")
        g.add_edge("retrieve", "rerank")
        g.add_edge("rerank", "adaptive_prompt")
        g.add_edge("adaptive_prompt", "generate")
        g.add_edge("generate", "citation_validate")
        
        # Conditional citation validation gatekeeper (Max 2 retries)
        def routing_gate(state: RAGState):
            val_res = state["validation_result"]
            attempts = state["attempt_count"]
            if val_res["valid"]:
                return "persist_metrics"
            if attempts >= 3:
                return "refuse_generation"
            return "generate"
            
        g.add_conditional_edges(
            "citation_validate",
            routing_gate,
            {
                "persist_metrics": "persist_metrics",
                "refuse_generation": "refuse_generation",
                "generate": "generate"
            }
        )
        
        g.add_edge("refuse_generation", "persist_metrics")
        g.add_edge("persist_metrics", END)
        
        return g.compile()

    def _node_query_rewrite(self, state):
        rewritten = self._rewrite_query(state["query"], state.get("chat_history", []))
        return {"rewritten_query": rewritten}
        
    def _node_retrieve(self, state):
        # Inject user_id context into the QA system for database logging
        self.qa_system.current_user_id = state["user_id"]
        
        # Call Cosine Similarity Chapter Search
        ch_meta = self.qa_system.find_chapter(state["rewritten_query"])
        print(f"[LangGraph] Selected Chapter: {ch_meta['chapter_name']} (Similarity: {ch_meta['similarity']:.1%})")
        return {"chapter_metadata": ch_meta}
        
    def _node_rerank(self, state):
        # Call custom load_and_search (Vector Search, BM25, RRF, CrossEncoder, Dynamic Boosting)
        # keeping existing high-quality retrieval and boosting layers intact
        ch_path = state["chapter_metadata"]["json_path"]
        chunks = self.qa_system.load_and_search(
            ch_path,
            state["rewritten_query"],
            n_results=5,
            difficulty=state["difficulty"],
            user_id=state["user_id"]
        )
        return {"chunks": chunks}
        
    def _node_adaptive_prompt(self, state):
        chunks = state["chunks"]
        difficulty = state["difficulty"]
        ch_name = state["chapter_metadata"]["chapter_name"]
        user_id = state.get("user_id")
        
        # Fetch pedagogical profile properties dynamically
        profile = None
        if chunks:
            top_chunk = chunks[0]
            profile = {
                "reasoning_style": top_chunk.get("reasoning_style", "Analytical"),
                "content_nature": top_chunk.get("content_nature", "Theoretical"),
                "assessment_style": top_chunk.get("assessment_style", "Conceptual Recall"),
                "pedagogy_style": ["Conceptual"]
            }
        
        # -- LEARNER MODEL LOOKUP --
        # Dynamically fetch the user's TopicMastery from PostgreSQL for this topic
        mastery_score = None
        confidence_score = None
        retention_score = None
        learning_velocity_status = None
        
        if user_id:
            try:
                from backend.core.database import SessionLocal, TopicMastery
                from backend.core.spaced_engine import calculate_retention, calculate_learning_velocity
                
                db = SessionLocal()
                try:
                    # Find the best matching mastery record for the active chapter/topic
                    mastery_record = db.query(TopicMastery).filter(
                        TopicMastery.user_id == user_id,
                        TopicMastery.topic_name.ilike(f"%{ch_name}%")
                    ).first()
                    
                    if mastery_record:
                        mastery_score = mastery_record.mastery_score or 0.0
                        confidence_score = mastery_record.confidence_score or 0.0
                        retention_score = calculate_retention(
                            mastery_score, confidence_score, mastery_record.last_updated
                        )
                        print(f"[LangGraph] Learner Model loaded: mastery={mastery_score:.2f}, "
                              f"confidence={confidence_score:.2f}, retention={retention_score:.2f}")
                    
                    # Calculate learning velocity for adaptive pacing
                    velocity_data = calculate_learning_velocity(db, user_id)
                    learning_velocity_status = velocity_data.get("velocity_status")
                finally:
                    db.close()
            except Exception as e:
                print(f"[LangGraph] Learner model lookup skipped: {e}")
        
        sys_prompt = get_chatbot_system_prompt(
            difficulty,
            profile=profile,
            mastery_score=mastery_score,
            confidence_score=confidence_score,
            retention_score=retention_score,
            learning_velocity=learning_velocity_status,
        )
        
        # Compile RAG context references
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            doc_type = chunk['type'].replace('content_', '').upper()
            context_parts.append(f"\n[{doc_type} #{i}] (Relevance: {chunk['relevance']:.1%})")
            context_parts.append(chunk['text'])
        context_text = "\n".join(context_parts)
        
        # Format chat memory
        chat_history = state.get("chat_history", [])
        history_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-6:]])
        
        user_prompt = f"""
        CONTEXT FROM CURRICULUM (Chapter: {ch_name}):
        {context_text}
        
        CONVERSATION HISTORY:
        {history_context}
        
        CURRENT QUESTION:
        {state['query']}
        
        STRICT INSTRUCTION:
        1. Answer the question strictly matching the pedagogical instructions for the {difficulty} level.
        2. You must ONLY base your answer on the provided "CONTEXT FROM CURRICULUM". Do not assume or extrapolate.
        3. Cite the source chunks you used by appending their exact index bracket at the end of the sentence or claim (e.g., [1], [2]). Only cite numbers corresponding to chunks listed in the context.
        4. If the context does not contain the information required to answer, state clearly that the lesson material does not cover it.
        """
        return {"system_prompt": sys_prompt, "user_prompt": user_prompt}
        
    def _node_generate(self, state):
        attempt = state.get("attempt_count", 0) + 1
        print(f"[LangGraph] Generating answer attempt {attempt}/3...")
        
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": state["system_prompt"]},
                {"role": "user", "content": state["user_prompt"]}
            ],
            model=self.model_name,
            temperature=0.3,
            max_tokens=800
        )
        answer = response.choices[0].message.content.strip()
        return {"raw_answer": answer, "attempt_count": attempt}
        
    def _node_citation_validate(self, state):
        answer = state["raw_answer"]
        chunks = state["chunks"]
        retrieved_count = len(chunks)
        
        # Re-build text context block
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            doc_type = chunk['type'].replace('content_', '').upper()
            context_parts.append(f"\n[{doc_type} #{i}] (Relevance: {chunk['relevance']:.1%})")
            context_parts.append(chunk['text'])
        context_text = "\n".join(context_parts)
        
        # Load citation validator
        import sys
        from pathlib import Path
        backend_path = str(Path(__file__).resolve().parent.parent)
        if backend_path not in sys.path:
            sys.path.append(backend_path)
        from validation.citation_validator import CitationValidator
        
        validator = CitationValidator(self.client, self.model_name)
        citation_check = validator.validate_citations_bounds(answer, retrieved_count)
        grounding_check = validator.verify_grounding(context_text, answer)
        
        valid = citation_check["valid"] and grounding_check["is_grounded"]
        
        # Formulate self-healing retry prompt
        feedback = ""
        if not valid:
            critique_parts = []
            if not citation_check["valid"]:
                critique_parts.append(
                    f"You used citation numbers {citation_check['hallucinated']} which do not exist in the context. "
                    f"You must only cite within range [1, {retrieved_count}]. Make sure to write citations in the exact format [index] (e.g. [1])."
                )
            if not grounding_check["is_grounded"]:
                critique_parts.append(
                    f"The following statements in your previous response are unsupported by the context: {grounding_check['hallucinations']}. "
                    f"Critique: {grounding_check['refusal_reason']}"
                )
            feedback_text = "\n".join(critique_parts)
            
            feedback = (
                f"{state['user_prompt']}\n\n"
                f"### HEALING CRITIQUE FROM VERIFIER (FAILED ATTEMPT):\n"
                f"Your previous attempt had the following issues:\n"
                f"{feedback_text}\n\n"
                f"Please regenerate the response. Rewrite it to be 100% strictly grounded in the provided textbook context. "
                f"Remove all unsupported statements and correct all citations."
            )
            
        return {
            "validation_result": {
                "valid": valid,
                "citation_check": citation_check,
                "grounding_check": grounding_check
            },
            "user_prompt": feedback if not valid else state["user_prompt"]
        }
        
    def _node_refuse_generation(self, state):
        print("[LangGraph] Verification failed repeatedly. Outputting soft refusal response.")
        refusal = (
            "I'm sorry, I couldn't find any relevant information in the current curriculum matching your question. "
            "The lesson material does not cover all details required for a complete grounded explanation. Let's focus on our active lesson topics!"
        )
        return {"raw_answer": refusal}
        
    def _node_persist_metrics(self, state):
        # Database persistence is handled directly inside SmartQA.load_and_search
        print("[LangGraph] Traces successfully logged in PostgreSQL.")
        return {}

    def get_response(self, user_question, difficulty="Beginner", user_id=None, session_id="default"):
        """
        Query Groq utilizing LangGraph Orchestration Workflow (StateGraph) with Redis Caching.
        """
        try:
            # Normalize user question
            normalized_q = " ".join(user_question.lower().split())
            
            # Retrieve active curriculum version hash
            curriculum_version = "unknown"
            if hasattr(self, "qa_system"):
                curriculum_version = self.qa_system.get_curriculum_version()
                
            # Construct Cache Key
            cache_key = f"chat:{curriculum_version}:{difficulty}:{normalized_q}"
            
            # Retrieve active history array from Redis key chat_history:{user_id}:{session_id}
            history_key = f"chat_history:{user_id}:{session_id}"
            chat_history = redis_client.get_json(history_key) or []
            
            # Check Chat Cache
            cached_res = redis_client.get_json(cache_key)
            if cached_res:
                print(f"[Redis Hit] Chat Answer cache hit for question: '{normalized_q}' [Version: {curriculum_version}]")
                # Maintain chat memory consistency
                chat_history.append({"role": "user", "content": user_question})
                chat_history.append({"role": "assistant", "content": cached_res.get("answer", "")})
                # Slice history to the last 20 messages and save back
                chat_history = chat_history[-20:]
                redis_client.set_json(history_key, chat_history, ex_seconds=86400)
                return cached_res

            # Cache Miss: Initialize state graph payload
            initial_state = {
                "query": user_question,
                "rewritten_query": user_question,
                "difficulty": difficulty,
                "user_id": user_id,
                "session_id": session_id,
                "chapter_metadata": None,
                "chunks": [],
                "system_prompt": "",
                "user_prompt": "",
                "raw_answer": "",
                "validation_result": {"valid": False},
                "attempt_count": 0,
                "error": None,
                "chat_history": chat_history
            }
            
            # Execute workflow
            final_state = self.workflow.invoke(initial_state)
            
            response_text = final_state["raw_answer"]
            ch_meta = final_state.get("chapter_metadata")
            chapter_name = ch_meta["chapter_name"] if ch_meta else "None"
            relevance = ch_meta["similarity"] if ch_meta else 0.0
            chunks = final_state.get("chunks", [])
            
            # Update chat memory
            chat_history.append({"role": "user", "content": user_question})
            chat_history.append({"role": "assistant", "content": response_text})
            chat_history = chat_history[-20:]
            redis_client.set_json(history_key, chat_history, ex_seconds=86400)
            
            result = {
                'answer': response_text,
                'chapter': chapter_name,
                'relevance': relevance,
                'sources': chunks[:3]
            }
            
            # Cache response in Redis for 24 hours
            redis_client.set_json(cache_key, result, ex_seconds=86400)
            
            return result
        except Exception as e:
            print(f"[LangGraph Chatbot Error] Workflow run failed: {e}")
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
                
            result = self.get_response(question, user_id="cli", session_id="cli")
            
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