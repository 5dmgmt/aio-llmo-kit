// ■ 置き場: 自分のサイトのリポの lib/jsonld.test.ts
// ■ 直す所: 下の「設定」の定数だけ。
// ■ 実行: node --test --experimental-strip-types lib/jsonld.test.ts
//         package.json の "test" に足す。Node.js の版によっては --experimental-strip-types は要らない（付けても害は無い）。
//
// 見る物: 頁ごとの日付（lib/page-dates.ts）・JSON-LD（WebPage・Organization・WebSite）・sitemap の lastmod・
//         見える「最終更新」・llms.txt の末尾・noindex の混入。
// 前提:   app/sitemap.ts を、相対の .ts で import して書くこと（"../lib/page-dates.ts" のように）。
//         node は "@/" の別名を解決できないので、読み込めずにこの検査が止まる。
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import sitemap from "../app/sitemap.ts";
import { organizationJsonLd, serializeJsonLd, webPageJsonLd, webSiteJsonLd } from "./jsonld.ts";
import { PAGE_DATES, PAGE_PATHS } from "./page-dates.ts";
import type { PagePath } from "./page-dates.ts";
import { SITE } from "./site.ts";

// ---------------------------------------------------------------- 設定（自分のサイトに合わせて直す所）

const APP_DIR = "app"; // scripts/page_dates.py の APP_DIR と同じ
const EXCLUDE: readonly string[] = []; // scripts/page_dates.py の EXCLUDE と同じ値（noindex の頁など）
const LAYOUT_FILE = "app/layout.tsx";
const UPDATED_LINE_FILE = "app/components/UpdatedLine.tsx";
const LLMS_FILE = "public/llms.txt"; // 無ければ llms.txt の検査は飛ばす
// 見える「最終更新」を出さない頁（本文に制定日・改定日がある規約の頁など）。無ければ空のまま
const NO_UPDATED_LINE: readonly string[] = [];

// ----------------------------------------------------------------

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const ROOT = fileURLToPath(new URL("../", import.meta.url));
const read = (relative: string) => readFileSync(path.join(ROOT, relative), "utf8");

// scripts/page_dates.py の route_to_url と同じ決め方
function routeToUrl(parts: string[]): string | null {
  const segments: string[] = [];
  for (const part of parts) {
    if (part.startsWith("(") && part.endsWith(")") && !part.startsWith("(.")) continue;
    if (part.startsWith("(.") || part.startsWith("@") || part.startsWith("_") || part.includes("[")) return null;
    segments.push(part);
  }
  return `/${segments.join("/")}`;
}

function isExcluded(urlPath: string): boolean {
  return EXCLUDE.some((pattern) =>
    pattern.endsWith("/*")
      ? urlPath === pattern.slice(0, -2) || urlPath.startsWith(`${pattern.slice(0, -2)}/`)
      : urlPath === pattern,
  );
}

// APP_DIR の下の静的な頁（page.tsx）を、URL の path → ファイルで返す。EXCLUDE の頁も含む
function staticPageFiles(dir = "", found = new Map<string, string>()): Map<string, string> {
  for (const entry of readdirSync(path.join(ROOT, APP_DIR, dir), { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (["node_modules", ".next", ".git"].includes(entry.name)) continue;
      staticPageFiles(path.posix.join(dir, entry.name), found);
    } else if (entry.name === "page.tsx") {
      const url = routeToUrl(dir === "" ? [] : dir.split("/"));
      if (url !== null) found.set(url, path.posix.join(APP_DIR, dir, entry.name));
    }
  }
  return found;
}

const pages = staticPageFiles();
const excludedFiles = [...pages].filter(([url]) => isExcluded(url));

// ---------------------------------------------------------------- 日付

test("頁の日付は YYYY-MM-DD の実在の日付で、公開日は更新日より後にならない", () => {
  assert.ok(PAGE_PATHS.length > 0);
  assert.deepEqual([...PAGE_PATHS], Object.keys(PAGE_DATES));
  for (const p of PAGE_PATHS) {
    const { published, modified } = PAGE_DATES[p];
    assert.match(published, DAY, `${p} published`);
    assert.match(modified, DAY, `${p} modified`);
    assert.ok(published <= modified, `${p}: published <= modified`);
    for (const day of [published, modified]) {
      assert.equal(new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10), day, `${p} ${day}`);
    }
  }
});

