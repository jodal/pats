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
}

function connect() {
  const ws = new WebSocket("ws://localhost:8000/ws");
  ws.onmessage = function(event) {
    const status = JSON.parse(event.data);
    addTweet(status);
  };
  ws.onclose = function(event) {
    // TODO Add exponential backoff
    setTimeout(connect, 2000);
  };
}

connect();
