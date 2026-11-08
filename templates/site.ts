// ■ 置き場: 自分のサイトのリポの lib/site.ts
// ■ 自分のサイトに合わせて直す所は、★ を付けた行だけです。
//
// サイトの名前・URL・運営の会社名・ロゴを 1 か所にまとめます。lib/jsonld.ts と app/components/UpdatedLine.tsx がここから値を取ります。
// ここに書く物は、すでに自分のサイトの頁に載っている物だけにしてください（載っていない住所・SNS・資格を足さない）。

// ★ 本番の URL（https から始め、末尾に / を付けない）。環境変数 NEXT_PUBLIC_SITE_URL があればそちらを使う
const DEFAULT_URL = "https://example.com";

export const SITE = {
  // ★ サイトの名前（ヘッダーやロゴに出している表記と同じにする）
  name: "サイト名",
  url: (process.env.NEXT_PUBLIC_SITE_URL?.trim() || DEFAULT_URL).replace(/\/+$/, ""),
  // ★ 運営している会社・団体の名前（会社案内に出している表記と同じにする）
  companyName: "会社名",
  // ★ ロゴ画像の path。正方形で、公開されている画像（public/ に置いた物なら "/logo.png" のように書く）
  logoPath: "/logo.png",
  // ★ サイトに載っている公式のリンク（SNS・会社の公式サイトなど）。載っていなければ空のままにする
  sameAs: [] as readonly string[],
  // ★ 頁の言語
  language: "ja",
  // ★ 見える「最終更新」の見出し語（llms.txt の末尾の語と、scripts/page_dates.py の LLMS_LABEL に合わせる）
  updatedLabel: "最終更新",
} as const;
