# 実装の仕様（Next.js App Router）

自分のサイトのリポに「頁ごとの日付・構造化データ（JSON-LD）・見える最終更新・sitemap・llms.txt」を入れるときの仕様です。実装は Claude Code に任せ、この文書を渡します。サイトごとの違いは、最初にそのサイトのリポを読んで見つけ、報告に書きます。

対象は Next.js の App Router（`app/` か `src/app/`）です。ほかのフレームワークや CMS には、この仕様の考え方だけが使えます。`templates/` の雛形は使えません。

## 0. 最初に読むもの（自分のサイトのリポで）

1. `CLAUDE.md`・`AGENTS.md`・`README` など、そのリポの掟。**掟はこの仕様より優先します**。文面・配色・公開・セキュリティの決まりがあれば、それに従います。
2. 頁の置き場（`app/` か `src/app/`）。`page.tsx` の一覧と、動的な頁（`[slug]`）の有無。
3. 既存の SEO まわり。`layout.tsx` の metadata、`robots.ts`／`robots.txt`、`sitemap.ts`／`sitemap.xml`、`public/llms.txt`、JSON-LD（`application/ld+json` を検索）、文面の置き場、テストの走らせ方（`package.json` の `test`）。
4. `tsconfig.json` の `paths`（`@/*` があるか）と、`allowImportingTsExtensions`。
5. 実測の結果（`bin/audit.py` の出力）。

## 1. 守ること

- **文面を新しく書きません。** 足してよい語は、見える「最終更新」の見出し語 1 つだけです（`lib/site.ts` の `updatedLabel`）。説明文・冒頭の文・description・title は変えません。
- **日付を手で書きません。** 頁のファイル（`page.tsx`）の git の履歴から `scripts/page_dates.py` が生成します。動的な頁（記事・お知らせなど）は、その内容が持つ公開日・更新日があればそれを使い、無ければ `datePublished`／`dateModified` を**省きます**（作りません）。
- **事実を足しません。** Organization の `sameAs` は、そのサイトにすでに載っているリンク（フッターの SNS・公式サイト）だけです。住所・電話・資格などは、頁にすでに書かれている物だけを使い、無ければ入れません。
- 既存の JSON-LD（Article・Book・FAQPage・Course・Person など）は**残して**、足りない物を足します。同じ型を二重に出しません。
- 配色・見た目は変えません。「最終更新」の 1 行だけ、小さく・右寄せ・控えめな色で、そのサイトの小さな文字の様式に合わせます。
- 依存を増やしません。`npm install` で新しい部品を入れません。
- 素の JavaScript を書きません（TypeScript で書きます）。
- `git commit`・`git push`・デプロイは、依頼した人が確認してから自分で行います。
- シークレット（`.env*`・API キー）を開かない・表示しない。

## 2. 入れるもの

`templates/` の雛形を、自分のサイトのリポの次の場所へ写して、各ファイルの先頭のコメントにある「直す所」だけを直します。**キット自体は、サイトのリポの外に置いてください**（`tsconfig.json` の `include` がキットの雛形まで拾って、型検査が失敗します）。

| 雛形 | 置き場 | 直す所 |
|---|---|---|
| `page_dates.py` | `scripts/page_dates.py` | `APP_DIR`・`OUT_TS`・`LLMS`・`EXCLUDE` |
| `site.ts` | `lib/site.ts` | `name`・`url`・`companyName`・`logoPath`・`sameAs`・`language`・`updatedLabel` |
| `jsonld.ts` | `lib/jsonld.ts` | 無し（`tsconfig.json` に `allowImportingTsExtensions: true` が要る） |
| `JsonLd.tsx` | `app/components/JsonLd.tsx` | `@/` の別名 |
| `UpdatedLine.tsx` | `app/components/UpdatedLine.tsx` | `@/` の別名・CSS |
| `jsonld.test.ts` | `lib/jsonld.test.ts` | 先頭の「設定」の定数 |
| `llms.txt.example` | `public/llms.txt`（無いときだけ） | 中身を自分のサイトの頁の文に |

### 2-1. `scripts/page_dates.py` と `lib/page-dates.ts`

- `python3 scripts/page_dates.py` で `lib/page-dates.ts`（生成物・手で編集しない）と、`public/llms.txt` の末尾の「最終更新」の行を作ります。
- 頁は `APP_DIR` の下の `page.tsx` から自動で見つけます。`(group)` は URL から外し、`[slug]` などの動的な頁・`@slot`・`_private` は対象にしません。noindex の頁・ログイン後の頁は `EXCLUDE` に書きます。
- 未 commit の頁は `modified` が今日（日本時間）になります。`python3 scripts/page_dates.py --check` が 0 で終わることを受け入れの条件にします。
- 浅い clone（CI やホスティングのビルド環境に多い）では履歴が足りません。生成は手元で行い、生成物を commit します。ビルドの中で回しません。

### 2-2. WebPage の JSON-LD（静的な全頁）

各 `page.tsx` で、metadata に渡す `title`・`description` と同じ値を `webPageJsonLd` に渡します。

```tsx
import type { Metadata } from "next";
import { JsonLd } from "@/app/components/JsonLd";
import { UpdatedLine } from "@/app/components/UpdatedLine";
import { webPageJsonLd } from "@/lib/jsonld";

const title = "（metadata の title と同じ値）";
const description = "（metadata の description と同じ値）";
export const metadata: Metadata = { title, description };

export default function Page() {
  return (
    <main>
      <JsonLd data={webPageJsonLd("/about", title, description)} />
      {/* 本文 */}
      <UpdatedLine path="/about" />
    </main>
  );
}
```

