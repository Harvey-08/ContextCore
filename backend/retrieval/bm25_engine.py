import re
from rank_bm25 import BM25Okapi

class BM25Engine:
    """
    Lexical retrieval engine using Rank-BM25.
    Tokenizes curriculum text chunks and supports exact matching for textbook terminology,
    formulas, abbreviations, and vocabulary.
    """
    def __init__(self, chunks: list):
        self.chunks = chunks
        self.corpus = [c["text"] for c in chunks]
        self.tokenized_corpus = [self._tokenize(text) for text in self.corpus]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _tokenize(self, text: str) -> list:
        """Alphanumeric word tokenizer, lowercased, preserving symbols."""
        if not text:
            return []
        text = text.lower()
        # Extract alphanumeric words and mathematical operators to support lexical search in formulas
        tokens = re.findall(r'\b\w+\b|[+\-*/=^]', text)
        return tokens

    def retrieve(self, query: str, top_n: int = 10) -> list:
        """
        Search lexical index and return chunks with their scores and original indices.
        """
        tokenized_query = self._tokenize(query)
        if not tokenized_query or not self.chunks:
            return []
        
        scores = self.bm25.get_scores(tokenized_query)
        
        results = []
        for idx, chunk in enumerate(self.chunks):
            score = float(scores[idx])
            results.append({
                **chunk,
                "bm25_score": score,
                "index": idx
            })
        
        # Sort by BM25 score descending
        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_n]
