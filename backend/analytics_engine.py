import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel

# Configuration
DATA_DIR = Path("generated_contents") / "quiz_assets"
HISTORY_FILE = DATA_DIR / "quiz_history.json"

class QuizResult(BaseModel):
    topic: str
    score: int
    total_questions: int
    date: str  # ISO format
    weak_subtopics: List[str] = []

def _load_history() -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save_history(history: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def save_quiz_result(result: QuizResult):
    """Save a new quiz result to history"""
    history = _load_history()
    # Add simple ID
    record = result.dict()
    record['id'] = len(history) + 1
    history.append(record)
    _save_history(history)
    return record

def get_analytics_dash_data():
    """
    Process history to return:
    1. Spiderweb data (Topic v/s Average Score %)
    2. Recent Activity
    3. Weakest Topics
    """
    history = _load_history()
    if not history:
        return {
            "spider_data": [],
            "recent_activity": [],
            "weakest_topics": []
        }

    # 1. Calculate Topic Scores
    topic_stats = {}
    for entry in history:
        t = entry['topic']
        score = entry['score']
        total = entry['total_questions']
        percentage = (score / total) * 100 if total > 0 else 0
        
        if t not in topic_stats:
            topic_stats[t] = {'sum_pct': 0, 'count': 0}
        
        topic_stats[t]['sum_pct'] += percentage
        topic_stats[t]['count'] += 1

    spider_data = []
    weakest_list = []
    
    for topic, stats in topic_stats.items():
        avg_score = round(stats['sum_pct'] / stats['count'], 1)
        spider_data.append({
            "subject": topic,
            "A": avg_score,
            "fullMark": 100
        })
        
        if avg_score < 70:  # Threshold for "Weak"
            weakest_list.append({"topic": topic, "score": avg_score})

    # Sort weakest
    weakest_list.sort(key=lambda x: x['score'])

    return {
        "spider_data": spider_data,
        "recent_activity": history[-5:], # Last 5
        "weakest_topics": weakest_list
    }

def get_recommendations(weak_topics: List[str], qa_system=None, llm_client=None, model_name="llama-3.1-8b-instant"):
    """
    Use RAG to get context and LLM to generate unique, personalized advice.
    """
    recommendations = []
    
    for topic_name in weak_topics:
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
                You are a concise Math Tutor. 
                TOPIC: "{topic_name}"
                CONTEXT: {context_text[:1000]}
                
                TASK:
                Provide a SHORT (max 2 sentences) learning advice for this student. 
                Identify the core concept they should review based on the context.
                Be direct and encouraging.
                
                ADVICE:
                """
                response = llm_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful math tutor providing concise advice."},
                        {"role": "user", "content": prompt}
                    ],
                    model=model_name,
                    temperature=0.7
                )
                suggestion = response.choices[0].message.content.strip()
            else:
                # Basic fallback if LLM is offline
                suggestion = f"Your performance in {topic_name} suggests you should revisit the introductory examples and practice the step-by-step solutions in this chapter."

            recommendations.append({
                "topic": topic_name,
                "suggestion": suggestion,
                "sources": sources
            })
            
        except Exception as e:
            print(f"Error generating smart rec for {topic_name}: {e}")
            recommendations.append({
                "topic": topic_name,
                "suggestion": f"Focus on mastering the foundational rules of {topic_name} before moving to advanced problems.",
                "sources": []
            })
            
    return recommendations
