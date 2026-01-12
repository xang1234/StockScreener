"""
PDF Extraction Service for downloading and extracting text from PDF documents.
Used for investor relations PDFs and SEC filings.
"""
import hashlib
import io
import logging
import re
from typing import Optional, Dict, Any, Tuple

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class PDFExtractionService:
    """Service for downloading and extracting text from PDF documents."""

    def __init__(self):
        self.max_size_bytes = settings.pdf_max_size_mb * 1024 * 1024
        self.timeout = settings.pdf_request_timeout
        self.user_agent = settings.sec_user_agent

    async def download_and_extract(self, url: str) -> Dict[str, Any]:
        """
        Download a PDF from URL and extract its text content.

        Args:
            url: URL of the PDF to download

        Returns:
            Dict with keys:
                - text: Extracted text content
                - text_length: Length of extracted text
                - token_estimate: Estimated token count
                - extraction_method: Method used (pdfplumber or pypdf)
                - document_hash: SHA-256 hash of PDF content
                - error: Error message if extraction failed
        """
        result = {
            "text": None,
            "text_length": 0,
            "token_estimate": 0,
            "extraction_method": None,
            "document_hash": None,
            "error": None,
        }

        try:
            # Download PDF
            pdf_content = await self._download_pdf(url)
            if pdf_content is None:
                result["error"] = "Failed to download PDF"
                return result

            # Calculate hash
            result["document_hash"] = hashlib.sha256(pdf_content).hexdigest()

            # Try pdfplumber first, fallback to pypdf
            text = self._extract_with_pdfplumber(pdf_content)
            if text:
                result["extraction_method"] = "pdfplumber"
            else:
                text = self._extract_with_pypdf(pdf_content)
                if text:
                    result["extraction_method"] = "pypdf"

            if text:
                # Clean and process text
                text = self._clean_text(text)
                result["text"] = text
                result["text_length"] = len(text)
                result["token_estimate"] = self._estimate_tokens(text)
            else:
                result["error"] = "Failed to extract text from PDF"

        except Exception as e:
            logger.error(f"PDF extraction error for {url}: {e}")
            result["error"] = str(e)

        return result

    async def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download PDF content from URL."""
        try:
            async with httpx.AsyncClient() as client:
                # First, check content length with HEAD request
                try:
                    head_response = await client.head(
                        url,
                        headers={"User-Agent": self.user_agent},
                        timeout=10,
                        follow_redirects=True,
                    )
                    content_length = head_response.headers.get("content-length")
                    if content_length and int(content_length) > self.max_size_bytes:
                        logger.warning(f"PDF too large: {content_length} bytes > {self.max_size_bytes}")
                        return None
                except Exception:
                    # HEAD request failed, proceed with GET anyway
                    pass

                # Download PDF
                response = await client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()

                # Check final content length
                if len(response.content) > self.max_size_bytes:
                    logger.warning(f"PDF too large after download: {len(response.content)} bytes")
                    return None

                # Verify it's a PDF
                if not response.content.startswith(b"%PDF"):
                    logger.warning(f"URL does not return a PDF: {url}")
                    return None

                return response.content

        except httpx.TimeoutException:
            logger.error(f"Timeout downloading PDF from {url}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading PDF from {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return None

    def _extract_with_pdfplumber(self, pdf_content: bytes) -> Optional[str]:
        """Extract text using pdfplumber (better for complex layouts)."""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            return "\n\n".join(text_parts) if text_parts else None

        except ImportError:
            logger.warning("pdfplumber not installed")
            return None
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
            return None

    def _extract_with_pypdf(self, pdf_content: bytes) -> Optional[str]:
        """Extract text using pypdf (fallback)."""
        try:
            from pypdf import PdfReader

            text_parts = []
            reader = PdfReader(io.BytesIO(pdf_content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n\n".join(text_parts) if text_parts else None

        except ImportError:
            logger.warning("pypdf not installed")
            return None
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\t+", " ", text)

        # Remove page numbers and headers/footers (common patterns)
        text = re.sub(r"\n\d+\n", "\n", text)
        text = re.sub(r"Page \d+ of \d+", "", text)

        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 4 chars per token)."""
        return len(text) // 4

    def extract_from_html(self, html_content: str) -> Tuple[str, int]:
        """
        Extract text from HTML content (for SEC filings that are HTML).

        Returns:
            Tuple of (extracted_text, token_estimate)
        """
        try:
            # Remove script and style elements
            html_content = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)

            # Remove XBRL/iXBRL hidden elements (SEC filings contain these)
            html_content = re.sub(r"<ix:hidden[^>]*>.*?</ix:hidden>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r"<div[^>]*style=[\"'][^\"']*display:\s*none[^\"']*[\"'][^>]*>.*?</div>", "", html_content, flags=re.DOTALL | re.IGNORECASE)

            # Remove XBRL namespace declarations and processing instructions
            html_content = re.sub(r"<\?xml[^>]*\?>", "", html_content, flags=re.IGNORECASE)

            # Remove empty XBRL context/unit elements that appear as text
            html_content = re.sub(r"(?:xbrli?|iso4217|nvda|us-gaap|dei):[a-zA-Z0-9_-]+", "", html_content)

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", html_content)

            # Decode HTML entities
            import html
            text = html.unescape(text)

            # Remove remaining XBRL-style identifiers (like "0001045810 2024-01-29")
            text = re.sub(r"\b\d{10}\s+\d{4}-\d{2}-\d{2}\b", "", text)

            # Remove CIK numbers standing alone
            text = re.sub(r"\b0{3,}\d{7,10}\b", "", text)

            # Clean text
            text = self._clean_text(text)

            return text, self._estimate_tokens(text)

        except Exception as e:
            logger.error(f"HTML extraction error: {e}")
            return "", 0
