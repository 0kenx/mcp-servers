import os
import sys
import json
import asyncio
import tempfile
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Tuple, Set, Annotated
from urllib.parse import urlparse, urlunparse
import httpx
from pydantic import BaseModel, Field, AnyUrl, ValidationError
import markdownify
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP, Context

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# Create MCP server
mcp = FastMCP("web-processing-server")

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30
# Default max length for fetched content before sending to AI (characters)
DEFAULT_FETCH_MAX_LENGTH = 20000
# Default User Agent
DEFAULT_USER_AGENT = "ModelContextProtocol-WebProcessor/1.0 (+https://github.com/modelcontextprotocol/servers)"
# Default OpenAI Model
DEFAULT_OPENAI_MODEL = "o3-mini"
# Default Max Tokens for OpenAI response
DEFAULT_OPENAI_MAX_TOKENS = 2000

# Command line argument parsing
if len(sys.argv) < 2:
    print(
        "Usage: python mcp_server_filesystem.py <allowed-directory> [additional-directories...]",
        file=sys.stderr,
    )
    sys.exit(1)

# --- OpenAI Setup ---
OPENAI_API_KEY = sys.argv[1]
if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
    # Decide if you want to exit or run without AI tools
    # sys.exit(1)
    openai_client = None
else:
    try:
        import openai

        openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        print(
            "Error: 'openai' library not installed. AI processing tools will not be available.",
            file=sys.stderr,
        )
        openai_client = None
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}", file=sys.stderr)
        openai_client = None

# --- AI Prompt ---
AI_PROCESSOR_SYSTEM_PROMPT = """
You are an expert web content processor. Your task is to analyze the provided web content (usually in Markdown format) and follow the user's instructions precisely to extract, summarize, format, or transform the information.

**Input:**
You will receive the web page content within `<content>` tags and the user's specific instructions within `<instructions>` tags.

**Output:**
- Respond *only* with the data requested by the instructions.
- Do not add any preamble, introduction, or explanation unless specifically asked for.
- If the instructions ask for a specific format (e.g., JSON, list, table), adhere to it strictly. Use Markdown for general text formatting unless otherwise specified.
- If you cannot fulfill the instructions based on the provided content (e.g., the information is missing), clearly state that you couldn't find the requested information in the content. Do not make assumptions or fetch external data.
- Be concise and accurate.
"""

# --- Helper Functions (Partially from Draft) ---


def extract_content_from_html(html: str, max_length: Optional[int] = None) -> str:
    """Extract and convert HTML content to Markdown format, with optional truncation."""
    if not html or not html.strip():
        return "<e>Empty HTML content</e>"

    try:
        # Use heading_style=ATX for '#' style headings
        content = markdownify.markdownify(html, heading_style=markdownify.ATX)
        if max_length and len(content) > max_length:
            content = (
                content[:max_length]
                + f"\n\n[Content truncated at {max_length} characters]"
            )
        return content
    except Exception as e:
        return f"<e>Failed to extract content from HTML: {str(e)}</e>"


def get_robots_txt_url(url: str) -> str:
    """Get the robots.txt URL for a given website URL."""
    try:
        parsed = urlparse(url)
        # Ensure scheme and netloc are present
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL structure for robots.txt lookup")
        robots_url = urlunparse(
            (parsed.scheme, parsed.netloc, "/robots.txt", "", "", "")
        )
        return robots_url
    except ValueError as e:
        print(
            f"Warning: Could not parse URL '{url}' for robots.txt: {e}", file=sys.stderr
        )
        return None  # Indicate failure


async def check_robots_txt(url: str, user_agent: str, timeout: int) -> bool:
    """Checks if crawling the URL is allowed by robots.txt. Returns True if allowed, False otherwise."""
    robots_url = get_robots_txt_url(url)
    if not robots_url:
        return True  # Proceed if we can't determine robots.txt URL

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            robots_response = await client.get(
                robots_url, headers={"User-Agent": user_agent}, timeout=timeout
            )

            if robots_response.status_code in (401, 403):
                print(
                    f"Warning: Access to {robots_url} denied (status {robots_response.status_code}). Assuming disallowed.",
                    file=sys.stderr,
                )
                return False  # Access denied, assume disallowed

            if robots_response.status_code == 200:
                robots_txt = robots_response.text
                parsed_url = urlparse(url)
                path = parsed_url.path or "/"  # Ensure path exists

                # Very basic parser - checks User-agent: * and specific agent
                lines = robots_txt.splitlines()
                relevant_rules = []
                current_agent = None
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        continue
                    key = parts[0].strip().lower()
                    value = parts[1].strip()

                    if key == "user-agent":
                        current_agent = value
                    elif key == "disallow":
                        # Apply rule if agent matches '*' or our specific agent
                        if current_agent in ("*", user_agent):
                            # Check if the disallowed path matches the start of our URL path
                            if path.startswith(value) and value:
                                print(
                                    f"Info: URL {url} disallowed by rule: {line} for agent {current_agent}",
                                    file=sys.stderr,
                                )
                                return False  # Disallowed by a matching rule

        # If no disallow rule matched
        return True
    except httpx.TimeoutException:
        print(
            f"Warning: Timeout fetching {robots_url}. Proceeding with caution.",
            file=sys.stderr,
        )
        return True  # Timeout, proceed cautiously
    except httpx.RequestError as e:
        print(
            f"Warning: Request error fetching {robots_url}: {e}. Proceeding with caution.",
            file=sys.stderr,
        )
        return True  # Network error, proceed cautiously
    except Exception as e:
        print(
            f"Warning: Error processing robots.txt for {url}: {e}. Proceeding with caution.",
            file=sys.stderr,
        )
        return True  # Other error, proceed cautiously


