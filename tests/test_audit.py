"""bin/audit.py の検査。ネットワークには出ない（urlopen を差し替えて、出ようとしたら失敗させる）。

実行: python3 -I -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("audit", ROOT / "bin" / "audit.py")
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit"] = audit
_spec.loader.exec_module(audit)


class NoNetwork(unittest.TestCase):
    """どのテストも、実際の通信が起きたら失敗する。"""

    def setUp(self) -> None:
        patcher = mock.patch("urllib.request.urlopen", side_effect=AssertionError("ネットワークに出てはいけません"))
        patcher.start()
        self.addCleanup(patcher.stop)


class RobotsTxt(NoNetwork):
    SAMPLE = """\
# コメントは読み飛ばす
User-agent: *
Disallow: /api/
Allow: /

User-agent: GPTBot
User-agent: CCBot # 2 つの bot で 1 つの group
Disallow: /

User-agent: Applebot-Extended
Disallow: /private/
Disallow: /tmp/

User-agent: OAI-SearchBot
Disallow:

Sitemap: https://example.com/sitemap.xml
"""

    def test_groups_are_split_by_user_agent_runs(self) -> None:
        groups = audit.robots_groups(self.SAMPLE)
        self.assertEqual(len(groups), 4)
        self.assertEqual(groups[0][0], {"*"})
        self.assertEqual(groups[0][1], ["/api/"])
        self.assertEqual(groups[0][2], ["/"])
        self.assertEqual(groups[1][0], {"gptbot", "ccbot"})
        self.assertEqual(groups[1][1], ["/"])
        self.assertEqual(groups[2][1], ["/private/", "/tmp/"])

    def test_bot_status(self) -> None:
        groups = audit.robots_groups(self.SAMPLE)
        self.assertEqual(audit.bot_status("GPTBot", groups), "全部不可")
        self.assertEqual(audit.bot_status("ccbot", groups), "全部不可")  # 大文字小文字は問わない
        self.assertEqual(audit.bot_status("Applebot-Extended", groups), "一部不可（/private/ /tmp/）")
        self.assertEqual(audit.bot_status("OAI-SearchBot", groups), "許可")  # Disallow が空＝許可
        # 名指しが無い bot は「*」と同じ扱い（表示は「*と同じ」・実際に効く規則は「*」の一部不可）
        self.assertEqual(audit.bot_status("PerplexityBot", groups), "*と同じ")
        self.assertEqual(audit.rules_status(audit.effective_rules("PerplexityBot", groups)), "一部不可（/api/）")

    def test_no_robots_txt_entries_means_allowed(self) -> None:
        groups = audit.robots_groups("")
        self.assertEqual(groups, [])
        self.assertEqual(audit.bot_status("GPTBot", groups), "*と同じ")
        self.assertEqual(audit.rules_status(audit.effective_rules("GPTBot", groups)), "記述なし（許可）")

    def test_disallow_all_with_exception(self) -> None:
        groups = audit.robots_groups("User-agent: ClaudeBot\nDisallow: /\nAllow: /public/\n")
        self.assertEqual(audit.bot_status("ClaudeBot", groups), "全部不可（例外の許可: /public/）")

    def test_allow_root_beats_disallow_root(self) -> None:
        groups = audit.robots_groups("User-agent: ClaudeBot\nDisallow: /\nAllow: /\n")
        self.assertEqual(audit.bot_status("ClaudeBot", groups), "許可")

    def test_same_bot_in_two_groups_is_merged(self) -> None:
        groups = audit.robots_groups("User-agent: GPTBot\nDisallow: /a/\n\nUser-agent: *\nDisallow: /x/\n\nUser-agent: gptbot\nDisallow: /b/\n")
        self.assertEqual(audit.bot_status("GPTBot", groups), "一部不可（/a/ /b/）")

    def test_report_warns_when_search_bots_are_blocked(self) -> None:
        text = "User-agent: *\nDisallow: /\n"
        lines = audit.robots_report(text)
        self.assertTrue(lines[0].endswith("*＝全部不可"))
        self.assertTrue(any(line.startswith("  WARN:") and "OAI-SearchBot" in line for line in lines))

    def test_report_does_not_warn_when_only_training_bots_are_blocked(self) -> None:
        text = "User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n"
        lines = audit.robots_report(text)
        self.assertFalse(any("WARN" in line for line in lines))
        self.assertIn("GPTBot=全部不可", lines[1])
        self.assertIn("OAI-SearchBot=*と同じ", lines[2])

    def test_bot_lists_are_disjoint(self) -> None:
        self.assertEqual(len(audit.AI_BOTS), len(set(audit.AI_BOTS)))
        self.assertIn("OAI-SearchBot", audit.SEARCH_BOTS)
        self.assertIn("GPTBot", audit.TRAIN_BOTS)
        self.assertIn("ChatGPT-User", audit.USER_BOTS)


class RobotsDirectives(NoNetwork):
    def test_meta_robots_in_any_attribute_order_and_quote(self) -> None:
        pages = [
            '<meta name="robots" content="noindex, nofollow">',
            '<meta content="noindex" name="robots">',
            "<meta name='robots' content='NOINDEX'>",
            '<META NAME="Robots" CONTENT="noindex">',
            '<meta name="robots" content="a > b, noindex">',
        ]
        for page in pages:
            self.assertEqual(audit.robots_directives(page, {}), ["noindex"], page)

    def test_googlebot_meta_and_snippet_directives(self) -> None:
        page = '<meta name="googlebot" content="nosnippet, max-snippet: 0"><meta name="robots" content="none">'
        self.assertEqual(audit.robots_directives(page, {}), ["max-snippet:0", "none", "nosnippet"])

    def test_harmless_directives_are_not_reported(self) -> None:
        page = '<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">'
        self.assertEqual(audit.robots_directives(page, {}), [])
        self.assertEqual(audit.robots_directives("<html></html>", {}), [])

    def test_other_meta_names_are_ignored(self) -> None:
        page = '<meta name="bingbot" content="noindex"><meta name="description" content="noindex">'
        self.assertEqual(audit.robots_directives(page, {}), [])

    def test_x_robots_tag(self) -> None:
        self.assertEqual(audit.robots_directives("", {"x-robots-tag": "noindex, nofollow"}), ["noindex"])
        self.assertEqual(audit.robots_directives("", {"x-robots-tag": "max-snippet: 0"}), ["max-snippet:0"])
        self.assertEqual(audit.robots_directives("", {"x-robots-tag": "nofollow"}), [])

    def test_x_robots_tag_with_bot_prefix(self) -> None:
        # Google 向け（googlebot）は数える。別の bot 向けは数えない
        self.assertEqual(audit.robots_directives("", {"x-robots-tag": "googlebot: nosnippet"}), ["nosnippet"])
        self.assertEqual(audit.robots_directives("", {"x-robots-tag": "bingbot: noindex, nosnippet"}), [])

    def test_x_robots_tag_given_twice(self) -> None:
        # 同じ名前のヘッダーが 2 つ来たときは改行でつながっている。宛名は行ごとに数え直す
        headers = {"x-robots-tag": "bingbot: noindex\nnosnippet"}
        self.assertEqual(audit.robots_directives("", headers), ["nosnippet"])


class JsonLd(NoNetwork):
    @staticmethod
    def block(body: str, attrs: str = "") -> str:
        return f'<script type="application/ld+json"{attrs}>{body}</script>'

    def test_single_object(self) -> None:
        page = self.block('{"@context":"https://schema.org","@type":"WebPage","datePublished":"2026-01-01"}')
        self.assertEqual(audit.jsonld_summary(page), (["WebPage"], ["datePublished"]))

    def test_graph_is_flattened(self) -> None:
        page = self.block(
            '{"@context":"https://schema.org","@graph":['
            '{"@type":"Organization","name":"A"},'
            '{"@type":"WebPage","datePublished":"2026-01-01","dateModified":"2026-01-02"},'
            '"not a node"]}'
        )
        types, dates = audit.jsonld_summary(page)
        self.assertEqual(types, ["Organization", "WebPage"])
        self.assertEqual(dates, ["dateModified", "datePublished"])

    def test_top_level_list_and_type_list(self) -> None:
        page = self.block('[{"@type":["Organization","LocalBusiness"]},{"@type":"WebSite"}]')
        self.assertEqual(audit.jsonld_summary(page)[0], ["Organization", "LocalBusiness", "WebSite"])

    def test_several_blocks_and_attributes_after_type(self) -> None:
        page = self.block('{"@type":"Organization"}', ' nonce="abc"') + self.block('{"@type":"WebSite"}')
        self.assertEqual(audit.jsonld_summary(page)[0], ["Organization", "WebSite"])

    def test_node_with_type_and_graph(self) -> None:
        page = self.block('{"@type":"WebPage","@graph":[{"@type":"Person"}]}')
        self.assertEqual(audit.jsonld_summary(page)[0], ["WebPage", "Person"])

    def test_broken_json_is_reported(self) -> None:
        page = self.block("{not json") + self.block('{"@type":"WebPage"}')
        self.assertEqual(audit.jsonld_summary(page)[0], ["ERR", "WebPage"])

    def test_escaped_angle_bracket_is_readable(self) -> None:
        page = self.block('{"@type":"WebPage","name":"\\u003c/script\\u003e"}')
        self.assertEqual(audit.jsonld_summary(page)[0], ["WebPage"])

    def test_no_jsonld(self) -> None:
        self.assertEqual(audit.jsonld_summary("<html></html>"), ([], []))
        self.assertEqual(audit.jsonld_summary('<script type="text/javascript">var a=1</script>'), ([], []))


class Sitemap(NoNetwork):
    URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.example.com/</loc><lastmod>2026-01-05</lastmod></url>
  <url><loc>https://www.example.com/about</loc><lastmod>2026-02-01</lastmod></url>
  <url><loc>https://www.example.com/blog?page=2</loc></url>
  <url><loc>https://www.example.com/about</loc></url>
  <url><loc>https://www.example.com</loc></url>
</urlset>"""

    INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.example.com/sitemap-1.xml</loc><lastmod>2026-03-01</lastmod></sitemap>
  <sitemap><loc>https://www.example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""

    def test_urlset(self) -> None:
        info = audit.parse_sitemap(self.URLSET)
        self.assertEqual(info["kind"], "urlset")
        self.assertEqual(len(info["locs"]), 5)
        self.assertEqual(max(info["lastmods"]), "2026-02-01")
        self.assertEqual(len(info["lastmods"]), 2)

    def test_paths_ignore_host_and_dedupe(self) -> None:
        info = audit.parse_sitemap(self.URLSET)
        self.assertEqual(audit.paths_from_locs(info["locs"]), ["/", "/about", "/blog?page=2"])

    def test_index(self) -> None:
        info = audit.parse_sitemap(self.INDEX)
        self.assertEqual(info["kind"], "index")
        self.assertEqual(len(info["locs"]), 2)

    def test_load_sitemap_reads_children_of_an_index(self) -> None:
        pages = {
            "http://localhost:3000/sitemap.xml": self.INDEX,
            "http://localhost:3000/sitemap-1.xml": self.URLSET,
            "http://localhost:3000/sitemap-2.xml": self.URLSET.replace("blog?page=2", "news"),
        }
        info = audit.load_sitemap("http://localhost:3000", lambda url: (pages[url], {}))
        self.assertEqual(info["kind"], "index")
        self.assertEqual(info["children"], 2)
        self.assertEqual(len(info["locs"]), 10)

    def test_empty_urlset(self) -> None:
        info = audit.parse_sitemap('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>')
        self.assertEqual(info["locs"], [])
        self.assertEqual(audit.paths_from_locs(info["locs"]), [])


GOOD_PAGE = """<!doctype html><html lang="ja"><head>
<title>コーヒー豆の選び方｜産地と焙煎度の違いを比べる入門ガイドです</title>
<meta name="description" content="コーヒー豆を選ぶときの見方を、産地と焙煎度の違いを表で比べながら説明します。味の好みから選ぶ手順、保存のしかた、買う前に確かめたい点を順に紹介する入門の頁です。">
<link rel="canonical" href="https://example.com/guide">
<meta property="og:image" content="https://example.com/og.png">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","datePublished":"2026-01-01","dateModified":"2026-02-01"}</script>
</head><body><header><h2>メニュー</h2></header>
<main><h1>豆の選び方</h1><h2>産地はどう選ぶ？</h2><p>本文です。</p><h2>焙煎度の違い</h2>
<table><tr><td>a</td></tr></table>
<script>window.__data = "この文字は本文に数えない"</script>
<script type="application/ld+json">{"@type":"Organization"}</script>
</main></body></html>"""


class AnalyzePage(NoNetwork):
    def test_good_page(self) -> None:
        row = audit.analyze_page(GOOD_PAGE, {}, "/guide")
        self.assertEqual(row["path"], "/guide")
        self.assertEqual(row["h1"], 1)
        self.assertEqual(row["h2"], 3)
        self.assertEqual(row["h2q"], 1)
        self.assertEqual(row["table"], 1)
        self.assertTrue(row["canonical"])
        self.assertTrue(row["og"])
        self.assertEqual(row["robots"], [])
        self.assertEqual(row["types"], ["WebPage", "Organization"])
        self.assertEqual(row["dates"], ["dateModified", "datePublished"])
        self.assertEqual(row["title"], len("コーヒー豆の選び方｜産地と焙煎度の違いを比べる入門ガイドです"))
        self.assertEqual(row["desc"], len("コーヒー豆を選ぶときの見方を、産地と焙煎度の違いを表で比べながら説明します。味の好みから選ぶ手順、保存のしかた、買う前に確かめたい点を順に紹介する入門の頁です。"))
        self.assertEqual(audit.page_flags(row), [])

    def test_script_text_in_main_is_not_counted(self) -> None:
        row = audit.analyze_page(GOOD_PAGE, {}, "/")
        self.assertNotIn("この文字", audit.text_of(GOOD_PAGE.split("<main>")[1]))
        self.assertEqual(row["chars"], len(audit.text_of("<h1>豆の選び方</h1><h2>産地はどう選ぶ？</h2><p>本文です。</p><h2>焙煎度の違い</h2>a")))

    def test_flags_for_a_bare_page(self) -> None:
        row = audit.analyze_page("<html><head></head><body><p>x</p></body></html>", {"x-robots-tag": "noindex"}, "/x")
        self.assertEqual(
            audit.page_flags(row),
            ["robots:noindex", "title", "desc", "h1", "canonical", "og", "日付なし"],
        )

    def test_canonical_and_og_need_a_value(self) -> None:
        page = '<link rel="canonical" href=""><meta property="og:image" content="">'
        row = audit.analyze_page(page, {}, "/")
        self.assertFalse(row["canonical"])
        self.assertFalse(row["og"])

    def test_link_rel_with_several_tokens_and_reverse_order(self) -> None:
        page = '<link href="https://example.com/" rel="canonical nofollow"><meta content="https://example.com/a.png" property="og:image">'
        row = audit.analyze_page(page, {}, "/")
        self.assertTrue(row["canonical"])
        self.assertTrue(row["og"])

    def test_description_with_entities(self) -> None:
        row = audit.analyze_page('<meta name="description" content="A &amp; B">', {}, "/")
        self.assertEqual(row["desc"], 5)

    def test_looks_like_html(self) -> None:
        self.assertTrue(audit.looks_like_html("<!DOCTYPE html><html>"))
        self.assertTrue(audit.looks_like_html("\n  <html lang='ja'>"))
        self.assertFalse(audit.looks_like_html("# サイト名\n\n> 説明\n"))


