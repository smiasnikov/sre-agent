"""Local Messages API fixture for exercising the real SDK orchestration loop."""

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, List
from uuid import uuid4

from agent.constants import MCP_PREFIX
from agent.schemas import JsonObject


class FixtureModelServer:
    def __init__(self, choose: Callable[[JsonObject], JsonObject]) -> None:
        self.identifier = str(uuid4())
        self.choose = choose
        self.requests: List[JsonObject] = []
        self.responses: List[JsonObject] = []

    def __enter__(self) -> "FixtureModelServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                body = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", "0")))
                )
                if self.path.split("?")[0] == "/v1/messages/count_tokens":
                    self.send_json({"input_tokens": 1})
                    return
                if self.path.split("?")[0] != "/v1/messages":
                    self.send_json({}, 404)
                    return
                message = owner.respond(body)
                if not body.get("stream"):
                    self.send_json(message)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for event in owner.events(message):
                    frame = "event: {}\ndata: {}\n\n".format(
                        event["type"], json.dumps(event)
                    )
                    self.wfile.write(frame.encode())
                self.wfile.flush()

            def send_json(self, value, status=200):
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.05),
            daemon=True,
        )
        self.thread.start()
        return self

    def __exit__(self, *args) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @staticmethod
    def cards(request: JsonObject) -> List[JsonObject]:
        def texts(content):
            if isinstance(content, str):
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            yield from texts(block.get("content", []))
                        elif "text" in block:
                            yield block["text"]

        cards = []
        for message in request.get("messages", []):
            for text in texts(message.get("content", [])):
                try:
                    # Error tool results may append SDK annotations after the JSON.
                    value, _ = json.JSONDecoder().raw_decode(text.lstrip())
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict) and isinstance(
                    value.get("incident_card"), dict
                ):
                    cards.append(value["incident_card"])
        return cards

    def respond(self, request: JsonObject) -> JsonObject:
        self.requests.append(copy.deepcopy(request))
        selected = self.choose(request)
        if "tool" in selected:
            content = {
                "type": "tool_use",
                "id": self.identifier + "-" + str(len(self.requests)),
                "name": MCP_PREFIX + selected["tool"],
                "input": selected["arguments"],
            }
            reason = "tool_use"
        else:
            content = {"type": "text", "text": selected["text"]}
            reason = "end_turn"
        response = {
            "id": self.identifier + "-message-" + str(len(self.requests)),
            "type": "message",
            "role": "assistant",
            "model": request["model"],
            "content": [content],
            "stop_reason": reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        self.responses.append(copy.deepcopy(response))
        return response

    @staticmethod
    def events(message: JsonObject) -> List[JsonObject]:
        block = message["content"][0]
        if block["type"] == "tool_use":
            start = dict(block, input={})
            delta = {
                "type": "input_json_delta",
                "partial_json": json.dumps(block["input"]),
            }
        else:
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        return [
            {
                "type": "message_start",
                "message": dict(message, content=[], stop_reason=None),
            },
            {"type": "content_block_start", "index": 0, "content_block": start},
            {"type": "content_block_delta", "index": 0, "delta": delta},
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": message["stop_reason"], "stop_sequence": None},
                "usage": {"output_tokens": 1},
            },
            {"type": "message_stop"},
        ]
