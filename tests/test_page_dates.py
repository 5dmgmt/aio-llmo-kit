"""templates/page_dates.py の検査。一時フォルダに小さな git リポを作って回す（ネットワークには出ない）。

実行: python3 -I -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("page_dates", ROOT / "templates" / "page_dates.py")
assert _spec is not None and _spec.loader is not None
page_dates = importlib.util.module_from_spec(_spec)
sys.modules["page_dates"] = page_dates
_spec.loader.exec_module(page_dates)

HAS_GIT = shutil.which("git") is not None


class RouteToUrl(unittest.TestCase):
    def test_static_routes(self) -> None:
        self.assertEqual(page_dates.route_to_url(()), "/")
        self.assertEqual(page_dates.route_to_url(("about",)), "/about")
        self.assertEqual(page_dates.route_to_url(("guide", "intro")), "/guide/intro")

    def test_route_group_is_removed(self) -> None:
        self.assertEqual(page_dates.route_to_url(("(marketing)", "pricing")), "/pricing")
        self.assertEqual(page_dates.route_to_url(("(marketing)",)), "/")

    def test_dynamic_and_special_routes_are_not_covered(self) -> None:
        for parts in (
            ("blog", "[slug]"),
            ("docs", "[...path]"),
            ("shop", "[[...path]]"),
            ("@modal", "login"),
            ("_components", "x"),
            ("feed", "(.)photo"),
            ("feed", "(..)photo"),
        ):
            self.assertIsNone(page_dates.route_to_url(parts), parts)

    def test_exclude_patterns(self) -> None:
        exclude = ("/login", "/admin/*")
        self.assertTrue(page_dates.is_excluded("/login", exclude))
        self.assertFalse(page_dates.is_excluded("/login/help", exclude))
        self.assertTrue(page_dates.is_excluded("/admin", exclude))
        self.assertTrue(page_dates.is_excluded("/admin/users", exclude))
        self.assertFalse(page_dates.is_excluded("/administrator", exclude))
        self.assertFalse(page_dates.is_excluded("/", exclude))


class Rendering(unittest.TestCase):
    def test_render_ts(self) -> None:
        rows = [
            (page_dates.Page("/", "app/page.tsx"), "2026-01-05", "2026-02-01"),
            (page_dates.Page("/about", "app/about/page.tsx"), "2026-01-06", "2026-01-06"),
        ]
        text = page_dates.render_ts(rows)
        self.assertIn("手で編集しない", text)
        self.assertIn('"/": { published: "2026-01-05", modified: "2026-02-01" },', text)
        self.assertIn('"/about": { published: "2026-01-06", modified: "2026-01-06" },', text)
        self.assertIn("export type PagePath = keyof typeof PAGE_DATES;", text)
        self.assertIn('export const PAGE_PATHS = [\n  "/",\n  "/about",\n] as const', text)
        self.assertTrue(text.endswith("\n"))

    def test_render_llms_replaces_or_appends_the_last_line(self) -> None:
        self.assertEqual(page_dates.render_llms("# a\n\n最終更新 2026-01-01\n", "2026-03-04"), "# a\n\n最終更新 2026-03-04\n")
        self.assertEqual(page_dates.render_llms("# a\n", "2026-03-04"), "# a\n\n最終更新 2026-03-04\n")

    def test_the_example_llms_file_takes_the_stamp(self) -> None:
        example = (ROOT / "templates" / "llms.txt.example").read_text(encoding="utf-8")
        out = page_dates.render_llms(example, "2026-03-04")
        self.assertTrue(out.endswith("\n最終更新 2026-03-04\n"))
        self.assertEqual(out.count("最終更新"), 1)

    def test_to_day_uses_the_configured_zone(self) -> None:
        # 日本時間（+9）に直す。UTC の 23:30 は翌日になる
        self.assertEqual(page_dates.to_day("2026-01-05T23:30:00+00:00"), "2026-01-06")
        self.assertEqual(page_dates.to_day("2026-01-05T08:00:00+09:00"), "2026-01-05")
        # git は UTC を末尾 Z で返すことがある（Python 3.10 以前でも読めること）
        self.assertEqual(page_dates.to_day("2026-02-10T23:30:00Z"), "2026-02-11")


@unittest.skipUnless(HAS_GIT, "git が無いので飛ばします")
class WithGit(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self.git("init", "-q")

    def git(self, *args: str, when: str | None = None) -> None:
        env = dict(self.env)
        if when:
            env["GIT_AUTHOR_DATE"] = when
            env["GIT_COMMITTER_DATE"] = when
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.com",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull, *args],
            check=True, capture_output=True, env=env,
        )

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str, when: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, when=when)

    def dates(self, file: str, today: str = "2026-06-01") -> tuple[str, str]:
        return page_dates.page_dates(self.root, file, today)

    def test_discover_pages(self) -> None:
        for relative in (
            "app/page.tsx",
            "app/about/page.tsx",
            "app/(marketing)/pricing/page.tsx",
            "app/blog/[slug]/page.tsx",
            "app/admin/page.tsx",
            "app/admin/users/page.tsx",
            "app/login/page.tsx",
            "app/@modal/page.tsx",
            "app/_private/page.tsx",
            "app/components/Header.tsx",
            "app/api/route.ts",
            "app/node_modules/x/page.tsx",
        ):
            self.write(relative, "export default function P() { return null; }\n")
        pages, skipped = page_dates.discover_pages(self.root, "app", ("/login", "/admin/*"))
        self.assertEqual([p.path for p in pages], ["/", "/about", "/pricing"])
        self.assertEqual(pages[2].file, "app/(marketing)/pricing/page.tsx")
        self.assertEqual(skipped, ["app/@modal/page.tsx", "app/_private/page.tsx", "app/blog/[slug]/page.tsx"])
        everything, _ = page_dates.discover_pages(self.root, "app", ())
        self.assertEqual(page_dates.unused_excludes([p.path for p in everything], ("/login", "/admin/*", "/typo")), ["/typo"])

    def test_missing_app_dir_stops_with_a_hint(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            page_dates.discover_pages(self.root, "app", ())
        self.assertIn("scripts/", str(caught.exception))

    def test_same_url_twice_stops(self) -> None:
        self.write("app/(a)/team/page.tsx", "x\n")
        self.write("app/(b)/team/page.tsx", "x\n")
        with self.assertRaises(SystemExit):
            page_dates.discover_pages(self.root, "app", ())

    def test_published_and_modified_come_from_the_history(self) -> None:
        self.write("app/about/page.tsx", "v1\n")
        self.commit("add", "2026-01-05T10:00:00+09:00")
        self.write("app/about/page.tsx", "v2\n")
        self.commit("edit", "2026-02-10T23:30:00+00:00")  # UTC の夜 → 日本時間では翌日
        self.assertEqual(self.dates("app/about/page.tsx"), ("2026-01-05", "2026-02-11"))

    def test_uncommitted_change_makes_modified_today(self) -> None:
        self.write("app/about/page.tsx", "v1\n")
        self.commit("add", "2026-01-05T10:00:00+09:00")
        self.write("app/about/page.tsx", "v2\n")
        self.assertEqual(self.dates("app/about/page.tsx", "2026-06-01"), ("2026-01-05", "2026-06-01"))

    def test_untracked_page_is_today_for_both(self) -> None:
        self.write("app/readme.txt", "x\n")
        self.commit("seed", "2026-01-05T10:00:00+09:00")
        self.write("app/new/page.tsx", "v1\n")
        self.assertEqual(self.dates("app/new/page.tsx", "2026-06-01"), ("2026-06-01", "2026-06-01"))

    def test_page_with_no_history_and_no_change_stops(self) -> None:
        self.write(".gitignore", "app/ignored/\n")
        self.commit("seed", "2026-01-05T10:00:00+09:00")
        self.write("app/ignored/page.tsx", "v1\n")  # 無視されているので untracked にも出ない
        with self.assertRaises(SystemExit):
            self.dates("app/ignored/page.tsx")

    def test_missing_page_file_stops(self) -> None:
        with self.assertRaises(SystemExit):
            page_dates.page_dates(self.root, "app/none/page.tsx", "2026-06-01")


if __name__ == "__main__":
    unittest.main()
