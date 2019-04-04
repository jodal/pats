import logging
from typing import Optional

from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, Router
from starlette.staticfiles import StaticFiles

from websockets.exceptions import ConnectionClosed

from pats import settings, twitter


logger = logging.getLogger(__name__)


async def client_home(request):
    return FileResponse("client/index.html")


client_app = Router(
    routes=[
        Route("/", endpoint=client_home, methods=["GET"]),
        Mount(
            "/",
            app=StaticFiles(directory="client", packages=["bootstrap4"]),
            name="static",
        ),
    ]
)


sample_stream = twitter.SampleStream()
filter_stream = twitter.FilterStream()


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


app = Starlette(debug=settings.DEBUG)
app.add_websocket_route("/ws", TwitterStream)
app.mount("/", client_app)
