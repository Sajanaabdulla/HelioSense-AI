import glob
import joblib
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from PyPDF2 import PdfReader


class KnowledgeStore:
    def __init__(self, docs_folder: Optional[str] = None, store_path: Optional[str] = None):
        root_dir = Path(__file__).resolve().parents[1]
        self.docs_folder = Path(docs_folder) if docs_folder else root_dir / 'Helia Doc'
        self.store_path = Path(store_path) if store_path else Path(__file__).resolve().parent / 'helia_vector_store.pkl'
        self.chunks: List[str] = []
        self.metadata: List[Dict[str, str]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.embeddings = None
        self._load_or_build()

    def _load_or_build(self):
        if self.store_path.exists():
            try:
                store = joblib.load(self.store_path)
                self.chunks = store['chunks']
                self.metadata = store['metadata']
                self.vectorizer = store['vectorizer']
                self.embeddings = store['embeddings']
                if self.chunks and self.vectorizer and self.embeddings is not None:
                    return
            except Exception:
                pass

        self._build_store()

    def _build_store(self):
        self.chunks = []
        self.metadata = []

        pdf_files = sorted(self.docs_folder.glob('*.pdf'))
        for pdf_file in pdf_files:
            self._ingest_pdf(pdf_file)

        if not self.chunks:
           self.chunks = ["HelioSense AI Solar Assistant"]
           self.metadata = [{
                "source": "default",
                "page": "1"
           }]

        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=20000
        )

        self.embeddings = self.vectorizer.fit_transform(self.chunks)
        self._save_store()

    def _ingest_pdf(self, path: Path):
        try:
            reader = PdfReader(str(path))
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ''
                page_text = re.sub(r'\s+', ' ', page_text).strip()
                if not page_text:
                    continue
                chunks = self._chunk_text(page_text)
                for chunk in chunks:
                    self.chunks.append(chunk)
                    self.metadata.append({
                        'source': path.name,
                        'page': str(page_number)
                    })
        except Exception:
            pass

    def _chunk_text(self, text: str, chunk_size: int = 120, overlap: int = 30) -> List[str]:
        words = text.split()
        if len(words) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = ' '.join(words[start:end]).strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    def _save_store(self):
        try:
            joblib.dump({
                'chunks': self.chunks,
                'metadata': self.metadata,
                'vectorizer': self.vectorizer,
                'embeddings': self.embeddings
            }, self.store_path)
        except Exception:
            pass

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, object]]:
        if not query or not self.chunks or self.vectorizer is None or self.embeddings is None:
            return []

        query_vec = self.vectorizer.transform([query])
        similarity = cosine_similarity(query_vec, self.embeddings)[0]
        ranked = sorted(
            enumerate(similarity), key=lambda item: item[1], reverse=True
        )
        results = []
        for index, score in ranked[:top_k]:
            if score <= 0:
                continue
            results.append({
                'chunk': self.chunks[index],
                'source': self.metadata[index]['source'],
                'page': self.metadata[index]['page'],
                'score': float(score)
            })
        return results


knowledge_store = KnowledgeStore()
