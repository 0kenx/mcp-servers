# Web Processing Agent MCP Server

A powerful web scraping and processing server that enables Claude to fetch web content, crawl websites, and analyze information with an AI agent.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [API Tools](#api-tools)
- [Contributing](#contributing)
- [License](#license)

This server allows Claude to interact with web content through the Model Context Protocol (MCP). It provides capabilities for fetching web pages, crawling websites, and processing content with AI.

## Features

- **Web Fetching**: Retrieve content from any URL with proper error handling
- **Website Crawling**: Navigate websites with configurable depth and page limits
- **AI Processing**: Analyze web content using OpenAI models (configurable)
- **Multiple Output Formats**: Get results in Markdown, HTML, Text, JSON, or Raw formats
- **Domain Controls**: Limit website crawling to specific domains
- **Timeout Management**: Handle long-running requests with configurable timeouts
- **Content Truncation**: Handle large web pages with automatic size limits

## Requirements

- Python 3.12+
- Required Python packages:
  - beautifulsoup4
  - httpx
  - markdownify
  - mcp[cli]
  - openai
  - pydantic

## Installation

### Option 1: Local Installation

1. Clone the repository:
```bash
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/web
```

2. Install dependencies using uv:
```bash
pip install uv
uv sync
```

3. Build docker
```bash
docker build . -t mcp/web
```

4. Add server to `claude_desktop_config.json`:
```
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
          "run",
          "-i",
          "--rm",
          "mcp/web,
          "sk-YOUR_OPENAI_API_KEY"
      ]
    }
  }
}

```


## API Tools

The server exposes several tools via MCP (Model Context Protocol):

### URL Fetching

#### `fetch_url`

Fetch content from a single URL without AI processing.

```python
fetch_url(
    url: str,                # URL to fetch
    timeout: int = 30,       # Request timeout in seconds
    output_type: str = 'markdown', # Output format ('markdown', 'html', 'text', 'json', 'raw')
    max_length: int = 100000 # Max chars to return
)
```

#### `fetch_and_process_urls`

Fetch content from multiple URLs and process them with OpenAI.

```python
fetch_and_process_urls(
    urls: List[str],                  # List of URLs to fetch
    instructions: str,                # Instructions for AI processing
    timeout: int = 30,                # Request timeout per URL
    max_length: int = 100000,         # Max chars per URL to process
    user_agent: Optional[str] = None, # Custom user agent
    openai_model: str = 'o3-mini',    # AI model to use
    openai_max_tokens: int = 10000,   # Max tokens for AI responses
    preprocess_to_format: str = 'markdown' # Format to convert content before AI processing
)
```

### Website Crawling

#### `crawl_website`

Crawl a website starting from a URL, collecting linked pages.

```python
crawl_website(
    url: str,                         # Starting URL
    max_pages: int = 5,               # Max pages to fetch
    max_depth: int = 2,               # Max link depth from start URL
    timeout: int = 30,                # Request timeout per page in seconds
    follow_links: bool = True,        # Find and follow links if True
    allowed_domains: Optional[List[str]] = None # Domains to restrict crawling to
)
```

#### `crawl_and_process_url`

Crawl a website and process discovered pages with AI based on instructions.

```python
crawl_and_process_url(
    url: str,                         # Starting URL to crawl
    instructions: str,                # Instructions for AI processing of crawled content
    max_pages: int = 5,               # Max pages to fetch
    max_depth: int = 2,               # Max link depth from start URL
    timeout: int = 30,                # Request timeout per page in seconds
    allowed_domains: Optional[List[str]] = None, # Domains to restrict crawling to
    openai_model: str = 'o3-mini',    # AI model to use
    openai_max_tokens: int = 10000    # Max tokens for AI response
)
```

## Contributing

Contributions are welcome! If you'd like to improve this project.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