test("日付を持つ頁は、APP_DIR の静的な頁から EXCLUDE を除いたものと同じ（python3 scripts/page_dates.py を回し忘れていない）", () => {
  const expected = [...pages.keys()].filter((url) => !isExcluded(url)).sort();
  assert.deepEqual([...PAGE_PATHS].sort(), expected);
  for (const [url] of excludedFiles) assert.ok(!(url in PAGE_DATES), `${url} は日付を持たない`);
});

// ---------------------------------------------------------------- sitemap

test("sitemap は静的な頁を載せ、lastModified は頁の modified。EXCLUDE の頁は載せない", async () => {
  const entries = await sitemap();
  const byPath = new Map<string, (typeof entries)[number]>();
  for (const entry of entries) {
    const url = new URL(entry.url);
    assert.equal(url.origin, new URL(SITE.url).origin, `${entry.url} は SITE.url から作る`);
    byPath.set(url.pathname, entry);
    assert.ok(!isExcluded(url.pathname), `${url.pathname} は EXCLUDE の頁なので載せない`);
  }
  const day = (value: unknown) => (value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10));
  for (const p of PAGE_PATHS) {
    const entry = byPath.get(p);
    assert.ok(entry, `${p} が sitemap に無い`);
    assert.equal(day(entry.lastModified), PAGE_DATES[p].modified, `${p} の lastModified`);
  }
});

// ---------------------------------------------------------------- 雛形の値

