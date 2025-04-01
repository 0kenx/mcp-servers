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
from pydantic import BaseModel, Field, AnyUrl
import markdownify

from mcp.server.fastmcp import FastMCP, Context
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS, INTERNAL_ERROR

# Create MCP server
mcp = FastMCP(\"web-fetching-server\")

# Default timeout for requests (in seconds)
DEFAULT_TIMEOUT = 30

# Default user agents
DEFAULT_USER_AGENT = \"ModelContextProtocol/1.0 (+https://github.com/modelcontextprotocol/servers)\"

# Output types
class OutputType(Enum):
    TEXT = \"text\"
    MARKDOWN = \"markdown\"
    HTML = \"html\"
    JSON = \"json\"
    BOTH = \"both\"

# Session tracking
@BaseModel
class Session:
    id: str
    url: str
    start_time: datetime
    content: str
    status_code: int
    transformed_content: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Dict[str, Any] = {}
    error: Optional[str] = None

# Active sessions
active_sessions: Dict[str, Session] = {}
last_session_id: int = 0

# Helper function to extract content from HTML
def extract_content_from_html(html: str) -> str:
    \"\"\"Extract and convert HTML content to Markdown format.

    Args:
        html: Raw HTML content to process

    Returns:
        Simplified markdown version of the content
    \"\"\"
    if not html.strip():
        return \"<e>Empty HTML content</e>\"
    
    try:
        content = markdownify.markdownify(
            html,
            heading_style=markdownify.ATX,
        )
        return content
    except Exception as e:
        return f\"<e>Failed to extract content from HTML: {str(e)}</e>\"

# Helper function to get robots.txt URL
def get_robots_txt_url(url: str) -> str:
    \"\"\"Get the robots.txt URL for a given website URL.

    Args:
        url: Website URL to get robots.txt for

    Returns:
        URL of the robots.txt file
    \"\"\"
    # Parse the URL into components
    parsed = urlparse(url)

    # Reconstruct the base URL with just scheme, netloc, and /robots.txt path
    robots_url = urlunparse((parsed.scheme, parsed.netloc, \"/robots.txt\", \"\", \"\", \"\"))

    return robots_url

# Define the FetchUrl parameters model
class FetchUrlParams(BaseModel):
    url: AnyUrl
    timeout: int = Field(default=DEFAULT_TIMEOUT, gt=0, lt=120)
    output_type: str = Field(default=\"markdown\")
    max_length: int = Field(default=50000, gt=0, lt=1000000)
    start_index: int = Field(default=0, ge=0)
    read_raw: bool = Field(default=False)
    ignore_robots: bool = Field(default=False)
    user_agent: Optional[str] = None

# Define the ProcessWebContent parameters model
class ProcessContentParams(BaseModel):
    content: str
    url: str
    content_type: Optional[str] = None
    output_type: str = Field(default=\"markdown\")
    instructions: Optional[str] = None
    extract_elements: Optional[List[str]] = None
    max_length: int = Field(default=50000, gt=0, lt=1000000)

# Define the WebCrawl parameters model
class WebCrawlParams(BaseModel):
    url: AnyUrl
    max_pages: int = Field(default=5, gt=0, lt=20)
    max_depth: int = Field(default=2, gt=0, lt=5)
    timeout: int = Field(default=30, gt=0, lt=120)
    output_type: str = Field(default=\"markdown\")
    output_file: Optional[str] = None
    follow_links: bool = Field(default=True)
    ignore_robots: bool = Field(default=False)
    user_agent: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    query: Optional[str] = None

# Define the AnalyzeUrl parameters model
class AnalyzeUrlParams(BaseModel):
    url: AnyUrl
    timeout: int = Field(default=DEFAULT_TIMEOUT, gt=0, lt=120)
    analyze_seo: bool = Field(default=True)
    analyze_accessibility: bool = Field(default=True)
    analyze_performance: bool = Field(default=True)
    analyze_content: bool = Field(default=True)
    output_type: str = Field(default=\"markdown\")
    user_agent: Optional[str] = None

# Implement async function to fetch a URL
async def fetch_url(
    url: str, 
    user_agent: str = DEFAULT_USER_AGENT, 
    timeout: int = DEFAULT_TIMEOUT, 
    ignore_robots: bool = False
) -> Tuple[str, str, int, Dict[str, Any]]:
    \"\"\"
    Fetch the URL and return the content, content type, status code, and metadata.
    
    Args:
        url: URL to fetch
        user_agent: User agent string to use in request
        timeout: Request timeout in seconds
        ignore_robots: Whether to ignore robots.txt restrictions
        
    Returns:
        Tuple containing (content, content_type, status_code, metadata)
    \"\"\"
    # Check robots.txt if not ignored
    if not ignore_robots:
        robots_url = get_robots_txt_url(url)
        try:
            async with httpx.AsyncClient() as client:
                robots_response = await client.get(
                    robots_url,
                    follow_redirects=True,
                    headers={\"User-Agent\": user_agent},
                    timeout=timeout
                )
                
                if robots_response.status_code in (401, 403):
                    return (
                        \"\",
                        \"\",
                        robots_response.status_code,
                        {\"error\": f\"Access to robots.txt at {robots_url} was denied (status {robots_response.status_code}). This suggests the site disallows bots.\"}
                    )
                
                # Basic check for Disallow directives that might apply to our URL
                if robots_response.status_code == 200:
                    robots_txt = robots_response.text
                    path = urlparse(url).path
                    
                    for line in robots_txt.splitlines():
                        if line.startswith(\"Disallow:\"):
                            disallowed_path = line.split(\":\", 1)[1].strip()
                            if path.startswith(disallowed_path) and disallowed_path:
                                return (
                                    \"\",
                                    \"\",
                                    403,
                                    {\"error\": f\"The site's robots.txt disallows access to this URL. Use ignore_robots=True to override.\"}
                                )
        except Exception as e:
            # If we can't fetch robots.txt, we'll just proceed with the request
            pass
    
    # Fetch the URL
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={\"User-Agent\": user_agent},
                timeout=timeout
            )
            
            content = response.text
            content_type = response.headers.get(\"content-type\", \"\")
            
            # Extract metadata
            metadata = {
                \"url\": str(response.url),
                \"status_code\": response.status_code,
                \"content_type\": content_type,
                \"headers\": dict(response.headers),
                \"elapsed\": response.elapsed.total_seconds(),
                \"size\": len(content),
                \"redirects\": [str(r.url) for r in response.history],
            }
            
            return (content, content_type, response.status_code, metadata)
    except httpx.TimeoutException:
        return (\"\", \"\", 408, {\"error\": f\"Request timed out after {timeout} seconds\"})
    except httpx.RequestError as e:
        return (\"\", \"\", 400, {\"error\": f\"Request error: {str(e)}\"})
    except Exception as e:
        return (\"\", \"\", 500, {\"error\": f\"Unknown error: {str(e)}\"})

# Process web content based on content type
def process_web_content(
    content: str,
    content_type: str,
    output_type: str = \"markdown\",
    url: str = \"\",
    max_length: int = 50000
) -> str:
    \"\"\"
    Process web content based on content type and requested output format.
    
    Args:
        content: Raw web content
        content_type: Content type from HTTP headers
        output_type: Desired output format (text, markdown, html, json)
        url: Original URL (for reference)
        max_length: Maximum length of content to return
        
    Returns:
        Processed content in the requested format
    \"\"\"
    # Truncate content if needed
    if len(content) > max_length:
        content_truncated = content[:max_length]
        truncation_notice = f\"\
\
[Content truncated. Original size: {len(content)} characters]\"
    else:
        content_truncated = content
        truncation_notice = \"\"
    
    # Process based on content type
    if \"text/html\" in content_type or \"<html\" in content_truncated[:1000].lower():
        # HTML content
        if output_type.lower() == \"html\":
            return content_truncated + truncation_notice
        elif output_type.lower() in [\"markdown\", \"text\"]:
            return extract_content_from_html(content_truncated) + truncation_notice
        elif output_type.lower() == \"json\":
            return json.dumps({
                \"url\": url,
                \"content_type\": content_type,
                \"raw_html\": content_truncated,
                \"markdown\": extract_content_from_html(content_truncated),
                \"truncated\": len(content) > max_length,
                \"original_size\": len(content)
            })
    elif \"application/json\" in content_type:
        # JSON content
        if output_type.lower() == \"json\":
            return content_truncated + truncation_notice
        elif output_type.lower() in [\"markdown\", \"text\"]:
            try:
                parsed = json.loads(content_truncated)
                formatted = json.dumps(parsed, indent=2)
                return f\"```json\
{formatted}\
```\" + truncation_notice
            except json.JSONDecodeError:
                return f\"```\
{content_truncated}\
```\" + truncation_notice
    elif \"text/\" in content_type:
        # Plain text or other text content
        if output_type.lower() in [\"text\", \"markdown\"]:
            return content_truncated + truncation_notice
        elif output_type.lower() == \"json\":
            return json.dumps({
                \"url\": url,
                \"content_type\": content_type,
                \"text\": content_truncated,
                \"truncated\": len(content) > max_length,
                \"original_size\": len(content)
            })
    
    # Default handling for other content types
    if output_type.lower() in [\"text\", \"markdown\"]:
        return f\"Content from {url} (type: {content_type}):\
\
```\
{content_truncated}\
```\" + truncation_notice
    elif output_type.lower() == \"json\":
        return json.dumps({
            \"url\": url,
            \"content_type\": content_type,
            \"raw\": content_truncated,
            \"truncated\": len(content) > max_length,
            \"original_size\": len(content)
        })
    
    return content_truncated + truncation_notice

# Define tool implementations
@mcp.tool()
async def fetch_url_content(url: str, timeout: int = DEFAULT_TIMEOUT, output_type: str = \"markdown\", max_length: int = 50000, read_raw: bool = False, ignore_robots: bool = False, user_agent: Optional[str] = None) -> str:
    \"\"\"
    Fetch content from a URL and return it in the requested format.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (default: 30)
        output_type: Output format (markdown, html, text, json)
        max_length: Maximum length of content to return
        read_raw: If True, don't process or convert the content
        ignore_robots: If True, ignore robots.txt restrictions
        user_agent: Custom user agent string (if not specified, a default will be used)
        
    Returns:
        Fetched content in the requested format
    \"\"\"
    global last_session_id, active_sessions
    
    # Create unique session ID
    last_session_id += 1
    session_id = str(last_session_id)
    
    # Use default user agent if none provided
    if not user_agent:
        user_agent = DEFAULT_USER_AGENT
    
    # Fetch the URL
    content, content_type, status_code, metadata = await fetch_url(
        url, 
        user_agent=user_agent,
        timeout=timeout,
        ignore_robots=ignore_robots
    )
    
    # Check for errors
    if status_code >= 400 or \"error\" in metadata:
        error_message = metadata.get(\"error\", f\"HTTP Error {status_code}\")
        return f\"Error fetching {url}: {error_message}\"
    
    # Process content based on type and requested output format
    if not read_raw:
        processed_content = process_web_content(
            content, 
            content_type, 
            output_type=output_type,
            url=url,
            max_length=max_length
        )
    else:
        processed_content = content[:max_length]
        if len(content) > max_length:
            processed_content += f\"\
\
[Content truncated. Original size: {len(content)} characters]\"
    
    # Store session for future reference
    session = Session(
        id=session_id,
        url=url,
        start_time=datetime.now(),
        content=content,
        status_code=status_code,
        transformed_content=processed_content,
        content_type=content_type,
        metadata=metadata
    )
    active_sessions[session_id] = session
    
    return processed_content

@mcp.tool()
async def process_web_content(content: str, url: str, content_type: Optional[str] = None, output_type: str = \"markdown\", instructions: Optional[str] = None, extract_elements: Optional[List[str]] = None, max_length: int = 50000) -> str:
    \"\"\"
    Process web content according to instructions.
    
    Args:
        content: Raw web content to process
        url: Source URL for reference
        content_type: MIME type of the content (if known)
        output_type: Output format (markdown, html, text, json)
        instructions: Special processing instructions (e.g., \"extract main article\", \"summarize\")
        extract_elements: List of HTML elements to extract (e.g., [\"h1\", \"main\", \"article\"])
        max_length: Maximum length of content to return
        
    Returns:
        Processed content in the requested format
    \"\"\"
    # Detect content type if not provided
    if not content_type:
        if content.strip().startswith(\"{\") and content.strip().endswith(\"}\"):
            content_type = \"application/json\"
        elif \"<html\" in content.lower()[:1000]:
            content_type = \"text/html\"
        else:
            content_type = \"text/plain\"
    
    # Process the content based on instructions
    if instructions:
        # Placeholder for future more sophisticated processing
        if \"extract main article\" in instructions.lower() and \"text/html\" in content_type:
            return extract_content_from_html(content)
        elif \"summarize\" in instructions.lower():
            # Simple summarization (first paragraph + section headings)
            if \"text/html\" in content_type:
                markdown = extract_content_from_html(content)
                lines = markdown.splitlines()
                summary_lines = []
                
                # Add first paragraph
                paragraph_found = False
                for line in lines:
                    if not paragraph_found and line.strip() and not line.startswith('#'):
                        summary_lines.append(line)
                        paragraph_found = True
                        break
                
                # Add headings
                for line in lines:
                    if line.startswith('#'):
                        summary_lines.append(line)
                
                return \"\
\
\".join(summary_lines)
            
    # Handle element extraction
    if extract_elements and \"text/html\" in content_type:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            extracted = []
            for selector in extract_elements:
                elements = soup.select(selector)
                for element in elements:
                    if output_type.lower() == \"html\":
                        extracted.append(str(element))
                    else:
                        extracted.append(markdownify.markdownify(str(element)))
            
            if extracted:
                return \"\
\
\".join(extracted)
        except ImportError:
            return \"Error: BeautifulSoup is required for element extraction\"
        except Exception as e:
            return f\"Error extracting elements: {str(e)}\"
    
    # Default processing
    return process_web_content(
        content, 
        content_type, 
        output_type=output_type,
        url=url,
        max_length=max_length
    )

@mcp.tool()
async def fetch_multiple_urls(urls: List[str], timeout: int = DEFAULT_TIMEOUT, output_type: str = \"markdown\", max_length: int = 10000, ignore_robots: bool = False, user_agent: Optional[str] = None) -> str:
    \"\"\"
    Fetch content from multiple URLs in parallel.
    
    Args:
        urls: List of URLs to fetch
        timeout: Request timeout in seconds for each URL
        output_type: Output format (markdown, html, text, json)
        max_length: Maximum length of content to return per URL
        ignore_robots: If True, ignore robots.txt restrictions
        user_agent: Custom user agent string
        
    Returns:
        Combined content from all URLs or JSON with results
    \"\"\"
    if not urls:
        return \"Error: No URLs provided\"
    
    # Use default user agent if none provided
    if not user_agent:
        user_agent = DEFAULT_USER_AGENT
    
    # Fetch all URLs in parallel
    async def fetch_one(url):
        try:
            content, content_type, status_code, metadata = await fetch_url(
                url, 
                user_agent=user_agent,
                timeout=timeout,
                ignore_robots=ignore_robots
            )
            
            if status_code >= 400 or \"error\" in metadata:
                error_message = metadata.get(\"error\", f\"HTTP Error {status_code}\")
                return {
                    \"url\": url,
                    \"success\": False,
                    \"error\": error_message,
                    \"content\": \"\",
                    \"content_type\": content_type,
                    \"status_code\": status_code
                }
            
            # Process content based on type and requested output format
            processed_content = process_web_content(
                content, 
                content_type, 
                output_type=output_type,
                url=url,
                max_length=max_length
            )
            
            return {
                \"url\": url,
                \"success\": True,
                \"content\": processed_content,
                \"content_type\": content_type,
                \"status_code\": status_code
            }
        except Exception as e:
            return {
                \"url\": url,
                \"success\": False,
                \"error\": str(e),
                \"content\": \"\",
                \"content_type\": \"\",
                \"status_code\": 500
            }
    
    # Execute all fetches in parallel
    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    # Format output based on requested type
    if output_type.lower() == \"json\":
        return json.dumps(results, indent=2)
    else:
        # Format as markdown with separators
        output = []
        for result in results:
            output.append(f\"## {result['url']}\")
            
            if result['success']:
                output.append(result['content'])
            else:
                output.append(f\"Error: {result.get('error', 'Unknown error')}\")
            
            output.append(\"\
---\
\")
        
        return \"\
\".join(output)

@mcp.tool()
async def crawl_website(url: str, max_pages: int = 5, max_depth: int = 2, timeout: int = 30, output_type: str = \"markdown\", output_file: Optional[str] = None, follow_links: bool = True, ignore_robots: bool = False, user_agent: Optional[str] = None, allowed_domains: Optional[List[str]] = None, query: Optional[str] = None) -> str:
    \"\"\"
    Crawl a website and collect content from multiple pages.
    
    Args:
        url: Starting URL to crawl
        max_pages: Maximum number of pages to crawl
        max_depth: Maximum link depth to follow
        timeout: Request timeout in seconds per page
        output_type: Output format (markdown, html, text, json)
        output_file: If provided, save results to this file
        follow_links: If True, follow links on the page
        ignore_robots: If True, ignore robots.txt restrictions
        user_agent: Custom user agent string
        allowed_domains: List of domains to restrict crawling to
        query: Optional search query to filter content
        
    Returns:
        Collected content from crawled pages
    \"\"\"
    global last_session_id
    
    # Create unique session ID for this crawl
    last_session_id += 1
    session_id = str(last_session_id)
    
    # Use default user agent if none provided
    if not user_agent:
        user_agent = DEFAULT_USER_AGENT
    
    # Parse the base URL to get the domain
    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc
    
    # Initialize allowed domains if not provided
    if not allowed_domains:
        allowed_domains = [base_domain]
    elif base_domain not in allowed_domains:
        allowed_domains.append(base_domain)
    
    # Queue of URLs to crawl
    to_crawl = [(url, 0)]  # (url, depth)
    crawled = set()
    results = []
    
    # Extract links from HTML content
    def extract_links(html_content, current_url):
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                absolute_url = urljoin(current_url, href)
                parsed = urlparse(absolute_url)
                
                # Skip fragment links and non-HTTP schemes
                if not parsed.scheme or not parsed.netloc or parsed.scheme not in ('http', 'https'):
                    continue
                
                # Check if domain is allowed
                if parsed.netloc not in allowed_domains:
                    continue
                
                links.append(absolute_url)
            
            return links
        except ImportError:
            return []
        except Exception as e:
            return []
    
    # Crawl pages until we hit the limit
    while to_crawl and len(crawled) < max_pages:
        current_url, depth = to_crawl.pop(0)
        
        # Skip if already crawled
        if current_url in crawled:
            continue
        
        # Mark as crawled
        crawled.add(current_url)
        
        # Fetch the URL
        content, content_type, status_code, metadata = await fetch_url(
            current_url, 
            user_agent=user_agent,
            timeout=timeout,
            ignore_robots=ignore_robots
        )
        
        # Skip if error
        if status_code >= 400 or \"error\" in metadata:
            error_message = metadata.get(\"error\", f\"HTTP Error {status_code}\")
            results.append({
                \"url\": current_url,
                \"success\": False,
                \"error\": error_message,
                \"depth\": depth
            })
            continue
        
        # Process content
        processed_content = process_web_content(
            content, 
            content_type, 
            output_type=\"markdown\",  # Always extract markdown for filtering
            url=current_url
        )
        
        # Apply query filter if provided
        include_page = True
        if query and query.strip():
            include_page = query.lower() in processed_content.lower()
        
        if include_page:
            # Format based on requested output type
            if output_type.lower() != \"markdown\":
                output_content = process_web_content(
                    content, 
                    content_type, 
                    output_type=output_type,
                    url=current_url
                )
            else:
                output_content = processed_content
            
            results.append({
                \"url\": current_url,
                \"success\": True,
                \"content\": output_content,
                \"content_type\": content_type,
                \"status_code\": status_code,
                \"depth\": depth
            })
        
        # Extract and queue links if not at max depth
        if follow_links and depth < max_depth and \"text/html\" in content_type:
            links = extract_links(content, current_url)
            
            # Add new links to the queue
            for link in links:
                if link not in crawled and len(crawled) + len(to_crawl) < max_pages:
                    to_crawl.append((link, depth + 1))
    
    # Format output based on requested type
    if output_type.lower() == \"json\":
        output = json.dumps({
            \"starting_url\": url,
            \"pages_crawled\": len(crawled),
            \"max_depth\": max_depth,
            \"results\": results
        }, indent=2)
    else:
        # Format as markdown with separators
        output_lines = [f\"# Crawl Results: {url}\", f\"Pages crawled: {len(crawled)}\", \"\"]
        
        for result in results:
            if result.get('success', False):
                output_lines.append(f\"## {result['url']} (Depth: {result['depth']})\")
                output_lines.append(result['content'])
                output_lines.append(\"\
---\
\")
        
        output = \"\
\".join(output_lines)
    
    # Save to file if requested
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            return f\"Crawl results saved to {output_file}. Crawled {len(crawled)} pages.\"
        except Exception as e:
            return f\"Error saving to file: {str(e)}\
\
{output}\"
    
    return output

@mcp.tool()
async def analyze_url(url: str, timeout: int = DEFAULT_TIMEOUT, analyze_seo: bool = True, analyze_accessibility: bool = True, analyze_performance: bool = True, analyze_content: bool = True, output_type: str = \"markdown\", user_agent: Optional[str] = None) -> str:
    \"\"\"
    Analyze a URL for SEO, accessibility, performance, and content metrics.
    
    Args:
        url: URL to analyze
        timeout: Request timeout in seconds
        analyze_seo: Include SEO analysis
        analyze_accessibility: Include accessibility analysis
        analyze_performance: Include performance metrics
        analyze_content: Include content analysis
        output_type: Output format (markdown, html, text, json)
        user_agent: Custom user agent string
        
    Returns:
        Analysis results in the requested format
    \"\"\"
    # Use default user agent if none provided
    if not user_agent:
        user_agent = DEFAULT_USER_AGENT
    
    # Fetch the URL
    content, content_type, status_code, metadata = await fetch_url(
        url, 
        user_agent=user_agent,
        timeout=timeout
    )
    
    # Check for errors
    if status_code >= 400 or \"error\" in metadata:
        error_message = metadata.get(\"error\", f\"HTTP Error {status_code}\")
        return f\"Error analyzing {url}: {error_message}\"
    
    # Results object
    analysis_results = {
        \"url\": url,
        \"status_code\": status_code,
        \"content_type\": content_type,
        \"analysis_time\": datetime.now().isoformat(),
        \"size\": len(content),
        \"load_time\": metadata.get(\"elapsed\", 0),
    }
    
    # Parse HTML with BeautifulSoup if content is HTML
    html_parsed = False
    if \"text/html\" in content_type or \"<html\" in content[:1000].lower():
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            html_parsed = True
            
            # Basic content analysis
            if analyze_content:
                analysis_results[\"content_analysis\"] = {
                    \"title\": soup.title.string if soup.title else \"No title found\",
                    \"headings\": {
                        \"h1\": len(soup.find_all('h1')),
                        \"h2\": len(soup.find_all('h2')),
                        \"h3\": len(soup.find_all('h3')),
                        \"h4\": len(soup.find_all('h4')),
                        \"h5\": len(soup.find_all('h5')),
                        \"h6\": len(soup.find_all('h6')),
                    },
                    \"links\": len(soup.find_all('a')),
                    \"images\": len(soup.find_all('img')),
                    \"paragraphs\": len(soup.find_all('p')),
                    \"lists\": len(soup.find_all(['ul', 'ol'])),
                    \"tables\": len(soup.find_all('table')),
                    \"forms\": len(soup.find_all('form')),
                    \"iframes\": len(soup.find_all('iframe')),
                    \"scripts\": len(soup.find_all('script')),
                    \"styles\": len(soup.find_all('style')),
                    \"meta_tags\": len(soup.find_all('meta')),
                }
                
                # Get word count - rough estimate
                text_content = soup.get_text(\" \", strip=True)
                analysis_results[\"content_analysis\"][\"word_count\"] = len(text_content.split())
                analysis_results[\"content_analysis\"][\"character_count\"] = len(text_content)
            
            # SEO analysis
            if analyze_seo:
                meta_description = soup.find('meta', attrs={'name': 'description'})
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                canonical_link = soup.find('link', attrs={'rel': 'canonical'})
                robots_meta =`
}
