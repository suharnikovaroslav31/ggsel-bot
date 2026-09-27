"""Точка входа: сразу отвечает на PORT, либо работает за Node-прокси Bothost."""

from __future__ import annotations

import os

_BEHIND = os.getenv("GGSEL_BEHIND_PROXY") == "1"

if not _BEHIND:
    import http.client
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    _PUBLIC = int(os.getenv("PORT") or os.getenv("WEB_PORT") or "3000")
    _INTERNAL = 3002 if _PUBLIC == 3001 else 3001
    os.environ["WEB_PORT"] = str(_INTERNAL)
    _backend = ("127.0.0.1", _INTERNAL)
    _HEALTH = b'{"ok":true,"service":"ggsel-miniapp"}'

    class _Front(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args) -> None:
            return

        def do_HEAD(self) -> None:
            self._reply(200, b"")

        def do_GET(self) -> None:
            self._forward()

        def do_POST(self) -> None:
            self._forward()

        def do_PUT(self) -> None:
            self._forward()

        def do_PATCH(self) -> None:
            self._forward()

        def do_DELETE(self) -> None:
            self._forward()

        def do_OPTIONS(self) -> None:
            self._forward()

        def _reply(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in {"host", "connection"}}
            try:
                conn = http.client.HTTPConnection(_backend[0], _backend[1], timeout=30)
                conn.request(self.command, self.path, raw, headers)
                resp = conn.getresponse()
                payload = resp.read()
                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    if key.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                        continue
                    self.send_header(key, value)
                if "content-length" not in {k.lower() for k, _ in resp.getheaders()}:
                    self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
                conn.close()
            except Exception:
                self._reply(200, _HEALTH)

    httpd = ThreadingHTTPServer(("0.0.0.0", _PUBLIC), _Front)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"health on 0.0.0.0:{_PUBLIC} -> {_INTERNAL}", flush=True)

import asyncio

from bot import main as bot_main

if __name__ == "__main__":
    asyncio.run(bot_main())
