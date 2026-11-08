// ■ 置き場: 自分のサイトのリポの lib/jsonld.ts
// ■ 直す所: ほぼ無し。値は lib/site.ts（SITE）と lib/page-dates.ts（scripts/page_dates.py の生成物）から取ります。
//           tsconfig.json の compilerOptions に "allowImportingTsExtensions": true が要ります（下の import が .ts で終わるため。
//           Next.js の既定の noEmit: true と併用できます）。
//
// 構造化データ（JSON-LD）を組み立てます。ここに文言を直書きしません。
// import が相対の .ts なのは、node --test の型除去実行から直接読めるようにするためです（Next.js の部品に依存しない）。
import { PAGE_DATES } from "./page-dates.ts";
import type { PagePath } from "./page-dates.ts";
import { SITE } from "./site.ts";

const CONTEXT = "https://schema.org";

export type JsonLd = Readonly<Record<string, unknown>>;

// 運営（Organization）。sameAs は SITE.sameAs が空でなければ出す（サイトに載っているリンクだけを入れる）
function organization(): Record<string, unknown> {
  return {
    "@type": "Organization",
    name: SITE.companyName,
    url: SITE.url,
    logo: `${SITE.url}${SITE.logoPath}`,
    ...(SITE.sameAs.length > 0 ? { sameAs: [...SITE.sameAs] } : {}),
  };
}

// 他の node の publisher に入れる最小の形（name と url だけ）
function publisher(): Record<string, unknown> {
  return { "@type": "Organization", name: SITE.companyName, url: SITE.url };
}

/** 全頁（layout）: 運営の Organization */
export function organizationJsonLd(): JsonLd {
  return { "@context": CONTEXT, ...organization() };
}

/** 全頁（layout）: WebSite。publisher は運営 */
export function webSiteJsonLd(): JsonLd {
  return {
    "@context": CONTEXT,
    "@type": "WebSite",
    name: SITE.name,
    url: SITE.url,
    inLanguage: SITE.language,
    publisher: publisher(),
  };
}

/**
 * 頁ごと: WebPage。日付は git の履歴から作った lib/page-dates.ts の値（手で書かない）。
 * title は `<title>` に出る値（template を通した後）、description は meta description と同じ値を渡す。
 */
export function webPageJsonLd(path: PagePath, title: string, description: string): JsonLd {
  const dates = PAGE_DATES[path];
  return {
    "@context": CONTEXT,
    "@type": "WebPage",
    name: title,
    description,
    url: `${SITE.url}${path}`,
    inLanguage: SITE.language,
    isPartOf: { "@type": "WebSite", name: SITE.name, url: SITE.url },
    datePublished: dates.published,
    dateModified: dates.modified,
    publisher: publisher(),
  };
}

/**
 * script タグの中へ入れる JSON 文字列。`<` と行区切りの文字を escape して、
 * 文中の `</script>` や HTML コメントでタグが途切れないようにする（読み戻すと元の JSON に戻る）。
 */
export function serializeJsonLd(data: JsonLd): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(new RegExp(String.fromCharCode(0x2028), "g"), "\\u2028")
    .replace(new RegExp(String.fromCharCode(0x2029), "g"), "\\u2029");
}
