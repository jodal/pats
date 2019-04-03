import asyncio
import logging
import json
import uuid
from typing import Optional, Tuple

from aioauth_client import TwitterClient

import aiohttp

from pats import settings


logger = logging.getLogger()

session = aiohttp.ClientSession()

client = TwitterClient(
    consumer_key=str(settings.TWITTER_CONSUMER_KEY),
    consumer_secret=str(settings.TWITTER_CONSUMER_SECRET),
    oauth_token=str(settings.TWITTER_ACCESS_TOKEN),
    oauth_token_secret=str(settings.TWITTER_ACCESS_TOKEN_SECRET),
)

# XXX aioauth_client's request method does too much, so it does not support
# streaming responses. To work around that, replace it with aiohttp's
# request method.
client._request = session.request


class Stream:
    method: str
    url: str

    def __init__(self):
        self._subscribers = {}
        self._running = asyncio.Event()

    def __str__(self):
        return f"Twitter {self.__class__.__name__}"

    def _subscribe(
        self, keywords: Optional[str] = None
    ) -> Tuple[uuid.UUID, asyncio.Queue]:
        sub_id: uuid.UUID = uuid.uuid4()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[sub_id] = (queue, keywords)
        asyncio.create_task(self._connect())
        return (sub_id, queue)

    def unsubscribe(self, sub_id: uuid.UUID) -> None:
        del self._subscribers[sub_id]
        if not self._subscribers:
            self._disconnect()

    async def _connect(self) -> None:
        if self._running.is_set():
            return
        self._running.set()

        params = {"delimited": "length"}
        keywords = {k for (_, k) in self._subscribers.values() if k is not None}
        if keywords:
            params["track"] = ",".join(keywords)

        response = await client.request(self.method, self.url, params=params)

        if response.status == 420:
            logger.warning(f"{self}: Rate limited by Twitter; waiting 60s")
            await asyncio.sleep(60)  # TODO Add exponential backoff
            self._running.clear()
            await self._connect()
            return

        response.raise_for_status()

        logger.info(f"{self}: Connected")

        while self._running.is_set() and not response.connection.closed:
            await self._read_item(response)

    def _disconnect(self) -> None:
        logger.info(f"{self}: Disconnecting now")
        self._running.clear()

    async def _read_item(self, response):
        length = 0
        while not response.connection.closed:
            line = await response.content.readline()
            line = line.strip() if line else line
            if not line:
                pass  # keep-alive
            elif line.isdigit():
                length = int(line)
                break

        data = await response.content.readexactly(length)
        await self._on_data(data)

    async def _on_data(self, raw_data: bytes) -> None:
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning(f"{self}: Ignored invalid JSON: {raw_data!r}")
            return

        if "in_reply_to_status_id" not in data:
            return  # Ignore everything but status updates

        if data.get("lang") not in ["en", "no"]:
            return  # Ignore everything but English and Norwegian

        for (queue, _) in self._subscribers.values():
            await queue.put(data)


class SampleStream(Stream):
    method = "GET"
    url = "https://stream.twitter.com/1.1/statuses/sample.json"

    def subscribe(self) -> Tuple[uuid.UUID, asyncio.Queue]:
        return self._subscribe()


class FilterStream(Stream):
    method = "POST"
    url = "https://stream.twitter.com/1.1/statuses/filter.json"

    def subscribe(self, keywords: str) -> Tuple[uuid.UUID, asyncio.Queue]:
        assert keywords
        return self._subscribe(keywords=keywords)

    # TODO Reconnect when new keywords are subscribed to