class Entry(NoNetwork):
    def test_no_arguments_prints_usage_and_does_not_touch_the_network(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = audit.main([])
        self.assertEqual(code, 0)
        self.assertIn("usage:", out.getvalue())
        self.assertIn("audit.py", out.getvalue())

    def test_site_must_be_an_origin(self) -> None:
        self.assertEqual(audit.normalize_site("https://example.com/"), "https://example.com")
        self.assertEqual(audit.normalize_site("http://localhost:3000"), "http://localhost:3000")
        for bad in ("example.com", "ftp://example.com", "https://example.com/blog", "file:///etc/hosts"):
            with self.assertRaises(ValueError, msg=bad):
                audit.normalize_site(bad)

    def test_fetch_refuses_other_schemes_before_connecting(self) -> None:
        with self.assertRaises(ValueError):
            audit.fetch("file:///etc/hosts")

    def test_paths_must_start_with_a_slash(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            audit.main(["https://example.com", "about"])
        self.assertEqual(caught.exception.code, 2)

    def test_version_matches_the_version_file(self) -> None:
        self.assertEqual(audit.__version__, (ROOT / "VERSION").read_text(encoding="utf-8").strip())

    def test_full_run_with_canned_responses(self) -> None:
        responses = {
            "/sitemap.xml": (Sitemap.URLSET, {}),
            "/": (GOOD_PAGE, {}),
            "/about": ("<html><head></head><body></body></html>", {"x-robots-tag": "noindex"}),
            "/robots.txt": ("User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n", {}),
            "/llms.txt": ("<!doctype html><html></html>", {}),
        }

        def fake_fetch(url: str, timeout: int = 20) -> tuple[str, dict]:
            path = url[len("http://localhost:3000"):]
            if path in responses:
                return responses[path]
            raise OSError("HTTP Error 404: Not Found")

        out = io.StringIO()
        with mock.patch.object(audit, "fetch", fake_fetch), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = audit.main(["http://localhost:3000", "--delay", "0", "--max-pages", "2"])
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("PASS", text)  # /（GOOD_PAGE は日付つきなので全項目を満たす）
        self.assertIn("WARN robots:noindex", text)  # /about
        self.assertIn("GPTBot=全部不可", text)
        self.assertIn("/llms.txt: なし（HTML が返っています）", text)
        self.assertIn("/llms-full.txt: なし", text)
        self.assertIn("sitemap.xml: 5 頁", text)


if __name__ == "__main__":
    unittest.main()
