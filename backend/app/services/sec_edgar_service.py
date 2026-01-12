"""
SEC EDGAR API Service for fetching 10-K and other SEC filings.
Handles CIK lookup, filing search, and document retrieval.
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx

from ..config import settings
from .pdf_extraction_service import PDFExtractionService

logger = logging.getLogger(__name__)


class SECEdgarService:
    """Service for interacting with SEC EDGAR API."""

    BASE_URL = "https://data.sec.gov"
    WWW_URL = "https://www.sec.gov"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

    # Common ticker to CIK mappings (cached for performance)
    _cik_cache: Dict[str, str] = {}

    def __init__(self):
        self.user_agent = settings.sec_user_agent
        self.rate_limit_delay = settings.sec_rate_limit_delay
        self.pdf_service = PDFExtractionService()
        self._last_request_time = 0

    async def _rate_limit(self):
        """Enforce rate limiting between SEC API requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _make_request(self, url: str) -> Optional[Dict[str, Any]]:
        """Make a rate-limited request to SEC API."""
        await self._rate_limit()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                        "Accept": "application/json",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"SEC API HTTP error: {e.response.status_code} for {url}")
            return None
        except Exception as e:
            logger.error(f"SEC API request error for {url}: {e}")
            return None

    async def _fetch_content(self, url: str) -> Optional[str]:
        """Fetch raw content from SEC (for HTML filings)."""
        await self._rate_limit()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                    },
                    timeout=60,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response.text

        except Exception as e:
            logger.error(f"SEC content fetch error for {url}: {e}")
            return None

    async def get_cik_for_symbol(self, symbol: str) -> Optional[str]:
        """
        Get SEC CIK (Central Index Key) for a ticker symbol.

        Args:
            symbol: Stock ticker symbol (e.g., NVDA, AAPL)

        Returns:
            10-digit zero-padded CIK string, or None if not found
        """
        symbol = symbol.upper()

        # Check cache first
        if symbol in self._cik_cache:
            return self._cik_cache[symbol]

        try:
            # SEC provides a ticker-to-CIK mapping file (on www.sec.gov, not data.sec.gov)
            url = f"{self.WWW_URL}/files/company_tickers.json"
            data = await self._make_request(url)

            if not data:
                return None

            # Search for ticker in the data
            for entry in data.values():
                if entry.get("ticker", "").upper() == symbol:
                    cik = str(entry.get("cik_str", ""))
                    # Pad to 10 digits
                    cik_padded = cik.zfill(10)
                    self._cik_cache[symbol] = cik_padded
                    return cik_padded

            logger.warning(f"CIK not found for symbol: {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error looking up CIK for {symbol}: {e}")
            return None

    async def get_company_filings(self, cik: str) -> Optional[Dict[str, Any]]:
        """
        Get company filing history from SEC.

        Args:
            cik: 10-digit zero-padded CIK

        Returns:
            Dict with company info and filings
        """
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
        return await self._make_request(url)

    async def find_10k_filing(
        self, symbol: str, year: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a 10-K filing for a company.

        Args:
            symbol: Stock ticker symbol
            year: Fiscal year (defaults to most recent)

        Returns:
            Dict with filing info including URL, or None if not found
        """
        cik = await self.get_cik_for_symbol(symbol)
        if not cik:
            return {"error": f"CIK not found for symbol: {symbol}"}

        company_data = await self.get_company_filings(cik)
        if not company_data:
            return {"error": f"Failed to fetch company data for {symbol}"}

        # Get filing info
        filings = company_data.get("filings", {}).get("recent", {})
        if not filings:
            return {"error": f"No filings found for {symbol}"}

        # Find 10-K filings
        forms = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])
        filing_dates = filings.get("filingDate", [])
        primary_documents = filings.get("primaryDocument", [])

        # Search for 10-K (or 10-K/A for amended)
        target_forms = ["10-K", "10-K/A"]
        found_filings = []

        for i, form in enumerate(forms):
            if form in target_forms:
                filing_date = filing_dates[i] if i < len(filing_dates) else None
                fiscal_year_from_date = None
                if filing_date:
                    # Parse filing date to determine fiscal year
                    # 10-Ks are typically filed within 60-90 days of fiscal year end
                    try:
                        date_obj = datetime.strptime(filing_date, "%Y-%m-%d")
                        # Fiscal year is usually the year before if filed early in year
                        if date_obj.month <= 3:
                            fiscal_year_from_date = date_obj.year - 1
                        else:
                            fiscal_year_from_date = date_obj.year - 1
                    except Exception:
                        pass

                found_filings.append({
                    "form": form,
                    "accession_number": accession_numbers[i] if i < len(accession_numbers) else None,
                    "filing_date": filing_date,
                    "primary_document": primary_documents[i] if i < len(primary_documents) else None,
                    "fiscal_year_estimate": fiscal_year_from_date,
                })

        if not found_filings:
            return {"error": f"No 10-K filings found for {symbol}"}

        # Filter by year if specified
        if year:
            matching = [f for f in found_filings if f.get("fiscal_year_estimate") == year]
            if matching:
                found_filings = matching
            else:
                # Try to match by filing date year
                matching = [
                    f for f in found_filings
                    if f.get("filing_date", "").startswith(str(year))
                       or f.get("filing_date", "").startswith(str(year + 1))
                ]
                if matching:
                    found_filings = matching

        # Get the most recent filing
        filing = found_filings[0]

        # Build document URL
        accession_no_dashes = filing["accession_number"].replace("-", "")
        cik_raw = cik.lstrip("0")
        primary_doc = filing["primary_document"]

        document_url = f"{self.ARCHIVES_URL}/{cik_raw}/{accession_no_dashes}/{primary_doc}"

        return {
            "symbol": symbol,
            "cik": cik,
            "form": filing["form"],
            "accession_number": filing["accession_number"],
            "filing_date": filing["filing_date"],
            "fiscal_year": filing.get("fiscal_year_estimate"),
            "document_url": document_url,
            "company_name": company_data.get("name"),
        }

    async def fetch_10k_text(
        self, symbol: str, year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch and extract text from a 10-K filing.

        Args:
            symbol: Stock ticker symbol
            year: Fiscal year (defaults to most recent)

        Returns:
            Dict with extracted text and metadata
        """
        # Find the filing
        filing_info = await self.find_10k_filing(symbol, year)
        if "error" in filing_info:
            return filing_info

        document_url = filing_info["document_url"]
        logger.info(f"Fetching 10-K from: {document_url}")

        # Determine if it's a PDF or HTML
        if document_url.lower().endswith(".pdf"):
            # Use PDF extraction
            extraction_result = await self.pdf_service.download_and_extract(document_url)
        else:
            # Assume HTML (most 10-Ks are HTML)
            html_content = await self._fetch_content(document_url)
            if not html_content:
                return {
                    **filing_info,
                    "error": "Failed to fetch 10-K document",
                }

            text, token_estimate = self.pdf_service.extract_from_html(html_content)
            extraction_result = {
                "text": text,
                "text_length": len(text),
                "token_estimate": token_estimate,
                "extraction_method": "html",
                "document_hash": None,  # Could compute hash of HTML
                "error": None if text else "Failed to extract text from HTML",
            }

        return {
            **filing_info,
            **extraction_result,
        }

    def parse_10k_sections(self, text: str) -> Dict[str, str]:
        """
        Parse 10-K text into named sections.

        Args:
            text: Full 10-K text

        Returns:
            Dict mapping section names to their content
        """
        sections = {}

        # Common 10-K section patterns
        section_patterns = [
            (r"(?i)ITEM\s*1[.\s]*(?:BUSINESS|Description of Business)", "Business"),
            (r"(?i)ITEM\s*1A[.\s]*RISK\s*FACTORS", "Risk Factors"),
            (r"(?i)ITEM\s*1B[.\s]*UNRESOLVED\s*STAFF", "Unresolved Staff Comments"),
            (r"(?i)ITEM\s*2[.\s]*PROPERTIES", "Properties"),
            (r"(?i)ITEM\s*3[.\s]*LEGAL\s*PROCEEDINGS", "Legal Proceedings"),
            (r"(?i)ITEM\s*4[.\s]*MINE\s*SAFETY", "Mine Safety Disclosures"),
            (r"(?i)ITEM\s*5[.\s]*MARKET", "Market for Common Equity"),
            (r"(?i)ITEM\s*6[.\s]*(?:SELECTED|RESERVED)", "Selected Financial Data"),
            (r"(?i)ITEM\s*7[.\s]*MANAGEMENT", "MD&A"),
            (r"(?i)ITEM\s*7A[.\s]*QUANTITATIVE", "Market Risk"),
            (r"(?i)ITEM\s*8[.\s]*FINANCIAL\s*STATEMENTS", "Financial Statements"),
            (r"(?i)ITEM\s*9[.\s]*CHANGES\s*IN", "Disagreements with Accountants"),
            (r"(?i)ITEM\s*9A[.\s]*CONTROLS", "Controls and Procedures"),
            (r"(?i)ITEM\s*10[.\s]*DIRECTORS", "Directors and Officers"),
            (r"(?i)ITEM\s*11[.\s]*EXECUTIVE", "Executive Compensation"),
            (r"(?i)ITEM\s*12[.\s]*SECURITY\s*OWNERSHIP", "Security Ownership"),
            (r"(?i)ITEM\s*13[.\s]*CERTAIN\s*RELATIONSHIPS", "Certain Relationships"),
            (r"(?i)ITEM\s*14[.\s]*PRINCIPAL\s*ACCOUNT", "Principal Accountant Fees"),
            (r"(?i)ITEM\s*15[.\s]*EXHIBITS", "Exhibits"),
        ]

        # Find all section starts
        section_positions = []
        for pattern, section_name in section_patterns:
            matches = list(re.finditer(pattern, text))
            for match in matches:
                section_positions.append((match.start(), section_name, match.end()))

        # Sort by position
        section_positions.sort(key=lambda x: x[0])

        # Extract section content
        for i, (start, name, content_start) in enumerate(section_positions):
            # End is the start of the next section or end of document
            if i + 1 < len(section_positions):
                end = section_positions[i + 1][0]
            else:
                end = len(text)

            section_text = text[content_start:end].strip()
            if section_text:
                sections[name] = section_text

        return sections
