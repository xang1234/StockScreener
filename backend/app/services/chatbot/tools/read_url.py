"""
Read URL Tool - Fetches and extracts text content from URLs.
Supports HTML pages and PDF documents.
"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ReadUrlTool:
    """Fetch and extract text content from URLs."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_CHARS = 100000
    USER_AGENT = "Mozilla/5.0 (compatible; StockResearchBot/1.0)"

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_chars: int = DEFAULT_MAX_CHARS
    ):
        self.timeout = timeout
        self.max_chars = max_chars
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
            )
        return self._client

    async def read_url(
        self,
        url: str,
        extract_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Fetch and extract text content from a URL.

        Args:
            url: URL to fetch
            extract_type: "auto", "html", or "pdf"

        Returns:
            Dict with extracted content and metadata
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {
                    "success": False,
                    "error": "Invalid URL format",
                    "url": url
                }

            client = await self._get_client()

            # Fetch content
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            # Determine extraction method
            if extract_type == "auto":
                if "pdf" in content_type or url.lower().endswith(".pdf"):
                    extract_type = "pdf"
                else:
                    extract_type = "html"

            # Extract text based on type
            if extract_type == "pdf":
                text = await self._extract_pdf(response.content)
            else:
                text = self._extract_html(response.text)

            # Truncate if too long
            if len(text) > self.max_chars:
                text = text[:self.max_chars] + "\n\n[Content truncated...]"
                truncated = True
            else:
                truncated = False

            # Extract title
            title = self._extract_title(response.text) if extract_type == "html" else url

            return {
                "success": True,
                "url": url,
                "title": title,
                "content": text,
                "content_type": extract_type,
                "char_count": len(text),
                "truncated": truncated,
            }

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching URL: {url}")
            return {
                "success": False,
                "error": "Request timed out",
                "url": url
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching URL {url}: {e.response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}",
                "url": url
            }
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url
            }

    def _extract_html(self, html: str) -> str:
        """Extract readable text from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for element in soup.find_all([
                "script", "style", "nav", "footer", "header",
                "aside", "form", "button", "iframe", "noscript"
            ]):
                element.decompose()

            # Try to find main content area
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find(class_=re.compile(r"(content|article|post|entry)", re.I)) or
                soup.find(id=re.compile(r"(content|article|post|entry)", re.I)) or
                soup.body or
                soup
            )

            # Get text with some structure preservation
            text = self._get_text_with_structure(main_content)

            # Clean up whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)

            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting HTML: {e}")
            # Fallback to basic text extraction
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

    def _get_text_with_structure(self, element) -> str:
        """Extract text preserving some structure (headers, paragraphs)."""
        if element is None:
            return ""

        lines = []

        for child in element.descendants:
            if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n## {text}\n")
            elif child.name == 'p':
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"{text}\n")
            elif child.name == 'li':
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")
            elif child.name == 'br':
                lines.append("\n")

        if not lines:
            return element.get_text(separator="\n", strip=True)

        return "\n".join(lines)

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Try og:title first (often better)
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                return og_title["content"]
            # Fall back to title tag
            if soup.title and soup.title.string:
                return soup.title.string.strip()
            # Try h1
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(strip=True)
            return ""
        except Exception:
            return ""

    async def _extract_pdf(self, content: bytes) -> str:
        """Extract text from PDF content."""
        try:
            # Use pdfplumber if available (already in requirements)
            import pdfplumber
            import io

            text_parts = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages[:50]:  # Limit to first 50 pages
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            return "\n\n".join(text_parts)

        except ImportError:
            logger.warning("pdfplumber not available, using pypdf fallback")
            try:
                from pypdf import PdfReader
                import io

                reader = PdfReader(io.BytesIO(content))
                text_parts = []
                for page in reader.pages[:50]:
                    text_parts.append(page.extract_text() or "")
                return "\n\n".join(text_parts)

            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                return "[Unable to extract PDF content]"

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return "[Unable to extract PDF content]"

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Tool definition for Groq API
READ_URL_TOOL = {
    "type": "function",
    "function": {
        "name": "read_url",
        "description": "Fetch and extract text content from a URL (HTML page or PDF). Use this after web_search to get the full content of a promising result.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch and extract content from"
                },
                "extract_type": {
                    "type": "string",
                    "enum": ["auto", "html", "pdf"],
                    "description": "Content extraction type. Use 'auto' to detect automatically.",
                    "default": "auto"
                }
            },
            "required": ["url"]
        }
    }
}
