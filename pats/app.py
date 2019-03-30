from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from pats import settings


app = Starlette(debug=settings.DEBUG)


@app.route("/")
async def homepage(request):
    return FileResponse("client/index.html")


@app.websocket_route("/ws")
async def websocket_hello(websocket):
    await websocket.accept()
    await websocket.send_json({"hello": "world"})
    await websocket.close()


app.mount(
    "/", StaticFiles(directory="client", packages=["bootstrap4"]), name="client"
)