async def fetch_url(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = DEFAULT_TIMEOUT,
    ignore_robots: bool = False,
) -> Tuple[Optional[str], Optional[str], int, Dict[str, Any]]:
    """
    Fetch the URL and return the content, content type, status code, and metadata.
    Returns (None, None, status, metadata) on error or disallowed by robots.txt.
    """
    metadata = {"original_url": url, "error": None}

    # 1. Check robots.txt if not ignored
    if not ignore_robots:
        is_allowed = await check_robots_txt(url, user_agent, timeout)
        if not is_allowed:
            metadata["error"] = (
                f"Access disallowed by robots.txt. Use ignore_robots=True to override."
            )
            return (None, None, 403, metadata)  # Use 403 Forbidden status

    # 2. Fetch the URL
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                url, headers={"User-Agent": user_agent}, timeout=timeout
            )

            # Update metadata from response
            metadata.update(
                {
                    "final_url": str(response.url),
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "headers": dict(response.headers),
                    "elapsed": response.elapsed.total_seconds(),
                    "redirects": [str(r.url) for r in response.history],
                }
            )

            # Check for HTTP errors after getting metadata
            if response.status_code >= 400:
                metadata["error"] = (
                    f"HTTP Error {response.status_code}: {response.reason_phrase}"
                )
                # Try to get body for context, even on error
                try:
                    content = response.text
                    metadata["size"] = len(content)
                except Exception:
                    content = ""
                    metadata["size"] = 0
                return (
                    content or "",
                    metadata["content_type"],
                    response.status_code,
                    metadata,
                )

            # Success case
            content = response.text
            content_type = metadata["content_type"]
            metadata["size"] = len(content)

            return (content, content_type, response.status_code, metadata)

    except httpx.TimeoutException:
        metadata["error"] = f"Request timed out after {timeout} seconds"
        return (None, None, 408, metadata)  # 408 Request Timeout
    except httpx.RequestError as e:
        metadata["error"] = f"Request error: {str(e)}"
        # Try to determine a status code if possible (e.g., DNS error -> ~404/503)
        status_code = 503 if "Name or service not known" in str(e) else 400
        return (
            None,
            None,
            status_code,
            metadata,
        )  # 400 Bad Request or 503 Service Unavailable
    except ValidationError as e:  # Handle Pydantic validation errors for AnyUrl
        metadata["error"] = f"Invalid URL format: {str(e)}"
        return (None, None, 400, metadata)
    except Exception as e:
        metadata["error"] = f"Unknown fetching error: {str(e)}"
        return (None, None, 500, metadata)  # 500 Internal Server Error


async def _call_openai(
    content: str, instructions: str, model: str, max_tokens: int
) -> Tuple[Optional[str], Optional[str]]:
    """Helper to call OpenAI API. Returns (result, error_message)."""
    if not openai_client:
        return None, "OpenAI client not initialized (missing API key or library)."

    user_message = f"<content>\n{content}\n</content>\n\n<instructions>\n{instructions}\n</instructions>"

    try:
        completion = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": AI_PROCESSOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.2,  # Lower temperature for more deterministic extraction
        )
        result = completion.choices[0].message.content
        return result.strip(), None
    except openai.APIError as e:
        error_msg = f"OpenAI API Error: {e.status_code} - {e.message}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return None, error_msg
    except Exception as e:
        error_msg = f"Error during OpenAI call: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return None, error_msg


# --- MCP Tools ---


