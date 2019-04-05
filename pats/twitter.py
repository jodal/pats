import asyncio
import logging
import json
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from aioauth_client import TwitterClient

import aiohttp

from pats import settings


logger = logging.getLogger()

timeout = aiohttp.ClientTimeout(
    total=None  # No limit. The connection might last for a very long time.
)
session = aiohttp.ClientSession(timeout=timeout)

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
Tweet = Dict


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
        self._running = False
        self._connection = None
        self._connection_keywords = []

    def __str__(self):
        return f"Twitter {self.__class__.__name__}"

    def _subscribe(self, keywords: Optional[List[str]] = None) -> Subscription:
        subscription = Subscription.new(
            keywords=keywords, unsubscribe_func=self.unsubscribe
        )
        self._subscribers[subscription.id] = subscription
        asyncio.create_task(self._connect_or_reconnect())
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        if subscription.id in self._subscribers:
            del self._subscribers[subscription.id]
        if not self._subscribers:
            asyncio.create_task(self._disconnect_soon())

    def _get_subscription_keywords(self) -> List[str]:
        return sorted(
            list(
                set(
                    keyword
                    for subscription in self._subscribers.values()
                    if subscription.keywords
                    for keyword in subscription.keywords
                )
            )
        )

    def _is_connected(self) -> bool:
        return bool(
            self._running and self._connection and not self._connection.closed
        )

    async def _connect_or_reconnect(self) -> None:
        if not self._is_connected():
            await self._connect()
        elif self._connection_keywords != self._get_subscription_keywords():
            await self._reconnect()
        else:
            pass  # Connected with the correct filters

    async def _connect(self) -> None:
        if self._is_connected():
            return
        self._running = True

        params = {"delimited": "length"}
        keywords = self._get_subscription_keywords()
        if keywords:
            params["track"] = ",".join(keywords)

        response = await client.request(self.method, self.url, params=params)

        if response.status == 420:
            logger.warning(f"{self}: Rate limited by Twitter; waiting 60s")
            await asyncio.sleep(60)  # TODO Add exponential backoff
            self._running = False
            await self._connect()
            return

        response.raise_for_status()

        self._connection = response.connection
        self._connection_keywords = keywords
        logger.info(f"{self}: Connected (filter: {','.join(keywords)})")

        while self._is_connected():
            await self._read_item(response)

    async def _disconnect_soon(self) -> None:
        minutes = 5
        logger.info(f"{self}: Disconnecting in {minutes} minutes")
        await asyncio.sleep(minutes * 60)
        if not self._subscribers:
            self._disconnect()

    def _disconnect(self) -> None:
        logger.info(f"{self}: Disconnecting now")
        self._running = False

    async def _reconnect(self) -> None:
        logger.info(
            f"{self}: Disconnecting "
            f"(filter: {','.join(self._connection_keywords)})"
        )
        self._running = False
        while self._connection and not self._connection.closed:
            asyncio.sleep(0.01)

        logger.info(
            f"{self}: Connecting "
            f"(filter: {','.join(self._get_subscription_keywords())})"
        )
        await self._connect()

    async def _read_item(self, response):
        length = 0
        while self._is_connected():
            line = (
                await response.content.readline()
            )  # TODO Break out of this to disconnect?
            line = line.strip() if line else line
            if not line:
                pass  # keep-alive
            elif line.isdigit():
                length = int(line)
                break

        data = await response.content.readexactly(length)
        await self._on_data(data)

    async def _on_data(self, data: bytes) -> None:
        try:
            tweet = json.loads(data)
        except json.JSONDecodeError:
            logger.warning(f"{self}: Ignored invalid JSON: {data!r}")
            return

        if "in_reply_to_status_id" not in tweet:
            return  # Ignore everything but status updates

        if tweet.get("lang") not in settings.TWITTER_LANGUAGES:
            return  # Ignore tweets in other languages

        await self._broadcast(tweet)

    async def _broadcast(self, tweet: Tweet) -> None:
        raise NotImplementedError


class SampleStream(Stream):
    method = "GET"
    url = "https://stream.twitter.com/1.1/statuses/sample.json"

    def subscribe(self) -> Subscription:
        return self._subscribe()

    async def _broadcast(self, tweet: Tweet) -> None:
        for subscription in self._subscribers.values():
            await subscription.queue.put(tweet)


class FilterStream(Stream):
    method = "POST"
    url = "https://stream.twitter.com/1.1/statuses/filter.json"

    def subscribe(self, keywords: List[str]) -> Subscription:
        assert keywords
        subscription = self._subscribe(keywords=keywords)
        return subscription

    async def _broadcast(self, tweet: Tweet) -> None:
        for subscription in self._subscribers.values():
            matching = any(
                keyword.lower() in tweet["text"].lower()
                for keyword in subscription.keywords
            )
            if matching:
                await subscription.queue.put(tweet)
