import math
from datetime import datetime
from sqlalchemy.orm import Session
from backend.core.database import TopicMastery, QuizResultHistory

# ----------------------------------------------------------------------
# CONFIDENCE FORMULA WEIGHT CONSTANTS (User-specified breakdown)
# ----------------------------------------------------------------------
# Normalizing baselines
SPEED_THRESHOLD_PER_Q = 45.0    # 45 seconds per question baseline
MAX_HINTS_PER_Q = 2.0           # Assume max 2 hints per question
MAX_CHANGES_PER_Q = 3.0         # Assume max 3 answer changes per question
MAX_CLARIFICATIONS = 5.0        # Cap at 5 clarification requests

# REBALANCED FORMULA WEIGHT CONSTANTS
W_ACCURACY = 0.35
W_RESPONSE_SPEED = 0.15
W_HINT_USAGE = 0.10
W_ANSWER_STABILITY = 0.10
W_CLARIFICATION = 0.10
W_CONSISTENCY = 0.20

def calculate_dynamic_confidence(
    score: int,
    total_questions: int,
    response_duration: float = 0.0,
    hints_used: int = 0,
    answer_changes_before_submit: int = 0,
    clarification_requests: int = 0,
    mastery_score: float = 0.0,
) -> dict:
    """
    Computes a multi-signal dynamic confidence score from behavioral cues.
    
    Formula:
        confidence = 0.35*accuracy + 0.15*response_speed + 0.10*hint_usage
                   + 0.10*answer_stability + 0.10*clarification_behavior + 0.20*knowledge_consistency
    
    Capped dynamically based on accuracy:
        confidence_cap = 0.20 + 0.80 * accuracy
    """
    if total_questions <= 0:
        return {
            "confidence_score": 0.0,
            "evidence": {
                "accuracy": 0.0,
                "response_speed": 0.0,
                "hint_usage": 0.0,
                "answer_stability": 0.0,
                "clarification_behavior": 0.0,
                "knowledge_consistency": 0.0,
                "confidence_cap": 0.20,
                "formula_weights": {
                    "accuracy": W_ACCURACY,
                    "response_speed": W_RESPONSE_SPEED,
                    "hint_usage": W_HINT_USAGE,
                    "answer_stability": W_ANSWER_STABILITY,
                    "clarification_behavior": W_CLARIFICATION,
                    "knowledge_consistency": W_CONSISTENCY,
                },
            },
        }

    # 1. Accuracy component (0.0 to 1.0)
    accuracy = score / total_questions

    # 2. Response speed component - penalizes slow responses
    response_speed = max(0.0, 1.0 - (response_duration / (total_questions * SPEED_THRESHOLD_PER_Q)))

    # 3. Hint usage component - penalizes heavy hint reliance
    hint_usage = max(0.0, 1.0 - (hints_used / (total_questions * MAX_HINTS_PER_Q)))

    # 4. Answer stability component - penalizes frequent answer changes
    answer_stability = max(0.0, 1.0 - (answer_changes_before_submit / (total_questions * MAX_CHANGES_PER_Q)))

    # 5. Clarification behavior - penalizes excessive clarification requests
    clarification_behavior = max(0.0, 1.0 - (clarification_requests / MAX_CLARIFICATIONS))

    # 6. Knowledge consistency - checks how aligned the quiz score is with historical mastery
    m_val = mastery_score if mastery_score is not None else 0.0
    knowledge_consistency = max(0.0, 1.0 - abs(accuracy - m_val))

    # Weighted aggregation
    raw_confidence = (
        W_ACCURACY * accuracy
        + W_RESPONSE_SPEED * response_speed
        + W_HINT_USAGE * hint_usage
        + W_ANSWER_STABILITY * answer_stability
        + W_CLARIFICATION * clarification_behavior
        + W_CONSISTENCY * knowledge_consistency
    )

    # Mastery-aware confidence cap based on student's current mastery
    m_val = mastery_score if mastery_score is not None else 0.0
    if m_val < 0.20:
        confidence_cap = 0.50
    elif m_val < 0.40:
        confidence_cap = 0.65
    elif m_val < 0.60:
        confidence_cap = 0.80
    else:
        confidence_cap = 1.00

    confidence_score = round(max(0.0, min(confidence_cap, raw_confidence)), 4)

    evidence = {
        "accuracy": round(accuracy, 4),
        "response_speed": round(response_speed, 4),
        "hint_usage": round(hint_usage, 4),
        "answer_stability": round(answer_stability, 4),
        "clarification_behavior": round(clarification_behavior, 4),
        "knowledge_consistency": round(knowledge_consistency, 4),
        "confidence_cap": confidence_cap,
        "formula_weights": {
            "accuracy": W_ACCURACY,
            "response_speed": W_RESPONSE_SPEED,
            "hint_usage": W_HINT_USAGE,
            "answer_stability": W_ANSWER_STABILITY,
            "clarification_behavior": W_CLARIFICATION,
            "knowledge_consistency": W_CONSISTENCY,
        },
        "raw_inputs": {
            "score": score,
            "total_questions": total_questions,
            "response_duration_seconds": response_duration,
            "hints_used": hints_used,
            "answer_changes": answer_changes_before_submit,
            "clarification_requests": clarification_requests,
            "mastery_score": m_val,
        },
    }

    return {"confidence_score": confidence_score, "evidence": evidence}


