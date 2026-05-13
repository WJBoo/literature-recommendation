from pathlib import Path

import httpx


class GutenbergClient:
    """Small client for approved Project Gutenberg robot harvest URLs."""

    def __init__(self, raw_dir: Path, user_agent: str) -> None:
        self.raw_dir = raw_dir
        self.user_agent = user_agent

    async def download_text_file(self, url: str, destination: Path) -> Path:
        destination = self.raw_dir / destination
        destination.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(headers={"User-Agent": self.user_agent}, timeout=60) as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)

        return destination