test("lib/site.ts の値が、雛形のまま残っていない", () => {
  assert.match(SITE.url, /^https?:\/\/[^/]+$/, "SITE.url は origin（末尾に / を付けない）");
  assert.ok(!SITE.url.includes("example.com"), "SITE.url が example.com のまま");
  assert.notEqual(SITE.name, "サイト名");
  assert.notEqual(SITE.companyName, "会社名");
  assert.ok(SITE.logoPath.startsWith("/"), "SITE.logoPath は / から始める");
  for (const link of SITE.sameAs) assert.match(link, /^https:\/\//, `sameAs ${link}`);
});

// ---------------------------------------------------------------- JSON-LD

test("全頁の WebPage に両方の日付・name・description・url・inLanguage・isPartOf・publisher がある", () => {
  for (const p of PAGE_PATHS) {
    const page = webPageJsonLd(p, "題", "説明") as Record<string, unknown>;
    assert.equal(page["@context"], "https://schema.org");
    assert.equal(page["@type"], "WebPage");
    assert.equal(page.name, "題");
    assert.equal(page.description, "説明");
    assert.equal(page.url, `${SITE.url}${p}`);
    assert.equal(page.inLanguage, SITE.language);
    assert.deepEqual(page.isPartOf, { "@type": "WebSite", name: SITE.name, url: SITE.url });
    assert.equal(page.datePublished, PAGE_DATES[p].published);
    assert.equal(page.dateModified, PAGE_DATES[p].modified);
    assert.match(String(page.datePublished), DAY);
    assert.match(String(page.dateModified), DAY);
    assert.deepEqual(page.publisher, { "@type": "Organization", name: SITE.companyName, url: SITE.url });
  }
});

test("Organization は name・url・logo（https から始まる URL）。sameAs は SITE.sameAs があるときだけ", () => {
  const org = organizationJsonLd() as Record<string, unknown>;
  assert.equal(org["@context"], "https://schema.org");
  assert.equal(org["@type"], "Organization");
  assert.equal(org.name, SITE.companyName);
  assert.equal(org.url, SITE.url);
  assert.equal(org.logo, `${SITE.url}${SITE.logoPath}`);
  if (SITE.sameAs.length > 0) assert.deepEqual(org.sameAs, [...SITE.sameAs]);
  else assert.ok(!("sameAs" in org), "載っているリンクが無いので sameAs は出さない");
});

test("WebSite は name・url・inLanguage・publisher を持つ", () => {
  const site = webSiteJsonLd() as Record<string, unknown>;
  assert.equal(site["@type"], "WebSite");
  assert.equal(site.name, SITE.name);
  assert.equal(site.url, SITE.url);
  assert.equal(site.inLanguage, SITE.language);
  assert.deepEqual(site.publisher, { "@type": "Organization", name: SITE.companyName, url: SITE.url });
});

test("serializeJsonLd は < と行区切りを escape し、読み戻すと元の値になる", () => {
  const first = PAGE_PATHS[0] as PagePath;
  for (const data of [webPageJsonLd(first, "題</script>", "説明<!-- x -->"), organizationJsonLd(), webSiteJsonLd()]) {
    const text = serializeJsonLd(data);
    assert.ok(!text.includes("<"));
    assert.deepEqual(JSON.parse(text), JSON.parse(JSON.stringify(data)));
  }
  const separators = serializeJsonLd({ text: `a${String.fromCharCode(0x2028)}b${String.fromCharCode(0x2029)}c` });
  assert.ok(separators.includes("\\u2028") && separators.includes("\\u2029"));
});

// ---------------------------------------------------------------- 頁のファイル

test("各 page.tsx が自分の頁の WebPage を出す。「最終更新」は NO_UPDATED_LINE 以外の頁が出す", () => {
  for (const p of PAGE_PATHS) {
    const file = pages.get(p);
    assert.ok(file, `${p} の page.tsx`);
    const source = read(file);
    assert.ok(source.includes("webPageJsonLd("), `${file}: webPageJsonLd を呼ぶ`);
    assert.ok(source.includes(`"${p}"`), `${file}: 自分の path "${p}" を渡す`);
    assert.equal(source.includes(`<UpdatedLine path="${p}" />`), !NO_UPDATED_LINE.includes(p), `${file}: UpdatedLine`);
  }
});

test("索引に載せる頁に noindex・nosnippet・max-snippet:0 を付けない。EXCLUDE の頁は WebPage も「最終更新」も出さない", () => {
  for (const p of PAGE_PATHS) {
    const file = pages.get(p);
    assert.ok(file, `${p} の page.tsx`);
    const source = read(file);
    assert.ok(!/noindex|nosnippet|max-snippet\s*:\s*0|index\s*:\s*false/.test(source), `${file}: 索引やスニペットを止める指定がある`);
  }
  for (const [, file] of excludedFiles) {
    const source = read(file);
    assert.ok(!source.includes("UpdatedLine") && !source.includes("webPageJsonLd"), `${file}`);
  }
});

test("layout は Organization と WebSite の JSON-LD を全頁に出し、canonical を持つ", () => {
  const layout = read(LAYOUT_FILE);
  for (const call of ["organizationJsonLd()", "webSiteJsonLd()"]) {
    assert.ok(layout.includes(`<JsonLd data={${call}} />`), `${LAYOUT_FILE}: ${call}`);
  }
  assert.ok(layout.includes("canonical"), `${LAYOUT_FILE}: alternates.canonical`);
  assert.ok(layout.includes("metadataBase"), `${LAYOUT_FILE}: metadataBase`);
});

test("「最終更新」の部品は PAGE_DATES の日付だけを出し、日付を手で書かない", () => {
  const source = read(UPDATED_LINE_FILE);
  assert.ok(source.includes("PAGE_DATES[path]"));
  assert.ok(source.includes("<time dateTime={modified}>"));
  assert.ok(!/\d{4}-\d{2}-\d{2}/.test(source.replace(/\/\/.*$/gm, "")), "日付を手で書かない");
});

// ---------------------------------------------------------------- llms.txt

test("llms.txt の末尾は「最終更新 {頁の更新日の最大}」で、URL は SITE.url の頁か公式のリンク", { skip: !existsSync(path.join(ROOT, LLMS_FILE)) }, () => {
  const text = read(LLMS_FILE);
  const latest = PAGE_PATHS.map((p) => PAGE_DATES[p].modified)
    .sort()
    .at(-1);
  assert.match(String(latest), DAY);
  assert.ok(text.endsWith(`\n${SITE.updatedLabel} ${latest}\n`), `末尾が「${SITE.updatedLabel} ${latest}」でない（python3 scripts/page_dates.py を回す）`);
  assert.equal(text.match(new RegExp(SITE.updatedLabel, "g"))?.length, 1, "「最終更新」の行は 1 つだけ");
  for (const url of text.match(/https?:\/\/[^\s)]+/g) ?? []) {
    if (SITE.sameAs.includes(url)) continue; // 公式のリンク（SNS など）は別のホストでよい
    assert.ok(url.startsWith(SITE.url), `${url} は SITE.url の頁ではない`);
  }
});
