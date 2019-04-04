# PATS - Python asyncio Twitter Search

A small tech demo featuring Python 3.7, asyncio, WebSockets, and Twitter.

## Features

### Default view

The default view shows a stream of realtime tweets,
using the [statuses/sample](https://developer.twitter.com/en/docs/tweets/sample-realtime/api-reference/get-statuses-sample) API.

### Filter view

The filter view shows a stream of realtime tweets matching the search query,
using the [statuses/filter](https://developer.twitter.com/en/docs/tweets/filter-realtime/overview/statuses-filter) API.

## Constraints

The Twitter realtime APIs only accept a single connection on their free tier.
However, the connection can filter on up to 400 keywords.
To change the filters one must reconnect to the API.

## System overview

```
      +-------------+
      | Web browser |          // client/index.html
      +-------------+          // client/main.js
         ^  ^  ^  ^
         |  |  |  |   N WebSocket connections
         |  |  |  |
       +------------+
       | Web server |          // pats/app.py
       +------------+
         ^  ^  ^  ^
         |  |  |  |   N asyncio queues
         |  |  |  |
      +----------------+
      | Twitter client |       // pats/twitter.py
      +----------------+
        ^            ^
        |            |   Two long-lived HTTP connections
        |            |
+------------+   +------------+
| Sample API |   | Filter API |
+------------+   +------------+
```

Once the server is started it sets up a sample stream and a filter stream,
but doesn't connect to the Twitter realtime APIs yet.

The web server serves an UI built from a single HTML and JS file,
found in the `client` dir.
The UI shows a stream of sample tweets and a form to filter the tweets.
The client-side JavaScripts opens a WebSocket back to the server.
The WebSocket connection request includes any filters that has been entered.

When the server (see `pats/app.py`) receives a WebSocket connection,
it registers as a subscriber to the requested Twitter stream,
passing on any filters,
and gets an `asyncio.Queue` back.

Until the WebSocket connection is closed,
the server waits for new tweets on the queue
and relays all tweets it receives to the WebSocket connection.

On the other side of the queue,
the Twitter client (see `pats/twitter.py`) connects to the Twitter API
as soon as it has at least one subscriber.
All tweets received from the Twitter APIs
are put on the queue of all active subscribers,
essentially broadcasting the tweets to all interested clients.

In the case of multiple user's applying filters,
the Filter API connection is restarted with the union of all filters.
When tweets are received from the Filter API,
they are relayed to the subscribed queues,
but only if the tweets contents matches the subscription's keywords.

## Scaling considerations

Given the above Twitter API connection constraints,
the current implementation is limited to a single server instance.
To be able to deploy this as a service across multiple servers,
replace the in-process `asyncio.Queue`s with out of process queues
between multiple web servers and the single Twitter client,
for example using Redis.

## Project setup

1. Install Python 3.7. If you have `pyenv`, change to the project dir and run:

```sh
pyenv install
```

2. Create and activate a `virtualenv`:

```sh
virtualenv -p $(pyenv which python) venv
source venv/bin/activate
```

3. Install dependencies:

```sh
pip install -r requirements-dev.txt
```

4. Run checks:

```sh
tox
```

5. Configure the app by creating an `.env` file from the `dev-template.env`
   template and filling out any missing pieces.

```sh
cp dev-template.env .env
$EDITOR .env
```

6. Start the web server:

```sh
python -m pats
```
