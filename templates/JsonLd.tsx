// ■ 置き場: 自分のサイトのリポの app/components/JsonLd.tsx
// ■ 直す所: import の "@/lib/jsonld" だけ。tsconfig.json の paths が "@/*" でないサイトは、相対パスにする
//
// 構造化データ（JSON-LD）を script タグとして出す部品です。
// 使い方（細かくは docs/spec.md）:
//   app/layout.tsx の <body> の先頭   <JsonLd data={organizationJsonLd()} /> と <JsonLd data={webSiteJsonLd()} />
//   各頁の page.tsx                   <JsonLd data={webPageJsonLd("/about", title, description)} />
// script の中の JSON は serializeJsonLd が作ります（`<` などを escape してあるので、文中に </script> があってもタグが途切れません）。
// CSP を使っているサイトは、ブラウザの開発者ツールのコンソールに警告が出ないかを確かめてください。
import { serializeJsonLd, type JsonLd as JsonLdData } from "@/lib/jsonld";

export function JsonLd({ data }: { data: JsonLdData }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }} />;
}
