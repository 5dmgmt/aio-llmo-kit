# Changelog

## 0.1.0 - 2026-11-08

- `bin/audit.py`: サイトの HTML・robots.txt・sitemap を読む実測を追加しました（標準ライブラリだけ・ネットワークに出るのは取得部分だけ）。
  - 頁ごとに、title・description の字数、h1・h2 の数、問いの形の見出し、表、本文の字数、canonical、OG 画像、JSON-LD の `@type`（`@graph` の中も）と日付の有無を出します。
  - meta robots／googlebot と `X-Robots-Tag` から、`noindex`・`nosnippet`・`max-snippet:0`・`none` を見つけて WARN にします。
  - robots.txt を学習／検索／利用者の操作の bot ごとに読み、許可・一部不可・全部不可を出します。検索の bot が全部不可のときは WARN を添えます。
  - llms.txt の有無と字数、sitemap（sitemap index を含む）の頁数と lastmod を出します。
  - `--max-pages`・`--delay` で、回す頁数とリクエストの間隔を調整できます。
- `templates/`（Next.js App Router 用）:
  - `page_dates.py`: `page.tsx` を自動で見つけ、git の履歴から頁ごとの日付を作って `lib/page-dates.ts` と llms.txt の末尾を更新します。`--check` に対応しています。
  - `site.ts`・`jsonld.ts`・`JsonLd.tsx`・`UpdatedLine.tsx`: Organization・WebSite・WebPage の JSON-LD と、見える「最終更新」。
  - `jsonld.test.ts`: `node --test` の検査（日付・JSON-LD・sitemap・noindex の混入・llms.txt の末尾）。
  - `llms.txt.example`: llms.txt の例。
- `docs/`: 点検表（14 項目）、実装の仕様、一次資料と要点、月次の計測の表。
- `PROMPT.md`: Claude Code に貼る導入プロンプト（導入・月次の計測・更新）。
- `tests/`: `python3 -I -m unittest discover -s tests` で、audit.py と page_dates.py を検査します。
