"""网关缺失时不改路由，官方模式只由显式成功选择决定。"""
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

import support

from wonton_agent import config as paths, gateway as agent, model_source


def write_hook(directory: Path, body: str) -> Path:
    hook = directory / "gateway-hook"
    hook.write_text("#!/usr/bin/env python3\nimport sys\n" + body)
    hook.chmod(0o755)
    return hook


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ab-gateway-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.record = self.tmp / "record"
        patch = mock.patch.object(paths, "AGENT_HOME", self.tmp / "home")
        patch.start()
        self.addCleanup(patch.stop)

    def run_gateway(self, config: dict, env: dict) -> str:
        # 不用 clear=True：清掉 PATH 会让钩子的 #!/usr/bin/env python3 找不到解释器；
        # 缺省变量显式给空串，和核心注入空值的语义一致。
        values = {"WONTON_MODEL_BASE_URL": "", "WONTON_MODEL_API_KEY": "", "WONTON_MODEL_DEFAULT": ""}
        values.update(env)
        with mock.patch.dict(os.environ, values):
            agent.apply_gateway(config)
        return self.record.read_text()

    def test_all_variables_present_applies(self):
        hook = write_hook(self.tmp, f"from pathlib import Path\n"
                                    f"Path({str(self.record)!r}).write_text(sys.argv[1])\n")
        action = self.run_gateway({"gateway": {"hook": str(hook)}}, {
            "WONTON_MODEL_BASE_URL": "http://gateway.example.internal/v1",
            "WONTON_MODEL_API_KEY": "secret",
            "WONTON_MODEL_DEFAULT": "group/default",
        })
        self.assertEqual(action, "apply")

    def test_incomplete_gateway_never_calls_clear(self):
        hook = write_hook(self.tmp, f"from pathlib import Path\n"
                                    f"Path({str(self.record)!r}).write_text(sys.argv[1])\n")
        ready = dict.fromkeys(agent.GATEWAY_ENV, "present")
        for name in agent.GATEWAY_ENV:
            for empty in ("", "   "):
                with self.subTest(name=name, empty=empty):
                    with self.assertRaises(model_source.ModelNotReady):
                        self.run_gateway({"gateway": {"hook": str(hook)}}, {**ready, name: empty})
                    self.assertFalse(self.record.exists())

    def test_explicit_official_choice_is_independent_of_gateway(self):
        method = {"id": "subscription", "model_source": "official"}
        model_source.select(method)
        hook = write_hook(self.tmp, f"from pathlib import Path\n"
                                    f"Path({str(self.record)!r}).write_text(sys.argv[1])\n")
        config = {"gateway": {"hook": str(hook)}, "login": [method]}
        for env in ({}, dict.fromkeys(agent.GATEWAY_ENV, "present")):
            with self.subTest(env=bool(env)):
                self.assertEqual(self.run_gateway(config, env), "clear")

    def test_extra_protocol_variable_is_required(self):
        hook = write_hook(self.tmp, "sys.exit(0)\n")
        config = {"gateway": {"hook": str(hook), "required_env": ["AB_TEST_PROTOCOL_URL"]}}
        with self.assertRaises(model_source.ModelNotReady):
            self.run_gateway(config, dict.fromkeys(agent.GATEWAY_ENV, "present"))

    def test_hook_receives_variable_values(self):
        # 钩子从环境里拿网关配置，底座原样传下去。
        hook = write_hook(self.tmp, "import os\n"
                                    f"from pathlib import Path\n"
                                    f"Path({str(self.record)!r}).write_text(os.environ['WONTON_MODEL_API_KEY'])\n")
        value = self.run_gateway({"gateway": {"hook": str(hook)}}, {
            "WONTON_MODEL_BASE_URL": "http://gateway.example.internal/v1",
            "WONTON_MODEL_API_KEY": "secret-value",
            "WONTON_MODEL_DEFAULT": "group/default",
        })
        self.assertEqual(value, "secret-value")

    def test_hook_failure_raises(self):
        hook = write_hook(self.tmp, "import sys\nsys.exit(3)\n")
        with self.assertRaises(RuntimeError) as caught:
            self.run_gateway({"gateway": {"hook": str(hook)}}, {
                "WONTON_MODEL_BASE_URL": "x", "WONTON_MODEL_API_KEY": "y", "WONTON_MODEL_DEFAULT": "z",
            })
        self.assertIn("退出码 3", str(caught.exception))

    def test_missing_hook_rejected(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                self.run_gateway({"gateway": {"hook": str(self.tmp / "no-such-hook")}}, {})
        self.assertIn("不可执行", stderr.getvalue())

    def test_non_executable_hook_rejected(self):
        hook = self.tmp / "not-executable"
        hook.write_text("#!/usr/bin/env python3\n")
        hook.chmod(stat.S_IRUSR | stat.S_IWUSR)
        stderr = StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                self.run_gateway({"gateway": {"hook": str(hook)}}, {})
        self.assertIn("不可执行", stderr.getvalue())

    def test_no_gateway_section_is_noop(self):
        agent.apply_gateway({})  # 不该抛错，也不该起进程


class AcpEnvTests(unittest.TestCase):
    """网关映射不能因变量缺失而变成继承的官方配置。"""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ab-env-")
        self.addCleanup(temporary.cleanup)
        patch = mock.patch.object(paths, "AGENT_HOME", Path(temporary.name))
        patch.start()
        self.addCleanup(patch.stop)

    def run_env(self, config: dict, env: dict) -> dict:
        # 缺省变量显式给空串，和核心注入空值的语义一致（照 GatewayTests.run_gateway）。
        values = {"WONTON_MODEL_BASE_URL": "", "WONTON_MODEL_API_KEY": "", "WONTON_MODEL_DEFAULT": ""}
        values.update(env)
        with mock.patch.dict(os.environ, values):
            return agent.acp_env(config)

    def test_gateway_ready_maps_variables(self):
        env = self.run_env(
            {"gateway": {"hook": "/x", "env": {
                "ANTHROPIC_AUTH_TOKEN": "WONTON_MODEL_API_KEY",
                "ANTHROPIC_BASE_URL": "WONTON_MODEL_BASE_URL"}}},
            {"WONTON_MODEL_BASE_URL": "http://gateway.example.internal/v1",
             "WONTON_MODEL_API_KEY": "secret", "WONTON_MODEL_DEFAULT": "group/default"})
        self.assertEqual(env, {"ANTHROPIC_AUTH_TOKEN": "secret",
                               "ANTHROPIC_BASE_URL": "http://gateway.example.internal/v1"})

    def test_no_gateway_section_maps_nothing(self):
        env = self.run_env({"acp": {"command": ["x"]}}, {
            "WONTON_MODEL_BASE_URL": "x", "WONTON_MODEL_API_KEY": "y", "WONTON_MODEL_DEFAULT": "z"})
        self.assertEqual(env, {})

    def test_gateway_without_env_table_maps_nothing(self):
        env = self.run_env({"gateway": {"hook": "/x"}}, {
            "WONTON_MODEL_BASE_URL": "x", "WONTON_MODEL_API_KEY": "y", "WONTON_MODEL_DEFAULT": "z"})
        self.assertEqual(env, {})

    def test_incomplete_gateway_variables_reject_model_start(self):
        with self.assertRaises(model_source.ModelNotReady):
            self.run_env(
                {"gateway": {"hook": "/x", "env": {"ANTHROPIC_AUTH_TOKEN": "WONTON_MODEL_API_KEY"}}},
                {"WONTON_MODEL_BASE_URL": "x", "WONTON_MODEL_API_KEY": "", "WONTON_MODEL_DEFAULT": "z"})

    def test_missing_mapped_source_rejects_model_start(self):
        with self.assertRaises(model_source.ModelNotReady):
            self.run_env(
                {"gateway": {"hook": "/x", "env": {"ANTHROPIC_AUTH_TOKEN": "AB_NO_SUCH_SOURCE"}}},
                {"WONTON_MODEL_BASE_URL": "x", "WONTON_MODEL_API_KEY": "y",
                 "WONTON_MODEL_DEFAULT": "z"})

    def test_official_choice_does_not_receive_gateway_credentials(self):
        method = {"id": "subscription", "model_source": "official"}
        model_source.select(method)
        env = self.run_env(
            {"gateway": {"hook": "/x", "env": {"API_KEY": "WONTON_MODEL_API_KEY"}}, "login": [method]},
            dict.fromkeys(agent.GATEWAY_ENV, "present"))
        self.assertEqual(env, {})


if __name__ == "__main__":
    unittest.main()
