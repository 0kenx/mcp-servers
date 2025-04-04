await asyncio.sleep(0.5)
        return {"id": item_id, "url": f"{self.base_url}/{item_id}"}
    
    async def process_batch(self, item_ids: list[int]) -> list[dict]: