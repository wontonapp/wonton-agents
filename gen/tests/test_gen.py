"""gen 的单元测试：claude-code 手写 compose 的语义等价、生成结果确定性、--check 的过期判定。

跑法（仓库根）：python3 -m unittest discover -s gen/tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gen  # noqa: E402

ROOT = gen.ROOT
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def parse(text: str) -> dict:
    return yaml.safe_load(text)


class ClaudeCodeTest(unittest.TestCase):
    """完成标准：拿 Claude Code 现有 compose 当样例，生成结果和手写版本语义相同。"""

    def setUp(self):
        self.fixture = FIXTURES / "claude-code"
        self.agent = gen.load_agent(self.fixture)
        self.output = gen.render_compose(self.fixture, self.agent)

    def test_services_match_handwritten(self):
        got = parse(self.output)["services"]
        expected = parse((self.fixture / "compose.expected.yml").read_text(encoding="utf-8"))["services"]
        self.assertEqual(got, expected)

    def test_x_wonton_matches_handwritten(self):
        got = parse(self.output)["x-wonton"]
        expected = parse((self.fixture / "compose.expected.yml").read_text(encoding="utf-8"))["x-wonton"]
        self.assertEqual(got, expected)

    def test_deterministic(self):
        again = gen.render_compose(self.fixture, gen.load_agent(self.fixture))
        self.assertEqual(self.output, again)

    def test_bridge_digest_from_template(self):
        text = parse(self.output)
        bridge_image = text["services"]["bridge"]["image"]
        self.assertIn("@sha256:", bridge_image)
        # 桥的摘要只写在 template/ 一处：gen/ 和 agent.yaml 里都不出现。
        for path in (ROOT / "gen" / "gen.py", self.fixture / "agent.yaml"):
            self.assertNotIn("wonton-acp-bridge", path.read_text(encoding="utf-8"))


class VariantsTest(unittest.TestCase):
    """可选字段的各种组合：话题模式、额外权限、无 webui、无 login、无 tags、env 值类型。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agent_dir = Path(self.tmp.name) / "mini"
        self.agent_dir.mkdir()
        (self.agent_dir / "agent.yaml").write_text("""
id: dev.mini
version: 0.2.0
title: { zh: Mini, en: Mini }
description: { zh: 一句话, en: One line }
about: { zh: "两段\\n\\n正文", en: "Two\\n\\nparagraphs" }
release_notes: { zh: 修复。, en: Fixed. }
license: MIT
notices: [NOTICE, LICENSE]
homepage: https://example.com
acp_mode: read-only
acp_topic_mode: workspace-write
memory: 1G
env:
  PLAIN: hello world
  FLAG: false
  COUNT: 3
  WITH_COLON: "a: b"
permissions: [storage.docs:read]
""", encoding="utf-8")
        self.output = gen.render_compose(self.agent_dir, gen.load_agent(self.agent_dir))
        self.data = parse(self.output)

    def test_topic_mode_reaches_bridge(self):
        env = self.data["services"]["bridge"]["environment"]
        self.assertEqual(env["WONTON_ACP_MODE"], "read-only")
        self.assertEqual(env["WONTON_ACP_TOPIC_MODE"], "workspace-write")

    def test_env_values_stay_strings(self):
        env = self.data["services"]["agent"]["environment"]
        self.assertEqual(env["PLAIN"], "hello world")
        self.assertEqual(env["FLAG"], "false")
        self.assertEqual(env["COUNT"], "3")
        self.assertEqual(env["WITH_COLON"], "a: b")

    def test_without_webui_no_web_service(self):
        self.assertNotIn("web", self.data["services"])
        self.assertNotIn("webui", self.data["x-wonton"])

    def test_without_login_no_login_key(self):
        self.assertNotIn("login", self.data["x-wonton"]["agent"])

    def test_extra_permissions_appended(self):
        self.assertEqual(self.data["x-wonton"]["permissions"],
                         ["matrix.bot", "tools", "models", "network.egress", "storage.docs:read"])

    def test_no_tags_key_when_absent(self):
        self.assertNotIn("tags", self.data["x-wonton"])

    def test_about_block_keeps_paragraphs(self):
        # | 字面量块按 YAML 规则保留末尾换行，和手写 compose 的 about 一致。
        self.assertEqual(self.data["x-wonton"]["about"]["zh"], "两段\n\n正文\n")


class CommittedTest(unittest.TestCase):
    """提交进仓库的生成结果必须是新的：echo 的 agent.yaml 和 compose 对得上。"""

    def test_echo_is_up_to_date(self):
        agent_dir = ROOT / "agents" / "echo"
        agent = gen.load_agent(agent_dir)
        committed = (agent_dir / gen.COMPOSE_NAME).read_text(encoding="utf-8")
        self.assertEqual(gen.render_compose(agent_dir, agent), committed)


class CheckTest(unittest.TestCase):
    """--check 对过期文件返回非零，对最新文件返回零。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        agent_dir = Path(self.tmp.name) / "stale"
        agent_dir.mkdir()
        (agent_dir / "agent.yaml").write_text(
            (FIXTURES / "claude-code" / "agent.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        output = gen.render_compose(agent_dir, gen.load_agent(agent_dir))
        self.fresh = agent_dir / gen.COMPOSE_NAME
        self.fresh.write_text(output, encoding="utf-8")

    def test_fresh_passes(self):
        self.assertEqual(gen.render_compose(self.fresh.parent, gen.load_agent(self.fresh.parent)),
                         self.fresh.read_text(encoding="utf-8"))

    def test_stale_detected(self):
        self.fresh.write_text(self.fresh.read_text(encoding="utf-8").replace("0.1.1", "0.0.9"),
                              encoding="utf-8")
        agent = gen.load_agent(self.fresh.parent)
        self.assertNotEqual(gen.render_compose(self.fresh.parent, agent),
                            self.fresh.read_text(encoding="utf-8"))


class ValidationTest(unittest.TestCase):
    """agent.yaml 写错时报错退出，不猜。"""

    def write_and_load(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        agent_dir = Path(tmp.name) / "bad"
        agent_dir.mkdir()
        (agent_dir / "agent.yaml").write_text(text, encoding="utf-8")
        with self.assertRaises(SystemExit):
            gen.load_agent(agent_dir)

    def test_unknown_field_rejected(self):
        self.write_and_load("id: ai.x\nversion: 0.1.0\ntitle: { en: X }\n"
                            "description: { en: d }\nabout: { en: a }\nrelease_notes: { en: r }\n"
                            "license: MIT\nnotices: [NOTICE]\nhomepage: https://example.com\n"
                            "acp_mode: plan\nmemory: 1G\nmodes: [plan]\n")

    def test_missing_field_rejected(self):
        self.write_and_load("id: ai.x\nversion: 0.1.0\n")

    def test_bad_id_rejected(self):
        self.write_and_load("id: X\nversion: 0.1.0\ntitle: { en: X }\n"
                            "description: { en: d }\nabout: { en: a }\nrelease_notes: { en: r }\n"
                            "license: MIT\nnotices: [NOTICE]\nhomepage: https://example.com\n"
                            "acp_mode: plan\nmemory: 1G\n")

    def test_webui_map_rejected(self):
        self.write_and_load("id: ai.x\nversion: 0.1.0\ntitle: { en: X }\n"
                            "description: { en: d }\nabout: { en: a }\nrelease_notes: { en: r }\n"
                            "license: MIT\nnotices: [NOTICE]\nhomepage: https://example.com\n"
                            "acp_mode: plan\nmemory: 1G\nwebui: {port: 9090}\n")


if __name__ == "__main__":
    unittest.main()
