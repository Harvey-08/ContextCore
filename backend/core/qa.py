import json
import os
from pathlib import Path
from typing import Dict
from sentence_transformers import SentenceTransformer
import chromadb
import numpy as np


class SmartQA:
    """Find relevant chapter and return context"""
    
    def __init__(self, content_dir: str = "backend/core/content"):
        self.content_dir = Path(content_dir)
        
        # Load model
        print("Loading model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
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
            
            print(f"  System Ready! Indexed {len(self.chapter_index)} topics across your curriculum.\n")
    
    def find_chapter(self, question: str) -> Dict:
        """Find most relevant chapter"""
        question_embedding = self.model.encode(question)
        
        similarities = []
        for chapter in self.chapter_index:
            similarity = np.dot(question_embedding, chapter['embedding']) / (
                np.linalg.norm(question_embedding) * np.linalg.norm(chapter['embedding'])
            )
            similarities.append({**chapter, 'similarity': float(similarity)})
        
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[0]
    
    def load_and_search(self, json_path: str, question: str, n_results: int = 10) -> list:
        """Load chapter and search"""
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            data = [data]
        
        # Create documents
        documents = []
        doc_id = 0
        
        for topic in data:
            topic_name = topic.get("topic_name", "")
            base_meta = {"topic_name": topic_name}
            
            # Topic
            documents.append({
                "id": str(doc_id),
                "text": f"Topic: {topic_name}",
                "metadata": {**base_meta, "doc_type": "topic"}
            })
            doc_id += 1
            
            # Learning objectives
            for lo in topic.get("learning_objectives", []):
                documents.append({
                    "id": str(doc_id),
                    "text": f"Learning Objective: {lo}",
                    "metadata": {**base_meta, "doc_type": "objective"}
                })
                doc_id += 1
            
            # Allowed concepts
            allowed = topic.get("allowed_concepts", [])
            if allowed:
                documents.append({
                    "id": str(doc_id),
                    "text": f"Concepts: {', '.join(allowed)}",
                    "metadata": {**base_meta, "doc_type": "concepts"}
                })
                doc_id += 1
            
            # Content blocks
            for block in topic.get("content_blocks", []):
                if block.get("text", "").strip():
                    documents.append({
                        "id": str(doc_id),
                        "text": block["text"],
                        "metadata": {**base_meta, "doc_type": f"content_{block.get('type', 'text')}"}
                    })
                    doc_id += 1
        
        # Create vector DB
        client = chromadb.EphemeralClient()
        collection = client.create_collection(name=f"temp_{int(os.urandom(4).hex(), 16)}")
        
        texts = [doc["text"] for doc in documents]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        
        collection.add(
            ids=[doc["id"] for doc in documents],
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=[doc["metadata"] for doc in documents]
        )
        
        # Search
        query_embedding = self.model.encode(question)
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results
        )
        
        # Return results
        chunks = []
        if results["documents"] and len(results["documents"]) > 0:
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                chunks.append({
                    "text": doc,
                    "type": meta.get("doc_type", ""),
                    "topic": meta.get("topic_name", ""),
                    "relevance": round(1 - distance, 3)
                })
        
        return chunks
    
    def ask(self, question: str, n_results: int = 10) -> Dict:
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
        
        # Load and search
        chunks = self.load_and_search(chapter['json_path'], question, n_results)
        
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
