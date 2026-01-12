"""
Groq API retry utility with exponential backoff.
Handles rate limits (429) and request too large (413) errors.
Supports multi-key rotation via GroqKeyManager.
"""
import asyncio
import logging
import random
import re
from typing import Callable, TypeVar, Any, Optional

from ...llm.groq_key_manager import get_groq_key_manager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class GroqRateLimitError(Exception):
    """Raised when Groq rate limit is exceeded (429)."""

    def __init__(self, message: str, retry_after: float = None):
        super().__init__(message)
        self.retry_after = retry_after


class GroqRequestTooLargeError(Exception):
    """Raised when request exceeds token limit (413)."""

    def __init__(self, message: str, tokens_used: int = None, token_limit: int = None):
        super().__init__(message)
        self.tokens_used = tokens_used
        self.token_limit = token_limit


def parse_groq_error(error: Exception) -> tuple[str, dict]:
    """
    Parse Groq API error to determine type and extract details.

    Returns:
        Tuple of (error_type, details_dict)
        error_type: "rate_limit", "too_large", or "other"
    """
    error_msg = str(error).lower()
    details = {}

    # Check for rate limit (429)
    if "429" in error_msg or "rate limit" in error_msg or "rate_limit" in error_msg:
        # Try to parse "Please try again in Xs" or similar
        retry_match = re.search(r'try again in (\d+(?:\.\d+)?)\s*(?:s|second)', error_msg)
        if retry_match:
            details["retry_after"] = float(retry_match.group(1))

        # Also check for "Please retry after X ms/s"
        retry_match2 = re.search(r'retry after (\d+(?:\.\d+)?)\s*(ms|s|second)', error_msg)
        if retry_match2:
            value = float(retry_match2.group(1))
            unit = retry_match2.group(2)
            if unit == "ms":
                value = value / 1000
            details["retry_after"] = value

        return "rate_limit", details

    # Check for request too large (413)
    if "413" in error_msg or "too large" in error_msg or "request entity too large" in error_msg:
        # Try to parse token counts
        tokens_match = re.search(r'(\d+)\s*tokens?.*?(\d+)\s*(?:limit|max)', error_msg)
        if tokens_match:
            details["tokens_used"] = int(tokens_match.group(1))
            details["token_limit"] = int(tokens_match.group(2))
        return "too_large", details

    return "other", details


async def call_groq_with_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
    api_key: Optional[str] = None
) -> T:
    """
    Call a Groq API function with exponential backoff retry.

    Args:
        func: Synchronous callable that makes the Groq API call
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Random jitter factor (0-1) to prevent thundering herd
        api_key: API key being used (for rate limit reporting)

    Returns:
        Result of the function call

    Raises:
        GroqRateLimitError: If rate limit persists after all retries
        GroqRequestTooLargeError: Immediately on 413 (not retryable)
        Exception: Other errors propagated directly

    Note:
        On rate limit, the same key is used for all retries (exponential backoff).
        Rotation to a different key happens on the NEXT call (not during retries).
        Use get_groq_api_key() before calling this function to get the current key.
    """
    loop = asyncio.get_running_loop()
    last_error = None
    key_manager = get_groq_key_manager()

    for attempt in range(max_retries + 1):
        try:
            # Run synchronous Groq call in executor
            return await loop.run_in_executor(None, func)

        except Exception as e:
            error_type, details = parse_groq_error(e)

            if error_type == "too_large":
                # 413 errors are not retryable - fail immediately
                raise GroqRequestTooLargeError(
                    str(e),
                    tokens_used=details.get("tokens_used"),
                    token_limit=details.get("token_limit")
                )

            if error_type == "rate_limit":
                last_error = e
                retry_after = details.get("retry_after")

                # Report rate limit to manager (rotation happens on NEXT request)
                if api_key and len(key_manager) > 0:
                    key_manager.report_rate_limit(api_key, retry_after)

                if attempt >= max_retries:
                    # Exhausted retries
                    raise GroqRateLimitError(
                        f"Rate limit exceeded after {max_retries} retries: {e}",
                        retry_after=retry_after
                    )

                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)

                # Use server-provided retry delay if available and reasonable
                server_delay = details.get("retry_after")
                if server_delay and server_delay <= max_delay:
                    delay = max(delay, server_delay)

                # Add jitter to prevent thundering herd
                jitter_amount = delay * jitter * random.random()
                delay += jitter_amount

                logger.warning(
                    f"Groq rate limit hit (attempt {attempt + 1}/{max_retries + 1}). "
                    f"Retrying in {delay:.1f}s..."
                )

                await asyncio.sleep(delay)
                continue

            # Other errors - don't retry
            raise

    # Should not reach here, but just in case
    if last_error:
        raise GroqRateLimitError(f"Rate limit exceeded: {last_error}")
    raise RuntimeError("Unexpected retry loop exit")


def get_groq_api_key() -> Optional[str]:
    """
    Get the current Groq API key from the key manager.

    Call this ONCE before starting a request, then pass the same key
    to call_groq_with_retry() for rate limit tracking.

    Returns:
        API key string, or None if no keys configured
    """
    key_manager = get_groq_key_manager()
    if len(key_manager) > 0:
        return key_manager.get_key()
    return None


async def call_groq_streaming_with_retry(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
    api_key: Optional[str] = None
) -> Any:
    """
    Call a Groq streaming API function with retry.

    This is a simpler wrapper since streaming calls need to be handled
    differently - we retry the entire streaming operation.

    Args:
        func: Callable that returns a streaming iterator
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Random jitter factor (0-1)
        api_key: API key being used (for rate limit reporting)

    Returns:
        The streaming iterator/result from func

    Raises:
        GroqRateLimitError: If rate limit persists after all retries
        GroqRequestTooLargeError: Immediately on 413 (not retryable)

    Note:
        On rate limit, the same key is used for all retries (exponential backoff).
        Rotation to a different key happens on the NEXT call (not during retries).
    """
    loop = asyncio.get_running_loop()
    key_manager = get_groq_key_manager()

    for attempt in range(max_retries + 1):
        try:
            # Run the streaming function setup in executor
            return await loop.run_in_executor(None, func)

        except Exception as e:
            error_type, details = parse_groq_error(e)

            if error_type == "too_large":
                raise GroqRequestTooLargeError(
                    str(e),
                    tokens_used=details.get("tokens_used"),
                    token_limit=details.get("token_limit")
                )

            if error_type == "rate_limit":
                retry_after = details.get("retry_after")

                # Report rate limit to manager (rotation happens on NEXT request)
                if api_key and len(key_manager) > 0:
                    key_manager.report_rate_limit(api_key, retry_after)

                if attempt >= max_retries:
                    raise GroqRateLimitError(
                        f"Rate limit exceeded after {max_retries} retries: {e}",
                        retry_after=retry_after
                    )

                delay = min(base_delay * (2 ** attempt), max_delay)
                server_delay = details.get("retry_after")
                if server_delay and server_delay <= max_delay:
                    delay = max(delay, server_delay)

                jitter_amount = delay * jitter * random.random()
                delay += jitter_amount

                logger.warning(
                    f"Groq rate limit hit on streaming call (attempt {attempt + 1}/{max_retries + 1}). "
                    f"Retrying in {delay:.1f}s..."
                )

                await asyncio.sleep(delay)
                continue

            raise

    raise RuntimeError("Unexpected retry loop exit")
