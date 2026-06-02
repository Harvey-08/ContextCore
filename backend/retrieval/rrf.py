def reciprocal_rank_fusion(vector_results: list, bm25_results: list, k: int = 60) -> list:
    """
    Combines vector and BM25 search results using Reciprocal Rank Fusion (RRF).
    Fuses rank lists without requiring manual weight tuning.
    Uniquely identifies items by their "id" key, falling back to a hash of "text".
    """
    rrf_scores = {}
    doc_map = {}
    
    # Process vector results and apply rank weighting
    for rank, item in enumerate(vector_results, 1):
        doc_id = item.get("id")
        if doc_id is None:
            doc_id = str(hash(item.get("text", "")))
        doc_map[doc_id] = item
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = 0.0
        rrf_scores[doc_id] += 1.0 / (k + rank)
        
    # Process BM25 results and apply rank weighting
    for rank, item in enumerate(bm25_results, 1):
        doc_id = item.get("id")
        if doc_id is None:
            doc_id = str(hash(item.get("text", "")))
        if doc_id not in doc_map:
            doc_map[doc_id] = item
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = 0.0
        rrf_scores[doc_id] += 1.0 / (k + rank)
        
    # Assemble fused list with unified scores
    fused_results = []
    for doc_id, score in rrf_scores.items():
        doc = doc_map[doc_id]
        fused_results.append({
            **doc,
            "rrf_score": score
        })
        
    # Sort by fused RRF score descending
    fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused_results