# ----------------------------------------------------------------------
# RETENTION (Ebbinghaus Forgetting Curve)
# ----------------------------------------------------------------------

def calculate_retention(mastery: float, confidence: float, last_updated: datetime, attempt_count: int = 1) -> float:
    """
    Computes cognitive memory retention index using the Ebbinghaus forgetting curve.
    Formula: R = R_max * e^(-t/S)
    where R_max = 0.5 + 0.4*mastery + 0.1*confidence (caps immediate max retention dynamically)
    and S is the memory strength parameter:
    S = mastery * (1 + confidence) * 10.0 * sqrt(max(1, attempt_count)) + 1.0
    """
    if not last_updated:
        return 0.0
        
    t = (datetime.utcnow() - last_updated).total_seconds() / (24 * 3600)  # in days
    t = max(0.0, t)
    
    m_val = mastery if mastery is not None else 0.0
    c_val = confidence if confidence is not None else 0.0
    attempts = attempt_count if attempt_count is not None else 1
    
    # 1. R_max dynamic knowledge limit
    r_max = max(0.0, min(1.0, 0.5 + 0.4 * m_val + 0.1 * c_val))
    
    # 2. Memory strength stabilized by repeated studying (attempt_count)
    strength = (m_val * (1.0 + c_val) * 10.0 * math.sqrt(max(1, attempts))) + 1.0
    
    # 3. Forgetting curve calculation
    retention = r_max * math.exp(-t / strength)
    
    return round(max(0.0, min(1.0, retention)), 3)


# ----------------------------------------------------------------------
# REVISION SCHEDULE (Priority Queue)
# ----------------------------------------------------------------------

