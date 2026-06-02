import json
import os
import sys
import hashlib
import re
from pathlib import Path
from typing import Dict
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
import numpy as np

# Path patching to ensure backend modules are importable
backend_path = str(Path(__file__).resolve().parent.parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)
from backend.cache.redis_client import redis_client


class SmartQA:
    """Find relevant chapter and return context"""
    
    def __init__(self, content_dir: str = "backend/core/content"):
        self.content_dir = Path(content_dir)
        
        # Load model
        print("Loading model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Load lightweight local cross-encoder reranker
        print("Loading local semantic reranker model...")
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        
        # Resolve Base Directory and Vector Store Path
        backend_dir = Path(__file__).resolve().parent.parent
        self.base_dir = backend_dir.parent
        self.vector_store_dir = self.base_dir / "vector_store"
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Persistent Chroma DB Client with Ephemeral Fallback
        print(f"Connecting to Persistent ChromaDB at {self.vector_store_dir}...")
        try:
            self.chroma_client = chromadb.PersistentClient(path=str(self.vector_store_dir))
        except Exception as chroma_err:
            print(f"[CRITICAL ERROR] Failed to initialize Persistent ChromaDB: {chroma_err}")
            print("[Persistent ChromaDB Fallback] Initializing Ephemeral Client to keep application online...")
            self.chroma_client = chromadb.EphemeralClient()
        
        # Create chapter index by recursively scanning folders
        self.chapter_index = []
        print(f"Scanning {self.content_dir} for curriculum files...")
        
        if self.content_dir.exists():
            for f in self.content_dir.rglob("*.json"):
                # Skip backend mapping files or non-curriculum JSONs
                if f.name.startswith("chapter_mapping") or "json_output" not in str(f.parent):
                    continue
                
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if isinstance(data, dict):
                            data = [data]
                        
                        # Use topics as chapter names for the index
                        for topic in data:
                            topic_name = topic.get("topic_name", "Unknown Topic")
                            unit = topic.get("unit", "General")
                            
                            # Create a rich search name: "Grade 7 > Math > Rational Numbers > Topic Name"
                            # We can infer the hierarchy from the path
                            rel_path = f.relative_to(self.content_dir)
                            hierarchy = " > ".join(rel_path.parts[:-2]) # Grade > Subject > Book
                            
                            search_name = f"{hierarchy} : {topic_name}"
                            
                            self.chapter_index.append({
                                'chapter_name': search_name,
                                'display_name': topic_name,
                                'hierarchy': hierarchy,
                                'json_file': f.name,
                                'json_path': str(f)
                            })
                except Exception as e:
                    print(f"  Error indexing {f.name}: {e}")
        
        if not self.chapter_index:
             print("  WARNING: No curriculum files found in content directory!")
        else:
            # Create chapter embeddings
            print(f"  Creating embeddings for {len(self.chapter_index)} topics...")
            chapter_names = [ch['chapter_name'] for ch in self.chapter_index]
            chapter_embeddings = self.model.encode(chapter_names, show_progress_bar=False)
            for i, chapter in enumerate(self.chapter_index):
                chapter['embedding'] = chapter_embeddings[i]
            
            # Startup persistent ChromaDB indexing check for newly added collections
            print("\n  [Startup Vector Store Setup] checking for new curriculum collections...")
            for chapter in self.chapter_index:
                self.index_curriculum_to_chroma(chapter['json_path'])
            print("  [Startup Vector Store Setup] Complete!\n")
            
            print(f"  System Ready! Indexed {len(self.chapter_index)} topics across your curriculum.\n")
            
    def _extract_username_from_path(self, json_path: str) -> str:
        """Extract the username from the curriculum JSON path for multi-user vector isolation."""
        try:
            path_obj = Path(json_path).resolve()
            # If the path contains 'generated_contents', the next part is the username
            parts = path_obj.parts
            if "generated_contents" in parts:
                idx = parts.index("generated_contents")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        except Exception:
            pass
        return "default"

    def get_scoped_collection_name(self, json_path: str) -> str:
        """Get user-scoped collection name to ensure absolute multi-user isolation."""
        username = self._extract_username_from_path(json_path)
        filename = Path(json_path).name
        raw_name = f"user_{username}_{filename}"
        return self.sanitize_collection_name(raw_name)

    def sanitize_collection_name(self, name: str) -> str:
        """Sanitize filenames to be compliant with ChromaDB collection name standards."""
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        sanitized = sanitized[:63]
        if not sanitized[0].isalnum():
            sanitized = "col_" + sanitized[1:]
        if not sanitized[-1].isalnum():
            sanitized = sanitized[:-1] + "0"
        return sanitized

    def get_curriculum_version(self) -> str:
        """Compute an 8-character MD5 version hash of active curriculum directories."""
        hasher = hashlib.md5()
        sorted_ch = sorted(self.chapter_index, key=lambda x: x['json_path'])
        if not sorted_ch:
            return "empty"
        for ch in sorted_ch:
            hasher.update(ch['json_path'].encode('utf-8'))
            if os.path.exists(ch['json_path']):
                mtime = os.path.getmtime(ch['json_path'])
                hasher.update(str(mtime).encode('utf-8'))
        return hasher.hexdigest()[:8]

    def index_curriculum_to_chroma(self, json_path: str, metadata: dict = None):
        """Index a single curriculum JSON file into Persistent ChromaDB if not already indexed."""
        import time
        try:
            json_path_obj = Path(json_path)
            if not json_path_obj.exists():
                print(f"[Vector Store] Error: Curriculum file not found at {json_path}")
                return
                
            col_name = self.get_scoped_collection_name(json_path)
            
            # Check if collection exists and contains vectors
            try:
                collection = self.chroma_client.get_collection(name=col_name)
                count = collection.count()
                if count > 0:
                    # Already indexed, skip!
                    return
            except Exception:
                # Collection doesn't exist yet, create it
                collection = self.chroma_client.create_collection(name=col_name)
                
            print(f"[Vector Store] Generating embeddings once for {json_path_obj.name} -> Chroma collection: '{col_name}'...")
            start_time = time.time()
            
            with open(json_path_obj, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            if isinstance(data, dict):
                data = [data]
                
            documents = []
            doc_id = 0
            
            # Extract basic curriculum attributes from the file path if metadata not present
            if metadata is None:
                metadata = {}
                parts = json_path_obj.resolve().parts
                for i, part in enumerate(parts):
                    if part.startswith("Grade_") and i + 1 < len(parts):
                        metadata["grade"] = part.replace("Grade_", "")
                        metadata["subject"] = parts[i+1].replace("_", " ")
                        break
            
            grade = metadata.get("grade", "Unknown")
            subject = metadata.get("subject", "General")
            
            for topic in data:
                topic_name = topic.get("topic_name", "")
                ped_profile = topic.get("pedagogical_profile", {})
                reasoning_style = ped_profile.get("reasoning_style", "Analytical")
                content_nature = ped_profile.get("content_nature", "Theoretical")
                assessment_style = ped_profile.get("assessment_style", "Conceptual Recall")
                
                base_meta = {
                    "topic": topic_name,
                    "subtopic": topic.get("unit", "hegp106"),
                    "reasoning_style": reasoning_style,
                    "content_nature": content_nature,
                    "assessment_style": assessment_style,
                    "grade": str(grade),
                    "subject": str(subject),
                    "json_path": str(json_path),
                    "chapter_name": json_path_obj.stem
                }
                
                # Add topic document
                documents.append({
                    "id": f"{col_name}_{doc_id}",
                    "text": f"Topic: {topic_name}",
                    "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "topic"}
                })
                doc_id += 1
                
                # Add learning objectives
                for lo in topic.get("learning_objectives", []):
                    documents.append({
                        "id": f"{col_name}_{doc_id}",
                        "text": f"Learning Objective: {lo}",
                        "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "objective"}
                    })
                    doc_id += 1
                    
                # Add allowed concepts
                allowed = topic.get("allowed_concepts", [])
                if allowed:
                    documents.append({
                        "id": f"{col_name}_{doc_id}",
                        "text": f"Concepts: {', '.join(allowed)}",
                        "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "concepts"}
                    })
                    doc_id += 1
                    
                # Add content blocks
                for block in topic.get("content_blocks", []):
                    if block.get("text", "").strip():
                        text_content = block["text"]
                        doc_type = f"content_{block.get('type', 'text')}"
                        
                        difficulty_val = "Intermediate"
                        lower_text = text_content.lower()
                        
                        beginner_keywords = ["simpler", "basic", "intro", "introduction", "outline", "simple", "overview"]
                        advanced_keywords = ["analyze", "critique", "evaluation", "complex", "synthesis", "framework", "edge case"]
                        
                        if reasoning_style in ["Symbolic", "Procedural"]:
                            advanced_keywords.extend(["proof", "prove", "proofs", "derivation", "identity", "theorem", "lemma", "verify", "^2", "formula"])
                            beginner_keywords.extend(["visualise", "visualize", "diagram", "illustrate", "analogy", "picture"])
                        elif reasoning_style in ["Narrative", "Interpretive"]:
                            advanced_keywords.extend(["historiography", "critical review", "primary source", "synthesis", "interpretive", "hermeneutic", "perspective"])
                            beginner_keywords.extend(["story", "narrative", "timeline", "event", "main"])
                        elif reasoning_style in ["Causal"]:
                            advanced_keywords.extend(["mechanism", "correlation", "causation", "systemic impact", "catalyst", "feedback loop"])
                            beginner_keywords.extend(["cause", "result", "happen", "effect"])
                        elif reasoning_style in ["Analytical", "Comparative"]:
                            advanced_keywords.extend(["contrasting", "differentiates", "paradigms", "methodology", "thesis"])
                            beginner_keywords.extend(["compare", "difference", "similar", "like"])

                        is_advanced = any(w in lower_text for w in advanced_keywords)
                        is_beginner = any(w in lower_text for w in beginner_keywords)
                        
                        if is_advanced:
                            difficulty_val = "Advanced"
                        elif is_beginner:
                            difficulty_val = "Beginner"
                            
                        prereqs = []
                        if any(w in lower_text for w in ["recall", "remember", "previously", "prerequisite", "first understand"]):
                           prereqs.append("foundational")
                           
                        documents.append({
                            "id": f"{col_name}_{doc_id}",
                            "text": text_content,
                            "metadata": {
                                **base_meta,
                                "difficulty": difficulty_val,
                                "prerequisites": ",".join(prereqs),
                                "doc_type": doc_type
                            }
                        })
                        doc_id += 1
                        
            if not documents:
                return
                
            texts = [doc["text"] for doc in documents]
            embeddings = self.model.encode(texts, show_progress_bar=False)
            
            collection.add(
                ids=[doc["id"] for doc in documents],
                documents=texts,
                embeddings=embeddings.tolist(),
                metadatas=[doc["metadata"] for doc in documents]
            )
            
            duration_ms = (time.time() - start_time) * 1000
            print(f"[Vector Store] Finished indexing '{col_name}' ({len(documents)} chunks) in {duration_ms:.2f}ms.")
        except Exception as e:
            print(f"[Vector Store Ingestion Error] Failed to index {json_path}: {e}")
    
    def find_chapter(self, question: str) -> Dict:
        """Find most relevant chapter using Redis Chapter Cache or Cosine Similarity."""
        normalized_q = " ".join(question.lower().split())
        cache_key = f"chapter:{normalized_q}"
        
        cached = redis_client.get_json(cache_key)
        if cached:
            print(f"[Redis Hit] Chapter Routing cache hit for: '{normalized_q}'")
            return cached
            
        question_embedding = self.model.encode(question)
        
        similarities = []
        for chapter in self.chapter_index:
            similarity = np.dot(question_embedding, chapter['embedding']) / (
                np.linalg.norm(question_embedding) * np.linalg.norm(chapter['embedding'])
            )
            similarities.append({**chapter, 'similarity': float(similarity)})
        
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        best_chapter = similarities[0]
        
        # Prepare serializable version without raw numpy/embedding
        redis_copy = {k: v for k, v in best_chapter.items() if k != 'embedding'}
        redis_client.set_json(cache_key, redis_copy, ex_seconds=86400) # 24 hours
        
        return best_chapter
    
    def _resolve_topic_level(self, user_id, topic_name: str, fallback_difficulty: str) -> str:
        """Resolve per-topic learner level from PostgreSQL mastery table, falling back to global level."""
        if not user_id or not topic_name:
            return fallback_difficulty
        try:
            from database import SessionLocal, TopicMastery
            db = SessionLocal()
            record = db.query(TopicMastery).filter(
                TopicMastery.user_id == user_id,
                TopicMastery.topic_name == topic_name
            ).first()
            db.close()
            if record:
                return record.current_estimated_level
        except Exception:
            pass
        return fallback_difficulty

    def load_and_search(self, json_path: str, question: str, n_results: int = 10, difficulty: str = "Beginner", user_id=None) -> list:
        """Load chapter from Persistent ChromaDB, fused with RRF, Cross-Encoder, and Mastery Boosting."""
        import time
        start_time = time.time()
        
        normalized_q = " ".join(question.lower().split())
        
        # Resolve adaptive learner profiles of this user to include in the retrieval hash
        mastery_details = ""
        if user_id:
            try:
                from backend.core.database import SessionLocal, TopicMastery
                db = SessionLocal()
                records = db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
                db.close()
                mastery_details = "|".join(
                    f"{r.topic_name}:{r.mastery_score}:{r.confidence_score}:{r.current_estimated_level}" 
                    for r in records
                )
            except Exception:
                pass
                
        # Retrieve curriculum version to prevent stale cache on updates
        curriculum_version = self.get_curriculum_version()
        
        # Secure SHA-256 retrieval hash of all adaptive query context parameters including version
        hash_input = f"{normalized_q}:{difficulty}:{user_id}:{n_results}:{json_path}:{mastery_details}:{curriculum_version}"
        question_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        cache_key = f"retrieve:{question_hash}"
        
        # Look up Redis Retrieval Cache
        cached_payload = redis_client.get_json(cache_key)
        if cached_payload:
            print(f"[Redis Hit] Retrieval cache hit for: '{normalized_q}'")
            chunks = cached_payload.get("chunks", [])
            
            # Observability logging for cached hits
            try:
                from backend.core.database import SessionLocal, RetrievalLog
                db_log = SessionLocal()
                
                user_id_val = user_id if user_id else (self.current_user_id if hasattr(self, "current_user_id") else None)
                retrieved_chunk_ids = [c.get("topic", "") + "_" + str(i) for i, c in enumerate(chunks)]
                selected_chunk_ids = [c["topic"] + "_" + c["type"] for c in chunks]
                
                matching_chapters = [ch for ch in self.chapter_index if ch['json_path'] == json_path]
                ch_meta = matching_chapters[0] if matching_chapters else self.find_chapter(question)
                
                retrieval_trace = {
                    "selected_chapter": ch_meta.get('chapter_name', "Unknown"),
                    "cache_status": "[Redis Cache Hit]",
                    "retrieved_chunk_ids": retrieved_chunk_ids,
                    "final_selected_chunks": selected_chunk_ids
                }
                
                pedagogical_trace = {
                    "learner_mastery_level": difficulty,
                    "cache_hit": True
                }
                
                log_record = RetrievalLog(
                    user_id=user_id_val,
                    query=question,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    rerank_scores=[c.get("relevance", 0.0) for c in chunks],
                    selected_chunk_ids=selected_chunk_ids,
                    learner_level=difficulty,
                    retrieval_latency=1.5,
                    retrieval_trace=retrieval_trace,
                    pedagogical_trace=pedagogical_trace
                )
                db_log.add(log_record)
                db_log.commit()
                db_log.close()
                print(f"[Observability Logged - Cache Hit] Query: '{question}', Latency: 1.50ms")
            except Exception as db_err:
                print(f"[Warning] Failed to write cached retrieval logs to database: {db_err}")
                
            return chunks

        # Cache Miss: Proceed to full pipeline using Persistent ChromaDB
        # Load JSON (Extremely fast, used for BM25 mapping)
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            data = [data]
        
        documents = []
        doc_id = 0
        
        for topic in data:
            topic_name = topic.get("topic_name", "")
            
            # Extract pedagogical profile keys if present
            ped_profile = topic.get("pedagogical_profile", {})
            reasoning_style = ped_profile.get("reasoning_style", "Analytical")
            content_nature = ped_profile.get("content_nature", "Theoretical")
            assessment_style = ped_profile.get("assessment_style", "Conceptual Recall")
            
            base_meta = {
                "topic": topic_name, 
                "subtopic": topic.get("unit", "hegp106"),
                "reasoning_style": reasoning_style,
                "content_nature": content_nature,
                "assessment_style": assessment_style
            }
            
            # Topic
            documents.append({
                "id": str(doc_id),
                "text": f"Topic: {topic_name}",
                "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "topic"}
            })
            doc_id += 1
            
            # Learning objectives
            for lo in topic.get("learning_objectives", []):
                documents.append({
                    "id": str(doc_id),
                    "text": f"Learning Objective: {lo}",
                    "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "objective"}
                })
                doc_id += 1
            
            # Allowed concepts
            allowed = topic.get("allowed_concepts", [])
            if allowed:
                documents.append({
                    "id": str(doc_id),
                    "text": f"Concepts: {', '.join(allowed)}",
                    "metadata": {**base_meta, "difficulty": "Beginner", "prerequisites": "", "doc_type": "concepts"}
                })
                doc_id += 1
            
            # Content blocks with dynamic metadata enrichment
            for block in topic.get("content_blocks", []):
                if block.get("text", "").strip():
                    text_content = block["text"]
                    doc_type = f"content_{block.get('type', 'text')}"
                    
                    # Classify difficulty dynamically based on content and pedagogical profile
                    difficulty_val = "Intermediate"
                    lower_text = text_content.lower()
                    
                    # Baseline keywords
                    beginner_keywords = ["simpler", "basic", "intro", "introduction", "outline", "simple", "overview"]
                    advanced_keywords = ["analyze", "critique", "evaluation", "complex", "synthesis", "framework", "edge case"]
                    
                    if reasoning_style in ["Symbolic", "Procedural"]:
                        advanced_keywords.extend(["proof", "prove", "proofs", "derivation", "identity", "theorem", "lemma", "verify", "^2", "formula"])
                        beginner_keywords.extend(["visualise", "visualize", "diagram", "illustrate", "analogy", "picture"])
                    elif reasoning_style in ["Narrative", "Interpretive"]:
                        advanced_keywords.extend(["historiography", "critical review", "primary source", "synthesis", "interpretive", "hermeneutic", "perspective"])
                        beginner_keywords.extend(["story", "narrative", "timeline", "event", "main"])
                    elif reasoning_style in ["Causal"]:
                        advanced_keywords.extend(["mechanism", "correlation", "causation", "systemic impact", "catalyst", "feedback loop"])
                        beginner_keywords.extend(["cause", "result", "happen", "effect"])
                    elif reasoning_style in ["Analytical", "Comparative"]:
                        advanced_keywords.extend(["contrasting", "differentiates", "paradigms", "methodology", "thesis"])
                        beginner_keywords.extend(["compare", "difference", "similar", "like"])

                    is_advanced = any(w in lower_text for w in advanced_keywords)
                    is_beginner = any(w in lower_text for w in beginner_keywords)
                    
                    if is_advanced:
                        difficulty_val = "Advanced"
                    elif is_beginner:
                        difficulty_val = "Beginner"
                    
                    # Check prerequisites
                    prereqs = []
                    if any(w in lower_text for w in ["recall", "remember", "previously", "prerequisite", "first understand"]):
                        prereqs.append("foundational")
                        
                    documents.append({
                        "id": str(doc_id),
                        "text": text_content,
                        "metadata": {
                            **base_meta,
                            "difficulty": difficulty_val,
                            "prerequisites": ",".join(prereqs),
                            "doc_type": doc_type
                        }
                    })
                    doc_id += 1
        
        # Load persistent collection
        col_name = self.get_scoped_collection_name(json_path)
        try:
            collection = self.chroma_client.get_collection(name=col_name)
            if collection.count() == 0:
                self.index_curriculum_to_chroma(json_path)
                collection = self.chroma_client.get_collection(name=col_name)
        except Exception:
            self.index_curriculum_to_chroma(json_path)
            collection = self.chroma_client.get_collection(name=col_name)
        
        # Search: Perform Hybrid BM25 + Vector Retrieval and fuse with RRF
        try:
            import sys
            # Ensure retrieval is in python path
            backend_path = str(Path(__file__).resolve().parent.parent)
            if backend_path not in sys.path:
                sys.path.append(backend_path)
            
            from retrieval.bm25_engine import BM25Engine
            from retrieval.rrf import reciprocal_rank_fusion
            
            bm25_engine = BM25Engine(documents)
        except Exception as err:
            print(f"[Warning] Failed to initialize BM25Engine: {err}")
            bm25_engine = None

        query_embedding = self.model.encode(question)
        candidate_count = min(20, len(documents))
        
        # 1. Vector Search
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=candidate_count
        )
        
        vector_candidates = []
        if results["documents"] and len(results["documents"]) > 0:
            for doc_idx, doc, meta, distance in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                raw_id = doc_idx.replace(f"{col_name}_", "")
                vector_candidates.append({
                    "id": raw_id,
                    "text": doc,
                    "metadata": meta,
                    "distance": float(distance)
                })
        
        # 2. BM25 search
        bm25_candidates = []
        if bm25_engine:
            bm25_candidates = bm25_engine.retrieve(question, top_n=candidate_count)
            
        # 3. Reciprocal Rank Fusion (RRF)
        fused_candidates = reciprocal_rank_fusion(vector_candidates, bm25_candidates, k=60)
        
        # Crop fused pool to top 20 for Semantic Reranking
        top_fused = fused_candidates[:20]
        
        # Return results
        chunks = []
        candidates = []
        
        if top_fused:
            # Semantic Reranking with Cross-Encoder
            pairs = [[question, cand["text"]] for cand in top_fused]
            rerank_scores = self.reranker.predict(pairs)
            
            for idx, score in enumerate(rerank_scores):
                top_fused[idx]["rerank_score"] = float(score)
                candidates.append(top_fused[idx])
            
            # Metadata Filtering & Topic-Mastery-Aware Adaptive Boosting with structured boost reasoning
            for idx, item in enumerate(candidates):
                meta = item["metadata"]
                doc_type = meta.get("doc_type", "")
                chunk_diff = meta.get("difficulty", "Intermediate")
                chunk_prereq = meta.get("prerequisites", "")
                text_lower = item["text"].lower()
                chunk_topic = meta.get("topic", "")
                
                r_style = meta.get("reasoning_style", "Analytical")
                c_nature = meta.get("content_nature", "Theoretical")

                # Resolve per-topic level from DB if user_id is available
                effective_level = self._resolve_topic_level(user_id, chunk_topic, difficulty)

                boosts_applied = []
                # Boost specific block types matching learner cognitive strategy (Topic-Level Adaptive Retrieval)
                if effective_level == "Beginner":
                    # Boost beginner difficulty chunks
                    if chunk_diff == "Beginner":
                        candidates[idx]["rerank_score"] += 1.5
                        boosts_applied.append("Beginner pacing difficulty (+1.5)")
                    # Boost prerequisite chunks - foundational recall
                    if chunk_prereq != "":
                        candidates[idx]["rerank_score"] += 1.0
                        boosts_applied.append("Foundational prerequisite block (+1.0)")
                    # Boost examples and visual analogies
                    if "example" in doc_type:
                        candidates[idx]["rerank_score"] += 1.0
                        boosts_applied.append("Worked example block (+1.0)")
                    
                    # Dynamic profile-driven beginner boosting:
                    if r_style in ["Symbolic", "Procedural", "Causal"]:
                        if any(w in text_lower for w in ["visualise", "visualize", "diagram", "illustrate", "analogy", "picture"]):
                            candidates[idx]["rerank_score"] += 0.8
                            boosts_applied.append("Beginner visual analogy (+0.8)")
                    elif r_style in ["Narrative", "Interpretive"]:
                        if any(w in text_lower for w in ["summary", "timeline", "chronology", "overview", "story"]):
                            candidates[idx]["rerank_score"] += 0.8
                            boosts_applied.append("Beginner historical overview (+0.8)")

                elif effective_level == "Advanced":
                    # Boost advanced chunks
                    if chunk_diff == "Advanced":
                        candidates[idx]["rerank_score"] += 1.0
                        boosts_applied.append("Advanced curriculum challenge (+1.0)")
                    
                    # Dynamic profile-driven advanced boosting:
                    if r_style in ["Symbolic", "Procedural"]:
                        # Boost proofs, derivations, formulas
                        if any(w in text_lower for w in ["proof", "prove", "proofs", "derivation", "identity", "theorem", "lemma", "formula"]):
                            candidates[idx]["rerank_score"] += 1.5
                            boosts_applied.append("Rigor proof formulation (+1.5)")
                    elif r_style in ["Narrative", "Interpretive", "Analytical"]:
                        # Boost deep critique, citations, sources, historiography
                        if any(w in text_lower for w in ["critique", "source", "historiography", "perspective", "framework", "synthesis", "methodology"]):
                            candidates[idx]["rerank_score"] += 1.5
                            boosts_applied.append("Historiography source analysis (+1.5)")
                    elif r_style in ["Causal"]:
                        # Boost feedback loops, mechanisms, multi-variable impact
                        if any(w in text_lower for w in ["mechanism", "feedback loop", "catalyst", "impact", "correlation", "causation"]):
                            candidates[idx]["rerank_score"] += 1.5
                            boosts_applied.append("Causal mechanism loop (+1.5)")

                    # Boost optimization concepts
                    if any(w in text_lower for w in ["optimization", "efficient", "faster", "fast"]):
                        candidates[idx]["rerank_score"] += 1.0
                        boosts_applied.append("Efficiency optimization (+1.0)")
                    # Boost edge cases and boundary conditions
                    if any(w in text_lower for w in ["edge case", "exception", "boundary", "constraint", "disallowed"]):
                        candidates[idx]["rerank_score"] += 1.0
                        boosts_applied.append("Boundary condition edge-case (+1.0)")
                else:
                    # Intermediate (balanced) - definitions and worked steps
                    if chunk_diff == "Intermediate":
                        candidates[idx]["rerank_score"] += 0.5
                        boosts_applied.append("Intermediate core lesson (+0.5)")
                    if "definition" in doc_type:
                        candidates[idx]["rerank_score"] += 0.3
                        boosts_applied.append("Textbook definition lookup (+0.3)")
                
                # Expose retrieval explanation
                if boosts_applied:
                    candidates[idx]["boost_reason"] = f"Boosted because of {', '.join(boosts_applied)} matching learner level {effective_level}."
                else:
                    candidates[idx]["boost_reason"] = f"Aligned with standard {effective_level} curriculum structure."
            
            # Sort candidates by final boosted score descending
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            # Crop to target n_results
            for cand in candidates[:n_results]:
                doc_type = cand["metadata"].get("doc_type", "")
                relevance = round(1 / (1 + np.exp(-cand["rerank_score"])), 3)
                
                chunks.append({
                    "text": cand["text"],
                    "type": doc_type,
                    "topic": cand["metadata"].get("topic", ""),
                    "subtopic": cand["metadata"].get("subtopic", ""),
                    "difficulty": cand["metadata"].get("difficulty", "Intermediate"),
                    "relevance": relevance,
                    "reasoning_style": cand["metadata"].get("reasoning_style", "Analytical"),
                    "content_nature": cand["metadata"].get("content_nature", "Theoretical"),
                    "assessment_style": cand["metadata"].get("assessment_style", "Conceptual Recall"),
                    "boost_reason": cand.get("boost_reason", "")
                })
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Write Observability logs into PostgreSQL
        try:
            from backend.core.database import SessionLocal, RetrievalLog
            db = SessionLocal()
            
            user_id_val = None
            if hasattr(self, "current_user_id"):
                user_id_val = self.current_user_id
            
            retrieved_chunk_ids = [c["metadata"].get("topic", "") + "_" + str(i) for i, c in enumerate(candidates)]
            rerank_scores_list = [c["rerank_score"] for c in candidates]
            selected_chunk_ids = [c["topic"] + "_" + c["type"] for c in chunks]
            
            # Resolve matching chapter from memory for trace explainability
            matching_chapters = [ch for ch in self.chapter_index if ch['json_path'] == json_path]
            ch_meta = matching_chapters[0] if matching_chapters else self.find_chapter(question)
            
            # Detailed traces for observational logging (Explainability & Traceability Feature 4)
            retrieval_trace = {
                "selected_chapter": ch_meta.get('chapter_name', "Unknown"),
                "chapter_similarity": round(ch_meta.get('similarity', 0.0), 3),
                "retrieved_chunk_ids": retrieved_chunk_ids[:10],
                "vector_similarity_scores": {v["id"]: round(1.0 - v["distance"], 3) for v in vector_candidates[:10]},
                "bm25_scores": {b["id"]: round(b["bm25_score"], 3) for b in bm25_candidates[:10]},
                "fused_rrf_ranks": {c["id"]: i for i, c in enumerate(fused_candidates[:10], 1)},
                "cross_encoder_scores": {c["id"]: round(c["rerank_score"], 3) for c in candidates[:10]},
                "final_selected_chunks": selected_chunk_ids
            }
            
            pedagogical_trace = {
                "learner_mastery_level": difficulty,
                "resolved_effective_level": self._resolve_topic_level(user_id_val, chunks[0]["topic"] if chunks else None, difficulty),
                "applied_boost_reasons": {c["topic"] + "_" + c["type"]: c.get("boost_reason", "") for c in chunks}
            }
            
            log_record = RetrievalLog(
                user_id=user_id_val,
                query=question,
                retrieved_chunk_ids=retrieved_chunk_ids[:10],
                rerank_scores=rerank_scores_list[:10],
                selected_chunk_ids=selected_chunk_ids,
                learner_level=difficulty,
                retrieval_latency=round(latency_ms, 2),
                retrieval_trace=retrieval_trace,
                pedagogical_trace=pedagogical_trace
            )
            db.add(log_record)
            db.commit()
            db.close()
            print(f"[Observability Logged] Query: '{question}', Level: {difficulty}, Latency: {latency_ms:.2f}ms")
        except Exception as db_err:
            print(f"[Warning] Failed to write retrieval logs to database: {db_err}")
            
        # Store computed result in Redis Cache for 12 hours
        cache_payload = {
            "chunks": chunks,
            "retrieval_scores": [c["relevance"] for c in chunks],
            "selected_chapter": json_path
        }
        redis_client.set_json(cache_key, cache_payload, ex_seconds=43200) # 12 hours
            
        return chunks
    
    def ask(self, question: str, n_results: int = 10, difficulty: str = "Beginner", user_id=None) -> Dict:
        """
        Ask a question and get chapter + context
        
        Returns:
            {
                'question': str,
                'chapter': str,
                'chapter_file': str,
                'chapter_relevance': float,
                'chunks': list,
                'context': str  # Formatted for LLM
            }
        """
        
        # Find chapter
        chapter = self.find_chapter(question)
        
        # Load and search (with reranker, topic-mastery level parameters, and user_id for per-concept boosting)
        chunks = self.load_and_search(chapter['json_path'], question, n_results, difficulty, user_id=user_id)
        
        # Format context for LLM
        context_parts = [
            "=" * 70,
            f"CONTEXT FROM CURRICULUM: {chapter['hierarchy']}",
            "=" * 70,
            f"\nTOPIC/CHAPTER: {chapter['display_name']}",
            f"RELEVANCE: {chapter['similarity']:.1%}",
            f"\nQUESTION: {question}",
            "\n" + "=" * 70,
            "\nRELEVANT CONTENT:\n"
        ]
        
        for i, chunk in enumerate(chunks, 1):
            doc_type = chunk['type'].replace('content_', '').upper()
            context_parts.append(f"\n[{doc_type} #{i}] (Relevance: {chunk['relevance']:.1%})")
            context_parts.append(chunk['text'])
        
        context_parts.append("\n" + "=" * 70)
        context_parts.append("END OF CONTEXT")
        context_parts.append("=" * 70)
        
        return {
            'question': question,
            'chapter': chapter['chapter_name'],
            'chapter_file': chapter['json_file'],
            'chapter_relevance': round(chapter['similarity'], 3),
            'chunks': chunks,
            'context': "\n".join(context_parts)
        }


def main():
    """Interactive Q&A"""
    print("=" * 70)
    print(" SMART Q&A - Dynamic Curriculum Search")
    print("=" * 70)
    
    qa = SmartQA()
    
    print("\n Ready! Ask any question.")
    print("   Type 'quit' to exit\n")
    
    while True:
        question = input(" Question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("\n Goodbye!")
            break
        
        if not question:
            continue
        
        try:
            result = qa.ask(question, n_results=8)
            
            print(f"\n{'='*70}")
            print("RESULT")
            print('='*70)
            print(f"\n Chapter: {result['chapter']}")
            print(f" File: {result['chapter_file']}")
            print(f" Relevance: {result['chapter_relevance']:.1%}")
            print(f" Found {len(result['chunks'])} relevant chunks")
            
            # Show top 3 chunks
            print(f"\n{'='*70}")
            print("TOP 3 CHUNKS")
            print('='*70)
            for i, chunk in enumerate(result['chunks'][:3], 1):
                doc_type = chunk['type'].replace('content_', '').upper()
                print(f"\n{i}. [{doc_type}] (Relevance: {chunk['relevance']:.1%})")
                text = chunk['text']
                if len(text) > 200:
                    text = text[:200] + "..."
                print(f"   {text}")
            
            # Ask if user wants full context
            show_context = input(f"\n{'='*70}\nShow full context for LLM? (y/n): ").strip().lower()
            if show_context == 'y':
                print(f"\n{'='*70}")
                print("CONTEXT FOR YOUR LLM")
                print('='*70)
                print(result['context'])
                print(f"\n Copy this context and use it in your LLM code!")
            
            print()
            
        except Exception as e:
            print(f"\n Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
