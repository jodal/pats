from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings, Secret


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)

TWITTER_LANGUAGES = config(
    "TWITTER_LANGUAGES", cast=CommaSeparatedStrings, default="en"
)
TWITTER_CONSUMER_KEY = config("TWITTER_CONSUMER_KEY", cast=Secret)
TWITTER_CONSUMER_SECRET = config("TWITTER_CONSUMER_SECRET", cast=Secret)
TWITTER_ACCESS_TOKEN = config("TWITTER_ACCESS_TOKEN", cast=Secret)
TWITTER_ACCESS_TOKEN_SECRET = config("TWITTER_ACCESS_TOKEN_SECRET", cast=Secret)
