const tweetTemplate = document.querySelector("template#tweet");
const streamEl = document.querySelector("#stream");

function addTweet(message) {
  const tweetEl = document.importNode(tweetTemplate.content, true);
  tweetEl.querySelector(".message").innerText = message;
  streamEl.prepend(tweetEl);
}

const ws = new WebSocket("ws://localhost:8000/ws");
ws.onmessage = function(event) {
  addTweet(event.data);
};

addTweet("Foo");