記事の頁にすでに Article があるときは、WebPage を足さず、Article に `dateModified`・`publisher`・`author` が無ければ足します（日付は内容が持つ物）。

### 2-3. Organization と WebSite（全頁）

`app/layout.tsx` の `<body>` の先頭に置きます。ブランドの名前が運営の会社と別なら、`organizationJsonLd` を写してブランドの Organization も 1 つ足し、`url`・`sameAs` はサイトに載っている物だけにします。

```tsx
<body>
  <JsonLd data={organizationJsonLd()} />
  <JsonLd data={webSiteJsonLd()} />
  {children}
</body>
```

代表者やプロフィールの頁があるときだけ、Person（name・jobTitle・url・載っている `sameAs`・`worksFor`）を足します。プロフィールの頁が無いサイトでは出しません。

### 2-4. 見える「最終更新」

静的な全頁の本文の最後（`<main>` の中の最後・フッターの前）に `<UpdatedLine path="/about" />` を置きます。本文に制定日・改定日がある頁（規約など）は、出さなくてかまいません（`jsonld.test.ts` の `NO_UPDATED_LINE` に書く）。

### 2-5. robots・canonical・OG・sitemap

- **公開する頁に `noindex`・`nosnippet`・`max-snippet:0` を付けません。** Google の AI 機能に載るには、索引に入り、スニペット付きで表示できることが前提です。
- 全頁に `canonical` と OG 画像を付けます。`layout.tsx` に次のように書くと、頁ごとに現在の頁の URL に解決されます。OG 画像は `app/opengraph-image.png` を置くか、metadata の `openGraph.images` に書きます。無ければ足します（title・description を流用し、文面は作りません）。

```tsx
export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  alternates: { canonical: "./" },
};
```

- `app/sitemap.ts` は、公開の静的な頁を載せ、`lastModified` を頁ごとの `modified` にします。**`jsonld.test.ts` が読み込めるよう、相対の `.ts` で import します。**

```ts
import type { MetadataRoute } from "next";
import { PAGE_DATES, PAGE_PATHS } from "../lib/page-dates.ts";
import { SITE } from "../lib/site.ts";

export default function sitemap(): MetadataRoute.Sitemap {
  return PAGE_PATHS.map((path) => ({ url: `${SITE.url}${path}`, lastModified: PAGE_DATES[path].modified }));
}
```

動的な頁（記事など）を足すときは、その内容が持つ更新日を `lastModified` に使います。noindex の頁は載せません。

- `app/robots.ts` は、既定では全部許可にして、sitemap の URL を書きます。**AI の bot をどう扱うかは、依頼した人が決めます**（実装側で勝手に断らない）。

```ts
import type { MetadataRoute } from "next";
import { SITE } from "../lib/site.ts";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${SITE.url}/sitemap.xml`,
  };
}
```

学習用の bot だけ断る場合の書き方の例です（検索用の bot は止めません）。bot 名を書いた group には `*` の指定が引き継がれないので、`*` に `disallow` を書いているサイトは、同じものをこちらにも書きます。

```ts
rules: [
  { userAgent: "*", allow: "/" },
  { userAgent: ["GPTBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "CCBot"], disallow: "/" },
],
```

### 2-6. `public/llms.txt`

- 無ければ `templates/llms.txt.example` を元に作ります。サイト名と一文・運営・主な頁の一覧（URL と、その頁の description か冒頭の一文）・用語（頁にある言葉だけ）・連絡先・最終更新です。
- あれば、末尾の最終更新の行だけを `page_dates.py` に任せます。
- **文は、頁にある物をそのまま使います。新しい主張を書きません。** Google 検索は llms.txt を使わないと Google が述べているので、優先度は低い作業です。

### 2-7. テスト

`lib/jsonld.test.ts` を置き、`package.json` の `test` に足します。

```json
"test": "node --test --experimental-strip-types lib/jsonld.test.ts"
```

見る物は、全頁の日付・WebPage の型と項目・Organization・WebSite・`serializeJsonLd` の往復・sitemap と `page-dates` の頁の一致・`noindex` の混入・見える「最終更新」・llms.txt の末尾です。

## 3. 受け入れ

- `python3 scripts/page_dates.py --check` が 0 で終わる。
- `npm test`・型検査（`npx tsc --noEmit`）・`npm run lint`・`npm run build` が通る。
- 手元で `next start`（空いているポート）を起動し、`python3 -I <キット>/bin/audit.py http://localhost:<ポート>` を回す。確かめる物は次のとおりです。
  - 静的な全頁に `datePublished`・`dateModified` と WebPage（または Article）が出ている。
  - 公開の頁に `robots:` の WARN が無い。
  - `can`（canonical）と `og` が全頁で 1。
  - robots・sitemap・llms.txt が読める。
- 幅 360px で横スクロールが出ない。「最終更新」の行がフッターと重ならない。
- 終わったら `next start` を止める。

## 4. 報告

最後の返事（または `docs/aio/` の記録）に次を書きます。

- 変えた・作ったファイルの一覧。
- 頁ごとの日付の表と、JSON-LD の型の一覧。
- テストの数と結果、`audit.py` の出力。
- そのサイト特有の判断（動的な頁の日付・ブランドの Organization・`sameAs` に入れた物と入れなかった物）。
- 迷った点と、そのサイトの掟とこの仕様が食い違った所。
