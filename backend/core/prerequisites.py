from pathlib import Path
from sqlalchemy.orm import Session


# DYNAMIC PREREQUISITE ENGINE
# Derives topic dependency chains from the user's ACTUAL uploaded curriculum
# JSON files instead of any hardcoded subject-specific data.

def _build_dynamic_prereq_map(db_session: Session, user_id: int) -> dict:
    """
    Scan the user's extracted curriculum JSON files and infer prerequisite
    relationships using two signals:

    1. Position ordering: topics extracted from the same file are treated as
       ordered - earlier topics are prerequisites for later ones (curriculum
       authors sequence topics from foundational to advanced).

    2. Concept overlap: if topic A's allowed_concepts overlap significantly
       with topic B's prerequisite-level concepts, A is inferred as a prereq
       for B.

    Returns a dict: { topic_name -> [prereq_topic_name, ...] }
    """
    import json
    from backend.core.database import User, LearnerProfile

    prereq_map = {}

    # Locate the user's content directory by querying the User table
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        user_name = user.name if user else None
    except Exception:
        user_name = None

    # Build search roots: user-specific dir first, then global fallback
    search_roots = []
    base = Path(__file__).parent.parent.parent / "generated_contents"

    if user_name:
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_name.strip())
        if safe_name:
            user_dir = base / safe_name / "content"
            if user_dir.exists():
                search_roots.append(user_dir)

    # Also scan all user subdirs (for shared content lookup)
    for child in base.iterdir():
        content_child = child / "content"
        if content_child.exists() and content_child not in search_roots:
            search_roots.append(content_child)

    for content_dir in search_roots:
        for json_file in content_dir.rglob("*.json"):
            # Skip chapter mapping index files
            if json_file.name.startswith("chapter_mapping"):
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    continue

                # Extract ordered topic names from this file
                topic_sequence = []
                for item in data:
                    name = item.get("topic_name", "").strip()
                    if name:
                        topic_sequence.append(name)
                        # Ensure every topic has an entry in the map
                        if name not in prereq_map:
                            prereq_map[name] = []

                # 1. Positional ordering: each topic depends on the one before it
                for i in range(1, len(topic_sequence)):
                    current = topic_sequence[i]
                    previous = topic_sequence[i - 1]
                    if previous not in prereq_map[current]:
                        prereq_map[current].append(previous)

                # 2. Concept overlap:
                # If an allowed concept of topic A appears in the learning objectives
                # or allowed concepts of topic B (where B is a different topic in the file),
                # A is inferred as a prerequisite for B.
                for A_idx, A_item in enumerate(data):
                    A_name = A_item.get("topic_name", "").strip()
                    A_concepts = [c.lower().strip() for c in A_item.get("allowed_concepts", []) if c.strip()]
                    if not A_name or not A_concepts:
                        continue

                    for B_idx, B_item in enumerate(data):
                        if A_idx == B_idx:
                            continue
                        B_name = B_item.get("topic_name", "").strip()
                        if not B_name:
                            continue

                        B_objectives = " ".join(B_item.get("learning_objectives", [])).lower()
                        B_allowed = " ".join(B_item.get("allowed_concepts", [])).lower()

                        overlap_found = False
                        for concept in A_concepts:
                            if len(concept) < 4:
                                continue
                            if concept in B_objectives or concept in B_allowed or concept in B_name.lower():
                                overlap_found = True
                                break

                        if overlap_found:
                            if B_name not in prereq_map:
                                prereq_map[B_name] = []
                            if A_name not in prereq_map[B_name] and A_name != B_name:
                                prereq_map[B_name].append(A_name)

            except Exception:
                continue  # Skip malformed JSON silently

    return prereq_map


def _get_prereq_map_for_user(db_session: Session, user_id: int) -> dict:
    """Return a dynamically-built prerequisite map for the given user."""
    return _build_dynamic_prereq_map(db_session, user_id)


