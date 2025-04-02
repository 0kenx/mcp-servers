# Web Processing MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Version](https://img.shields.io/badge/version-0.1.0-green) ![Python](https://img.shields.io/badge/Python-3.12+-blue)

A sophisticated web content retrieval and analysis platform that enables AI assistants like Claude to fetch, crawl, and intelligently process web content. This server bridges the gap between AI assistants and the internet, providing both raw content access and AI-powered information extraction capabilities.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [MCP Tools](#mcp-tools)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Web Processing MCP Server serves as an intelligent bridge between AI assistants and the broader internet. It enables capabilities ranging from simple URL content fetching to multi-page website crawling with intelligent processing of discovered content. By combining web access with AI-powered analysis, this server transforms raw web data into structured, useful information.

## Features

### Content Retrieval

- **Single-URL Fetching**: Retrieve content from any URL with robust error handling and timeout management
- **Website Crawling**: Navigate through websites by following links with configurable depth and page limits
- **Domain Control**: Restrict crawling to specific domains to maintain focus and respect site boundaries
- **Request Customization**: Configure timeouts, user agents, and other request parameters

### Content Processing

- **Format Conversion**: Transform web content into Markdown, HTML, Text, JSON, or Raw formats
- **Size Management**: Handle large web pages with automatic size limits and intelligent truncation
- **Content Cleaning**: Remove ads, navigation elements, and other clutter (when using Markdown output)
- **Structure Preservation**: Maintain document structure, links, and important formatting
- **Web Search**: Perform web searches using the Brave Search API

### AI Analysis

- **OpenAI Integration**: Process web content using OpenAI models with configurable parameters
- **Custom Instructions**: Provide specific directions for how the AI should analyze content
- **Multi-URL Processing**: Collect and analyze content from multiple sources in a single operation
- **Information Extraction**: Extract specific data points, summaries, or insights from web content

### Performance & Reliability

- **Asynchronous Processing**: Handle multiple requests efficiently without blocking
- **Error Resilience**: Gracefully handle connection issues, timeouts, and malformed content
- **Rate Limiting**: Built-in mechanisms to respect website rate limits and prevent overloading
- **Caching**: Optional response caching to improve performance and reduce redundant requests

## Requirements

### Software Requirements
- **Python**: Version 3.12 or newer
- **Docker**: For containerized deployment (recommended)
- **OpenAI API Key**: Required for AI processing capabilities
- **Brave API Key**: Required for web search functionality

### Python Dependencies
- **Web Processing**: beautifulsoup4, httpx, markdownify
- **API Framework**: fastapi, uvicorn, pydantic
- **AI Integration**: openai
- **MCP Protocol**: mcp[cli]

## Installation

### Option 1: Docker Installation (Recommended)

The Docker installation provides a self-contained environment with all dependencies configured:

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/web

# Build the Docker image
docker build . -t mcp/web

# Run the server with your OpenAI API key
docker run -p 3007:3007 -i --rm mcp/web sk-YOUR_OPENAI_API_KEY
```

### Option 2: Local Installation

For users who prefer direct installation on their system:

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/web

# Install dependencies using pip
pip install -r requirements.txt

# Or using uv (faster)
pip install uv
uv sync

# Run the server
python -m src.server sk-YOUR_OPENAI_API_KEY
```

## Configuration with Claude

Add the Web Processing MCP Server to your Claude configuration file:

```json
{
  "mcpServers": {
    "web": {
      "command": "docker",
      "args": [
          "run",
          "-i",
          "--rm",
          "-e",
          "OPENAI_API_KEY",
          "-e",
          "BRAVE_API_KEY",
          "mcp/web"
      ],
      "env": {
        "OPENAI_API_KEY": "sk-YOUR_OPENAI_KEY",
        "BRAVE_API_KEY": "YOUR_BRAVE_KEY"
      }
    }
  }
}
```

**Note**: Replace `sk-YOUR_OPENAI_KEY` with your actual OpenAI API key (required for AI processing capabilities) and `YOUR_BRAVE_KEY` with your Brave Search API key (required for web search functionality).


## MCP Tools

The following tools are exposed via Model Context Protocol (MCP) for AI assistants to use:

### Basic URL Fetching

#### `fetch_url`

Retrieve content from a single URL without AI processing.

```python
fetch_url(
    url: str,                         # URL to fetch
    timeout: int = 30,                # Request timeout in seconds
    output_type: str = 'markdown',    # Output format ('markdown', 'html', 'text', 'json', 'raw')
    max_length: int = 100000          # Maximum characters to return
)
```

**Example use by Claude:**
```
Can you fetch the content from https://example.com and tell me what it contains?
```

### AI-Enhanced URL Processing

#### `fetch_and_process_urls`

Fetch content from multiple URLs and analyze them using AI based on specific instructions.

```python
fetch_and_process_urls(
    urls: List[str],                  # List of URLs to fetch
    instructions: str,                # Instructions for AI processing
    timeout: int = 30,                # Request timeout per URL
    max_length: int = 100000,         # Max characters per URL to process
    user_agent: Optional[str] = None, # Custom user agent string
    openai_model: str = 'o3-mini',    # AI model to use for processing
    openai_max_tokens: int = 10000,   # Maximum tokens for AI responses
    preprocess_to_format: str = 'markdown' # Format to convert content before AI processing
)
```

**Example use by Claude:**
```
I need you to analyze the following websites: https://site1.com and https://site2.com. Compare their approaches to climate change solutions and identify the key differences.
```

### Website Crawling

#### `crawl_website`

Crawl a website starting from a URL, collecting content from linked pages.

```python
crawl_website(
    url: str,                         # Starting URL
    max_pages: int = 5,               # Maximum pages to fetch
    max_depth: int = 2,               # Maximum link depth from start URL
    timeout: int = 30,                # Request timeout per page in seconds
    follow_links: bool = True,        # Find and follow links if True
    allowed_domains: Optional[List[str]] = None # Domains to restrict crawling to
)
```

**Example use by Claude:**
```
Crawl https://example.com with max_depth=2 and max_pages=10 to collect information about their product offerings.
```

### Advanced AI-Enhanced Crawling

#### `crawl_and_process_url`

Crawl a website and process all discovered pages with AI based on custom instructions.

```python
crawl_and_process_url(
    url: str,                         # Starting URL to crawl
    instructions: str,                # Instructions for AI processing of crawled content
    max_pages: int = 5,               # Maximum pages to fetch
    max_depth: int = 2,               # Maximum link depth from start URL
    timeout: int = 30,                # Request timeout per page in seconds
    allowed_domains: Optional[List[str]] = None, # Domains to restrict crawling to
    openai_model: str = 'o3-mini',    # AI model to use
    openai_max_tokens: int = 10000    # Maximum tokens for AI response
)
```

**Example use by Claude:**
```
Crawl the documentation at https://docs.example.com and create a comprehensive summary of their API endpoints, with examples of how each is used.
```

### Web Search

#### `search_web`

Performs a web search using the Brave Search API and returns formatted results.

```python
search_web(
    query: str,                      # The search query string
    count: int = 10,                  # Number of results to return (1-20, default: 10)
    offset: int = 0,                  # Result offset for pagination (default: 0)
    timeout: int = 30                 # Request timeout in seconds (default: 30)
)
```

**Example use by Claude:**
```
Search the web for "latest developments in quantum computing" and summarize the results.
```

#### `search_web_and_process`

Performs a Brave web search, then processes the results with an AI agent based on instructions.

```python
search_web_and_process(
    query: str,                      # The search query string
    instructions: str,                # Instructions for the AI on how to process the search results
    count: int = 10,                  # Number of search results to retrieve (1-20, default: 10)
    offset: int = 0,                  # Result offset for pagination (default: 0)
    search_timeout: int = 30,         # Timeout for the Brave Search API call (default: 30)
    openai_model: str = 'o3-mini',    # AI model to use for processing (default: 'o3-mini')
    openai_max_tokens: int = 10000    # Max tokens for the AI response (default: 10000)
)
```

**Example use by Claude:**
```
Search the web for "climate change solutions" and analyze the different approaches mentioned across the search results.
```

## Use Cases

### Research & Information Gathering

- **Comprehensive Research**: Gather information from multiple sources on a specific topic
- **Web Searching**: Perform web searches and analyze results across multiple sources
- **Competitive Analysis**: Compare multiple websites or products by crawling and analyzing their content
- **Documentation Exploration**: Process technical documentation and extract key information
- **News Monitoring**: Collect and analyze news from multiple sources

### Content Analysis & Summary

- **Document Summarization**: Extract key points from lengthy web content
- **Information Extraction**: Pull specific data points or statistics from web pages
- **Sentiment Analysis**: Analyze opinions and sentiments expressed in web content
- **Trend Identification**: Identify patterns or trends across multiple web sources

### Technical Applications

- **API Documentation Review**: Process API documentation to understand endpoints and usage
- **Code Examples Collection**: Gather code examples for specific programming tasks
- **Technical Troubleshooting**: Search for solutions to technical problems across multiple sources
- **Learning Resources**: Collect and organize educational content on specific topics

## Security Considerations

### Safe Web Interaction

- **Domain Restrictions**: Use the `allowed_domains` parameter to prevent unintended crawling
- **Rate Limiting**: Control request frequency to avoid overwhelming websites
- **Timeout Management**: Set appropriate timeouts to prevent hanging connections
- **User Agent Configuration**: Use respectful user agents that identify your bot

### API Key Protection

- **Key Security**: Keep your OpenAI API key secure and never expose it in client-side code
- **Usage Monitoring**: Regularly monitor your OpenAI API usage to detect unexpected activity
- **Rate Limiting**: Implement rate limiting in high-traffic scenarios to control costs

### Data Privacy

- **Sensitive Information**: Be cautious when processing content that may contain personal or sensitive information
- **Content Storage**: Consider how and where crawled content is stored, if at all
- **Terms of Service**: Ensure your web crawling activities comply with websites' terms of service

## Contributing

Contributions are welcome! If you'd like to improve this project.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
