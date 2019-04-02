import asyncio
import logging
from typing import Tuple

import tweepy

from pats import settings


logger = logging.getLogger()


auth = tweepy.OAuthHandler(
    str(settings.TWITTER_CONSUMER_KEY), str(settings.TWITTER_CONSUMER_SECRET)
)
auth.set_access_token(
    str(settings.TWITTER_ACCESS_TOKEN),
    str(settings.TWITTER_ACCESS_TOKEN_SECRET),
)


class StreamListener(tweepy.StreamListener):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue

    def on_connect(self):
        logger.info("Connected to stream")

    def on_disconnect(self, notice):
        logger.error(f"Stream disconnected: {notice}")

    def on_warning(self, notice):
        logger.warning(f"Stream warning: {notice}")

    def on_error(self, status_code):
        logger.warning(f"Twitter error code: {status_code}")
        return False

    def on_status(self, status):
        logger.debug(f"New tweet {status.text}")
        try:
            self.queue.put_nowait(status._json)
        except asyncio.QueueFull:
            logger.warning("Lost tweet because of full queue")


def create_stream() -> Tuple[tweepy.Stream, asyncio.Queue]:
    queue: asyncio.Queue = asyncio.Queue()
    stream = tweepy.Stream(auth=auth, listener=StreamListener(queue))
    return (stream, queue)