@mcp.tool()
async def fetch_and_process_url(
    url: str,
    instructions: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_length: int = DEFAULT_FETCH_MAX_LENGTH,
    ignore_robots: bool = False,
    user_agent: Optional[str] = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
    output_format_hint: str = "markdown",  # Hint for pre-processing before AI
) -> str:
    """
    Fetches content from a URL, processes it with an AI model based on instructions, and returns the result.

    Args:
        url: The URL to fetch.
        instructions: Specific instructions for the AI on how to process the content.
        timeout: Request timeout in seconds.
        max_length: Max characters of fetched content to process (truncates if longer).
        ignore_robots: If True, ignore robots.txt restrictions.
        user_agent: Custom user agent string.
        openai_model: The OpenAI model to use (e.g., 'o3-mini').
        openai_max_tokens: Max tokens for the AI's response.
        output_format_hint: Format to convert content to BEFORE sending to AI ('markdown', 'text', 'html'). Markdown recommended.

    Returns:
        The processed result from the AI, or an error message.
    """
    if not openai_client:
        return "Error: OpenAI client not available. Cannot process with AI."

    # Validate URL format early
    try:
        AnyUrl(url)
    except ValidationError as e:
        return f"Invalid URL format: {e}"

    _user_agent = user_agent or DEFAULT_USER_AGENT

    # 1. Fetch content
    content, content_type, status_code, metadata = await fetch_url(
        url, user_agent=_user_agent, timeout=timeout, ignore_robots=ignore_robots
    )

    # Handle fetch errors
    if status_code >= 400 or content is None:
        error_msg = metadata.get(
            "error", f"Failed to fetch URL (Status: {status_code})"
        )
        return f"Error fetching {url}: {error_msg}"

    # 2. Pre-process content based on hint (usually convert to Markdown)
    processed_content = ""
    if "text/html" in (content_type or "") and output_format_hint != "html":
        processed_content = extract_content_from_html(content, max_length=max_length)
    elif "text/" in (content_type or "") or output_format_hint == "text":
        processed_content = content[:max_length]
        if len(content) > max_length:
            processed_content += f"\n\n[Content truncated at {max_length} characters]"
    else:  # Keep raw for JSON, XML, or if hint is html
        processed_content = content[:max_length]
        if len(content) > max_length:
            processed_content += f"\n\n[Content truncated at {max_length} characters]"

    if "<e>Failed to extract content" in processed_content:
        # If markdownify failed significantly, maybe try sending raw HTML snippet?
        # Or just report the failure? Let's report it for now.
        return (
            f"Error processing HTML content from {url}: Could not convert to Markdown."
        )

    if not processed_content.strip():
        return (
            f"Error: Fetched content from {url} appears to be empty after processing."
        )

    # 3. Call OpenAI
    ai_result, ai_error = await _call_openai(
        content=processed_content,
        instructions=instructions,
        model=openai_model,
        max_tokens=openai_max_tokens,
    )

    if ai_error:
        return f"Error processing content from {url} with AI: {ai_error}"

    return ai_result or "AI returned an empty response."


@mcp.tool()
async def fetch_and_process_multiple_urls(
    urls: List[str],
    instructions: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_length: int = DEFAULT_FETCH_MAX_LENGTH,
    ignore_robots: bool = False,
    user_agent: Optional[str] = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
    output_format_hint: str = "markdown",
    output_structure: str = "json",  # 'json' or 'markdown' for the combined output
) -> str:
    """
    Fetches multiple URLs, processes each with an AI model using the same instructions, and returns combined results.

    Args:
        urls: A list of URLs to fetch and process.
        instructions: Specific instructions for the AI (applied to each URL's content).
        timeout: Request timeout in seconds for each URL.
        max_length: Max characters of fetched content per URL to process.
        ignore_robots: If True, ignore robots.txt restrictions for all URLs.
        user_agent: Custom user agent string.
        openai_model: The OpenAI model to use.
        openai_max_tokens: Max tokens for the AI's response for each URL.
        output_format_hint: Format to convert content to BEFORE sending to AI ('markdown', 'text', 'html').
        output_structure: How to format the final combined output ('json' map or 'markdown' sections).

    Returns:
        Combined results as a JSON string map {url: result/error} or a single Markdown string.
    """
    if not openai_client:
        return "Error: OpenAI client not available. Cannot process with AI."
    if not urls:
        return "Error: No URLs provided."

    _user_agent = user_agent or DEFAULT_USER_AGENT

    async def _fetch_and_process_one(url: str):
        try:
            # Validate URL
            try:
                AnyUrl(url)
            except ValidationError as e:
                return url, f"Invalid URL format: {e}"

            # Fetch
            content, content_type, status_code, metadata = await fetch_url(
                url,
                user_agent=_user_agent,
                timeout=timeout,
                ignore_robots=ignore_robots,
            )

            if status_code >= 400 or content is None:
                return (
                    url,
                    f"Error fetching: {metadata.get('error', f'Status {status_code}')}",
                )

            # Pre-process
            processed_content = ""
            if "text/html" in (content_type or "") and output_format_hint != "html":
                processed_content = extract_content_from_html(
                    content, max_length=max_length
                )
            elif "text/" in (content_type or "") or output_format_hint == "text":
                processed_content = content[:max_length]
                if len(content) > max_length:
                    processed_content += (
                        f"\n\n[Content truncated at {max_length} chars]"
                    )
            else:
                processed_content = content[:max_length]
                if len(content) > max_length:
                    processed_content += (
                        f"\n\n[Content truncated at {max_length} chars]"
                    )

            if "<e>Failed to extract content" in processed_content:
                return url, "Error processing HTML: Could not convert to Markdown."
            if not processed_content.strip():
                return url, "Error: Fetched content appears empty after processing."

            # Call AI
            ai_result, ai_error = await _call_openai(
                content=processed_content,
                instructions=instructions,
                model=openai_model,
                max_tokens=openai_max_tokens,
            )

            if ai_error:
                return url, f"AI Error: {ai_error}"
            return url, ai_result or "AI returned empty response."

        except Exception as e:
            return url, f"Unexpected error processing this URL: {str(e)}"

    # Run all processing tasks concurrently
    tasks = [_fetch_and_process_one(u) for u in urls]
    results_list = await asyncio.gather(*tasks)

    # Format output
    if output_structure.lower() == "json":
        results_dict = {url: result_or_error for url, result_or_error in results_list}
        try:
            return json.dumps(results_dict, indent=2)
        except TypeError as e:
            return json.dumps(
                {"error": "Failed to serialize results to JSON", "details": str(e)}
            )
    else:
        # Markdown output
        output_parts = [f"# AI Processing Results for Multiple URLs\n"]
        output_parts.append(f"**Instructions Applied:**\n```\n{instructions}\n```\n---")
        for url, result_or_error in results_list:
            output_parts.append(f"## Result for: {url}\n")
            output_parts.append(f"```markdown\n{result_or_error}\n```\n---")
        return "\n".join(output_parts)


