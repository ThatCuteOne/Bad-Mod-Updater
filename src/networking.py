import asyncio
import aiofiles
import aiohttp
import logging

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

import config
logger = logging.getLogger("Network")


MODRINTH_BASE = "https://api.modrinth.com/v2"

concurrent_downloads = 10

def should_retry(exception):
    # Don't retry on 404 errors
    if "Resource not found" in str(exception):
        return False
    return True


async def download_jar(download_url,filename):
    """Downloads jar file from given url"""
    logger = logging.getLogger("Mod Downloader")
    logger.info(f"Downloading {filename} [{download_url}]")
    async with asyncio.Semaphore(concurrent_downloads):
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(download_url) as response:
                    response.raise_for_status()
                    async with aiofiles.open(f"./mods/{filename}", 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                        logger.info(f"Downloaded {filename} ✅")
                        return True
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                logger.error(f"file not found[404 error]: {download_url}")
            else:
                logger.exception(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.2, min=4, max=10),retry=retry_if_exception(should_retry))
async def modrinth_api_endpoint_request(endpoint:str,params=None):
    url = f"{MODRINTH_BASE}/{endpoint}"
    async with aiohttp.ClientSession() as client:
        try:
            response = await client.get(
                url,
                params=params
            )
            
            if not response.is_success:
                if response.status_code == 404:
                        logger.error(f"Resource not found at {url}")
                        raise Exception(f"Resource not found at {url}")
                error_text = response.text
                logger.error(f"Request to {url} failed: {error_text}")
                raise Exception(f"Request to {url} failed: {error_text}")
            
            return response.json()
        except aiohttp.RequestError as e:
            logger.error(f"Request to {url} failed: {e}")
            raise Exception(f"Request to {url} failed: {e}")
        except aiohttp.TimeoutException as e:
            logger.error(f"Request to {url} timed out: {e}")
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.2, min=4, max=10),retry=retry_if_exception(should_retry))
async def modrinth_api_post_newest_versions(hashes:list,endpoint:str="version_files/update"):
    url = f"{MODRINTH_BASE}/{endpoint}"
    async with aiohttp.ClientSession() as client:
        try:
            response = await client.post(
                url,
                json={
                    "hashes": hashes,
                    "algorithm": "sha512",
                    "loaders":[config.LOADER],
                    "game_versions": config.MINECRAFT_VERSIONS
                }
            )
            if not response:
                if response.status_code == 404:
                        logger.error(f"Resource not found at {url}")
                        raise Exception(f"Resource not found at {url}")
                error_text = response.text
                logger.error(f"Request to {url} failed: {error_text}")
                raise Exception(f"Request to {url} failed: {error_text}")
            
            return await response.json()
        except aiohttp.RequestError as e:
            logger.error(f"Request to {url} failed: {e}")
            raise Exception(f"Request to {url} failed: {e}")
        except aiohttp.TimeoutException as e:
            logger.error(f"Request to {url} timed out: {e}")