def get_revision_schedule(db_session: Session, user_id: int) -> list:
    """
    Scan all user masteries and build a Priority Queue of topics needing active revision.
    
    Triggers:
        - retention_score < 0.50
        - confidence_score < 0.50
        - mastery_score stagnant (< 0.60 and not studied in 7+ days)
    
    Returns topics sorted by highest revision priority (lowest retention/mastery) first.
    """
    masteries = db_session.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
    schedule = []
    
    for m in masteries:
        m_score = m.mastery_score if m.mastery_score is not None else 0.0
        c_score = m.confidence_score if m.confidence_score is not None else 0.0
        attempts = m.attempt_count if m.attempt_count is not None else 1
        retention = calculate_retention(m_score, c_score, m.last_updated, attempts)
        days_since = (datetime.utcnow() - m.last_updated).days if m.last_updated else 0
        
        # Revision triggers: retention < 50%, confidence < 50%, or stagnant mastery
        needs_revision = (
            retention < 0.50
            or c_score < 0.50
            or (days_since >= 7 and m_score < 0.60)
        )
        
        if needs_revision:
            # Calculate composite priority score (lower = more urgent)
            priority_score = round((retention * 0.4) + (m_score * 0.3) + (c_score * 0.3), 3)
            
            # Formulate explainable revision reason and priority tags
            retention_pct = round(retention * 100, 1)
            mastery_pct = round(m_score * 100, 1)
            confidence_pct = round(c_score * 100, 1)
            
            if retention < 0.25:
                status = "Critical Revision Needed"
                urgency = "high"
                reason = f"Retention decayed critically to {retention_pct}%. Memory strength requires immediate review."
            elif retention < 0.50:
                status = "Revision Due"
                urgency = "medium"
                reason = f"Retention dropped below threshold to {retention_pct}% since last studied {days_since} days ago."
            elif c_score < 0.50:
                status = "Confidence Building Needed"
                urgency = "medium"
                reason = f"Low confidence detected ({confidence_pct}%). Practice recommended to stabilize understanding."
            elif days_since >= 7 and m_score < 0.60:
                status = "Review Recommended"
                urgency = "low"
                reason = f"Stagnant mastery ({mastery_pct}%). Topic has not been visited in {days_since} days."
            else:
                status = "Review Recommended"
                urgency = "low"
                reason = "Routine prerequisite review to reinforce cognitive understanding."
            
            schedule.append({
                "topic": m.topic_name,
                "retention": retention,
                "retention_percentage": retention_pct,
                "last_studied_days": days_since,
                "mastery_score": m_score,
                "mastery_percentage": mastery_pct,
                "confidence_score": c_score,
                "confidence_percentage": confidence_pct,
                "priority_score": priority_score,
                "status": status,
                "urgency": urgency,
                "reason": reason
            })
            
    # Sort schedule by priority score ascending (most urgent first)
    schedule.sort(key=lambda x: x["priority_score"])
    return schedule


# ----------------------------------------------------------------------
# LEARNING VELOCITY & GROWTH STATUS
# ----------------------------------------------------------------------

def calculate_learning_velocity(db_session: Session, user_id: int) -> dict:
    """
    Calculate learning velocity (improvement trends) and absorption speeds.
    
    Growth Statuses:
        - "Rapid Growth"               (avg delta > 10.0)
        - "Steady Growth"              (avg delta > 2.0)
        - "Maintaining Levels"         (stable / flat)
        - "Struggling Pattern Detected" (avg delta < -2.0, declining)
    """
    results = db_session.query(QuizResultHistory).filter(
        QuizResultHistory.user_id == user_id
    ).order_by(QuizResultHistory.date.asc()).all()
    
    if not results or len(results) < 2:
        return {
            "velocity_status": "Needs More Data",
            "growth_label": "Insufficient Data",
            "absorption_speed": "Stable",
            "overall_improvement": 0.0,
            "total_attempts": len(results) if results else 0,
            "trend_direction": "neutral",
        }
        
    # Calculate percentage scores
    percentages = []
    for r in results:
        percentages.append((r.score / r.total_questions) * 100.0 if r.total_questions > 0 else 0.0)
        
    first_score = percentages[0]
    last_score = percentages[-1]
    net_improvement = last_score - first_score
    
    # Calculate rolling score slope (delta between consecutive quizzes)
    deltas = [percentages[i] - percentages[i - 1] for i in range(1, len(percentages))]
    avg_delta = sum(deltas) / len(deltas)
    
    # Recent trend: use last 3 deltas if available
    recent_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
    recent_avg = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0.0
    
    if avg_delta > 10.0:
        absorption = "Accelerated"
        status = "Rapidly Rising"
        growth_label = "Rapid Growth"
        trend = "strongly_positive"
    elif avg_delta > 2.0:
        absorption = "Consistent"
        status = "Steady Growth"
        growth_label = "Steady Growth"
        trend = "positive"
    elif avg_delta < -2.0:
        absorption = "Slowed"
        status = "Struggling Pattern Detected"
        growth_label = "Struggling Pattern Detected"
        trend = "negative"
    else:
        absorption = "Stable"
        status = "Maintaining Score Levels"
        growth_label = "Maintaining Levels"
        trend = "neutral"
        
    return {
        "velocity_status": status,
        "growth_label": growth_label,
        "absorption_speed": absorption,
        "overall_improvement": round(net_improvement, 1),
        "average_delta": round(avg_delta, 2),
        "recent_trend_delta": round(recent_avg, 2),
        "total_attempts": len(results),
        "trend_direction": trend,
    }
