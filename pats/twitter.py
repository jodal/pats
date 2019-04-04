import asyncio
import logging
import json
import uuid
from dataclasses import dataclass
from typing import Callable, List, Optional

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


UnsubscribeFunc = Callable[["Subscription"], None]


@dataclass
class Subscription:
    id: uuid.UUID
    queue: asyncio.Queue
    keywords: List[str]
    unsubscribe_func: Optional[UnsubscribeFunc] = None

    @classmethod
    def new(
        cls,
        keywords: Optional[List[str]] = None,
        unsubscribe_func: Optional[UnsubscribeFunc] = None,
    ) -> "Subscription":
        return cls(
            id=uuid.uuid4(),
            queue=asyncio.Queue(),
            keywords=keywords or [],
            unsubscribe_func=unsubscribe_func,
        )

    def unsubscribe(self):
        if self.unsubscribe_func is None:
            return
        self.unsubscribe_func(self)


class Stream:
    method: str
    url: str

    def __init__(self):
        self._subscribers = {}
        self._running = asyncio.Event()

    def __str__(self):
        return f"Twitter {self.__class__.__name__}"

    def _subscribe(self, keywords: Optional[List[str]] = None) -> Subscription:
        subscription = Subscription.new(
            keywords=keywords, unsubscribe_func=self.unsubscribe
        )
        self._subscribers[subscription.id] = subscription
        asyncio.create_task(self._connect())
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        if subscription.id in self._subscribers:
            del self._subscribers[subscription.id]
        if not self._subscribers:
            asyncio.create_task(self._disconnect_soon())

    async def _connect(self) -> None:
        if self._running.is_set():
            return
        self._running.set()

        params = {"delimited": "length"}
        keywords = {
            keyword
            for subscription in self._subscribers.values()
            if subscription.keywords
            for keyword in subscription.keywords
        }
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

    async def _disconnect_soon(self) -> None:
        minutes = 5
        logger.info(f"{self}: Disconnecting in {minutes} minutes")
        await asyncio.sleep(minutes * 60)
        if not self._subscribers:
            self._disconnect()

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

        for subscription in self._subscribers.values():
            await subscription.queue.put(data)


class SampleStream(Stream):
    method = "GET"
    url = "https://stream.twitter.com/1.1/statuses/sample.json"

    def subscribe(self) -> Subscription:
        return self._subscribe()


class FilterStream(Stream):
    method = "POST"
    url = "https://stream.twitter.com/1.1/statuses/filter.json"

    def subscribe(self, keywords: List[str]) -> Subscription:
        assert keywords
        return self._subscribe(keywords=keywords)

    # TODO Reconnect when new keywords are subscribed to
