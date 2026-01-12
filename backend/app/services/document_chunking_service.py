"""
Document Chunking Service for large documents.
Splits documents into chunks and provides semantic search via embeddings.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from ..config import settings
from ..models.document_cache import DocumentCache, DocumentChunk

logger = logging.getLogger(__name__)


class DocumentChunkingService:
    """Service for chunking large documents and semantic search."""

    # 10-K section headers for intelligent splitting
    SECTION_PATTERNS = [
        (r"(?i)ITEM\s*1[.\s]*(?:BUSINESS|Description)", "Item 1 - Business"),
        (r"(?i)ITEM\s*1A[.\s]*RISK", "Item 1A - Risk Factors"),
        (r"(?i)ITEM\s*2[.\s]*PROPERTIES", "Item 2 - Properties"),
        (r"(?i)ITEM\s*7[.\s]*MANAGEMENT", "Item 7 - MD&A"),
        (r"(?i)ITEM\s*7A[.\s]*QUANTITATIVE", "Item 7A - Market Risk"),
        (r"(?i)ITEM\s*8[.\s]*FINANCIAL", "Item 8 - Financial Statements"),
        (r"(?i)ITEM\s*9A[.\s]*CONTROLS", "Item 9A - Controls"),
        (r"(?i)ITEM\s*10[.\s]*DIRECTORS", "Item 10 - Directors"),
        (r"(?i)ITEM\s*11[.\s]*EXECUTIVE", "Item 11 - Executive Compensation"),
    ]

    def __init__(self, db: Session):
        self.db = db
        self.target_tokens = settings.doc_chunk_target_tokens
        self.max_tokens = settings.doc_chunk_max_tokens
        self.overlap_tokens = settings.doc_chunk_overlap_tokens
        self.context_limit = settings.doc_context_window_limit
        self._model = None
        self._embedding_model_name = "all-MiniLM-L6-v2"

    def _get_embedding_model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._embedding_model_name)
                logger.info(f"Loaded embedding model: {self._embedding_model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model

    def needs_chunking(self, token_estimate: int) -> bool:
        """Check if a document needs to be chunked."""
        return token_estimate > self.context_limit

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (4 chars per token approximation)."""
        return len(text) // 4

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_document(
        self, text: str, document_type: str = "generic"
    ) -> List[Dict[str, Any]]:
        """
        Split a document into chunks.

        Args:
            text: Full document text
            document_type: Type of document (sec_10k, ir_pdf, generic)

        Returns:
            List of chunk dicts with section_name, chunk_text, chunk_tokens
        """
        chunks = []

        if document_type == "sec_10k":
            # Try to split by 10-K sections first
            section_chunks = self._split_by_sections(text)
            if section_chunks:
                # Further split large sections
                for section_name, section_text in section_chunks:
                    section_token_est = self._estimate_tokens(section_text)
                    if section_token_est > self.max_tokens:
                        # Split this section into smaller chunks
                        sub_chunks = self._split_by_size(section_text, section_name)
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append({
                            "section_name": section_name,
                            "chunk_text": section_text,
                            "chunk_tokens": section_token_est,
                        })
            else:
                # Fallback to size-based splitting
                chunks = self._split_by_size(text, None)
        else:
            # Generic size-based splitting
            chunks = self._split_by_size(text, None)

        # Add chunk indices
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i

        return chunks

    def _split_by_sections(self, text: str) -> List[Tuple[str, str]]:
        """Split 10-K text by section headers."""
        sections = []

        # Find all section positions
        section_positions = []
        for pattern, section_name in self.SECTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                section_positions.append((match.start(), section_name))

        if not section_positions:
            return []

        # Sort by position
        section_positions.sort(key=lambda x: x[0])

        # Extract section content
        for i, (start, name) in enumerate(section_positions):
            if i + 1 < len(section_positions):
                end = section_positions[i + 1][0]
            else:
                end = len(text)

            section_text = text[start:end].strip()
            if section_text and len(section_text) > 100:  # Skip tiny sections
                sections.append((name, section_text))

        return sections

    def _split_by_size(
        self, text: str, section_name: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Split text into chunks by target size with overlap."""
        chunks = []
        sentences = self._split_into_sentences(text)

        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            # If adding this sentence exceeds max, save current chunk
            if current_tokens + sentence_tokens > self.max_tokens and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "section_name": section_name,
                    "chunk_text": chunk_text,
                    "chunk_tokens": current_tokens,
                })

                # Keep overlap sentences
                overlap_tokens = 0
                overlap_sentences = []
                for s in reversed(current_chunk):
                    s_tokens = self._estimate_tokens(s)
                    if overlap_tokens + s_tokens <= self.overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break

                current_chunk = overlap_sentences
                current_tokens = overlap_tokens

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "section_name": section_name,
                "chunk_text": chunk_text,
                "chunk_tokens": current_tokens,
            })

        return chunks

    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for chunks.

        Args:
            chunks: List of chunk dicts

        Returns:
            Same chunks with embedding added
        """
        try:
            model = self._get_embedding_model()
            texts = [chunk["chunk_text"] for chunk in chunks]

            # Generate embeddings in batch
            embeddings = model.encode(texts, show_progress_bar=False)

            for i, chunk in enumerate(chunks):
                # Serialize embedding to JSON
                chunk["embedding"] = json.dumps(embeddings[i].tolist())
                chunk["embedding_model"] = self._embedding_model_name

            return chunks

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Return chunks without embeddings
            for chunk in chunks:
                chunk["embedding"] = None
                chunk["embedding_model"] = None
            return chunks

    def store_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> bool:
        """
        Store chunks in database.

        Args:
            document_id: ID of parent DocumentCache record
            chunks: List of chunk dicts

        Returns:
            True if successful
        """
        try:
            # Delete existing chunks for this document
            self.db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete()

            # Insert new chunks
            for chunk in chunks:
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk["chunk_index"],
                    section_name=chunk.get("section_name"),
                    chunk_text=chunk["chunk_text"],
                    chunk_tokens=chunk.get("chunk_tokens"),
                    embedding=chunk.get("embedding"),
                    embedding_model=chunk.get("embedding_model"),
                )
                self.db.add(db_chunk)

            # Update parent document
            doc = self.db.query(DocumentCache).filter(
                DocumentCache.id == document_id
            ).first()
            if doc:
                doc.is_chunked = True

            self.db.commit()
            logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing chunks: {e}")
            self.db.rollback()
            return False

    def semantic_search(
        self,
        document_id: int,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search chunks using semantic similarity.

        Args:
            document_id: ID of document to search
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of matching chunks with similarity scores
        """
        try:
            # Get chunks for this document
            chunks = self.db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.isnot(None),
            ).all()

            if not chunks:
                logger.warning(f"No chunks with embeddings found for document {document_id}")
                return []

            # Generate query embedding
            model = self._get_embedding_model()
            query_embedding = model.encode(query)

            # Calculate similarities
            results = []
            for chunk in chunks:
                try:
                    chunk_embedding = np.array(json.loads(chunk.embedding))
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                    results.append({
                        "chunk_index": chunk.chunk_index,
                        "section_name": chunk.section_name,
                        "chunk_text": chunk.chunk_text,
                        "chunk_tokens": chunk.chunk_tokens,
                        "similarity": float(similarity),
                    })
                except Exception as e:
                    logger.warning(f"Error processing chunk {chunk.id}: {e}")
                    continue

            # Sort by similarity and return top_k
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def get_relevant_context(
        self,
        document_id: int,
        query: str,
        max_tokens: int = 8000,
    ) -> str:
        """
        Get relevant context from a chunked document for a query.

        Args:
            document_id: ID of document
            query: User's query
            max_tokens: Maximum tokens to return

        Returns:
            Combined text from relevant chunks
        """
        # Search for relevant chunks
        results = self.semantic_search(document_id, query, top_k=10)

        if not results:
            return ""

        # Combine chunks up to token limit
        combined_text = []
        current_tokens = 0

        for result in results:
            chunk_tokens = result.get("chunk_tokens", 0)
            if current_tokens + chunk_tokens > max_tokens:
                break

            section_header = ""
            if result.get("section_name"):
                section_header = f"\n\n--- {result['section_name']} ---\n\n"

            combined_text.append(section_header + result["chunk_text"])
            current_tokens += chunk_tokens

        return "\n".join(combined_text)
