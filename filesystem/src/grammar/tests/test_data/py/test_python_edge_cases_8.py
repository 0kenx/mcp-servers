await asyncio.sleep(1)  # Simulate network delay
    return f"Data from {url}"

async def process_urls(urls: list[str]) -> list[str]: