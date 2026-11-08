# 点検表（14 項目）

自分のサイトが、AI 検索（Google の AI Overview・AI モード、ChatGPT、Perplexity、Gemini など）に正しく読まれる土台になっているかを見る表です。`bin/audit.py` の結果と、手で読んで判断する項目を並べています。

## 使い方

1. `python3 -I bin/audit.py https://自分のサイト` を回し、表の「確かめ方」の列に当たる所を読みます。
2. 項目ごとに **PASS**（満たしている）・**WARN**（直したほうがよい）・**確認**（手で見る必要がある、またはまだ見ていない）を付けます。
3. 付けた結果を、自分のサイトのリポの記録（たとえば `docs/aio/YYYY-MM.md`）に貼ります。直す物は、技術の直し（[spec.md](spec.md)）と文の直し（Claude Code が起案し、オーナーが決める）に分けます。

「根拠」の列の見方は次のとおりです。

- **一次**: 各社の公式文書に書かれていること（出どころは [sources.md](sources.md)）。
- **判断**: このキットの目安です。各社が定めた基準ではありません。サイトの性質に合わせて変えてかまいません。
- **二次**: 他者の解説が根拠です。一次資料では確かめられていません。

| # | 見る所 | 目安 | 確かめ方 | 根拠 |
|---|---|---|---|---|
| 1 | 前提 | 索引に入り、スニペット付きで表示できる頁であること。`noindex`・`nosnippet`・`max-snippet:0` を使わない。Search Console の「Search generative AI」が「含める」になっている。AI 機能から外したい頁があるときだけ、Search Console の設定で外す | audit.py の `robots:` の WARN／Search Console（手） | 一次（Google） |
| 2 | 一次情報 | 頁に、自分の経験・数字・事例・判断が入っている。他所の要約だけの頁や、生成 AI で量産できる内容は弱い。Google の解説では、ほかの提案より効くとされています | 読んで判断（手） | 一次（Google） |
| 3 | 冒頭の 1 文 | 頁の冒頭が「問い→答え」で、1 文で言い切れている（そのまま引ける長さ） | 読んで判断（手） | 判断 |
| 4 | 問いの形の節 | 人が聞く問い（「〜とは」「〜の違い」「〜の選び方」）に、見出し＋2〜3 文＋必要なら表で答えている | audit.py の `h2?` 列 | 判断 |
| 5 | 表 | 比べる物が 2 つ以上あるとき、表がある | audit.py の `table` 列 | 判断 |
| 6 | エンティティ | 運営の名前・サイト名・人物・商品の表記が、頁・構造化データ・公式のリンクで一致している。JSON-LD に Organization（name・url・logo・sameAs）・WebSite・WebPage があり、必要に応じて Person や Product を足す。表示している文字と一致させ、サイトに載っていない事実を足さない。構造化データは必須ではない（Google が述べている）。名前の一貫とリッチリザルトのために入れる | audit.py の JSON-LD 列 | 判断（構造化データが必須でないのは一次） |
| 7 | 日付 | 全頁に `datePublished`／`dateModified`（WebPage）と、見える「最終更新」がある。日付は手で書かず、git の履歴から生成する | audit.py の dates 列と「日付なし」の WARN | 判断（Google は AI 機能の要件として挙げていない） |
| 8 | 出どころ | 数字や引用に、出典と時点が添えてある | 読んで判断（手） | 判断 |
| 9 | 基本の SEO | title 30〜40 字・description 70〜120 字（日本語の目安）、h1 は 1 つ、OG 画像、canonical、sitemap（頁ごとの lastmod）、robots。全デバイスで崩れず、速く、重複が無い | audit.py の title／desc／h1／can／og 列と sitemap の行 | 一次（基本の SEO）／判断（字数） |
| 10 | AI の巡回 bot | 方針を決めて robots.txt に書く。**既定は全部許可**。学習だけ断るなら下の表の「学習」の bot を Disallow する（検索には残る）。検索の bot は止めない | audit.py の最後の robots.txt の欄 | 一次（各社の公式文書） |
| 11 | llms.txt | Google 検索は使わないと Google が述べている。置くなら他の AI 向けの任意の備えで、優先度は低い。頁の一覧・用語・連絡先・最終更新を書き、頁の文を変えたら同じ commit で直す | audit.py の llms.txt の行 | 一次（Google が使わないこと）／判断 |
| 12 | FAQ | FAQPage の構造化データを入れるなら、頁に見えている Q&A と一致させる。答えは最初の 1 文で結論を言う。FAQPage のリッチリザルトの表示は縮小・終了したとの情報があるが、一次資料では確かめていない。Google の最新の文書で確かめる | 読んで判断（手） | 二次（表示の縮小）／判断 |
| 13 | 計測 | Search Console の Generative AI performance report（表示回数・頁／国／日付／デバイス）、AI からの流入（referrer）、固定の問いでの引かれ方を、月 1 回記録する場所がある。Discover は別のレポート。名称や提供範囲は変わることがあるので、画面で確かめる | [monthly.md](monthly.md) | 一次（レポートの存在）／判断（運用） |
| 14 | Bing | Bing Webmaster Tools に登録し、sitemap を出す。ChatGPT の検索や Copilot が Bing の索引を使うとされるが、一次資料では確かめていない。IndexNow（更新を知らせる仕組み）は任意 | Bing Webmaster Tools（手） | 二次／一次（IndexNow） |

## 項目 10: AI の巡回 bot の分け方

巡回 bot は、**学習用**と**検索用**が別です。検索の回答に出したいなら、検索用の bot を止めません。

| 区分 | bot | 止めたときに起きること（各社の説明の要点） |
|---|---|---|
| 学習 | GPTBot（OpenAI）、ClaudeBot（Anthropic）、Google-Extended（Google）、Applebot-Extended（Apple）、CCBot（Common Crawl） | 学習データに使われなくなる。検索の回答には影響しない。Applebot-Extended は巡回せず、学習に使うかどうかの意思表示だけを受け取る。Google-Extended は学習の可否で、AI 機能に載るかどうかは Search Console の設定で決める |
| 検索 | OAI-SearchBot（OpenAI）、Claude-SearchBot（Anthropic）、PerplexityBot（Perplexity） | その検索サービスの回答に出なくなる場合がある（OpenAI は OAI-SearchBot を断ると ChatGPT の検索結果に出なくなると説明している） |
| 利用者の操作 | ChatGPT-User、Claude-User、Perplexity-User | 利用者が頁を開くよう頼んだときの取得。robots.txt に従わないことがあると説明されている |

robots.txt では、bot 名を書いた group を作ると、その bot には `User-agent: *` の group が適用されません。`*` に書いた `Disallow: /api/` などは、bot 名つきの group には書き足します。反映には時間がかかることがあります。

## 直す順の目安

1. **前提の抜け**: noindex、駐車中の頁、応答しない頁。ここが抜けていると、ほかを直しても引かれる前提が整いません。
2. **土台が無いサイト**: robots.txt・sitemap・JSON-LD。
3. **日付と lastmod**: git の履歴からの生成と、見える「最終更新」。
4. **文の直し**: 一次情報、冒頭の 1 文、問いの形の節、数字の出どころ。時間がかかるので最後にまとめて進めます。