# --- Non-AI Tools (Mainly from Draft - Kept for Utility) ---


@mcp.tool()
async def fetch_url_content(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",  # markdown, html, text, json
    max_length: int = 50000,
    read_raw: bool = False,  # If true, ignores output_type and returns raw text
    ignore_robots: bool = False,
    user_agent: Optional[str] = None,
) -> str:
    """
    (Non-AI) Fetches content from a URL and returns it, optionally processing HTML to Markdown/Text.

    Args:
        url: URL to fetch.
        timeout: Request timeout in seconds.
        output_type: Output format ('markdown', 'html', 'text', 'json'). Ignored if read_raw is True.
        max_length: Maximum length of content to return (truncates if longer).
        read_raw: If True, return raw content without processing (ignores output_type).
        ignore_robots: If True, ignore robots.txt restrictions.
        user_agent: Custom user agent string.

    Returns:
        Fetched content in the requested format, or an error message.
    """
    try:
        AnyUrl(url)
    except ValidationError as e:
        return f"Error: Invalid URL format: {e}"

    _user_agent = user_agent or DEFAULT_USER_AGENT

    content, content_type, status_code, metadata = await fetch_url(
        url, user_agent=_user_agent, timeout=timeout, ignore_robots=ignore_robots
    )

    if status_code >= 400 or content is None:
        error_msg = metadata.get(
            "error", f"Failed to fetch URL (Status: {status_code})"
        )
        return f"Error fetching {url}: {error_msg}"

    # Handle truncation notice separately
    truncated = False
    if len(content) > max_length:
        content = content[:max_length]
        truncated = True
        truncation_notice = f"\n\n[Content truncated. Original size: {metadata.get('size', 'unknown')} chars]"
    else:
        truncation_notice = ""

    if read_raw:
        return content + truncation_notice

    # Process based on output type
    output_type_lower = output_type.lower()

    if output_type_lower == "json":
        output_data = {
            "url": metadata.get("final_url", url),
            "status_code": status_code,
            "content_type": content_type,
            "truncated": truncated,
            "original_size": metadata.get("size"),
            "metadata": {
                k: v
                for k, v in metadata.items()
                if k
                not in [
                    "headers",
                    "error",
                    "final_url",
                    "status_code",
                    "content_type",
                    "size",
                ]
            },  # Avoid redundant/large fields
        }
        if "text/html" in (content_type or ""):
            output_data["markdown_content"] = extract_content_from_html(
                content
            )  # No length limit here, raw content already truncated
            output_data["raw_html_snippet"] = content  # Use already truncated content
        elif "application/json" in (content_type or ""):
            try:
                output_data["parsed_json"] = json.loads(content)
            except json.JSONDecodeError:
                output_data["raw_content"] = content
        else:
            output_data["text_content"] = content
        return (
            json.dumps(output_data, indent=2) + truncation_notice
        )  # Notice outside JSON

    elif "text/html" in (content_type or ""):
        if output_type_lower == "html":
            return content + truncation_notice
        elif output_type_lower in ["markdown", "text"]:
            # Use text for text type for cleaner output if markdownify fails
            return extract_content_from_html(content) + truncation_notice
        else:  # Default to markdown for unknown types from HTML
            return extract_content_from_html(content) + truncation_notice

    # Handle non-HTML types
    elif output_type_lower in ["text", "markdown", "html"]:  # Treat as text
        return content + truncation_notice
    else:  # Default fallback is raw text for unknown output types
        return content + truncation_notice


