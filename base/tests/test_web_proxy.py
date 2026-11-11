"""登录网页的转发：请求经代理到达上游、上游挂了连接就断。HTTP 走 http.client，
代理和上游都真起（线程），不 mock。"""
import http.client
import os
import socket
import threading
import unittest
from unittest import mock

from wonton_agent import web_proxy


class Upstream(threading.Thread):
    """每次连接回一个固定的响应，记下收到的字节。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.received = b""
        self.connections = 0

    def port(self) -> int:
        return self.listener.getsockname()[1]

    def run(self):
        while True:
            conn, _ = self.listener.accept()
            self.connections += 1
            try:
                data = conn.recv(64 * 1024)
                self.received += data
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            except OSError:
                pass
            finally:
                conn.close()


class WebProxyTests(unittest.TestCase):
    def setUp(self):
        self.upstream = Upstream()
        self.upstream.start()
        self.addCleanup(self.upstream.listener.close)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(self.listener.close)
        env = {
            "WEB_PORT": str(self.listener.getsockname()[1]),
            "WEB_UPSTREAM_HOST": "127.0.0.1",
            "WEB_UPSTREAM_PORT": str(self.upstream.port()),
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        threading.Thread(target=web_proxy.serve, args=(self.listener,), daemon=True).start()

    def get(self, path: str) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.listener.getsockname()[1], timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode()
        conn.close()
        return response.status, body

    def test_forwards_to_upstream(self):
        status, body = self.get("/api/logins")
        self.assertEqual((status, body), (200, "ok"))
        self.assertIn(b"GET /api/logins", self.upstream.received)

    def test_two_requests(self):
        self.assertEqual(self.get("/a")[1], "ok")
        self.assertEqual(self.get("/b")[1], "ok")
        self.assertEqual(self.upstream.connections, 2)

    def test_upstream_down_closes(self):
        # 上游没起来：连接立即被挂断（健康检查的上游探测靠这个变红）。
        os.environ["WEB_UPSTREAM_PORT"] = "1"
        conn = http.client.HTTPConnection("127.0.0.1", self.listener.getsockname()[1], timeout=5)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            self.fail(f"上游挂了还拿到响应：{response.status}")
        except (http.client.RemoteDisconnected, ConnectionError, OSError):
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
