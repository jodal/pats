import logging

from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from pats import settings, twitter


logger = logging.getLogger(__name__)

sample_stream = twitter.SampleStream()

app = Starlette(debug=settings.DEBUG)


@app.route("/")
async def homepage(request):
    return FileResponse("client/index.html")


@app.websocket_route("/ws")
class SampleStream(WebSocketEndpoint):
    encoding = "text"

    async def on_connect(self, websocket):
        await websocket.accept()
        logger.info("WebSocket connected")
        self.subscription_id, queue = sample_stream.subscribe()
        while True:
            status = await queue.get()
            await websocket.send_json(status)

    async def on_disconnect(self, websocket, close_code):
        logger.info("WebSocket disconnected")
        sample_stream.unsubscribe(self.subscription_id)


app.mount(
    "/", StaticFiles(directory="client", packages=["bootstrap4"]), name="client"
)
