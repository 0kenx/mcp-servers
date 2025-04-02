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


def _extract_content_from_html(html: str, max_length: Optional[int] = None) -> str:
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


async def _fetch_url(
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


async def _process_web_content(
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
        processed_output = _extract_content_from_html(content)

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
                processed_output = _extract_content_from_html(
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


async def _crawl_url(
    url: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_domains: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Core crawling logic to collect content from multiple linked pages.

    Returns:
        Tuple containing (list of page content dicts, crawl metadata dict)
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
    except ImportError:
        raise ImportError("'beautifulsoup4' library is required for crawling.")

    try:
        AnyUrl(url)  # Validate start URL
    except ValidationError as e:
        raise ValueError(f"Invalid start URL format: {e}")

    _user_agent = DEFAULT_USER_AGENT
    start_time = datetime.now()

    # Determine base domain and allowed domains
    try:
        parsed_start_url = urlparse(url)
        base_domain = parsed_start_url.netloc
        if not base_domain:
            raise ValueError("Could not determine domain from start URL")
    except Exception as e:
        raise ValueError(f"Error parsing start URL domain: {e}")

    if not allowed_domains:
        _allowed_domains = {base_domain}
    else:
        _allowed_domains = set(allowed_domains)
        _allowed_domains.add(base_domain)  # Ensure start domain is always allowed

    # BFS crawl state
    queue = asyncio.Queue()
    queue.put_nowait((url, 0))  # (url, depth)
    crawled = {url}  # Set to track visited URLs
    pages_content = []  # List to store page content

    async def worker():
        while not queue.empty() and len(crawled) <= max_pages:
            try:
                current_url, depth = await queue.get()

                print(
                    f"Crawling [Depth:{depth}, Total:{len(crawled)}/{max_pages}]: {current_url}",
                    file=sys.stderr,
                )

                # Fetch page
                content, content_type, status_code, metadata = await _fetch_url(
                    current_url,
                    user_agent=_user_agent,
                    timeout=timeout,
                )

                if status_code < 400 and content is not None:
                    # Pre-process content
                    processed_content = ""
                    if "text/html" in (content_type or ""):
                        processed_content = _extract_content_from_html(content)
                    elif "text/" in (content_type or ""):
                        processed_content = content
                    else:
                        processed_content = content

                    if processed_content and processed_content.strip():
                        pages_content.append(
                            {
                                "url": metadata.get("final_url", current_url),
                                "depth": depth,
                                "content": processed_content,
                                "content_type": content_type,
                                "status_code": status_code,
                            }
                        )

                    # Find and queue links if conditions met
                    if depth < max_depth and "text/html" in (content_type or ""):
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
                    f"Error in crawler worker for {current_url}: {e}",
                    file=sys.stderr,
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

    # Prepare metadata
    crawl_metadata = {
        "start_url": url,
        "pages_crawled": len(crawled),
        "pages_with_content": len(pages_content),
        "max_depth_reached": max((p.get("depth", 0) for p in pages_content), default=0),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
        "allowed_domains": list(_allowed_domains),
    }

    return pages_content, crawl_metadata


# --- MCP Tools ---


@mcp.tool()
async def fetch_and_process_urls(
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
    Fetches list of URLs, combines content, and processes with an external AI agent following instructions.

    Args:
        urls: List of URLs to fetch
        instructions: Instructions for AI to process the combined content
        timeout: Request timeout per URL in seconds (default: 30)
        max_length: Max chars per URL to process (default: 100000)
        user_agent: Custom user agent string
        openai_model: AI model to use (default: 'o3-mini')
        openai_max_tokens: Max tokens for AI responses (default: 10000)
        preprocess_to_format: Format to convert content to BEFORE sending to AI ('markdown', 'text', 'html'). Markdown recommended.

    Returns:
        AI-processed combined content
    """
    if not openai_client:
        return "Error: OpenAI client not available. Cannot process with AI."
    if not urls:
        return "Error: No URLs provided."

    _user_agent = user_agent or DEFAULT_USER_AGENT

    async def _fetch_one(url: str):
        try:
            # Validate URL
            try:
                AnyUrl(url)
            except ValidationError as e:
                return url, None, f"Invalid URL format: {e}"

            # Fetch
            content, content_type, status_code, metadata = await _fetch_url(
                url,
                user_agent=_user_agent,
                timeout=timeout,
            )

            if status_code >= 400 or content is None:
                return (
                    url,
                    None,
                    f"Error fetching: {metadata.get('error', f'Status {status_code}')}",
                )

            # Pre-process
            processed_content = ""
            if "text/html" in (content_type or "") and preprocess_to_format != "html":
                processed_content = _extract_content_from_html(
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
                return (
                    url,
                    None,
                    "Error processing HTML: Could not convert to Markdown.",
                )
            if not processed_content.strip():
                return (
                    url,
                    None,
                    "Error: Fetched content appears empty after processing.",
                )

            return url, processed_content, None

        except Exception as e:
            return url, None, f"Unexpected error processing this URL: {str(e)}"

    # Run all fetch tasks concurrently
    tasks = [_fetch_one(u) for u in urls]
    results_list = await asyncio.gather(*tasks)

    # Combine all successful content
    combined_content = ""
    fetch_summary = []

    for url, content, error in results_list:
        if content:
            combined_content += f"\n\n--- URL: {url} ---\n\n{content}\n\n"
            fetch_summary.append({"url": url, "status": "success"})
        else:
            fetch_summary.append({"url": url, "status": "error", "error": error})

    if not combined_content:
        return "Error: No content could be fetched from any of the provided URLs."

    # Call AI once with combined content
    ai_result, ai_error = await _call_openai(
        content=combined_content,
        instructions=instructions,
        model=openai_model,
        max_tokens=openai_max_tokens,
    )

    if ai_error:
        return f"Error processing the combined content with AI: {ai_error}"

    # Format output
    output_parts = ["# AI Agent Processing of Multiple URLs\n"]
    output_parts.append(f"**Instructions Applied:**\n```\n{instructions}\n```\n")

    # Add fetch summary
    output_parts.append("## URLs Processed\n")
    for item in fetch_summary:
        if item["status"] == "success":
            output_parts.append(f"- SUCCESS: {item['url']}")
        else:
            output_parts.append(f"- ERROR: {item['url']} - {item['error']}")

    output_parts.append("\n## AI Agent Analysis Result\n")
    output_parts.append(ai_result or "AI agent returned an empty response.")

    return "\n".join(output_parts)


@mcp.tool()
async def crawl_and_process_url(
    url: str,
    instructions: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_domains: Optional[List[str]] = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
) -> str:
    """
    Crawls website and processes discovered pages with AI based on instructions.

    Args:
        url: Starting URL to crawl
        instructions: Instructions for AI processing of crawled content
        max_pages: Max pages to fetch (default: 5)
        max_depth: Max link depth from start URL (default: 2)
        timeout: Request timeout per page in seconds (default: 30)
        allowed_domains: Domains to restrict crawling to (default: start URL's domain)
        openai_model: AI model to use (default: 'o3-mini')
        openai_max_tokens: Max tokens for AI response (default: 10000)

    Returns:
        AI-processed content from crawled pages
    """
    if not openai_client:
        return "Error: OpenAI client not available. Cannot process with AI."

    try:
        # Call the core crawling function
        pages_content, crawl_metadata = await _crawl_url(
            url=url,
            max_pages=max_pages,
            max_depth=max_depth,
            timeout=timeout,
            allowed_domains=allowed_domains,
        )

        if not pages_content:
            return "No valid content was found during crawling."

        # Prepare content for AI processing
        combined_content = ""
        for i, page in enumerate(pages_content):
            combined_content += f"\n\n--- PAGE {i + 1}: {page['url']} ---\n\n"
            combined_content += page["content"]

        # Process with AI
        ai_result, ai_error = await _call_openai(
            content=combined_content,
            instructions=instructions,
            model=openai_model,
            max_tokens=openai_max_tokens,
        )

        if ai_error:
            return f"Error processing crawled content with AI: {ai_error}"

        # Markdown output
        output_parts = ["# AI Analysis of Crawled Content\n"]
        output_parts.append(f"- Starting URL: {url}")
        output_parts.append(f"- Pages Crawled: {crawl_metadata['pages_crawled']}")
        output_parts.append(
            f"- Pages With Content: {crawl_metadata['pages_with_content']}"
        )
        output_parts.append(
            f"- Max Depth Reached: {crawl_metadata['max_depth_reached']}"
        )
        output_parts.append(
            f"- Duration: {crawl_metadata['duration_seconds']:.2f} seconds"
        )
        output_parts.append("\n## AI Analysis\n")
        output_parts.append(ai_result or "AI returned an empty response.")
        return "\n".join(output_parts)

    except ImportError as e:
        return f"Error: {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error during crawl and process: {str(e)}"


# --- Non-AI Tools ---


@mcp.tool()
async def fetch_url(
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

    content, content_type, status_code, metadata = await _fetch_url(
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
            output_data["markdown_content"] = _extract_content_from_html(
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
            return _extract_content_from_html(content) + truncation_notice
        else:  # Default to markdown for unknown types from HTML
            return _extract_content_from_html(content) + truncation_notice

    # Handle non-HTML types
    elif output_type_lower in ["text", "markdown", "html"]:  # Treat as text
        return content + truncation_notice
    else:  # Default fallback is raw text for unknown output types
        return content + truncation_notice


@mcp.tool()
async def crawl_website(
    url: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
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
        follow_links: Find and follow links if True (default: True)
        allowed_domains: Domains to restrict crawling to (default: start URL's domain)

    Returns:
        Combined crawl results or status if saving to file
    """
    try:
        if not follow_links:
            max_depth = 0

        # Call the core crawling function
        pages_content, crawl_metadata = await _crawl_url(
            url=url,
            max_pages=max_pages,
            max_depth=max_depth,
            timeout=timeout,
            allowed_domains=allowed_domains,
        )

        if not pages_content:
            return "No valid content was found during crawling."

        # Format output
        output_parts = [f"# Crawl Report for: {url}\n"]
        output_parts.append(f"- Pages Crawled: {crawl_metadata['pages_crawled']}")
        output_parts.append(
            f"- Pages With Content: {crawl_metadata['pages_with_content']}"
        )
        output_parts.append(
            f"- Max Depth Reached: {crawl_metadata['max_depth_reached']}"
        )
        output_parts.append(
            f"- Duration: {crawl_metadata['duration_seconds']:.2f} seconds"
        )
        output_parts.append("\n## Page Details:\n---")

        for page in pages_content:
            output_parts.append(
                f"### [{page.get('status_code', 'N/A')}] {page['url']} (Depth: {page['depth']})"
            )
            if page.get("content"):
                output_parts.append(
                    f"**Content Snippet:**\n```\n{page['content'][:500]}...\n```"
                )
            else:
                output_parts.append("*(No content processed)*")
            output_parts.append("---")

        output_str = "\n".join(output_parts)

        return output_str

    except ImportError as e:
        return f"Error: {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error during crawl: {str(e)}"


if __name__ == "__main__":
    if not openai_client:
        print(
            "Warning: OpenAI client not initialized. AI-powered tools (`fetch_and_process_*`) will return errors.",
            file=sys.stderr,
        )
    print("Web Processing MCP Server running", file=sys.stderr)
    mcp.run()
