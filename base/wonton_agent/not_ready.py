"""网关未就绪时只提供 ACP 初始化和登录发现，不启动会请求模型的上游程序。"""
import asyncio
import json
import socket


async def respond(client: socket.socket, methods: list[dict] | None, reason: str) -> None:
    reader, writer = await asyncio.open_unix_connection(sock=client, limit=2 ** 24)
    try:
        while line := await reader.readline():
            try:
                request = json.loads(line)
            except ValueError:
                continue
            if not isinstance(request, dict) or "id" not in request:
                continue
            reply = {"jsonrpc": "2.0", "id": request["id"]}
            if request.get("method") == "initialize":
                reply["result"] = {"protocolVersion": 1, "agentCapabilities": {},
                                   "authMethods": methods or []}
            else:
                reply["error"] = {"code": -32000, "message": reason,
                                  "data": {"category": "not_ready"}}
            writer.write((json.dumps(reply, ensure_ascii=False) + "\n").encode())
            await writer.drain()
    except (OSError, ValueError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()
