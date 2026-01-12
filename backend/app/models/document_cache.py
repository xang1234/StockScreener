"""
Document cache models for SEC filings and IR PDFs.
Stores extracted text and embeddings for chatbot document analysis.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ..database import Base


class DocumentCache(Base):
    """Cache for extracted document text from SEC filings and IR PDFs."""

    __tablename__ = "document_cache"

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String(20), nullable=False)  # sec_10k, sec_10q, ir_pdf
    symbol = Column(String(10), index=True)
    source_url = Column(String(1000), nullable=False, unique=True)
    cik = Column(String(20))  # SEC Central Index Key
    accession_number = Column(String(30))  # SEC accession number
    filing_date = Column(DateTime(timezone=True))
    fiscal_year = Column(Integer)
    title = Column(String(500))
    document_hash = Column(String(64))  # SHA-256 hash for change detection
    full_text = Column(Text)
    text_length = Column(Integer)
    token_count_estimate = Column(Integer)
    is_chunked = Column(Boolean, default=False)
    extraction_method = Column(String(30))  # pdfplumber, pypdf, html
    extraction_error = Column(Text)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_document_cache_symbol", "symbol"),
        Index("idx_document_cache_type", "document_type"),
        Index("idx_document_cache_cik", "cik"),
    )


class DocumentChunk(Base):
    """Chunks of large documents with embeddings for semantic search."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("document_cache.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    section_name = Column(String(200))  # "Risk Factors", "MD&A", etc.
    chunk_text = Column(Text, nullable=False)
    chunk_tokens = Column(Integer)
    embedding = Column(Text)  # JSON-serialized numpy array
    embedding_model = Column(String(50), default="all-MiniLM-L6-v2")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("DocumentCache", back_populates="chunks")

    __table_args__ = (
        Index("idx_document_chunks_document", "document_id"),
        Index("idx_document_chunks_section", "section_name"),
    )
