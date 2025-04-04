tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results

class DataProcessor:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def fetch_item(self, item_id: int) -> dict: