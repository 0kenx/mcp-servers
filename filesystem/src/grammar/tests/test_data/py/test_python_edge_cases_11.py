tasks = [self.fetch_item(item_id) for item_id in item_ids]
        return await asyncio.gather(*tasks)

# Async context manager
class AsyncResource:
    async def __aenter__(self):
        await asyncio.sleep(0.1)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.sleep(0.1)
    
    async def work(self):
        await asyncio.sleep(0.2)
        return "work done"

# Async iterator
class AsyncCounter:
    def __init__(self, limit: int):
        self.limit = limit
        self.count = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.count < self.limit:
            self.count += 1
            await asyncio.sleep(0.1)
            return self.count
        else:
            raise StopAsyncIteration