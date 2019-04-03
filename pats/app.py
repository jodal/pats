import logging

from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

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

    async def on_connect(self, websocket):
        keywords = websocket.query_params.get("filter")

        await websocket.accept()
        logger.info(f"WebSocket connected (filter: {keywords})")

        if keywords:
            sub_id, queue = filter_stream.subscribe(keywords)
            self.unsubscribe = lambda: filter_stream.unsubscribe(sub_id)
        else:
            sub_id, queue = sample_stream.subscribe()
            self.unsubscribe = lambda: sample_stream.unsubscribe(sub_id)

        while True:
            status = await queue.get()
            await websocket.send_json(status)

    async def on_disconnect(self, websocket, close_code):
        logger.info("WebSocket disconnected")
        self.unsubscribe()


app.mount(
    "/", StaticFiles(directory="client", packages=["bootstrap4"]), name="client"
)
