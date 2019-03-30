# PATS - Python asyncio Twitter Search

## Views

### Default view

Default view shows a stream of realtime tweets,
using the [statuses/sample](https://developer.twitter.com/en/docs/tweets/sample-realtime/api-reference/get-statuses-sample) API.

### Search view

Search view shows a stream of realtime tweets matching the search query,
using the [statuses/filter](https://developer.twitter.com/en/docs/tweets/filter-realtime/overview/statuses-filter) API.

At the free level, the API only supports a single connection.
However, the connection can filter on up to 400 keywords.
Changing the filters requires the connection to be reconnected,
potentially loosing tweets.
