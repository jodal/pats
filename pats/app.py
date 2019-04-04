import logging
from typing import Optional

from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from websockets.exceptions import ConnectionClosed

from pats import settings, twitter


logger = logging.getLogger(__name__)

sample_stream = twitter.SampleStream()
filter_stream = twitter.FilterStream()

app = Starlette(debug=settings.DEBUG)


@app.route("/")
async def homepage(request):
    return FileResponse("client/index.html")


@app.websocket_route("/ws")
class TwitterStream(WebSocketEndpoint):
    encoding = "text"
    subscription: Optional[twitter.Subscription] = None

    async def on_connect(self, websocket):
        keywords = websocket.query_params.get("filter")

        await websocket.accept()
        logger.info(f"WebSocket connected (filter: {keywords})")

        if keywords:
            self.subscription = filter_stream.subscribe(keywords.split(","))
        else:
            self.subscription = sample_stream.subscribe()

        while True:
            tweet = await self.subscription.queue.get()
            try:
                await websocket.send_json(tweet)
            except ConnectionClosed:
                logger.info("WebSocket closed unexpectedly")
                self.subscription.unsubscribe()
                return

    async def on_disconnect(self, websocket, close_code):
        logger.info("WebSocket disconnected by client")
        self.subscription.unsubscribe()


app.mount(
    "/", StaticFiles(directory="client", packages=["bootstrap4"]), name="client"
)