@mcp.tool()
async def process_web_content(  # Note: This does NOT use AI.
    content: str,
    url: str = "(source URL not provided)",
    content_type: Optional[str] = None,
    output_type: str = "markdown",
    instructions: Optional[str] = None,  # Basic instructions only
    extract_elements: Optional[List[str]] = None,  # Requires beautifulsoup4
    max_length: int = 50000,
) -> str:
    """
    (Non-AI) Process provided web content (e.g., HTML to Markdown, basic extraction).

    Args:
        content: Raw web content to process.
        url: Source URL (for context/logging).
        content_type: MIME type (e.g., 'text/html', 'application/json'). Auto-detected if None.
        output_type: Output format ('markdown', 'html', 'text', 'json').
        instructions: Basic instructions (e.g., 'extract main article' - very limited).
        extract_elements: CSS selectors for elements to extract from HTML (requires beautifulsoup4).
        max_length: Maximum length of the returned content.

    Returns:
        Processed content or an error message.
    """
    # Auto-detect content type if not provided
    if not content_type:
        content_lower_snippet = content[:1000].lower().strip()
        if (
            content_lower_snippet.startswith("{")
            and content_lower_snippet.endswith("}")
            or content_lower_snippet.startswith("[")
        ):
            content_type = "application/json"
        elif (
            "<html" in content_lower_snippet
            or "<!doctype html" in content_lower_snippet
        ):
            content_type = "text/html"
        else:
            content_type = "text/plain"  # Default

    # --- Basic Instruction Handling (Non-AI) ---
    processed_output = None
    if instructions:
        if (
            "extract main article" in instructions.lower()
            and "text/html" in content_type
        ):
            # Simplistic: try markdownify first
            processed_output = extract_content_from_html(content)
        # Add more basic, non-AI instruction handlers here if needed
        # else: return f"Unsupported instruction for non-AI processing: '{instructions}'"

    # --- Element Extraction (Requires BeautifulSoup) ---
    elif extract_elements and "text/html" in content_type:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(content, "html.parser")
            extracted_parts = []
            for selector in extract_elements:
                elements = soup.select(selector)
                for element in elements:
                    if output_type.lower() == "html":
                        extracted_parts.append(str(element))
                    else:  # Default to markdown/text
                        try:
                            extracted_parts.append(
                                markdownify.markdownify(
                                    str(element), heading_style=markdownify.ATX
                                )
                            )
                        except Exception:
                            extracted_parts.append(
                                element.get_text(" ", strip=True)
                            )  # Fallback to text
            processed_output = "\n\n---\n\n".join(extracted_parts)
            if not processed_output:
                processed_output = (
                    f"<e>No elements found matching selectors: {extract_elements}</e>"
                )
        except ImportError:
            return "Error: 'beautifulsoup4' library is required for element extraction."
        except Exception as e:
            return f"Error extracting elements: {str(e)}"

    # --- Default Processing based on output_type if no specific handler used ---
    if processed_output is None:
        output_type_lower = output_type.lower()
        if output_type_lower == "json":
            # Basic JSON structure for provided content
            try:
                # Try parsing if it looks like JSON
                if content_type == "application/json":
                    parsed = json.loads(content)
                else:
                    parsed = content  # Keep as string otherwise
                processed_output = json.dumps(
                    {"url": url, "content_type": content_type, "content": parsed},
                    indent=2,
                )
            except json.JSONDecodeError:
                processed_output = json.dumps(
                    {
                        "url": url,
                        "content_type": content_type,
                        "error": "Content is not valid JSON",
                        "raw_content": content[:500] + "...",
                    },
                    indent=2,
                )  # Include snippet
        elif "text/html" in content_type:
            if output_type_lower == "html":
                processed_output = content
            else:
                processed_output = extract_content_from_html(
                    content
                )  # Default to markdown
        else:  # Plain text or other types
            processed_output = content

    # Final truncation
    if len(processed_output) > max_length:
        processed_output = (
            processed_output[:max_length]
            + f"\n\n[Processed content truncated at {max_length} characters]"
        )

    return processed_output


@mcp.tool()
async def fetch_multiple_urls(  # Note: This does NOT use AI.
    urls: List[str],
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",  # markdown, html, text, json
    max_length: int = 10000,  # Max length *per URL* in combined output
    ignore_robots: bool = False,
    user_agent: Optional[str] = None,
    output_structure: str = "json",  # 'json' or 'markdown'
) -> str:
    """
    (Non-AI) Fetches content from multiple URLs and combines them (JSON map or Markdown sections).

    Args:
        urls: List of URLs to fetch.
        timeout: Request timeout in seconds for each URL.
        output_type: Output format for each URL's content ('markdown', 'html', 'text', 'json').
        max_length: Maximum length of content *per URL* to include in the output.
        ignore_robots: If True, ignore robots.txt restrictions.
        user_agent: Custom user agent string.
        output_structure: How to format the final combined output ('json' map or 'markdown' sections).


    Returns:
        Combined content as a JSON string map {url: result/error} or a single Markdown string.
    """
    if not urls:
        return f"Error: No URLs provided."

    _user_agent = user_agent or DEFAULT_USER_AGENT

    async def _fetch_one_basic(url: str):
        # Simplified fetch & format for the non-AI multi-fetch
        try:
            AnyUrl(url)  # Validate
            content, content_type, status_code, metadata = await fetch_url(
                url,
                user_agent=_user_agent,
                timeout=timeout,
                ignore_robots=ignore_robots,
            )

            if status_code >= 400 or content is None:
                return (
                    url,
                    f"Error fetching: {metadata.get('error', f'Status {status_code}')}",
                )

            # Use the other non-AI tool for basic processing (avoids duplicating logic)
            processed_content = await process_web_content(
                content=content,
                url=url,
                content_type=content_type,
                output_type=output_type,
                max_length=max_length,
            )
            # Check if processing itself returned an error message
            if processed_content.startswith("Error:") or processed_content.startswith(
                "<e>"
            ):
                return url, processed_content
            else:
                return url, processed_content

        except ValidationError as e:
            return url, f"Invalid URL format: {e}"
        except Exception as e:
            return url, f"Unexpected error processing this URL: {str(e)}"

    tasks = [_fetch_one_basic(u) for u in urls]
    results_list = await asyncio.gather(*tasks)

    # Format output
    if output_structure.lower() == "json":
        results_dict = {url: result_or_error for url, result_or_error in results_list}
        try:
            return json.dumps(results_dict, indent=2)
        except TypeError as e:
            return json.dumps(
                {"error": "Failed to serialize results to JSON", "details": str(e)}
            )
    else:  # Markdown
        output_parts = [f"# Basic Fetch Results for Multiple URLs\n---"]
        for url, result_or_error in results_list:
            output_parts.append(f"## Result for: {url}\n")
            output_parts.append(
                f"{result_or_error}\n---"
            )  # Assume result is already formatted string
        return "\n".join(output_parts)