def check_prerequisites(db_session: Session, user_id: int, topic_name: str) -> list:
    """
    Check if the user has weak mastery (<60%) in the prerequisite topics
    of the given topic, using a dynamically built dependency map from
    their uploaded curriculum files.

    Returns a list of prerequisite gap details:
    [{ prereq_topic, mastery, score_percentage }, ...]
    """
    from backend.core.database import TopicMastery

    prereq_map = _get_prereq_map_for_user(db_session, user_id)
    clean_topic = topic_name.strip()
    prereqs = prereq_map.get(clean_topic, [])

    # Case-insensitive substring fallback if no exact match
    if not prereqs:
        for key in prereq_map:
            if key.lower() in clean_topic.lower() or clean_topic.lower() in key.lower():
                prereqs = prereq_map[key]
                break

    gaps = []
    for p in prereqs:
        record = db_session.query(TopicMastery).filter(
            TopicMastery.user_id == user_id,
            TopicMastery.topic_name == p
        ).first()

        mastery = record.mastery_score if record else 0.0
        if mastery < 0.60:
            gaps.append({
                "prereq_topic": p,
                "mastery": round(mastery, 2),
                "score_percentage": round(mastery * 100, 1)
            })
    return gaps


def get_personalized_roadmap(db_session: Session, user_id: int, available_topics: list) -> list:
    """
    Generate a personalized multi-milestone learning roadmap based on the
    student's mastery profile and dynamically-derived prerequisite graph.

    Chooses between:
    - Accelerated route (avg mastery >= 75%)
    - Scaffolded reinforcement route (avg mastery < 75%)
    """
    from backend.core.database import TopicMastery

    prereq_map = _get_prereq_map_for_user(db_session, user_id)

    # Fetch user mastery scores
    masteries = db_session.query(TopicMastery).filter(
        TopicMastery.user_id == user_id
    ).all()
    mastery_map = {m.topic_name: m.mastery_score for m in masteries}

    # Fall back to all dynamically-discovered topics if none were passed in
    if not available_topics:
        available_topics = list(prereq_map.keys())

    if not available_topics:
        return []

    # Categorize available topics based on current mastery and prerequisite readiness
    weak_topics = []
    ready_topics = []
    advanced_topics = []

    for topic in available_topics:
        m_score = mastery_map.get(topic, 0.0)
        prereqs = prereq_map.get(topic, [])
        unmet_prereqs = [p for p in prereqs if mastery_map.get(p, 0.0) < 0.60]

        if unmet_prereqs:
            weak_topics.append((topic, m_score, unmet_prereqs))
        elif m_score < 0.50:
            ready_topics.append((topic, m_score))
        else:
            advanced_topics.append((topic, m_score))

    # Overall average mastery
    avg_mastery = sum(mastery_map.values()) / len(mastery_map) if mastery_map else 0.0

    # Safe topic picker with fallback
    def pick(lst, n, fallback_index=0):
        chosen = [t[0] for t in lst[:n]] if lst else []
        if not chosen and available_topics:
            chosen = [available_topics[min(fallback_index, len(available_topics) - 1)]]
        return chosen

    if avg_mastery >= 0.75:
        roadmap = [
            {
                "phase": "Milestone 1: Mastery Expansion",
                "focus": "Review core concepts briefly and target advanced edge-cases from your curriculum.",
                "topics": pick(ready_topics, 2, 0),
                "type": "Accelerated"
            },
            {
                "phase": "Milestone 2: Deep Concept Application",
                "focus": "Dive deep into complex topics, proofs, and algorithmic patterns.",
                "topics": pick(advanced_topics, 2, 1),
                "type": "Accelerated"
            },
            {
                "phase": "Milestone 3: Challenge and Synthesis",
                "focus": "Integrate concepts across topics and tackle constraint-based problems.",
                "topics": pick(advanced_topics, 2, -1),
                "type": "Accelerated"
            }
        ]
    else:
        roadmap = [
            {
                "phase": "Milestone 1: Prerequisite Stabilization",
                "focus": "Build strong foundations in prerequisite topics before progressing.",
                "topics": list(set([p for t in weak_topics for p in t[2]]))[:3]
                          or pick(ready_topics, 1, 0),
                "type": "Scaffolded"
            },
            {
                "phase": "Milestone 2: Core Concept Mastery",
                "focus": "Use visual analogies and worked examples to master ready-level topics.",
                "topics": pick(ready_topics, 2, 1),
                "type": "Scaffolded"
            },
            {
                "phase": "Milestone 3: Guided Progression",
                "focus": "Transition from scaffolded tutoring to independent problem-solving.",
                "topics": pick(weak_topics, 2, -1),
                "type": "Scaffolded"
            }
        ]

    return roadmap
