import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.spaced_engine import calculate_retention, calculate_dynamic_confidence

def run_learner_model_validation():
    print("=" * 60)
    print("           LEARNER MODEL ACCURACY HARDENING VALIDATION          ")
    print("=" * 60)

    # Case A: Mastery = 90%, Confidence = 85%, Recent Study
    m_a = 0.90
    c_a = 0.85
    recent_date = datetime.utcnow()
    attempts_a = 3
    retention_a = calculate_retention(m_a, c_a, recent_date, attempt_count=attempts_a)
    
    print("\n[CASE A: PERFECT / EXPERT STUDENT]")
    print(f"Mastery:       {m_a * 100:.1f}%")
    print(f"Confidence:    {c_a * 100:.1f}%")
    print("Study Status:  Recent (0 days delta)")
    print(f"Attempts:      {attempts_a}")
    print(f"Calculated Retention: {retention_a * 100:.1f}% (Expected: High Retention >= 90%)")
    assert retention_a >= 0.90, "Case A failed High Retention check!"

    # Case B: Mastery = 20%, Confidence = 50%, Recent Study
    m_b = 0.20
    c_b = 0.50
    attempts_b = 1
    retention_b = calculate_retention(m_b, c_b, recent_date, attempt_count=attempts_b)
    
    print("\n[CASE B: INITIATIVE / BEGINNER STUDENT]")
    print(f"Mastery:       {m_b * 100:.1f}%")
    print(f"Confidence:    {c_b * 100:.1f}%")
    print("Study Status:  Recent (0 days delta)")
    print(f"Attempts:      {attempts_b}")
    print(f"Calculated Retention: {retention_b * 100:.1f}% (Expected: Moderate Retention 60%-70%)")
    assert 0.55 <= retention_b <= 0.75, "Case B failed Moderate Retention check!"

    # Case C: Mastery = 80%, Inactive = 30 Days
    m_c = 0.80
    c_c = 0.75
    inactive_date = datetime.utcnow() - timedelta(days=30)
    attempts_c = 2
    retention_c = calculate_retention(m_c, c_c, inactive_date, attempt_count=attempts_c)
    
    print("\n[CASE C: FORGETTING / INACTIVE STUDENT]")
    print(f"Mastery:       {m_c * 100:.1f}%")
    print(f"Confidence:    {c_c * 100:.1f}%")
    print("Study Status:  30 Days Inactive")
    print(f"Attempts:      {attempts_c}")
    print(f"Calculated Retention: {retention_c * 100:.1f}% (Expected: Retention Decay < 60%)")
    assert retention_c < 0.60, "Case C failed Retention Decay check!"

    # Case D: Mastery = 10%, Score = 2/5 (Accuracy = 40%), Inactive = 30 Days
    m_d = 0.10
    c_d_raw = 0.78
    
    conf_res = calculate_dynamic_confidence(
        score=2,
        total_questions=5,
        response_duration=10.0,
        hints_used=0,
        answer_changes_before_submit=0,
        clarification_requests=0,
        mastery_score=m_d
    )
    final_conf = conf_res["confidence_score"]
    conf_cap = conf_res["evidence"]["confidence_cap"]
    
    retention_d = calculate_retention(m_d, final_conf, inactive_date, attempt_count=1)
    
    print("\n[CASE D: STRUGGLING / WEAK LEARNER]")
    print(f"Mastery:       {m_d * 100:.1f}%")
    print("Quiz Score:    2/5 (40% accuracy)")
    print(f"Mastery Cap:   {conf_cap * 100:.1f}% (Expected: 50.0%)")
    print(f"Final Bounded Confidence: {final_conf * 100:.1f}% (Expected: Capped at 50.0%)")
    print(f"Study Status:  30 Days Inactive")
    print(f"Calculated Retention:     {retention_d * 100:.1f}% (Expected: Very Low Retention < 20%)")
    
    assert conf_cap == 0.50, "Case D failed Confidence Cap validation!"
    assert final_conf <= 0.50, "Case D failed Confidence Bounded check!"
    assert retention_d < 0.20, "Case D failed Very Low Retention check!"

    print("\n" + "=" * 60)
    print("               ALL VALIDATION CHECKS PASSED                     ")
    print("=" * 60)

if __name__ == "__main__":
    run_learner_model_validation()