# --- Crawl and Analyze Tools (From Draft - Require beautifulsoup4) ---
# These are kept as potentially useful non-AI tools.


@mcp.tool()
async def crawl_website(
    url: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",  # Format for content of *each* page
    output_file: Optional[str] = None,  # If provided, saves result to file
    follow_links: bool = True,
    ignore_robots: bool = False,
    user_agent: Optional[str] = None,
    allowed_domains: Optional[List[str]] = None,  # Restrict crawl
    # query: Optional[str] = None # Querying content adds complexity, removed for now
) -> str:
    """
    (Non-AI) Crawls a website starting from a URL, collects content from linked pages. Requires beautifulsoup4.

    Args:
        url: Starting URL to crawl.
        max_pages: Maximum number of pages to fetch.
        max_depth: Maximum link depth to follow from the start URL.
        timeout: Request timeout in seconds per page.
        output_type: Output format for each page's content ('markdown', 'html', 'text', 'json').
        output_file: Optional file path to save the combined results.
        follow_links: If False, only fetches the starting URL.
        ignore_robots: If True, ignore robots.txt restrictions.
        user_agent: Custom user agent string.
        allowed_domains: List of domain names (e.g., 'example.com') to restrict crawling to. If None, uses the starting URL's domain.

    Returns:
        Combined content from crawled pages (JSON or Markdown), or status message if saving to file. Requires 'beautifulsoup4'.
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except ImportError:
        return "Error: 'beautifulsoup4' library is required for crawling."

    try:
        AnyUrl(url)  # Validate start URL
    except ValidationError as e:
        return f"Error: Invalid start URL format: {e}"

    _user_agent = user_agent or DEFAULT_USER_AGENT
    start_time = datetime.now()

    # Determine base domain and allowed domains
    try:
        parsed_start_url = urlparse(url)
        base_domain = parsed_start_url.netloc
        if not base_domain:
            raise ValueError("Could not determine domain from start URL")
    except Exception as e:
        return f"Error parsing start URL domain: {e}"

    if not allowed_domains:
        _allowed_domains = {base_domain}
    else:
        _allowed_domains = set(allowed_domains)
        _allowed_domains.add(base_domain)  # Ensure start domain is always allowed

    # BFS crawl state
    queue = asyncio.Queue()
    queue.put_nowait((url, 0))  # (url, depth)
    crawled = {url}  # Set to track visited URLs
    results = []  # List to store results for each page

    async def worker():
        while not queue.empty() and len(crawled) <= max_pages:
            try:
                current_url, depth = await queue.get()

                print(
                    f"Crawling [Depth:{depth}, Total:{len(crawled)}/{max_pages}]: {current_url}",
                    file=sys.stderr,
                )

                # Fetch page
                content, content_type, status_code, metadata = await fetch_url(
                    current_url,
                    user_agent=_user_agent,
                    timeout=timeout,
                    ignore_robots=ignore_robots,
                )

                page_result = {
                    "url": metadata.get("final_url", current_url),
                    "depth": depth,
                    "status_code": status_code,
                    "content_type": content_type,
                    "error": metadata.get("error"),
                    "content": None,
                }

                if status_code < 400 and content is not None:
                    # Process content for this page
                    page_result["content"] = await process_web_content(
                        content=content,
                        url=current_url,
                        content_type=content_type,
                        output_type=output_type,
                        max_length=20000,  # Limit content per page in output
                    )

                    # Find and queue links if conditions met
                    if (
                        follow_links
                        and depth < max_depth
                        and "text/html" in (content_type or "")
                    ):
                        try:
                            soup = BeautifulSoup(content, "html.parser")
                            for a_tag in soup.find_all("a", href=True):
                                href = a_tag["href"]
                                try:
                                    absolute_url = urljoin(current_url, href)
                                    parsed_link = urlparse(absolute_url)

                                    # Basic validation and filtering
                                    if (
                                        parsed_link.scheme in ("http", "https")
                                        and parsed_link.netloc
                                        and parsed_link.netloc in _allowed_domains
                                        and absolute_url not in crawled
                                        and len(crawled) + queue.qsize() < max_pages
                                    ):
                                        crawled.add(absolute_url)
                                        await queue.put((absolute_url, depth + 1))
                                except Exception as link_e:
                                    print(
                                        f"Warning: Skipping link '{href}' due to parsing error: {link_e}",
                                        file=sys.stderr,
                                    )
                        except Exception as parse_e:
                            print(
                                f"Warning: Could not parse links on {current_url}: {parse_e}",
                                file=sys.stderr,
                            )

                results.append(page_result)
                queue.task_done()

            except asyncio.CancelledError:
                print("Crawler task cancelled.", file=sys.stderr)
                break
            except Exception as e:
                print(
                    f"Error in crawler worker for {current_url}: {e}", file=sys.stderr
                )
                queue.task_done()  # Ensure task is marked done even on error

    # Run crawler worker(s) - simple single worker for now
    # Use a timeout for the whole crawl process
    crawl_timeout = max_pages * timeout + 10  # Rough estimate
    try:
        await asyncio.wait_for(worker(), timeout=crawl_timeout)
        # Wait for queue to be fully processed if worker finishes early
        await queue.join()
    except asyncio.TimeoutError:
        print(
            f"Warning: Crawl timed out after {crawl_timeout} seconds.", file=sys.stderr
        )
    except Exception as e:
        print(f"Error during crawl execution: {e}", file=sys.stderr)

    # Format final output
    crawl_summary = {
        "start_url": url,
        "pages_attempted": len(crawled),
        "pages_successful": sum(
            1 for r in results if r["status_code"] < 400 and r["error"] is None
        ),
        "max_depth_reached": max((r["depth"] for r in results), default=0),
        "allowed_domains": list(_allowed_domains),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
        "results": results,
    }

    output_str = ""
    if output_type.lower() == "json":
        try:
            output_str = json.dumps(crawl_summary, indent=2)
        except TypeError:
            output_str = json.dumps({"error": "Failed to serialize crawl results"})
    else:  # Markdown summary
        output_parts = [f"# Crawl Report for: {url}\n"]
        output_parts.append(f"- Pages Attempted: {crawl_summary['pages_attempted']}")
        output_parts.append(f"- Pages Successful: {crawl_summary['pages_successful']}")
        output_parts.append(
            f"- Max Depth Reached: {crawl_summary['max_depth_reached']}"
        )
        output_parts.append(
            f"- Duration: {crawl_summary['duration_seconds']:.2f} seconds"
        )
        output_parts.append("\n## Page Details:\n---")
        for page in results:
            output_parts.append(
                f"### [{page['status_code']}] {page['url']} (Depth: {page['depth']})"
            )
            if page["error"]:
                output_parts.append(f"**Error:** {page['error']}")
            elif page["content"]:
                output_parts.append(
                    f"**Content Snippet ({output_type}):**\n```\n{page['content'][:500]}...\n```"
                )  # Show snippet
            else:
                output_parts.append("*(No content processed)*")
            output_parts.append("---")
        output_str = "\n".join(output_parts)

    # Save to file if requested
    if output_file:
        try:
            # Ensure directory exists if path includes directories
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_str)
            return f"Crawl results saved to '{output_file}'. Attempted {len(crawled)} pages."
        except Exception as e:
            return f"Error saving crawl results to file '{output_file}': {e}\n\n{output_str[:1000]}..."  # Return error and snippet

    return output_str


@mcp.tool()
async def analyze_url(  # Note: This does NOT use AI.
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    analyze_seo: bool = True,
    # analyze_accessibility: bool = True, # Complex, removed for now
    # analyze_performance: bool = True, # Basic perf included
    analyze_content: bool = True,
    output_type: str = "markdown",  # 'markdown' or 'json'
    user_agent: Optional[str] = None,
) -> str:
    """
    (Non-AI) Fetches a URL and performs basic analysis (SEO, Content Structure). Requires beautifulsoup4.

    Args:
        url: URL to analyze.
        timeout: Request timeout in seconds.
        analyze_seo: Include basic SEO checks (title, meta description, canonical).
        analyze_content: Include basic content structure analysis (headings, links, images).
        output_type: Output format ('markdown' or 'json').
        user_agent: Custom user agent string.

    Returns:
        Analysis results in the requested format. Requires 'beautifulsoup4'.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: 'beautifulsoup4' library is required for analysis."

    try:
        AnyUrl(url)
    except ValidationError as e:
        return f"Error: Invalid URL format: {e}"

    _user_agent = user_agent or DEFAULT_USER_AGENT

    content, content_type, status_code, metadata = await fetch_url(
        url,
        user_agent=_user_agent,
        timeout=timeout,
        ignore_robots=True,  # Ignore robots for analysis
    )

    if (
        status_code >= 400
        or content is None
        or not ("text/html" in (content_type or ""))
    ):
        error_msg = (
            metadata.get("error", f"HTTP Status {status_code}")
            if content is None
            else f"Content type '{content_type}' is not HTML"
        )
        return f"Error: Cannot analyze {url}. Reason: {error_msg}"

    results = {
        "url": metadata.get("final_url", url),
        "status_code": status_code,
        "content_type": content_type,
        "load_time_seconds": metadata.get("elapsed"),
        "content_size_bytes": metadata.get("size"),
        "analysis_timestamp": datetime.now().isoformat(),
        "seo_analysis": {},
        "content_analysis": {},
    }

    try:
        soup = BeautifulSoup(content, "html.parser")

        # --- SEO Analysis ---
        if analyze_seo:
            title_tag = soup.find("title")
            results["seo_analysis"]["title"] = (
                title_tag.string.strip() if title_tag else None
            )
            desc_tag = soup.find("meta", attrs={"name": "description"})
            results["seo_analysis"]["meta_description"] = (
                desc_tag["content"].strip()
                if desc_tag and "content" in desc_tag.attrs
                else None
            )
            keywords_tag = soup.find("meta", attrs={"name": "keywords"})
            results["seo_analysis"]["meta_keywords"] = (
                keywords_tag["content"].strip()
                if keywords_tag and "content" in keywords_tag.attrs
                else None
            )
            canonical_tag = soup.find("link", attrs={"rel": "canonical"})
            results["seo_analysis"]["canonical_url"] = (
                canonical_tag["href"]
                if canonical_tag and "href" in canonical_tag.attrs
                else None
            )
            robots_tag = soup.find("meta", attrs={"name": "robots"})
            results["seo_analysis"]["meta_robots"] = (
                robots_tag["content"]
                if robots_tag and "content" in robots_tag.attrs
                else None
            )
            og_title = soup.find("meta", property="og:title")
            results["seo_analysis"]["og_title"] = (
                og_title["content"]
                if og_title and "content" in og_title.attrs
                else None
            )
            og_desc = soup.find("meta", property="og:description")
            results["seo_analysis"]["og_description"] = (
                og_desc["content"] if og_desc and "content" in og_desc.attrs else None
            )

        # --- Content Analysis ---
        if analyze_content:
            headings = {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 7)}
            text_content = soup.get_text(" ", strip=True)
            results["content_analysis"] = {
                "headings_count": headings,
                "links_count": len(soup.find_all("a", href=True)),
                "images_count": len(soup.find_all("img")),
                "images_missing_alt": len(
                    soup.find_all("img", alt=lambda x: not x or not x.strip())
                ),
                "paragraphs_count": len(soup.find_all("p")),
                "lists_count": len(soup.find_all(["ul", "ol"])),
                "tables_count": len(soup.find_all("table")),
                "forms_count": len(soup.find_all("form")),
                "iframes_count": len(soup.find_all("iframe")),
                "scripts_count": len(soup.find_all("script")),
                "styles_count": len(soup.find_all("style")),  # Inline/internal styles
                "word_count": len(text_content.split()),
                "character_count": len(text_content),
            }

    except Exception as e:
        results["error"] = f"Error during HTML parsing or analysis: {str(e)}"

    # --- Format Output ---
    if output_type.lower() == "json":
        try:
            return json.dumps(results, indent=2)
        except TypeError:
            return json.dumps({"error": "Failed to serialize analysis results"})
    else:  # Markdown
        md_parts = [f"# Analysis Report for: {results['url']}\n"]
        md_parts.append(f"- Status Code: {results['status_code']}")
        md_parts.append(
            f"- Load Time: {results['load_time_seconds']:.3f}s"
            if results["load_time_seconds"] is not None
            else "- Load Time: N/A"
        )
        md_parts.append(
            f"- Content Size: {results['content_size_bytes']} bytes"
            if results["content_size_bytes"] is not None
            else "- Content Size: N/A"
        )

        if results.get("error"):
            md_parts.append(f"\n**Analysis Error:** {results['error']}")

        if analyze_seo and results["seo_analysis"]:
            md_parts.append("\n## SEO Analysis")
            for key, value in results["seo_analysis"].items():
                md_parts.append(
                    f"- **{key.replace('_', ' ').title()}**: {value if value is not None else '*Not Found*'}"
                )

        if analyze_content and results["content_analysis"]:
            md_parts.append("\n## Content Analysis")
            ca = results["content_analysis"]
            md_parts.append(f"- **Word Count**: {ca['word_count']}")
            md_parts.append(f"- **Character Count**: {ca['character_count']}")
            md_parts.append(
                "- **Headings**: "
                + ", ".join(
                    f"H{i}: {count}"
                    for i, count in ca["headings_count"].items()
                    if count > 0
                )
            )
            md_parts.append(f"- **Links**: {ca['links_count']}")
            md_parts.append(
                f"- **Images**: {ca['images_count']} ({ca['images_missing_alt']} missing alt text)"
            )
            md_parts.append(f"- **Paragraphs**: {ca['paragraphs_count']}")
            md_parts.append(f"- **Lists (ul/ol)**: {ca['lists_count']}")
            md_parts.append(f"- **Tables**: {ca['tables_count']}")
            md_parts.append(f"- **Forms**: {ca['forms_count']}")

        return "\n".join(md_parts)


if __name__ == "__main__":
    if not openai_client:
        print(
            "Warning: OpenAI client not initialized. AI-powered tools (`fetch_and_process_*`) will return errors.",
            file=sys.stderr,
        )
    print("Web Processing MCP Server running", file=sys.stderr)
    mcp.run()
