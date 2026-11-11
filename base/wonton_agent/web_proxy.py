"""登录网页的转发：compose 里的 web 服务把请求转给默认 Bot 的 agent 容器。

webui 不能指向 Bot 服务（旧核心仍按这条判），而登录页在 agent 容器里（每个 Bot 一份），
所以模板架一个全插件一份的转发：只搬运字节，不解 HTTP；上游地址默认 agent-default:8080
（核心给默认 Bot 的服务别名），网页只发相对路径的 fetch，Host 不用改。
"""
import os
import socket
import threading

LISTEN_HOST = "0.0.0.0"


def upstream() -> tuple[str, int]:
    host = os.environ.get("WEB_UPSTREAM_HOST") or "agent-default"
    port = int(os.environ.get("WEB_UPSTREAM_PORT") or "8080")
    return host, port


def pump(source: socket.socket, target: socket.socket) -> None:
    try:
        while True:
            data = source.recv(512 * 1024)
            if not data:
                break
            target.sendall(data)
    except OSError:
        pass
    finally:
        # 关写半边，让对端读到 EOF；再关整个 socket 收掉读方向。
        try:
            target.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        source.close()
        target.close()


def handle(client: socket.socket) -> None:
    host, port = upstream()
    try:
        server = socket.create_connection((host, port), timeout=10)
    except OSError:
        # 上游连不上：立即挂断，网页显示不出内容，健康检查（上游探测）会变红。
        client.close()
        return
    client.settimeout(None)
    threads = [
        threading.Thread(target=pump, args=(client, server), daemon=True),
        threading.Thread(target=pump, args=(server, client), daemon=True),
    ]
    for thread in threads:
        thread.start()


def serve(listener: socket.socket) -> None:
    host, upstream_port = upstream()
    print(f"web-proxy :{listener.getsockname()[1]} → {host}:{upstream_port}", flush=True)
    while True:
        client, _ = listener.accept()
        handle(client)


def main() -> None:
    port = int(os.environ.get("WEB_PORT") or "8080")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((LISTEN_HOST, port))
    listener.listen(64)
    serve(listener)
