import sys
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse
import httpx
from pydantic import AnyUrl, ValidationError
import markdownify

from mcp.server.fastmcp import FastMCP


# Create MCP server
mcp = FastMCP("web-processing-server")

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30
# Default max length for fetched content before sending to AI (characters)
DEFAULT_FETCH_MAX_LENGTH = 100000
# Default User Agent
DEFAULT_USER_AGENT = "ModelContextProtocol-WebProcessor/1.0 (+https://github.com/modelcontextprotocol/servers)"
# Default OpenAI Model
DEFAULT_OPENAI_MODEL = "o3-mini"
# Default Max Tokens for OpenAI response
DEFAULT_OPENAI_MAX_TOKENS = 10000

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

# --- AI Agent System Prompt ---
AI_AGENT_SYSTEM_PROMPT = """
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


async def fetch_url(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[Optional[str], Optional[str], int, Dict[str, Any]]:
    """
    Fetch the URL and return the content, content type, status code, and metadata.
    Returns (None, None, status, metadata) on error.
    """
    metadata = {"original_url": url, "error": None}

    # Fetch the URL
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


async def process_web_content(
    content: str,
    url: str,
    content_type: Optional[str] = None,
    output_type: str = "markdown",
    extract_elements: Optional[List[str]] = None,
) -> str:
    """Processes web content with basic transformations."""
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
    if "text/html" in content_type:
        # Simplistic: try markdownify first
        processed_output = extract_content_from_html(content)

    # --- Element Extraction (Requires BeautifulSoup) ---
    if extract_elements and "text/html" in content_type:
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

    return processed_output


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
                {"role": "system", "content": AI_AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=max_tokens,
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
    user_agent: Optional[str] = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
    preprocess_to_format: str = "markdown",  # Hint for pre-processing before AI
) -> str:
    """
    Fetches URL content and processes it with an external AI agent based on instructions.
    
    Args:
        url: URL to fetch
        instructions: Prompts for the AI agent on how toprocess data
        timeout: Request timeout in seconds (default: 30)
        max_length: Max chars to process (default: 100000)
        user_agent: Custom user agent string.
        openai_model: AI model to use (default: 'o3-mini')
        openai_max_tokens: Max tokens for AI response (default: 10000)
        preprocess_to_format: Format to convert content to BEFORE sending to AI ('markdown', 'text', 'html'). Markdown recommended.
    
    Returns:
        AI-processed content or error message
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
        url, user_agent=_user_agent, timeout=timeout
    )

    # Handle fetch errors
    if status_code >= 400 or content is None:
        error_msg = metadata.get(
            "error", f"Failed to fetch URL (Status: {status_code})"
        )
        return f"Error fetching {url}: {error_msg}"

    # 2. Pre-process content based on hint (usually convert to Markdown)
    processed_content = ""
    if "text/html" in (content_type or "") and preprocess_to_format != "html":
        processed_content = extract_content_from_html(content, max_length=max_length)
    elif "text/" in (content_type or "") or preprocess_to_format == "text":
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
    user_agent: Optional[str] = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
    preprocess_to_format: str = "markdown",
) -> str:
    """
    Fetches multiple URLs and processes each with an external AI agent using the same instructions.
    
    Args:
        urls: List of URLs to fetch
        instructions: Instructions for AI to process each URL
        timeout: Request timeout per URL in seconds (default: 30)
        max_length: Max chars per URL to process (default: 100000)
        user_agent: Custom user agent string
        openai_model: AI model to use (default: 'o3-mini')
        openai_max_tokens: Max tokens for AI responses (default: 10000)
        preprocess_to_format: Format to convert content to BEFORE sending to AI ('markdown', 'text', 'html'). Markdown recommended.
    
    Returns:
        Combined results as JSON map or markdown
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
            )

            if status_code >= 400 or content is None:
                return (
                    url,
                    f"Error fetching: {metadata.get('error', f'Status {status_code}')}",
                )

            # Pre-process
            processed_content = ""
            if "text/html" in (content_type or "") and preprocess_to_format != "html":
                processed_content = extract_content_from_html(
                    content, max_length=max_length
                )
            elif "text/" in (content_type or "") or preprocess_to_format == "text":
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
    output_parts = ["# AI Processing Results for Multiple URLs\n"]
    output_parts.append(f"**Instructions Applied:**\n```\n{instructions}\n```\n---")
    for url, result_or_error in results_list:
        output_parts.append(f"## Result for: {url}\n")
        output_parts.append(f"```markdown\n{result_or_error}\n```\n---")
    return "\n".join(output_parts)



# --- Non-AI Tools ---


@mcp.tool()
async def fetch_url_content(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",
    max_length: int = DEFAULT_FETCH_MAX_LENGTH,

) -> str:
    """
    Fetches URL content without AI processing.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (default: 30)
        output_type: Output format (default: 'markdown', options: 'html', 'text', 'json', 'raw')
        max_length: Max chars to return (default: 100000)
    
    Returns:
        Fetched content in requested format or error message
    """
    try:
        AnyUrl(url)
    except ValidationError as e:
        return f"Error: Invalid URL format: {e}"

    _user_agent = DEFAULT_USER_AGENT

    content, content_type, status_code, metadata = await fetch_url(
        url, user_agent=_user_agent, timeout=timeout
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

    # Process based on output type
    output_type_lower = output_type.lower()

    if output_type_lower == "raw":
        return content
    elif output_type_lower == "json":
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
async def fetch_multiple_urls(  # Note: This does NOT use AI.
    urls: List[str],
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",  # markdown, html, text, json
    max_length: int = DEFAULT_FETCH_MAX_LENGTH,  # Max length *per URL* in combined output
    output_structure: str = "json",  # 'json' or 'markdown'
) -> str:
    """
    Fetches multiple URLs (non-AI) and combines their content.
    
    Args:
        urls: URLs to fetch
        timeout: Request timeout per URL in seconds (default: 30)
        output_type: Format for each URL's content (default: 'markdown')
        max_length: Max chars per URL in output (default: 100000)
        output_structure: Combined output format (default: 'json', alt: 'markdown')
    
    Returns:
        Combined content as JSON map or markdown
    """
    if not urls:
        return "Error: No URLs provided."

    _user_agent = DEFAULT_USER_AGENT

    async def _fetch_one_basic(url: str):
        # Simplified fetch & format for the non-AI multi-fetch
        try:
            AnyUrl(url)  # Validate
            content, content_type, status_code, metadata = await fetch_url(
                url,
                user_agent=_user_agent,
                timeout=timeout,
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
        output_parts = ["# Basic Fetch Results for Multiple URLs\n---"]
        for url, result_or_error in results_list:
            output_parts.append(f"## Result for: {url}\n")
            output_parts.append(
                f"{result_or_error}\n---"
            )  # Assume result is already formatted string
        return "\n".join(output_parts)


# --- Crawl and Analyze Tools  ---

@mcp.tool()
async def crawl_website(
    url: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "markdown",  # Format for content of *each* page
    output_file: Optional[str] = None,  # If provided, saves result to file
    follow_links: bool = True,
    allowed_domains: Optional[List[str]] = None,  # Restrict crawl
) -> str:
    """
    Crawls website starting from URL, collecting linked pages.
    
    Args:
        url: Starting URL
        max_pages: Max pages to fetch (default: 5)
        max_depth: Max link depth from start URL (default: 2)
        timeout: Request timeout per page in seconds (default: 30)
        output_type: Content format per page (default: 'markdown')
        output_file: Path to save results (default: None)
        follow_links: Find and follow links if True (default: True)
        ignore_robots: Skip robots.txt checks if True (default: True)
        allowed_domains: Domains to restrict crawling to (default: start URL's domain)
    
    Returns:
        Combined crawl results or status if saving to file
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

    _user_agent = DEFAULT_USER_AGENT
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
    pages_content = []  # List to store page content for AI processing

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
                )

                if status_code < 400 and content is not None:
                    # Pre-process content for AI
                    processed_content = ""
                    if "text/html" in (content_type or ""):
                        processed_content = extract_content_from_html(content)
                    elif "text/" in (content_type or ""):
                        processed_content = content
                    else:
                        processed_content = content

                    if processed_content and processed_content.strip():
                        pages_content.append({
                            "url": metadata.get("final_url", current_url),
                            "depth": depth,
                            "content": processed_content,
                            "content_type": content_type
                        })

                    # Find and queue links if conditions met
                    if (
                        depth < max_depth
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

                queue.task_done()

            except asyncio.CancelledError:
                print("Crawler task cancelled.", file=sys.stderr)
                break
            except Exception as e:
                print(
                    f"Error in crawler worker for {current_url}: {e}", file=sys.stderr
                )
                queue.task_done()  # Ensure task is marked done even on error

    # Run crawler worker
    crawl_timeout = max_pages * timeout + 10
    try:
        await asyncio.wait_for(worker(), timeout=crawl_timeout)
        await queue.join()
    except asyncio.TimeoutError:
        print(
            f"Warning: Crawl timed out after {crawl_timeout} seconds.", file=sys.stderr
        )
    except Exception as e:
        print(f"Error during crawl execution: {e}", file=sys.stderr)

    if not pages_content:
        return "No valid content was found during crawling."

    # Prepare content for AI processing
    combined_content = ""
    for i, page in enumerate(pages_content):
        combined_content += f"\n\n--- PAGE {i+1}: {page['url']} ---\n\n"
        combined_content += page['content']

    # Process with AI
    ai_result, ai_error = await _call_openai(
        content=combined_content,
        instructions=instructions,
        model=openai_model,
        max_tokens=openai_max_tokens,
    )

    if ai_error:
        return f"Error processing crawled content with AI: {ai_error}"

    if output_structure.lower() == "json":
        try:
            # Try to add some structure to the result
            result_data = {
                "crawl_info": {
                    "start_url": url,
                    "pages_crawled": len(crawled),
                    "pages_with_content": len(pages_content),
                    "max_depth_reached": max((p["depth"] for p in pages_content), default=0),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                },
                "ai_processed_result": ai_result
            }
            return json.dumps(result_data, indent=2)
        except:
            # Fall back to simple JSON if structuring fails
            return json.dumps({"result": ai_result})
    else:
        # Markdown output
        output_parts = ["# AI Analysis of Crawled Content\n"]
        output_parts.append(f"- Starting URL: {url}")
        output_parts.append(f"- Pages Crawled: {len(crawled)}")
        output_parts.append(f"- Pages With Content: {len(pages_content)}")
        output_parts.append(f"- Duration: {(datetime.now() - start_time).total_seconds():.2f} seconds")
        output_parts.append("\n## AI Analysis\n")
        output_parts.append(ai_result or "AI returned an empty response.")
        return "\n".join(output_parts)


if __name__ == "__main__":
    if not openai_client:
        print(
            "Warning: OpenAI client not initialized. AI-powered tools (`fetch_and_process_*`) will return errors.",
            file=sys.stderr,
        )
    print("Web Processing MCP Server running", file=sys.stderr)
    mcp.run()
