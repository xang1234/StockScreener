"""
Document Tools for chatbot - SEC 10-K and IR PDF reading.
Orchestrates document fetching, caching, and retrieval.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from ....config import settings
from ....models.document_cache import DocumentCache, DocumentChunk
from ...sec_edgar_service import SECEdgarService
from ...pdf_extraction_service import PDFExtractionService
from ...document_chunking_service import DocumentChunkingService

logger = logging.getLogger(__name__)


class DocumentTools:
    """High-level document tools for the chatbot."""

    def __init__(self, db: Session):
        self.db = db
        self.sec_service = SECEdgarService()
        self.pdf_service = PDFExtractionService()
        self.chunking_service = DocumentChunkingService(db)
        self.cache_ttl_days = settings.sec_cache_ttl_days
        self.context_limit = settings.doc_context_window_limit

    async def get_sec_10k(
        self,
        symbol: str,
        year: Optional[int] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get SEC 10-K filing content for a company.

        Args:
            symbol: Stock ticker symbol
            year: Fiscal year (defaults to most recent)
            query: Search query for large documents (semantic search)

        Returns:
            Dict with filing content and metadata
        """
        symbol = symbol.upper()
        logger.info(f"Getting 10-K for {symbol}, year={year}, query={query}")

        try:
            # Check cache first
            cached = self._get_cached_10k(symbol, year)
            if cached:
                logger.info(f"Found cached 10-K for {symbol}")
                return self._prepare_response(cached, query)

            # Fetch from SEC
            result = await self.sec_service.fetch_10k_text(symbol, year)

            if "error" in result and result.get("text") is None:
                return {"error": result["error"]}

            # Cache the result
            doc = self._cache_document(
                document_type="sec_10k",
                symbol=symbol,
                source_url=result.get("document_url", ""),
                cik=result.get("cik"),
                accession_number=result.get("accession_number"),
                filing_date=self._parse_date(result.get("filing_date")),
                fiscal_year=result.get("fiscal_year"),
                title=f"{result.get('company_name', symbol)} 10-K",
                full_text=result.get("text"),
                text_length=result.get("text_length"),
                token_estimate=result.get("token_estimate"),
                extraction_method=result.get("extraction_method"),
                document_hash=result.get("document_hash"),
            )

            # Check if chunking needed
            if doc and result.get("token_estimate", 0) > self.context_limit:
                self._chunk_document(doc, result.get("text", ""), "sec_10k")

            return self._prepare_response(doc, query)

        except Exception as e:
            logger.error(f"Error getting 10-K for {symbol}: {e}", exc_info=True)
            return {"error": f"Failed to retrieve 10-K: {str(e)}"}

    async def read_ir_pdf(
        self,
        url: str,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read and extract text from an investor relations PDF.

        Args:
            url: Direct URL to the PDF
            query: Search query for large documents (semantic search)

        Returns:
            Dict with PDF content and metadata
        """
        logger.info(f"Reading IR PDF from {url}, query={query}")

        try:
            # Check cache first
            cached = self._get_cached_by_url(url)
            if cached:
                logger.info(f"Found cached PDF for {url}")
                return self._prepare_response(cached, query)

            # Download and extract
            result = await self.pdf_service.download_and_extract(url)

            if result.get("error"):
                return {"error": result["error"]}

            # Try to extract title from URL
            title = self._extract_title_from_url(url)

            # Cache the result
            doc = self._cache_document(
                document_type="ir_pdf",
                symbol=None,  # Unknown for direct URLs
                source_url=url,
                title=title,
                full_text=result.get("text"),
                text_length=result.get("text_length"),
                token_estimate=result.get("token_estimate"),
                extraction_method=result.get("extraction_method"),
                document_hash=result.get("document_hash"),
            )

            # Check if chunking needed
            if doc and result.get("token_estimate", 0) > self.context_limit:
                self._chunk_document(doc, result.get("text", ""), "ir_pdf")

            return self._prepare_response(doc, query)

        except Exception as e:
            logger.error(f"Error reading PDF from {url}: {e}", exc_info=True)
            return {"error": f"Failed to read PDF: {str(e)}"}

    def _get_cached_10k(self, symbol: str, year: Optional[int]) -> Optional[DocumentCache]:
        """Get cached 10-K if available and not expired."""
        cutoff = datetime.utcnow() - timedelta(days=self.cache_ttl_days)

        query = self.db.query(DocumentCache).filter(
            DocumentCache.document_type == "sec_10k",
            DocumentCache.symbol == symbol,
            DocumentCache.fetched_at >= cutoff,
        )

        if year:
            query = query.filter(DocumentCache.fiscal_year == year)

        return query.order_by(DocumentCache.fetched_at.desc()).first()

    def _get_cached_by_url(self, url: str) -> Optional[DocumentCache]:
        """Get cached document by URL if not expired."""
        cutoff = datetime.utcnow() - timedelta(days=self.cache_ttl_days)

        return self.db.query(DocumentCache).filter(
            DocumentCache.source_url == url,
            DocumentCache.fetched_at >= cutoff,
        ).first()

    def _cache_document(
        self,
        document_type: str,
        source_url: str,
        symbol: Optional[str] = None,
        cik: Optional[str] = None,
        accession_number: Optional[str] = None,
        filing_date: Optional[datetime] = None,
        fiscal_year: Optional[int] = None,
        title: Optional[str] = None,
        full_text: Optional[str] = None,
        text_length: Optional[int] = None,
        token_estimate: Optional[int] = None,
        extraction_method: Optional[str] = None,
        document_hash: Optional[str] = None,
    ) -> Optional[DocumentCache]:
        """Cache document in database."""
        try:
            # Check if URL already exists
            existing = self.db.query(DocumentCache).filter(
                DocumentCache.source_url == source_url
            ).first()

            if existing:
                # Update existing
                existing.full_text = full_text
                existing.text_length = text_length
                existing.token_count_estimate = token_estimate
                existing.extraction_method = extraction_method
                existing.document_hash = document_hash
                existing.updated_at = datetime.utcnow()
                self.db.commit()
                return existing

            # Create new
            doc = DocumentCache(
                document_type=document_type,
                symbol=symbol,
                source_url=source_url,
                cik=cik,
                accession_number=accession_number,
                filing_date=filing_date,
                fiscal_year=fiscal_year,
                title=title,
                full_text=full_text,
                text_length=text_length,
                token_count_estimate=token_estimate,
                extraction_method=extraction_method,
                document_hash=document_hash,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            return doc

        except Exception as e:
            logger.error(f"Error caching document: {e}")
            self.db.rollback()
            return None

    def _chunk_document(
        self, doc: DocumentCache, text: str, document_type: str
    ) -> bool:
        """Chunk document and store embeddings."""
        try:
            logger.info(f"Chunking document {doc.id} ({doc.token_count_estimate} tokens)")

            # Generate chunks
            chunks = self.chunking_service.chunk_document(text, document_type)

            # Generate embeddings
            chunks = self.chunking_service.generate_embeddings(chunks)

            # Store chunks
            return self.chunking_service.store_chunks(doc.id, chunks)

        except Exception as e:
            logger.error(f"Error chunking document {doc.id}: {e}")
            return False

    def _prepare_response(
        self, doc: Optional[DocumentCache], query: Optional[str]
    ) -> Dict[str, Any]:
        """Prepare response with document content and references."""
        if not doc:
            return {"error": "Document not found"}

        response = {
            "document_type": doc.document_type,
            "symbol": doc.symbol,
            "title": doc.title,
            "source_url": doc.source_url,
            "filing_date": doc.filing_date.isoformat() if doc.filing_date else None,
            "fiscal_year": doc.fiscal_year,
            "text_length": doc.text_length,
            "token_estimate": doc.token_count_estimate,
            "is_chunked": doc.is_chunked,
        }

        # Track sections used for references
        sections_used = set()

        # If document is chunked and query provided, use semantic search
        if doc.is_chunked and query:
            logger.info(f"Using semantic search for query: {query}")
            # Use semantic_search directly to get section information
            search_results = self.chunking_service.semantic_search(
                doc.id, query, top_k=10
            )
            if search_results:
                # Combine chunks up to token limit (same logic as get_relevant_context)
                combined_text = []
                current_tokens = 0
                max_tokens = 8000

                for result in search_results:
                    chunk_tokens = result.get("chunk_tokens", 0)
                    if current_tokens + chunk_tokens > max_tokens:
                        break

                    section_name = result.get("section_name")
                    section_header = ""
                    if section_name:
                        section_header = f"\n\n--- {section_name} ---\n\n"
                        sections_used.add(section_name)

                    combined_text.append(section_header + result["chunk_text"])
                    current_tokens += chunk_tokens

                response["content"] = "\n".join(combined_text)
                response["retrieval_method"] = "semantic_search"
            else:
                # Fallback to truncated full text
                response["content"] = self._truncate_text(doc.full_text, 8000)
                response["retrieval_method"] = "truncated"
        elif doc.is_chunked:
            # Large document without query - provide summary/beginning
            response["content"] = self._truncate_text(doc.full_text, 8000)
            response["retrieval_method"] = "truncated"
            response["note"] = "Document is large. Provide a query for targeted search."
        else:
            # Document fits in context
            response["content"] = doc.full_text
            response["retrieval_method"] = "full"

        # Build references array
        response["references"] = self._build_references(doc, sections_used)

        return response

    def _build_references(
        self, doc: DocumentCache, sections_used: set
    ) -> list:
        """Build references array for the response."""
        references = []

        if doc.document_type == "sec_10k":
            # Build title with fiscal year if available
            title_parts = []
            if doc.symbol:
                title_parts.append(doc.symbol)
            title_parts.append("10-K")
            if doc.fiscal_year:
                title_parts.append(f"FY{doc.fiscal_year}")

            base_title = " ".join(title_parts)

            if sections_used:
                # Create a reference for each section used
                for section in sections_used:
                    references.append({
                        "type": "sec_10k",
                        "title": f"{base_title} - {section}",
                        "url": doc.source_url or "",
                        "section": section,
                    })
            else:
                # Single reference for the whole document
                references.append({
                    "type": "sec_10k",
                    "title": base_title,
                    "url": doc.source_url or "",
                })

        elif doc.document_type == "ir_pdf":
            references.append({
                "type": "ir_pdf",
                "title": doc.title or "IR Document",
                "url": doc.source_url or "",
            })

        return references

    def _truncate_text(self, text: Optional[str], max_tokens: int) -> str:
        """Truncate text to approximately max_tokens."""
        if not text:
            return ""

        # Rough approximation: 4 chars per token
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        return text[:max_chars] + "\n\n[Document truncated. Provide a query for targeted search.]"

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return None

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a title from URL path."""
        try:
            from urllib.parse import urlparse, unquote
            path = urlparse(url).path
            filename = path.split("/")[-1]
            # Remove extension and clean up
            title = filename.rsplit(".", 1)[0]
            title = unquote(title)
            title = title.replace("-", " ").replace("_", " ")
            return title[:200] if title else "PDF Document"
        except Exception:
            return "PDF Document"
