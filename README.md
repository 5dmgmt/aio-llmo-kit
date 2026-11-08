# aio-llmo-kit

自分のサイトが、AI 検索（Google の AI Overview・AI モード、ChatGPT、Perplexity、Gemini など）に正しく読まれる状態になっているかを測り、直し、月に 1 回見直すための道具です。Claude Code と一緒に使うことを想定しています。

- **実測**: `bin/audit.py`。サイトの HTML・robots.txt・sitemap を読んで、頁ごとの状態と AI の巡回 bot の設定を一覧にします（Python の標準ライブラリだけで動きます）。
- **点検表**: 14 項目。何を見るか、どこで確かめるか、根拠が公式文書なのか目安なのかを分けて書いています。
- **雛形（Next.js）**: 頁ごとの日付を git の履歴から生成する script、JSON-LD の部品、見える「最終更新」、テスト、llms.txt の例。
- **月次の計測**: Search Console のレポートと、固定の問いでの見え方を記録する表。
- **導入プロンプト**: Claude Code に貼る文面（`PROMPT.md`）。実測から直しまでの段取りと、守ってほしいことを書いています。

AI に引かれることを保証する道具ではありません。何ができて何ができないかは、「[できないこと](#できないこと)」に書きました。Google・OpenAI・Anthropic・Perplexity・Apple の公式の物ではありません。

## 先に知っておきたいこと（Google の公式見解の要点）

Google が公開している説明の要点です（原文の URL は [docs/sources.md](docs/sources.md)）。このキットは、この内容に沿って作っています。

- AI Overview と AI モードに載るために、特別な追加の条件や AI 向けの印（markup）は求められていません。**索引に入り、スニペット付きで検索結果に出せる頁**であることが前提です。`noindex`・`nosnippet`・`max-snippet:0` を使っていないか、Search Console の「Search generative AI」が「含める」になっているかを確かめます。
- 効くとされているのは、書き手自身の経験や専門から出た**一次情報**、読者に伝わる構成（段落・節・見出し）、画像・動画の基本、そして検索の基本（クロールできる・速い・全デバイスで使える・重複が少ない）です。AI のための裏技は挙げられていません。
- llms.txt のような AI 向けの機械可読ファイル、文を細切れにすること、AI 向けの書き直しは、Google 検索では不要という趣旨の説明です。検索のバリエーションごとに頁を量産するのはスパムにあたります。
- AI の巡回 bot は、**学習用と検索用が別**です（OpenAI・Anthropic・Perplexity・Apple の説明）。検索の回答に出したいなら、検索用の bot は止めません。

つまり、土台は「ふだんの頁の質」と「検索の基本」です。このキットが入れる日付・構造化データ・llms.txt は、それを機械にも読み取りやすくするための補助で、AI Overview に載る条件ではありません。

## 入れ方

必要なもの: `python3`（3.9 以降で確かめています。標準ライブラリだけを使い、`pip install` は要りません）、`git`。雛形のテストを動かすには Node.js も使います。

1. キットを、**自分のサイトのリポの外**に clone します（リポの中に置くと、型検査がキットの雛形まで拾って失敗します）。

   ```bash
   git clone https://github.com/5dmgmt/aio-llmo-kit ~/Tools/aio-llmo-kit
   ```

   git を使わないときは、GitHub の画面から zip をダウンロードして展開してもかまいません。

2. 自分のサイトのリポで Claude Code を開き、[PROMPT.md](PROMPT.md) の枠の中の文を貼り付けます。文中の `<キットのパス>` は、clone した場所（上の例なら `~/Tools/aio-llmo-kit`）に書き換えてください。実測・直し・月次の計測までを一緒に進めます。

3. 実測だけを先に試すなら、ターミナルで次を実行します。

   ```bash
   python3 -I ~/Tools/aio-llmo-kit/bin/audit.py https://自分のサイト
   ```

## 流れ

1. **実測**: `bin/audit.py` を自分のサイトに回して、結果を読みます。
2. **点検表**: [docs/checklist.md](docs/checklist.md) の 14 項目に PASS／WARN／確認を付けます。
3. **技術の直し**: [docs/spec.md](docs/spec.md) の仕様どおりに、頁ごとの日付・JSON-LD・見える最終更新・sitemap・llms.txt・テストを入れます（Claude Code が実装します）。
4. **文の直し**: 冒頭の 1 文、問いの形の節、一次情報、数字の出どころ。Claude Code が案を出し、**オーナーが決めます**。
5. **bot の方針**: robots.txt で AI の巡回 bot をどう扱うかを決めます（既定は全部許可）。
6. **月次の計測**: [docs/monthly.md](docs/monthly.md) の表を、月に 1 回埋めます。

## 実測 `bin/audit.py`

```bash
python3 -I bin/audit.py https://example.com                  # sitemap.xml の頁を順に見る
python3 -I bin/audit.py https://example.com / /about         # 頁を指定する
python3 -I bin/audit.py http://localhost:3000 / /about       # 手元で起動したサイトを見る
python3 -I bin/audit.py                                      # 使い方を表示する
```

オプション: `--max-pages N`（sitemap から回す頁の上限・既定 50）、`--delay 秒`（リクエストの間隔・既定 0.5）。本番のサイトには自動でアクセスすることになるので、**サイトごとに順番に、1 回ずつ**回してください。短い間隔で繰り返すと、ホスティング側の防御に bot として止められることがあります。

頁ごとに次の列を出します。

| 列 | 内容 |
|---|---|
| title／desc | `<title>`・meta description の字数（日本語の頁の目安は 30〜40 字・70〜120 字。Google が定めた基準ではありません） |
| h1／h2／h2? | h1 の数、h2 の数、そのうち問いの形（「？」を含む）の数 |
| table | 表の数 |
| chars | `<main>` の本文の字数（script・style の中身は数えません） |
| can／og | canonical・OG 画像があるか（1 ならある） |
| JSON-LD / dates | JSON-LD の `@type`（`@graph` の中も）と、`datePublished`・`dateModified` のうち見つかった物 |
| 末尾の判定 | `PASS`、または `WARN` と理由（`robots:noindex`・`title`・`desc`・`h1`・`canonical`・`og`・`日付なし`） |

`robots:` の WARN は、meta robots／googlebot と `X-Robots-Tag` に、`noindex`・`nosnippet`・`max-snippet:0`・`none` があるときに出ます。AI 機能に載る前提を外す指定です。

最後に、robots.txt を **学習／検索／利用者の操作**の bot ごとに「許可・一部不可・全部不可」で表示し、llms.txt の有無と字数、sitemap の頁数と lastmod を出します。検索の bot が全部不可のときは WARN を添えます。

見るのは、取得した HTML までです。JavaScript で後から描く内容と、Search Console の設定・レポートは見えません。Search Console は手で確かめます。

## Next.js に入れる物 `templates/`

自分のサイトのリポ（Next.js の App Router）に写して使う雛形です。各ファイルの先頭のコメントに、置き場と「直す所」を書いています。細かい仕様は [docs/spec.md](docs/spec.md) です。

| 雛形 | 置き場（自分のリポ） | 内容 |
|---|---|---|
| `page_dates.py` | `scripts/page_dates.py` | `app/**/page.tsx` を見つけ、git の履歴から頁ごとの `published`／`modified` を出して `lib/page-dates.ts` を生成し、llms.txt の末尾の最終更新を更新する。`--check` で最新かを確認できる |
| `site.ts` | `lib/site.ts` | サイト名・URL・運営の名前・ロゴ・公式リンクをまとめる |
| `jsonld.ts` | `lib/jsonld.ts` | Organization・WebSite・WebPage の JSON-LD を組み立てる。`serializeJsonLd` が script タグの中の文字列を安全に作る |
| `JsonLd.tsx` | `app/components/JsonLd.tsx` | JSON-LD を script タグで出す部品 |
| `UpdatedLine.tsx` | `app/components/UpdatedLine.tsx` | 見える「最終更新 YYYY-MM-DD」の 1 行 |
| `jsonld.test.ts` | `lib/jsonld.test.ts` | `node --test` の検査。全頁の日付・型・往復・sitemap と日付の一致・noindex の混入など |
| `llms.txt.example` | `public/llms.txt` | llms.txt の例（任意） |

日付は、頁のファイル（`page.tsx`）の git の履歴から作ります。手で書きません。履歴が浅い clone では正しく出ないので、手元で生成して、生成物を commit します。

## 月次の計測

[docs/monthly.md](docs/monthly.md) を `docs/aio/YYYY-MM.md` にコピーして使います。Search Console の Generative AI performance report の表示回数、固定の問い（6 つ前後）での見え方、AI サービスからの流入、問い合わせでの言及を記録します。AI の回答は毎回変わるので、数か月ぶんを並べて傾向を見ます。

## できないこと

- **AI の回答に引かれることは保証できません。** 回答は毎回変わり、各社が何をどう取り込むかは、公開されていない部分が多くあります。
- **順位を上げる道具ではありません。** 検索の順位や表示回数を上げることを約束しません。
- **Google が AI 機能のために求めている特別な markup やファイルはありません。** このキットの JSON-LD は頁の内容を機械に分かりやすくする補助で、AI Overview に載る条件ではありません。
- **llms.txt は Google 検索では使われないと Google が述べています。** 置くのは他の AI サービス向けの任意の備えで、効果は確かめられていません。
- **文面の質は、道具では作れません。** 一次情報や冒頭の 1 文は、サイトの持ち主の経験から出る物です。Claude Code の案は、持ち主が決めます。
- 実測は、取得した HTML を読む範囲です。JavaScript で後から描く内容、画像の中の文字、Search Console の設定とレポートは見えません。
- 雛形は Next.js の App Router 向けです。`app/[lang]/` のように全頁が動的な構成は、頁を自動で見つけられません（audit.py は CMS など、どの作りのサイトにも使えます）。
- 日付は、頁のファイルの git の履歴から作ります。文面を別のファイルに置いているサイトでは、文面だけを直しても日付が動きません。
- 各社の bot の名前や挙動は変わることがあります。点検表の項目 10 を使う前に、[docs/sources.md](docs/sources.md) の一次資料で最新の状態を確かめてください。
- 動作を確かめているのは macOS（Python 3.9 と 3.15）です。

## 新しい版に更新する

clone したフォルダで、次を実行します。

```bash
cd ~/Tools/aio-llmo-kit
git pull
cat VERSION
```

[CHANGELOG.md](CHANGELOG.md) で、増えた機能を確かめてください。すでに自分のサイトに写した雛形は、自動では更新されません。新しい版の雛形との差を見て、取り込みたい所だけを写します。Claude Code に頼むときは、[PROMPT.md](PROMPT.md) の「新しい版が出たとき」の枠を使えます。

## ファイル一覧

```
aio-llmo-kit/
  README.md        この文書
  PROMPT.md        Claude Code に貼る導入プロンプト
  LICENSE          MIT
  CHANGELOG.md     変更履歴
  VERSION          版
  bin/audit.py     実測
  templates/       Next.js に写す雛形
  docs/
    checklist.md   点検表（14 項目）
    spec.md        実装の仕様
    sources.md     一次資料と要点
    monthly.md     月次の計測の表
  tests/           audit.py と page_dates.py の検査（ネットワークに出ません）
```

## テスト

```bash
python3 -I -m unittest discover -s tests
```

`bin/audit.py` の robots.txt の読み取り・bot の判定・robots 指示（meta と X-Robots-Tag）・JSON-LD の読み取り・sitemap の読み取りと、`templates/page_dates.py` の頁の見つけ方・日付の決め方を検査します。ネットワークには出ません。

## License

MIT License です。詳細は [LICENSE](LICENSE) をご覧ください。
