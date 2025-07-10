from pathlib import Path
import httpx

async def request(url:str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def search(prompt: str, limit: int = 1,type="mod") -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url="https://api.modrinth.com/v2/search",
            params={
                "query": prompt,
                "limit": limit,
                "facets":f"[[\"project_type:{type}\"]]"
            }
        )
        response.raise_for_status()
        return response.json()

async def download_file(url: str,destination: Path):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        with open(destination, "wb") as f:
            f.write(response.content)