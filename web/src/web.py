import sys
import os
import json
import asyncio
import httpx
import markdownify
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pydantic import AnyUrl, ValidationError

from mcp.server.fastmcp import FastMCP

MCP_INSTRUCTIONS = """
This Web Processing MCP Server enables you to retrieve, crawl, search, and intelligently process web content, transforming raw web data into structured, useful information.

The server excels at tasks ranging from fetching single URLs to multi-page website crawling with intelligent processing of discovered content. By combining web access with AI-powered analysis, this server enables comprehensive web interaction capabilities.

Key capabilities:
- Use `fetch_url` for simple content retrieval from a single known URL
- Use `fetch_urls_and_process` when you need to analyze content from multiple specific URLs with an AI agent according to your instructions. This is the recommended tool
- Use `crawl_website` when you need to systematically explore a website's content, following links with configurable depth and page limits
- Use `crawl_url_and_process` for deep analysis of entire website sections with an AI agent according to your instructions
- Use `search_web` when you need to find information across the internet on a specific topic
- Use `search_web_and_process` when you need to synthesize search results into coherent insights with an AI agent according to your instructions. This is useful when going through many results

For optimal performance:
- Provide clear, specific instructions when using AI processing agents
- Use domain restrictions with the `allowed_domains` parameter to prevent unintended crawling
- Set appropriate timeouts and page limits to manage processing time
- Consider content size limits based on the type and depth of information you're looking for
"""

# Create MCP server
mcp = FastMCP("web-processing-server", instructions=MCP_INSTRUCTIONS)

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30
# Default max length for fetched content before sending to AI (characters)
DEFAULT_FETCH_MAX_LENGTH = 100000
# Default max lentgh to feed into OpenAI agent (characters)
DEFAULT_AGENT_INPUT_MAX_LENGTH = 500000
# Default User Agent
DEFAULT_USER_AGENT = "ModelContextProtocol-WebProcessor/1.0 (+https://github.com/modelcontextprotocol/servers)"
# Default OpenAI Model
DEFAULT_OPENAI_MODEL = "o3-mini"
# Default Max Tokens for OpenAI response
DEFAULT_OPENAI_MAX_TOKENS = 10000
# Default number of search results
DEFAULT_SEARCH_COUNT = 10
# Brave API Endpoint
BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"

# --- OpenAI Setup ---
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if (
    not OPENAI_API_KEY
    or OPENAI_API_KEY == "YOUR_OPENAI_KEY"
    or OPENAI_API_KEY == "sk-YOUR_OPENAI_KEY"
):  # Added check for placeholder:
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

# --- Brave Search Setup ---
BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY')
if (
    not BRAVE_API_KEY or BRAVE_API_KEY == "YOUR_BRAVE_KEY"
):  # Added check for placeholder
    print(
        "Error: BRAVE_API_KEY not provided or is a placeholder. Search tools will not be available.",
        file=sys.stderr,
    )
    # Exit because search is fundamental here, unlike optional AI processing for fetch
    sys.exit(1)

# --- AI Agent System Prompt ---
AI_AGENT_SYSTEM_PROMPT = """
You are an expert web content processor and search result analyst. Your task is to analyze the provided content (which might be web page content in Markdown or search results) and follow the user's instructions precisely.

**Input Format:**
You will receive the content within `<content>` tags and the user's specific instructions within `<instructions>` tags. The content could be:
1.  Markdown representation of a single web page.
2.  A collection of search results, typically formatted with Title, URL, and Description for each result.
3.  A combination of content from multiple fetched URLs.

**Output Guidelines:**
- Respond ONLY with the data requested by the instructions.
- Do not add any preamble, introduction, explanation, or conversational filler unless explicitly asked for.
- If the instructions ask for a specific format (e.g., JSON, list, table), adhere to it strictly. Use Markdown for general text formatting unless otherwise specified.
- If you cannot fulfill the instructions based on the provided content (e.g., information missing from the search results or web page), clearly state that you couldn't find the requested information in the provided content. Do not make assumptions or fetch external data beyond what's given.
- Be concise, factual, and accurate, directly addressing the user's instructions based ONLY on the provided `<content>`.
"""

