"""Reject excessive/chunked bodies before multipart or image decoding."""
import os

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self.limit = int(os.environ.get("LOOPSIGHT_MAX_REQUEST_BYTES", "4000000"))
        if not 1024 <= self.limit <= 32 * 1024 * 1024:
            raise ValueError("request body limit outside supported bounds")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError()
        except ValueError:
            return await JSONResponse({"detail": "invalid content length"}, status_code=400)(scope, receive, send)
        if declared > self.limit:
            return await self.reject(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limit:
                return await self.reject(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)

    async def reject(self, scope, receive, send):
        await JSONResponse({"detail": f"Upload too large: the request budget is {self.limit} bytes. Use a smaller image or omit the optional reference."},
                           status_code=413)(scope, receive, send)
