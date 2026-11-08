#!/usr/bin/env python3
"""AI 検索への備えの実測。標準ライブラリだけで動きます。

使い方:
  python3 -I bin/audit.py https://example.com                  sitemap.xml の頁を順に見る
  python3 -I bin/audit.py https://example.com / /about         頁を指定して見る
  python3 -I bin/audit.py http://localhost:3000 / /about       手元で起動したサイトを見る

オプション:
  --max-pages N   sitemap から回す頁の上限（既定 50）
  --delay 秒      リクエストの間隔（既定 0.5）。本番のサイトには間隔を空けて、サイトごとに順番に回します

頁ごとに出す物: title・description の字数、h1・h2 の数、問いの形の見出し、表、本文の字数、
canonical・OG 画像の有無、robots の meta と X-Robots-Tag（noindex・nosnippet・max-snippet:0 は
AI 機能に載る前提を外します）、JSON-LD の @type（@graph の中も）と日付の有無。
最後に robots.txt を AI の bot ごと（学習／検索／利用者の操作）に読み、llms.txt と sitemap を見ます。

見るのは「取得した HTML」までです。JavaScript で後から描く内容、Search Console の設定とレポートは見えません。
title 30〜40 字・description 70〜120 字は、日本語の頁の目安です（Google が定めた基準ではありません）。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

__version__ = "0.1.0"

USER_AGENT = f"Mozilla/5.0 (compatible; aio-llmo-kit-audit/{__version__})"
MAX_BYTES = 5_000_000  # 1 回の取得の上限。巨大なファイルを読み込まないため
MAX_CHILD_SITEMAPS = 5  # sitemap index の子を読む上限

# 巡回 bot は「学習」と「検索」が別です。OpenAI・Anthropic・Perplexity・Apple の公式の説明に基づく分け方
# （出どころは docs/sources.md）。検索に出したいなら、検索の bot は止めません。
TRAIN_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "CCBot"]
SEARCH_BOTS = ["OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"]
USER_BOTS = ["ChatGPT-User", "Claude-User", "Perplexity-User"]  # 利用者の操作。robots.txt を無視することがある
AI_BOTS = TRAIN_BOTS + SEARCH_BOTS + USER_BOTS

# 索引に入ること・スニペット付きで表示されることを止める指示（AI 機能に載る前提を外す）
BAD_ROBOTS = ("noindex", "nosnippet", "max-snippet:0", "none")
# 値を取る指示。「max-snippet: 0」のように「名前: 値」の形なので、bot 名の前置きと区別する
VALUE_DIRECTIVES = ("max-snippet", "max-image-preview", "max-video-preview", "unavailable_after")
# Google の検索に対して効く指示の宛名（それ以外の bot 名の前置きは、別の巡回ロボット向け）
GOOGLE_AGENTS = ("googlebot", "google")


# ---------------------------------------------------------------- 取得（ネットワークに出るのはここだけ）


def fetch(url: str, timeout: int = 20) -> tuple[str, dict]:
    """(本文, ヘッダー) を返す。同じ名前のヘッダーが複数あるときは改行でつなぐ。http／https 以外は拒否する。"""
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError(f"http／https の URL だけ読めます: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310（scheme は上で確認済み）
        raw = response.read(MAX_BYTES)
        headers: dict[str, str] = {}
        for key in response.headers.keys():
            lowered = key.lower()
            if lowered not in headers:
                headers[lowered] = "\n".join(response.headers.get_all(key) or [])
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, "replace"), headers
    except LookupError:
        return raw.decode("utf-8", "replace"), headers


class Fetcher:
    """リクエストの間に待ちを入れる取得役。2 回目以降の前に delay 秒待つ。"""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.count = 0

    def __call__(self, url: str) -> tuple[str, dict]:
        if self.count and self.delay > 0:
            time.sleep(self.delay)
        self.count += 1
        return fetch(url)


# ---------------------------------------------------------------- HTML の読み取り（ネットワークなし）


def text_of(fragment: str) -> str:
    """タグを外した本文。script・style・noscript の中身は数えない。"""
    fragment = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


_ATTR = re.compile(r"""([^\s=/>"']+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")


def html_tags(page: str, name: str) -> list[dict]:
    """<name ...> の属性を辞書にして返す（属性の順・引用符の種類を問わない。値は HTML のエスケープを戻す）。"""
    tags = []
    for match in re.finditer(rf"""<{name}\b((?:[^>"']|"[^"]*"|'[^']*')*)>""", page, re.I):
        attrs = {}
        for key, double, single, bare in _ATTR.findall(match.group(1)):
            value = double or single or bare
            attrs[key.lower()] = html.unescape(value)
        tags.append(attrs)
    return tags


def directives_in(value: str) -> list[str]:
    """robots の指示を 1 つずつに分ける。「max-snippet: 0」は「max-snippet:0」にそろえる。

    X-Robots-Tag は「googlebot: nosnippet」のように bot 名が前に付くことがある。Google 向け以外の宛名は捨てる。
    ヘッダーが複数あるときは改行で区切られている（宛名は行ごとに数え直す）。
    """
    found = []
    for line in value.lower().split("\n"):
        applies = True
        for piece in line.split(","):
            piece = piece.strip()
            prefix = re.match(r"^([a-z][a-z0-9_-]*)\s*:\s*(.*)$", piece)
            if prefix and prefix.group(1) not in VALUE_DIRECTIVES:
                applies = prefix.group(1) in GOOGLE_AGENTS
                piece = prefix.group(2).strip()
            piece = re.sub(r"\s*:\s*", ":", piece)
            if piece and applies:
                found.append(piece)
    return found


def robots_directives(page: str, headers: dict) -> list[str]:
    """meta robots／googlebot と X-Robots-Tag のうち、索引やスニペットを止める指示だけ返す。"""
    found: list[str] = []
    for tag in html_tags(page, "meta"):
        if tag.get("name", "").lower() in ("robots", "googlebot"):
            found += directives_in(tag.get("content", ""))
    found += directives_in(headers.get("x-robots-tag", ""))
    return sorted({d for d in found if d in BAD_ROBOTS})


_JSONLD_BLOCK = re.compile(
    r"""<script\b[^>]*\btype\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script>""", re.S | re.I
)


def jsonld_nodes(data: object) -> list[dict]:
    """JSON-LD の 1 ブロックから、型を持つ node を平らに取り出す（@graph の中も）。"""
    nodes: list[dict] = []
    for item in data if isinstance(data, list) else [data]:
        if not isinstance(item, dict):
            continue
        if "@type" in item:
            nodes.append(item)
        graph = item.get("@graph")
        if isinstance(graph, list):
            nodes += [node for node in graph if isinstance(node, dict)]
    return nodes


def jsonld_summary(page: str) -> tuple[list[str], list[str]]:
    """(@type の一覧, datePublished／dateModified のうち見つかった物)。読めないブロックは型に ERR と出す。"""
    types: list[str] = []
    dates: set[str] = set()
    for block in _JSONLD_BLOCK.findall(page):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            types.append("ERR")
            continue
        for node in jsonld_nodes(data):
            kind = node.get("@type")
            types += [kind] if isinstance(kind, str) else [str(k) for k in kind] if isinstance(kind, list) else ["?"]
            dates.update(key for key in ("datePublished", "dateModified") if key in node)
    return types, sorted(dates)


def analyze_page(page: str, headers: dict, path: str) -> dict:
    """取得済みの HTML とヘッダーから、頁の実測値を作る（ネットワークなし）。"""
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    metas = html_tags(page, "meta")
    description = next((m.get("content", "") for m in metas if m.get("name", "").lower() == "description"), None)
    h1 = re.findall(r"<h1\b[^>]*>(.*?)</h1>", page, re.S | re.I)
    h2 = [text_of(x) for x in re.findall(r"<h2\b[^>]*>(.*?)</h2>", page, re.S | re.I)]
    main = re.search(r"<main\b[^>]*>(.*?)</main>", page, re.S | re.I)
    types, dates = jsonld_summary(page)
    return {
        "path": path,
        "title": len(text_of(title.group(1))) if title else 0,
        "desc": len(description) if description else 0,
        "h1": len(h1),
        "h2": len(h2),
        "h2q": sum(1 for x in h2 if "？" in x or "?" in x),
        "table": len(re.findall(r"<table\b", page, re.I)),
        "chars": len(text_of(main.group(1))) if main else 0,
        "canonical": any(
            "canonical" in tag.get("rel", "").lower().split() and bool(tag.get("href")) for tag in html_tags(page, "link")
        ),
        "og": any(m.get("property", "").lower() == "og:image" and bool(m.get("content")) for m in metas),
        "robots": robots_directives(page, headers),
        "types": types,
        "dates": dates,
    }


def page_flags(row: dict) -> list[str]:
    """WARN の理由。title・description の字数は日本語の頁の目安。"""
    flags = []
    if row["robots"]:
        flags.append("robots:" + "+".join(row["robots"]))  # AI 機能の前提（索引・スニペット可）を外している
    if not 30 <= row["title"] <= 40:
        flags.append("title")
    if not 70 <= row["desc"] <= 120:
        flags.append("desc")
    if row["h1"] != 1:
        flags.append("h1")
    if not row["canonical"]:
        flags.append("canonical")
    if not row["og"]:
        flags.append("og")
    if not row["dates"]:
        flags.append("日付なし")
    return flags


def looks_like_html(text: str) -> bool:
    """llms.txt などの URL に、存在しない頁の代わりの HTML が返っていないかを見る。"""
    head = text.lstrip()[:200].lower()
    return head.startswith("<!doctype") or head.startswith("<html") or "<head" in head


# ---------------------------------------------------------------- robots.txt


def robots_groups(robots: str) -> list[tuple[set, list, list]]:
    """robots.txt を (user-agent の集合, Disallow の一覧, Allow の一覧) の group に分ける。"""
    groups: list[tuple[set, list, list]] = []
    agents: set = set()
    disallow: list = []
    allow: list = []
    fresh = True  # user-agent の行が続いている間は True。規則の行が来ると False
    for raw in robots.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if not fresh:
                groups.append((agents, disallow, allow))
                agents, disallow, allow = set(), [], []
            agents.add(value.lower())
            fresh = True
        elif key in ("disallow", "allow"):
            fresh = False
            (disallow if key == "disallow" else allow).append(value)
    if agents:
        groups.append((agents, disallow, allow))
    return groups


def rules_for(agent: str, groups: list) -> tuple[list, list] | None:
    """その user-agent を名指しした group の規則をまとめる。名指しが無ければ None。"""
    own = [g for g in groups if agent.lower() in g[0]]
    if not own:
        return None
    return [d for g in own for d in g[1]], [a for g in own for a in g[2]]


def rules_status(rules: tuple[list, list] | None) -> str:
    if rules is None:
        return "記述なし（許可）"
    disallow, allow = rules
    if "/" in disallow and "/" not in allow:
        exceptions = [a for a in allow if a]
        return "全部不可" + (f"（例外の許可: {' '.join(exceptions)}）" if exceptions else "")
    paths = [d for d in disallow if d and not (d == "/" and "/" in allow)]
    return f"一部不可（{' '.join(paths)}）" if paths else "許可"


def effective_rules(bot: str, groups: list) -> tuple[list, list] | None:
    """その bot に実際に効く規則。名指しの group があればそれ、無ければ「*」の group（bot 名つきの group は「*」を引き継がない）。"""
    own = rules_for(bot, groups)
    return own if own is not None else rules_for("*", groups)


def bot_status(bot: str, groups: list) -> str:
    """表示用。名指しの group があればその状態、無ければ「*と同じ」。"""
    own = rules_for(bot, groups)
    return rules_status(own) if own is not None else "*と同じ"


def robots_report(robots: str) -> list[str]:
    groups = robots_groups(robots)
    lines = [f"robots.txt（学習と検索は別の bot。検索に出したいなら検索の bot は許可）  *＝{rules_status(rules_for('*', groups))}"]
    for label, bots in (("学習", TRAIN_BOTS), ("検索", SEARCH_BOTS), ("利用者の操作", USER_BOTS)):
        lines.append(f"  {label}: " + "・".join(f"{bot}={bot_status(bot, groups)}" for bot in bots))
    blocked = [bot for bot in SEARCH_BOTS if rules_status(effective_rules(bot, groups)).startswith("全部不可")]
    if blocked:
        lines.append(
            "  WARN: 検索の bot が全部不可です（" + "・".join(blocked) + "）。その検索サービスの回答に出なくなる場合があります。意図した設定か確かめてください"
        )
    return lines


# ---------------------------------------------------------------- sitemap


def parse_sitemap(xml_text: str) -> dict:
    """sitemap.xml を読む。kind は urlset か index（sitemap index）。locs は URL、lastmods は lastmod の値。"""
    root = ET.fromstring(xml_text)
    kind = "index" if root.tag.rsplit("}", 1)[-1] == "sitemapindex" else "urlset"
    locs, lastmods = [], []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "loc" and element.text and element.text.strip():
            locs.append(element.text.strip())
        elif tag == "lastmod" and element.text and element.text.strip():
            lastmods.append(element.text.strip())
    return {"kind": kind, "locs": locs, "lastmods": lastmods}


def paths_from_locs(locs: list[str]) -> list[str]:
    """URL の一覧から path（と query）だけ取る。sitemap は本番のホストで書かれているので、手元のサイトに回すときもホストは問わない。"""
    paths: list[str] = []
    for loc in locs:
        parts = urlsplit(loc)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if path not in paths:
            paths.append(path)
    return paths


def load_sitemap(base: str, get) -> dict:
    """sitemap.xml を取得して読む。index のときは子を MAX_CHILD_SITEMAPS 個まで読んで URL を足す。"""
    info = parse_sitemap(get(base + "/sitemap.xml")[0])
    if info["kind"] == "index":
        locs, lastmods = [], list(info["lastmods"])
        for child in info["locs"][:MAX_CHILD_SITEMAPS]:
            sub = parse_sitemap(get(base + (urlsplit(child).path or "/"))[0])
            locs += sub["locs"]
            lastmods += sub["lastmods"]
        info = {"kind": "index", "locs": locs, "lastmods": lastmods, "children": len(info["locs"])}
    return info


# ---------------------------------------------------------------- 出力


def format_row(row: dict, width: int) -> str:
    flags = page_flags(row)
    verdict = "WARN " + " ".join(flags) if flags else "PASS"
    return (
        f"{row['path']:{width}} {row['title']:5} {row['desc']:5} {row['h1']:3} {row['h2']:3} {row['h2q']:4} "
        f"{row['table']:5} {row['chars']:6} {int(row['canonical']):3} {int(row['og']):3}  "
        f"{row['types']} {row['dates']}  {verdict}"
    )


def header_row(width: int) -> str:
    return (
        f"{'path':{width}} {'title':5} {'desc':5} {'h1':3} {'h2':3} {'h2?':4} {'table':5} {'chars':6} "
        f"{'can':3} {'og':3}  JSON-LD / dates"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("site", help="サイトの origin（例: https://example.com）。パスは付けない")
    parser.add_argument("paths", nargs="*", help="見る頁のパス（例: / /about）。省略すると sitemap.xml の頁")
    parser.add_argument("--max-pages", type=int, default=50, help="sitemap から回す頁の上限（既定 50）")
    parser.add_argument("--delay", type=float, default=0.5, help="リクエストの間隔（秒・既定 0.5）")
    parser.add_argument("--version", action="version", version=f"aio-llmo-kit audit {__version__}")
    return parser


def normalize_site(site: str) -> str:
    parts = urlsplit(site)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"サイトは https://example.com の形で指定してください: {site}")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError(f"サイトは origin だけ指定してください（頁は後ろに並べます）: {site}")
    return f"{parts.scheme}://{parts.netloc}"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    try:
        base = normalize_site(args.site)
    except ValueError as error:
        parser.error(str(error))
    bad = [p for p in args.paths if not p.startswith("/")]
    if bad:
        parser.error(f"頁のパスは / から始めてください: {' '.join(bad)}")

    get = Fetcher(args.delay)
    sitemap: dict | None = None
    sitemap_error = ""
    try:
        sitemap = load_sitemap(base, get)
    except Exception as error:  # noqa: BLE001
        sitemap_error = str(error)

    if args.paths:
        paths = args.paths
    elif sitemap and sitemap["locs"]:
        paths = paths_from_locs(sitemap["locs"])
    else:
        print(f"sitemap.xml が読めないので / だけ見ます: {sitemap_error or '頁がありません'}", file=sys.stderr)
        paths = ["/"]
    if len(paths) > args.max_pages:
        print(f"頁が {len(paths)} 件あるので、先頭の {args.max_pages} 件だけ見ます（--max-pages で変えられます）", file=sys.stderr)
        paths = paths[: args.max_pages]

    width = min(max([14] + [len(p) for p in paths]) + 1, 48)
    print(header_row(width))
    for path in paths:
        try:
            page, headers = get(base + path)
            print(format_row(analyze_page(page, headers, path), width))
        except Exception as error:  # noqa: BLE001
            print(f"{path:{width}} 読めません: {error}")

    print()
    try:
        for line in robots_report(get(base + "/robots.txt")[0]):
            print(line)
    except Exception as error:  # noqa: BLE001
        print(f"robots.txt が読めません: {error}")
    for name in ("/llms.txt", "/llms-full.txt"):
        try:
            text = get(base + name)[0]
            if looks_like_html(text):
                print(f"{name}: なし（HTML が返っています）")
            else:
                print(f"{name}: {len(text)} 字（Google は使わない。他の AI 向け・優先度は低い）")
        except Exception:  # noqa: BLE001
            print(f"{name}: なし")
    if sitemap:
        newest = max(sitemap["lastmods"]) if sitemap["lastmods"] else "なし"
        note = f"・sitemap index の子 {sitemap['children']} 件のうち先頭 {MAX_CHILD_SITEMAPS} 件まで" if sitemap["kind"] == "index" else ""
        print(f"sitemap.xml: {len(sitemap['locs'])} 頁・lastmod {len(sitemap['lastmods'])} 件・最新 {newest}{note}")
    else:
        print(f"sitemap.xml が読めません: {sitemap_error}")
    print("手で見る: Search Console の設定「Search generative AI」が「含める」か／Generative AI performance report の表示回数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