# --- Helper Functions ---


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
        # Add more specific error logging if markdownify fails
        print(f"Error during markdownify: {e}", file=sys.stderr)
        # Fallback to basic text extraction if markdownify fails completely
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(" ", strip=True)
            if max_length and len(text_content) > max_length:
                text_content = (
                    text_content[:max_length]
                    + f"\n\n[Content truncated at {max_length} characters]"
                )
            return (
                text_content
                if text_content
                else f"<e>Failed to extract content from HTML, even as text: {str(e)}</e>"
            )
        except ImportError:
            return f"<e>Failed to extract content from HTML: {str(e)}. BeautifulSoup not installed for fallback.</e>"
        except Exception as bs_e:
            return f"<e>Failed to extract content from HTML: {str(e)}. Fallback text extraction failed: {bs_e}</e>"


async def _fetch_url(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[Optional[str], Optional[str], int, Dict[str, Any]]:
    """
    Fetch the URL and return the content, content type, status code, and metadata.
    Returns (None, None, status, metadata) on error.
    """
    metadata = {"original_url": url, "error": None}
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=timeout)

            metadata.update(
                {
                    "final_url": str(response.url),
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "headers": dict(
                        response.headers
                    ),  # Be careful logging headers in prod
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

    # Ensure content and instructions are not excessively long before sending
    # This is a basic safety check, more sophisticated truncation might be needed
    if len(content) > DEFAULT_AGENT_INPUT_MAX_LENGTH:  # Example limit
        content = (
            content[:DEFAULT_AGENT_INPUT_MAX_LENGTH]
            + "\n\n[SYSTEM NOTE: Input content truncated due to length limit]"
        )
        print(
            "Warning: Truncating content sent to OpenAI due to length.", file=sys.stderr
        )

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
        return result.strip() if result else "", None
    except openai.APIError as e:
        error_msg = f"OpenAI API Error: {e.status_code} - {e.message}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return None, error_msg
    except Exception as e:
        if "rate limit" in str(e).lower():
            error_msg = f"OpenAI Error: Rate limit possibly exceeded. {str(e)}"
        else:
            error_msg = f"Error during OpenAI call: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return None, error_msg


async def _call_brave_search(
    query: str,
    count: int = DEFAULT_SEARCH_COUNT,
    offset: int = 0,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls the Brave Search API and returns formatted results or an error message.
    Returns (formatted_results, error_message).
    """
    if not BRAVE_API_KEY:
        return None, "Brave API Key not configured."

    params = {
        "q": query,
        "count": min(max(1, count), 20),  # Ensure count is between 1 and 20
        "offset": max(0, offset),  # Ensure offset is non-negative
        # Add other parameters like 'safesearch', 'country', 'search_lang' if needed
        "search_lang": "en",  # Default to english results
        "safesearch": "moderate",
    }
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
        "User-Agent": DEFAULT_USER_AGENT,  # Good practice to identify your client
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                BRAVE_SEARCH_API_URL, params=params, headers=headers, timeout=timeout
            )

        if response.status_code == 429:
            return (
                None,
                f"Brave API Error: Rate limit exceeded (HTTP 429). Response: {response.text}",
            )
        elif response.status_code == 401:
            return (
                None,
                f"Brave API Error: Authentication failed (HTTP 401). Check your API key. Response: {response.text}",
            )
        elif response.status_code >= 400:
            return (
                None,
                f"Brave API Error: {response.status_code} {response.reason_phrase}. Response: {response.text}",
            )

        data = response.json()

        # --- Process Web Results ---
        web_results = data.get("web", {}).get("results", [])
        if not web_results:
            # Check for other result types or return no results found
            # For now, just focus on web results
            return "No web search results found.", None

        formatted_results = []
        for i, result in enumerate(web_results):
            title = result.get("title", "N/A")
            description = result.get("description", "N/A")
            url = result.get("url", "N/A")
            # You could add more fields like age if needed: result.get("age")
            formatted_results.append(
                f"Result {i + 1 + offset}:\nTitle: {title}\nDescription: {description}\nURL: {url}"
            )

        return "\n\n".join(formatted_results), None

    except httpx.TimeoutException:
        return None, f"Brave API request timed out after {timeout} seconds."
    except httpx.RequestError as e:
        return None, f"Brave API request error: {str(e)}"
    except json.JSONDecodeError:
        return (
            None,
            f"Brave API error: Failed to decode JSON response. Status: {response.status_code}, Body: {response.text[:500]}...",
        )  # Show snippet
    except Exception as e:
        return None, f"Unknown error during Brave search: {str(e)}"


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
        from urllib.parse import urljoin, urlparse
    except ImportError:
        raise ImportError("'beautifulsoup4' library is required for crawling.")

    try:
        # Basic validation of start URL format
        parsed_initial_url = urlparse(url)
        if not parsed_initial_url.scheme or not parsed_initial_url.netloc:
            raise ValueError(
                f"Invalid start URL format: {url}. Must include scheme (http/https) and domain."
            )
    except Exception as e:
        raise ValueError(f"Invalid start URL: {e}")

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
        # Validate provided allowed domains are reasonable (basic check)
        _allowed_domains = set()
        for domain in allowed_domains:
            if isinstance(domain, str) and "." in domain:
                _allowed_domains.add(domain.lower().strip())
            else:
                print(
                    f"Warning: Skipping invalid allowed domain '{domain}'",
                    file=sys.stderr,
                )
        _allowed_domains.add(
            base_domain.lower().strip()
        )  # Ensure start domain is always allowed

    # BFS crawl state
    queue = asyncio.Queue()
    queue.put_nowait((url, 0))  # (url, depth)
    crawled = {url}  # Set to track visited URLs
    pages_content = []  # List to store page content
    processed_count = 0  # Count pages actually processed for content

    crawl_metadata = {
        "start_url": url,
        "pages_crawled": 0,  # URLs attempted to fetch
        "pages_with_content": 0,  # Pages successfully processed with content
        "max_depth_reached": 0,
        "duration_seconds": 0,
        "allowed_domains": list(_allowed_domains),
        "errors": [],
    }

    # Limit concurrent fetches to avoid overwhelming sites or hitting local limits
    MAX_CONCURRENT_FETCHES = 5
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def worker(worker_id):
        nonlocal processed_count
        while True:
            try:
                # Wait if queue is empty for a moment, then check conditions
                try:
                    current_url, depth = await asyncio.wait_for(
                        queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check if crawl should stop
                    if queue.empty() and processed_count >= max_pages:
                        break  # All done
                    if (datetime.now() - start_time).total_seconds() > (
                        max_pages * timeout + 60
                    ):  # Overall timeout
                        print(f"Worker {worker_id}: Crawl timed out.", file=sys.stderr)
                        crawl_metadata["errors"].append(
                            "Overall crawl timeout exceeded"
                        )
                        break
                    continue  # Queue was temporarily empty, try again

                crawl_metadata["pages_crawled"] += 1
                crawl_metadata["max_depth_reached"] = max(
                    crawl_metadata["max_depth_reached"], depth
                )

                # Check if max_pages limit is already reached by other workers
                if processed_count >= max_pages:
                    queue.task_done()
                    continue  # Stop processing new URLs

                print(
                    f"Worker {worker_id}: Crawling [Depth:{depth}, Count:{processed_count}/{max_pages}]: {current_url}",
                    file=sys.stderr,
                )

                async with semaphore:  # Limit concurrency
                    # Fetch page using the passed user_agent
                    content, content_type, status_code, metadata = await _fetch_url(
                        current_url,
                        timeout=timeout,
                    )

                page_data = {
                    "url": metadata.get("final_url", current_url),
                    "depth": depth,
                    "status_code": status_code,
                    "content_type": content_type,
                    "content": None,  # Initialize content as None
                    "error": metadata.get("error"),
                }

                if status_code < 400 and content is not None:
                    processed_content = ""
                    if content_type and "text/html" in content_type:
                        # Use _extract_content_from_html (which handles errors/fallbacks)
                        # Don't apply max_length here, apply later if needed by consumer
                        processed_content = _extract_content_from_html(content)
                        if "<e>Failed to extract content" in processed_content:
                            page_data["error"] = (
                                processed_content  # Store extraction error
                            )
                            print(
                                f"Warning: Failed to extract content for {page_data['url']}: {processed_content}",
                                file=sys.stderr,
                            )
                            processed_content = (
                                ""  # Don't include error message as content
                            )
                        elif not processed_content.strip():
                            print(
                                f"Note: Extracted empty content from {page_data['url']}",
                                file=sys.stderr,
                            )

                    elif content_type and "text/" in content_type:
                        processed_content = content  # Store raw text
                    # Add handling for JSON, XML etc. if needed here
                    # else: Ignore non-text/html content for now? Or store raw?
                    #    processed_content = f"[Non-HTML/Text Content Type: {content_type}]"

                    if processed_content and processed_content.strip():
                        page_data["content"] = processed_content
                        pages_content.append(page_data)
                        processed_count += (
                            1  # Increment only if content was successfully processed
                        )

                    # Find and queue links only if successful fetch and content is HTML
                    # And depth/page limits not reached
                    if (
                        depth < max_depth
                        and content_type
                        and "text/html" in content_type
                        and processed_count < max_pages
                    ):
                        try:
                            soup = BeautifulSoup(content, "html.parser")
                            links_found = 0
                            for a_tag in soup.find_all("a", href=True):
                                # Check page limit inside loop to avoid adding too many tasks
                                if processed_count + queue.qsize() >= max_pages:
                                    break

                                href = a_tag["href"]
                                try:
                                    absolute_url = urljoin(current_url, href)
                                    parsed_link = urlparse(absolute_url)

                                    # Clean URL (remove fragment)
                                    clean_url = parsed_link._replace(
                                        fragment=""
                                    ).geturl()

                                    # Basic validation and filtering
                                    if (
                                        parsed_link.scheme in ("http", "https")
                                        and parsed_link.netloc  # Has domain
                                        and parsed_link.netloc.lower().strip()
                                        in _allowed_domains
                                        and clean_url not in crawled
                                    ):
                                        # Check queue size relative to max_pages more carefully
                                        # Estimate remaining capacity needed
                                        if len(crawled) < max_pages:
                                            crawled.add(clean_url)
                                            await queue.put((clean_url, depth + 1))
                                            links_found += 1

                                except Exception:
                                    # Don't log every minor link error unless debugging
                                    # print(f"Worker {worker_id}: Skipping link '{href}' due to parsing error: {link_e}", file=sys.stderr)
                                    pass  # Ignore invalid links silently
                            # print(f"Worker {worker_id}: Found {links_found} new valid links on {current_url}", file=sys.stderr)

                        except Exception as parse_e:
                            err_msg = (
                                f"Could not parse links on {current_url}: {parse_e}"
                            )
                            page_data["error"] = (
                                f"{page_data.get('error', '')} | {err_msg}"
                                if page_data.get("error")
                                else err_msg
                            )
                            print(f"Warning: {err_msg}", file=sys.stderr)
                else:
                    # Record error from fetch
                    err_msg = (
                        page_data["error"] or f"Fetch failed with status {status_code}"
                    )
                    crawl_metadata["errors"].append(f"{page_data['url']}: {err_msg}")
                    print(
                        f"Worker {worker_id}: Failed ({status_code}) {current_url} - {err_msg}",
                        file=sys.stderr,
                    )
                    # Optionally add page_data with error to pages_content?
                    # pages_content.append(page_data) # If you want to include failed pages

                queue.task_done()

            except asyncio.CancelledError:
                print(f"Worker {worker_id} cancelled.", file=sys.stderr)
                break
            except Exception as e:
                # Log unexpected worker errors
                worker_error_url = "UnknownURL"
                try:
                    worker_error_url = current_url  # Try to get URL if defined
                except NameError:
                    pass
                print(
                    f"Error in crawler worker {worker_id} for {worker_error_url}: {e}",
                    file=sys.stderr,
                )
                import traceback

                traceback.print_exc(file=sys.stderr)
                try:
                    queue.task_done()  # Ensure task_done is called even on unexpected error
                except ValueError:  # Might happen if task_done called twice
                    pass
                # Decide if worker should stop or continue
                break  # Stop worker on unexpected error

    # --- Start and manage workers ---
    worker_tasks = []
    num_workers = MAX_CONCURRENT_FETCHES
    for i in range(num_workers):
        task = asyncio.create_task(worker(i))
        worker_tasks.append(task)

    # Wait for queue to be processed
    await queue.join()

    # Cancel any workers that might still be waiting (e.g., on queue.get timeout)
    for task in worker_tasks:
        task.cancel()

    # Wait for tasks to finish cancellation
    await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Update final metadata
    crawl_metadata["duration_seconds"] = (datetime.now() - start_time).total_seconds()
    crawl_metadata["pages_with_content"] = len(
        pages_content
    )  # Count based on list length now

    print(
        f"Crawl finished. Attempted: {crawl_metadata['pages_crawled']}, Succeeded w/ Content: {crawl_metadata['pages_with_content']}",
        file=sys.stderr,
    )
    if crawl_metadata["errors"]:
        print(
            "Crawl encountered errors:\n - "
            + "\n - ".join(crawl_metadata["errors"][:5]),
            file=sys.stderr,
        )  # Show first 5 errors

    # Sort results by depth, then URL for consistency (optional)
    pages_content.sort(key=lambda p: (p.get("depth", 99), p.get("url", "")))

    return pages_content, crawl_metadata


# --- MCP Tools ---


@mcp.tool()
async def fetch_urls_and_process(
    urls: List[str],
    instructions: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_length: int = DEFAULT_FETCH_MAX_LENGTH,
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
            format_lower = preprocess_to_format.lower()
            if "text/html" in (content_type or "") and format_lower != "html":
                processed_content = _extract_content_from_html(
                    content, max_length=max_length
                )
                if "<e>Failed to extract content" in processed_content:
                    # Log the error but maybe proceed with raw text if possible?
                    print(
                        f"Warning: Markdown conversion failed for {url}. Using raw text snippet.",
                        file=sys.stderr,
                    )
                    raw_text = content[:max_length]  # Simple text slice
                    if len(content) > max_length:
                        raw_text += f"\n\n[Content truncated at {max_length} chars]"
                    processed_content = (
                        raw_text
                        if raw_text.strip()
                        else f"<e>Failed to extract content from HTML for {url}</e>"
                    )
            elif "text/" in (content_type or "") or format_lower == "text":
                processed_content = content[:max_length]
                if len(content) > max_length:
                    processed_content += (
                        f"\n\n[Content truncated at {max_length} chars]"
                    )
            elif format_lower == "html" and "text/html" in (content_type or ""):
                processed_content = content[:max_length]
                if len(content) > max_length:
                    processed_content += (
                        f"\n\n[Content truncated at {max_length} chars]"
                    )
            else:  # Other content types or raw request
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
            print(f"Unexpected error processing URL {url}: {e}", file=sys.stderr)
            return url, None, f"Unexpected error processing this URL: {str(e)}"

    # Run all fetch tasks concurrently
    tasks = [_fetch_one(u) for u in urls]
    results_list = await asyncio.gather(*tasks)

    # Combine all successful content
    combined_content = ""
    fetch_summary = []
    has_successful_fetch = False

    for url, content, error in results_list:
        if content:
            combined_content += f"\n\n--- URL: {url} ---\n\n{content}\n\n"
            fetch_summary.append({"url": url, "status": "success"})
            has_successful_fetch = True
        else:
            fetch_summary.append(
                {"url": url, "status": "error", "error": error or "Unknown fetch error"}
            )

    if not has_successful_fetch:
        summary_str = "\n".join(
            [f"- ERROR: {item['url']} - {item['error']}" for item in fetch_summary]
        )
        return f"Error: No content could be fetched successfully from any of the provided URLs.\n\nFetch Summary:\n{summary_str}"

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

    if ai_error:
        output_parts.append(
            f"**Error processing the combined content with AI:** {ai_error}"
        )
        # Optionally include the raw combined content if AI failed, for debugging
        # output_parts.append("\n**Raw Combined Content (for debugging):**\n" + combined_content[:2000] + "...")
    else:
        output_parts.append(ai_result or "AI agent returned an empty response.")

    return "\n".join(output_parts)


@mcp.tool()
async def crawl_url_and_process(
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
        content_urls = []
        for i, page in enumerate(pages_content):
            page_url = page.get("url", "Unknown URL")
            page_content = page.get("content", "")
            if page_content and page_content.strip():
                combined_content += f"\n\n--- PAGE {i + 1}: {page_url} ---\n\n"
                combined_content += page_content
                content_urls.append(page_url)
            else:
                print(
                    f"Note: Skipping empty content from {page_url} during crawl processing.",
                    file=sys.stderr,
                )

        if not combined_content:
            return "Crawling completed, but no processable content was extracted from the pages."

        # Process with AI
        ai_result, ai_error = await _call_openai(
            content=combined_content,
            instructions=instructions,
            model=openai_model,
            max_tokens=openai_max_tokens,
        )

        # Markdown output
        output_parts = ["# AI Analysis of Crawled Content\n"]
        output_parts.append(f"- Starting URL: {url}")
        output_parts.append(
            f"- Pages Crawled Attempted: {crawl_metadata.get('pages_crawled', 'N/A')}"
        )
        output_parts.append(f"- Pages With Content Processed: {len(content_urls)}")
        output_parts.append(
            f"- Max Depth Reached: {crawl_metadata.get('max_depth_reached', 'N/A')}"
        )
        output_parts.append(
            f"- Duration: {crawl_metadata.get('duration_seconds', -1):.2f} seconds"
        )
        output_parts.append(
            f"- Allowed Domains: {crawl_metadata.get('allowed_domains', ['N/A'])}"
        )

        output_parts.append("\n## URLs Included in AI Analysis:\n")
        if content_urls:
            for u in content_urls:
                output_parts.append(f"- {u}")
        else:
            output_parts.append("*None*")

        output_parts.append("\n## AI Analysis Result\n")
        if ai_error:
            output_parts.append(
                f"**Error processing crawled content with AI:** {ai_error}"
            )
        else:
            output_parts.append(ai_result or "AI agent returned an empty response.")

        return "\n".join(output_parts)

    except ImportError as e:
        # Ensure bs4 is mentioned if it's the cause
        if "beautifulsoup4" in str(e).lower():
            return "Error: 'beautifulsoup4' library is required for crawling. Please install it (`pip install beautifulsoup4`)."
        return f"Error: Missing library dependency - {str(e)}"
    except ValueError as e:  # Catch URL validation errors etc.
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        print(
            f"Unexpected error during crawl and process: {e}", file=sys.stderr
        )  # Log stacktrace for debugging
        import traceback

        traceback.print_exc(file=sys.stderr)
        return f"Unexpected error during crawl and process: {str(e)}"


@mcp.tool()
async def search_web_and_process(
    query: str,
    instructions: str,
    count: int = DEFAULT_SEARCH_COUNT,
    offset: int = 0,
    search_timeout: int = DEFAULT_TIMEOUT,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_max_tokens: int = DEFAULT_OPENAI_MAX_TOKENS,
) -> str:
    """
    Performs a Brave web search, then processes the results with an AI agent based on instructions.

    Args:
        query: The search query string.
        instructions: Instructions for the AI on how to process the search results.
        count: Number of search results to retrieve (1-20, default: 10).
        offset: Result offset for pagination (default: 0).
        search_timeout: Timeout for the Brave Search API call (default: 30).
        openai_model: AI model to use for processing (default: 'o3-mini').
        openai_max_tokens: Max tokens for the AI response (default: 10000).

    Returns:
        The AI-processed analysis of the search results or an error message.
    """
    if not openai_client:
        return (
            "Error: OpenAI client not available. Cannot process search results with AI."
        )
    if not query or not query.strip():
        return "Error: Search query cannot be empty."
    if not instructions or not instructions.strip():
        return "Error: Processing instructions cannot be empty."

    # 1. Perform the Brave Search
    search_results, search_error = await _call_brave_search(
        query=query, count=count, offset=offset, timeout=search_timeout
    )

    if search_error:
        return f"Error performing web search: {search_error}"
    if not search_results:
        return f'No web search results found for query "{query}". Cannot proceed with AI processing.'

    # 2. Process results with OpenAI
    ai_result, ai_error = await _call_openai(
        content=search_results,  # Pass the formatted search results string
        instructions=instructions,
        model=openai_model,
        max_tokens=openai_max_tokens,
    )

    # 3. Format the final output
    output_parts = [f'# AI Processing of Web Search Results for: "{query}"\n']
    output_parts.append(f"**Instructions Applied:**\n```\n{instructions}\n```\n")
    # Optionally include raw search results for context, maybe truncated?
    # output_parts.append("## Raw Search Results Used:\n")
    # output_parts.append(f"```\n{search_results[:1000]}...\n```\n") # Example truncation

    output_parts.append("## AI Agent Analysis Result:\n")
    if ai_error:
        output_parts.append(
            f"**Error processing the search results with AI:** {ai_error}"
        )
        # Optionally include the raw search results if AI failed
        # output_parts.append("\n**Raw Search Results (for debugging):**\n" + search_results)
    else:
        output_parts.append(ai_result or "AI agent returned an empty response.")

    return "\n".join(output_parts)


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

    content, content_type, status_code, metadata = await _fetch_url(
        url, timeout=timeout
    )

    if (
        content is None
    ):  # Check for None specifically, as empty string might be valid content
        error_msg = metadata.get(
            "error",
            f"Failed to fetch URL (Status: {status_code}) - No content received",
        )
        return f"Error fetching {url}: {error_msg}"

    # Handle error status codes even if content was returned (e.g., error page HTML)
    if status_code >= 400:
        error_msg = metadata.get("error", f"HTTP Status {status_code}")
        # Include content snippet in error if available and useful
        content_snippet = ""
        if content:
            try:
                # Try getting text from error page
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, "html.parser")
                body_text = (
                    soup.body.get_text(" ", strip=True) if soup.body else content
                )
                content_snippet = f"\nResponse Body Snippet:\n{body_text[:500]}..."
            except ImportError:
                content_snippet = f"\nResponse Body Snippet (raw):\n{content[:500]}..."
            except Exception:
                content_snippet = f"\nResponse Body Snippet (raw):\n{content[:500]}..."

        return f"Error fetching {url}: {error_msg}{content_snippet}"

    # Handle truncation notice separately
    original_size = metadata.get("size", len(content))  # Use metadata size if available
    truncated = False
    if max_length > 0 and len(content) > max_length:  # Check max_length > 0
        content = content[:max_length]
        truncated = True
        truncation_notice = f"\n\n[Content truncated at {max_length} characters. Original size: {original_size} chars]"
    else:
        truncation_notice = ""

    # Process based on output type
    output_type_lower = output_type.lower()

    if output_type_lower == "raw":
        return content + truncation_notice
    elif output_type_lower == "json":
        output_data = {
            "url": metadata.get("final_url", url),
            "status_code": status_code,
            "content_type": content_type,
            "truncated": truncated,
            "original_size": metadata.get("size"),
            "metadata": {  # Include selected metadata
                "elapsed_seconds": metadata.get("elapsed"),
                "redirect_history": metadata.get("redirects", []),
            },
        }
        if "text/html" in (content_type or ""):
            # Provide both markdown and raw (truncated) html snippet
            output_data["markdown_content"] = _extract_content_from_html(
                content
            )  # No length limit here, content is already truncated
            output_data["raw_html_snippet"] = content  # Use already truncated content
        elif "application/json" in (content_type or ""):
            try:
                output_data["parsed_json_content"] = json.loads(content)
            except json.JSONDecodeError:
                output_data["raw_content"] = content  # Include raw if not valid JSON
                output_data["parsing_error"] = "Content received is not valid JSON"
        elif "text/" in (content_type or ""):
            output_data["text_content"] = content
        else:  # Other types
            output_data["raw_content"] = content  # Store as raw content

        try:
            return (
                json.dumps(output_data, indent=2) + truncation_notice
            )  # Notice outside JSON
        except TypeError as json_e:
            return f"Error: Could not serialize fetched data to JSON: {json_e}. Raw content was: {content[:500]}..."

    elif "text/html" in (content_type or ""):
        if output_type_lower == "html":
            return content + truncation_notice
        elif output_type_lower in [
            "markdown",
            "text",
        ]:  # Treat text request same as markdown for HTML
            extracted = _extract_content_from_html(content)
            if "<e>Failed to extract content" in extracted:
                return (
                    f"Error processing HTML for {url}: Could not convert to Markdown/Text. Raw HTML snippet:\n{content[:1000]}..."
                    + truncation_notice
                )
            return extracted + truncation_notice
        else:  # Default to markdown for unknown types from HTML
            extracted = _extract_content_from_html(content)
            if "<e>Failed to extract content" in extracted:
                return (
                    f"Error processing HTML for {url}: Could not convert to Markdown. Raw HTML snippet:\n{content[:1000]}..."
                    + truncation_notice
                )
            return extracted + truncation_notice

    # Handle non-HTML types
    elif output_type_lower in [
        "text",
        "markdown",
        "html",
    ]:  # Treat output request as text if input is text/*
        return content + truncation_notice
    else:  # Default fallback is raw text for unknown output types or non-text content
        print(
            f"Warning: Unknown output_type '{output_type}' requested for content-type '{content_type}'. Returning raw text.",
            file=sys.stderr,
        )
        return content + truncation_notice


@mcp.tool()
async def crawl_website(
    url: str,
    max_pages: int = 5,
    max_depth: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
    allowed_domains: Optional[List[str]] = None,  # Restrict crawl
) -> str:
    """
    Crawls website starting from URL, collecting linked pages.

    Args:
        url: Starting URL
        max_pages: Max pages to fetch (default: 5)
        max_depth: Max link depth from start URL (default: 2)
        timeout: Request timeout per page in seconds (default: 30)
        allowed_domains: Domains to restrict crawling to (default: start URL's domain)

    Returns:
        Combined crawl results or status if saving to file
    """
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
            meta_info = f" (Start URL: {crawl_metadata.get('start_url', url)}, Duration: {crawl_metadata.get('duration_seconds', -1):.2f}s)"
            return f"No valid content was found during crawling{meta_info}."

        # Format output
        output_parts = [f"# Crawl Report for: {url}\n"]
        output_parts.append(
            f"- Pages Crawled Attempted: {crawl_metadata.get('pages_crawled', 'N/A')}"
        )
        output_parts.append(
            f"- Pages With Content Extracted: {crawl_metadata.get('pages_with_content', 'N/A')}"
        )
        output_parts.append(
            f"- Max Depth Reached: {crawl_metadata.get('max_depth_reached', 'N/A')}"
        )
        output_parts.append(
            f"- Duration: {crawl_metadata.get('duration_seconds', -1):.2f} seconds"
        )
        output_parts.append(
            f"- Allowed Domains: {crawl_metadata.get('allowed_domains', ['N/A'])}"
        )

        output_parts.append("\n## Page Details (Markdown Snippets):\n---")

        for page in pages_content:
            page_url = page.get("url", "Unknown URL")
            status = page.get("status_code", "N/A")
            depth = page.get("depth", "N/A")
            content = page.get("content", "")

            output_parts.append(f"### [{status}] {page_url} (Depth: {depth})")
            if content and content.strip():
                # Show snippet of the processed (Markdown) content
                snippet = content[:500].strip()
                if len(content) > 500:
                    snippet += "..."
                output_parts.append(
                    f"**Content Snippet:**\n```markdown\n{snippet}\n```"
                )
            else:
                output_parts.append("*(No content processed or content was empty)*")
            output_parts.append("---")

        return "\n".join(output_parts)

    except ImportError as e:
        if "beautifulsoup4" in str(e).lower():
            return "Error: 'beautifulsoup4' library is required for crawling. Please install it (`pip install beautifulsoup4`)."
        return f"Error: Missing library dependency - {str(e)}"
    except ValueError as e:  # Catch URL validation errors etc.
        return f"Error: Invalid input - {str(e)}"
    except Exception as e:
        print(f"Unexpected error during crawl: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return f"Unexpected error during crawl: {str(e)}"


@mcp.tool()
async def search_web(
    query: str,
    count: int = DEFAULT_SEARCH_COUNT,
    offset: int = 0,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Performs a web search using the Brave Search API and returns formatted results.

    Args:
        query: The search query string.
        count: Number of results to return (1-20, default: 10).
        offset: Result offset for pagination (default: 0).
        timeout: Request timeout in seconds (default: 30).

    Returns:
        A string containing the formatted search results or an error message.
    """
    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    results, error = await _call_brave_search(
        query=query, count=count, offset=offset, timeout=timeout
    )

    if error:
        return f"Error performing web search: {error}"
    elif not results:
        return "No web search results found for the query."
    else:
        # Add a header to the results for clarity
        return f'# Web Search Results for: "{query}"\n\n{results}'


if __name__ == "__main__":
    if not openai_client:
        print(
            "Warning: OpenAI client not initialized. AI-powered tools (`fetch_and_process_*`) will return errors.",
            file=sys.stderr,
        )
    print("Web Processing MCP Server running", file=sys.stderr)
    mcp.run()
