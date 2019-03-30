from starlette.config import Config


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
