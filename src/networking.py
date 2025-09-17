import httpx
import logging

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
logger = logging.getLogger("Network")


MODRINTH_BASE = "https://api.modrinth.com/v2"

def should_retry(exception):
    # Don't retry on 404 errors
    if "Resource not found" in str(exception):
        return False
    return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.2, min=4, max=10),retry=retry_if_exception(should_retry))
async def modrinth_api_endpoint_request(endpoint:str,params=None):
    url = f"{MODRINTH_BASE}/{endpoint}"
    async with httpx.AsyncClient() as client:
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
        except httpx.RequestError as e:
            logger.error(f"Request to {url} failed: {e}")
            raise Exception(f"Request to {url} failed: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Request to {url} timed out: {e}")