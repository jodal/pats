function showFilter() {
  const url = new URL(document.location);
  const filter = url.searchParams.get("filter");
  document.querySelector("input[name='filter']").value = filter;
}

function connect() {
  const protocol = window.location.protocol == "http:" ? "ws" : "wss";
  const ws = new WebSocket(
    `${protocol}://${document.location.host}/ws${document.location.search}`
  );

  ws.onmessage = function(event) {
    const status = JSON.parse(event.data);
    addTweet(status);
  };

  ws.onclose = function(event) {
    // TODO Add exponential backoff
    setTimeout(connect, 2000);
  };
}

const tweetTemplate = document.querySelector("template#tweet");
const streamEl = document.querySelector("#stream");

function addTweet(status) {
  const tweetEl = document.importNode(tweetTemplate.content, true);
  tweetEl.querySelector(".profile-img").src =
    status.user.profile_image_url_https;
  tweetEl.querySelector(".name").innerText = status.user.name;
  tweetEl.querySelector(".screen-name").innerText = `@${
    status.user.screen_name
  }`;
  tweetEl.querySelector(".created-at").innerText = status.created_at;
  tweetEl.querySelector(".text").innerText = status.text;
  streamEl.prepend(tweetEl);

  // TODO Trim length of page to not use infinite memory
}

showFilter();
connect();
