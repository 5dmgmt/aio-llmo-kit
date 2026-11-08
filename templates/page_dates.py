#!/usr/bin/env python3
"""頁ごとの datePublished / dateModified を git の履歴から出して、次の 2 つを書く。

  1. OUT_TS（lib/page-dates.ts） … 頁ごとの日付。生成物なので手で編集しない
  2. LLMS（public/llms.txt）     … 末尾の「最終更新 YYYY-MM-DD」の 1 行だけ。ファイルが無ければ触らない

置き場: 自分のサイトのリポの scripts/page_dates.py（このファイルをコピーして、下の「設定」だけ直す）。
対象: Next.js の App Router（APP_DIR の下の page.tsx）。頁は自動で見つける。

日付の決め方（頁のファイルの git の履歴だけを見る）:
  - published ＝ そのファイルの最初の commit の日
  - modified  ＝ そのファイルの最新の commit の日
  - 未 commit の変更がある頁は、modified を今日にする。commit したあとも同じ日付になるので、
    commit の前後どちらでも --check が通る（履歴が無い untracked の頁は published も今日）
  - llms.txt の日付は、対象の頁の modified の最大
  - 日付は TZ_OFFSET_HOURS の時刻帯で切る（既定は日本時間）

頁の見つけ方:
  - (group) のフォルダは URL に出ないので外す
  - [slug]・[...slug] の動的な頁、@slot（並列ルート）、_private のフォルダ、(.)xxx（割り込みルート）は対象にしない
    （動的な頁の日付は、その内容が持つ公開日・更新日を使う。無ければ日付を作らない）
  - EXCLUDE に書いた頁（noindex の頁など）は対象にしない

使い方（リポジトリのどこからでも）:
  python3 scripts/page_dates.py           生成する
  python3 scripts/page_dates.py --check   生成物が最新かを見る（違えば終了コード 1）

日付は手で書かない。頁を直して commit したら、この script を回して生成物も commit する。
文面を頁のファイルの外（別の content ファイルなど）に置いていると、文面だけを直したときに日付が動かない。
そのときは、頁のファイルにも触れる commit にするか、日付の決め方を自分のサイトに合わせて直す。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------- 設定（自分のサイトに合わせて直す所）

APP_DIR = "app"  # 頁の置き場。src/app を使っているなら "src/app"
OUT_TS = "lib/page-dates.ts"  # 生成物の置き場
LLMS = "public/llms.txt"  # 無ければ触らない
LLMS_LABEL = "最終更新 "  # llms.txt の末尾の行の頭。見える「最終更新」の語と合わせる
TZ_OFFSET_HOURS = 9  # 日付を切る時刻帯（9 ＝ 日本時間）
PAGE_FILE_NAMES = ("page.tsx",)  # 頁のファイル名

# 日付も sitemap も持たせない頁（noindex の頁・ログイン後の頁など）。URL の path で書く。
# 末尾が /* の物は、その下すべて（"/admin/*" は /admin と /admin/ の下）
EXCLUDE: tuple[str, ...] = (
    # "/login",
    # "/admin/*",
)

# ----------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))
SKIP_DIRS = {"node_modules", ".next", ".git"}


class Page(NamedTuple):
    path: str  # 公開 URL の path
    file: str  # ROOT からの頁ファイル（posix の相対パス）


def route_to_url(parts: tuple[str, ...]) -> str | None:
    """app/ からの頁のフォルダ（page.tsx があるフォルダ）を URL の path にする。対象にしない頁は None。"""
    segments = []
    for part in parts:
        if part.startswith("(") and part.endswith(")") and not part.startswith("(."):
            continue  # route group は URL に出ない
        if part.startswith(("(.", "@", "_")) or "[" in part:
            return None  # 割り込みルート・並列ルート・private フォルダ・動的な頁
        segments.append(part)
    return "/" + "/".join(segments)


def is_excluded(path: str, exclude: tuple[str, ...]) -> bool:
    for pattern in exclude:
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if path == prefix or path.startswith(prefix + "/"):
                return True
        elif path == pattern:
            return True
    return False


def discover_pages(root: Path, app_dir: str, exclude: tuple[str, ...]) -> tuple[list[Page], list[str]]:
    """(対象の頁, 動的などで対象にしなかった頁のファイル)。"""
    base = root / app_dir
    if not base.is_dir():
        sys.exit(
            f"頁の置き場がありません: {app_dir}\n"
            "このファイルは自分のサイトのリポの scripts/ に置いて使います。src/app を使っているなら APP_DIR を直してください。"
        )
    pages: list[Page] = []
    skipped: list[str] = []
    for current, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in files:
            if name not in PAGE_FILE_NAMES:
                continue
            folder = Path(current).relative_to(base)
            relative_file = (Path(app_dir) / folder / name).as_posix()
            url = route_to_url(folder.parts)
            if url is None:
                skipped.append(relative_file)
            elif not is_excluded(url, exclude):
                pages.append(Page(url, relative_file))
    seen: dict[str, str] = {}
    for page in pages:
        if page.path in seen:
            sys.exit(f"同じ URL の頁が 2 つあります: {page.path}（{seen[page.path]} と {page.file}）")
        seen[page.path] = page.file
    pages.sort(key=lambda page: (page.path != "/", page.path))
    return pages, sorted(skipped)


def unused_excludes(pages_all: list[str], exclude: tuple[str, ...]) -> list[str]:
    """EXCLUDE に書いてあるのに、該当する頁が無い項目（書き間違いに気づくため）。"""
    return [p for p in exclude if not any(is_excluded(path, (p,)) for path in pages_all)]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} が失敗しました: {result.stderr.strip()}")
    return result.stdout


def ensure_full_history(root: Path) -> None:
    # 浅い clone（CI やホスティングのビルド環境に多い）では履歴が足りず、published が実際より新しく出てしまう
    if git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        sys.exit("浅い clone なので日付が正しく出ません。`git fetch --unshallow` してから回してください")


def to_day(iso: str) -> str:
    # UTC の commit は git が末尾を Z で返す。Python 3.10 以前の fromisoformat は Z を読めないので +00:00 にする
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    return datetime.fromisoformat(iso).astimezone(TZ).date().isoformat()


def page_dates(root: Path, file: str, today: str) -> tuple[str, str]:
    """(published, modified)。commit した日（committer date）で数える。"""
    if not (root / file).is_file():
        sys.exit(f"頁のファイルがありません: {file}")
    # git log は新しい順。--follow で名前の変更をまたぐ
    log = [line for line in git(root, "log", "--follow", "--format=%cI", "--", file).splitlines() if line]
    dirty = bool(git(root, "status", "--porcelain", "--", file).strip())
    if not log:
        if not dirty:
            sys.exit(f"git の履歴がありません: {file}（git add して commit してください）")
        return today, today
    published = to_day(log[-1])
    modified = today if dirty else to_day(log[0])
    return published, modified


def render_ts(rows: list[tuple[Page, str, str]]) -> str:
    lines = [
        "// 生成物。手で編集しない。",
        "// scripts/page_dates.py が、各頁のファイル（app/<頁>/page.tsx）の git の履歴から作る。",
        "// 頁を直して commit したら `python3 scripts/page_dates.py` を回して、この生成物も commit する。`--check` で最新かを見られる。",
        "// published ＝ 最初の commit の日・modified ＝ 最新の commit の日（YYYY-MM-DD）。",
        "",
        "export const PAGE_DATES = {",
    ]
    for page, published, modified in rows:
        lines.append(f"  {json.dumps(page.path)}: {{ published: {json.dumps(published)}, modified: {json.dumps(modified)} }},")
    lines += [
        "} as const;",
        "",
        "export type PagePath = keyof typeof PAGE_DATES;",
        "",
        "// sitemap・llms.txt に載せる静的な頁（PAGE_DATES の並びと同じ）",
        "export const PAGE_PATHS = [",
    ]
    lines += [f"  {json.dumps(page.path)}," for page, _, _ in rows]
    lines += ["] as const satisfies readonly PagePath[];", ""]
    return "\n".join(lines)


def render_llms(current: str, latest: str, label: str = LLMS_LABEL) -> str:
    lines = current.rstrip().split("\n")
    stamp = f"{label}{latest}"
    if lines and lines[-1].startswith(label):
        lines[-1] = stamp
    else:
        lines += ["", stamp]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="生成物が最新かを見る（違えば終了コード 1）")
    args = parser.parse_args(argv)

    ensure_full_history(ROOT)
    pages, skipped = discover_pages(ROOT, APP_DIR, EXCLUDE)
    if not pages:
        sys.exit(f"{APP_DIR} に対象の頁（{' / '.join(PAGE_FILE_NAMES)}）がありません")
    everything = discover_pages(ROOT, APP_DIR, ())[0]
    for pattern in unused_excludes([p.path for p in everything], EXCLUDE):
        print(f"注意: EXCLUDE の {pattern} に当たる頁がありません", file=sys.stderr)

    today = datetime.now(TZ).date().isoformat()
    rows = [(page, *page_dates(ROOT, page.file, today)) for page in pages]
    latest = max(modified for _, _, modified in rows)

    targets = [(ROOT / OUT_TS, render_ts(rows))]
    llms_path = ROOT / LLMS
    if llms_path.is_file():
        targets.append((llms_path, render_llms(llms_path.read_text(encoding="utf-8"), latest)))

    if args.check:
        stale = [path for path, wanted in targets if not path.is_file() or path.read_text(encoding="utf-8") != wanted]
        for path in stale:
            print(f"古い: {path.relative_to(ROOT)}（python3 scripts/page_dates.py で作り直す）", file=sys.stderr)
        if stale:
            return 1
        print(f"OK: {len(rows)} 頁・最終更新 {latest}")
        return 0

    for path, wanted in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted, encoding="utf-8")
        print(f"書いた: {path.relative_to(ROOT)}")
    for page, published, modified in rows:
        print(f"  {page.path:20} published {published}  modified {modified}")
    for file in skipped:
        print(f"  対象外（動的などの頁）: {file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
