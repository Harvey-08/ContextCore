import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

def get_recommendations(weak_topics: List[str], qa_system=None, llm_client=None, model_name="llama-3.1-8b-instant"):
    """
    Use RAG to get context and LLM to generate unique, personalized advice.
    Returns detailed metrics (mastery, confidence, retention, difficulty recommendation) for explainability.
    """
    from backend.core.database import SessionLocal, TopicMastery
    from backend.core.spaced_engine import calculate_retention
    
    recommendations = []
    db = SessionLocal()
    
    try:
        for topic_name in weak_topics:
            # Query real DB stats
            record = db.query(TopicMastery).filter(TopicMastery.topic_name.ilike(f"%{topic_name}%")).first()
            
            m_score = 0.0
            c_score = 0.0
            retention = 0.0
            estimated_level = "Beginner"
            attempts = 1
            
            if record:
                m_score = record.mastery_score or 0.0
                c_score = record.confidence_score or 0.0
                attempts = record.attempt_count or 1
                retention = calculate_retention(m_score, c_score, record.last_updated, attempts)
                estimated_level = record.current_estimated_level or "Beginner"
                
            mastery_percentage = round(m_score * 100, 1)
            confidence_percentage = round(c_score * 100, 1)
            retention_percentage = round(retention * 100, 1)
            
            try:
                context_text = ""
                sources = []
                
                # 1. Get context from RAG if available
                if qa_system:
                    results = qa_system.ask(f"Key concepts, prerequisites and common mistakes for {topic_name}", n_results=3)
                    context_text = results.get('context', "")
                    sources = results.get('sources', [])[:2]

                # 2. Use LLM to generate personalized advice if available
                if llm_client:
                    prompt = f"""
                    You are a concise, curriculum-native learning advisor. 
                    TOPIC: "{topic_name}"
                    CONTEXT: {context_text[:1000]}
                    STUDENT PROFILE: Mastery={mastery_percentage}%, Confidence={confidence_percentage}%, Retention={retention_percentage}%
                    
                    TASK:
                    Provide a SHORT (max 2 sentences) learning advice for this student. 
                    Identify the core concept they should review based on the context.
                    Be direct, encouraging, and highly specific to the pedagogical style of the topic.
                    
                    ADVICE:
                    """
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "You are a helpful, subject-agnostic learning advisor providing concise advice."},
                            {"role": "user", "content": prompt}
                        ],
                        model=model_name,
                        temperature=0.7
                    )
                    suggestion = response.choices[0].message.content.strip()
                else:
                    # Basic fallback if LLM is offline
                    suggestion = f"Your performance in {topic_name} suggests you should revisit the introductory sections and practice the review exercises in this topic."

                # Detailed explainability reasons matching Issue 5
                prereq_weight = "High" if m_score < 0.40 else "Medium" if m_score < 0.75 else "Low"
                reason_expl = f"Low mastery of {mastery_percentage}% detected. Reviewing this textbook concept is critical to prevent learning gaps."
                if retention_percentage < 50:
                    reason_expl = f"Memory retention has dropped to {retention_percentage}%. Immediate active recall practice is highly recommended."
                elif confidence_percentage < 50:
                    reason_expl = f"Knowledge gap detected with low confidence indicator ({confidence_percentage}%). Scaffolded exercises are advised."

                recommendations.append({
                    "topic": topic_name,
                    "suggestion": suggestion,
                    "sources": sources,
                    "mastery_percentage": mastery_percentage,
                    "confidence_percentage": confidence_percentage,
                    "retention_percentage": retention_percentage,
                    "difficulty_recommendation": estimated_level,
                    "prereq_weight": prereq_weight,
                    "reason": reason_expl
                })
                
            except Exception as e:
                print(f"Error generating smart rec for {topic_name}: {e}")
                recommendations.append({
                    "topic": topic_name,
                    "suggestion": f"Focus on mastering the foundational concepts of {topic_name} before moving to advanced problems.",
                    "sources": [],
                    "mastery_percentage": mastery_percentage,
                    "confidence_percentage": confidence_percentage,
                    "retention_percentage": retention_percentage,
                    "difficulty_recommendation": estimated_level,
                    "prereq_weight": "Medium",
                    "reason": "Foundational conceptual stability check."
                })
    finally:
        db.close()
        
    return recommendations
