"""gen 的单元测试：claude-code 手写 compose 的语义等价、生成结果确定性、--check 的过期判定。

跑法（仓库根）：python3 -m unittest discover -s gen/tests -v
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        # 桥镜像的版本跟着 template/ 升级，不属生成逻辑；摘要钉住由 test_bridge_digest_from_template 管。
        for services in (got, expected):
            services["bridge"]["image"] = "<bridge image>"
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


def pin_like_publish(text: str, name: str, version: str, digest: str) -> str:
    """按 publish.sh pin_image 的规则逐行把自身镜像行改写成 <仓库>:<版本>@<摘要>，模拟发布写回。"""
    line = re.compile(rf"^(\s*image:\s*(?:&\S+\s+)?)(\S+/{name})(?::[^@\s]+)?"
                      rf"(?:@sha256:[0-9a-f]{{64}})?(\s*(?:#.*)?)$")
    return "\n".join(f"{m.group(1)}{m.group(2)}:{version}@{digest}{m.group(3)}"
                     if (m := line.match(text_line)) else text_line
                     for text_line in text.split("\n"))


class PinTest(unittest.TestCase):
    """发布写回的摘要：同版本保留（发版后 --check 仍过），版本一换旧摘要不残留。"""

    DIGEST_A = "sha256:" + "a1" * 32
    DIGEST_B = "sha256:" + "b2" * 32

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agent_dir = Path(self.tmp.name) / "mini"
        self.agent_dir.mkdir()
        self.write_agent("version: 0.2.0")
        self.fresh = gen.render_compose(self.agent_dir, gen.load_agent(self.agent_dir))
        self.write_compose(self.fresh)

    def write_agent(self, version_line: str):
        text = (FIXTURES / "claude-code" / "agent.yaml").read_text(encoding="utf-8")
        # fixture 自带 webui: true：compose 里有两处自身镜像（agent 和 web），和 dsh 一样。
        text = re.sub(r"^version: .*$", version_line, text, count=1, flags=re.M)
        (self.agent_dir / "agent.yaml").write_text(text, encoding="utf-8")

    def write_compose(self, text: str):
        (self.agent_dir / gen.COMPOSE_NAME).write_text(text, encoding="utf-8")

    def self_image_lines(self, text: str) -> list[str]:
        return [line for line in text.split("\n") if re.match(r"^\s*image:\s*\S+/mini:", line)]

    def test_publish_writeback_still_fresh(self):
        self.write_compose(pin_like_publish(self.fresh, "mini", "0.2.0", self.DIGEST_A))
        agent = gen.load_agent(self.agent_dir)
        output = gen.render_compose(self.agent_dir, agent)
        self.assertEqual(output, (self.agent_dir / gen.COMPOSE_NAME).read_text(encoding="utf-8"))
        # agent 和 web 两处都钉上。
        self.assertEqual(output.count("@" + self.DIGEST_A), 2)
        with mock.patch("sys.argv", ["gen.py", "--check", str(self.agent_dir)]):
            gen.main()

    def test_unrelated_edit_keeps_digest(self):
        self.write_compose(pin_like_publish(self.fresh, "mini", "0.2.0", self.DIGEST_A))
        # 发版后改标题这类无关字段，重新生成不丢摘要。
        text = (self.agent_dir / "agent.yaml").read_text(encoding="utf-8")
        (self.agent_dir / "agent.yaml").write_text(
            text.replace("zh: Claude Code", "zh: Claude Code 改名", 1), encoding="utf-8")
        output = gen.render_compose(self.agent_dir, gen.load_agent(self.agent_dir))
        self.assertEqual(output.count("@" + self.DIGEST_A), 2)

    def test_version_bump_drops_stale_digest(self):
        self.write_compose(pin_like_publish(self.fresh, "mini", "0.2.0", self.DIGEST_A))
        self.write_agent("version: 0.3.0")
        output = gen.render_compose(self.agent_dir, gen.load_agent(self.agent_dir))
        lines = self.self_image_lines(output)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertTrue(line.strip().endswith("/mini:0.3.0"), line)
            self.assertNotIn("@sha256:", line)
        # 重新写盘后再生成也稳定，--check 过。
        self.write_compose(output)
        with mock.patch("sys.argv", ["gen.py", "--check", str(self.agent_dir)]):
            gen.main()

    def test_conflicting_digests_rejected(self):
        text = pin_like_publish(self.fresh, "mini", "0.2.0", self.DIGEST_A)
        self.write_compose(text.replace(self.DIGEST_A, self.DIGEST_B, 1))
        with self.assertRaises(SystemExit):
            gen.render_compose(self.agent_dir, gen.load_agent(self.agent_dir))


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
