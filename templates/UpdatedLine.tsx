// ■ 置き場: 自分のサイトのリポの app/components/UpdatedLine.tsx
// ■ 直す所: import の "@/lib/..." だけ（tsconfig.json の paths が "@/*" でないサイトは相対パスにする）。
//           見た目は自分のサイトの CSS で付ける（下の例）。見出し語は lib/site.ts の SITE.updatedLabel。
//
// 「最終更新 YYYY-MM-DD」の 1 行。頁の本文の最後（<main> の中の最後・フッターの前）に置きます。
//   <UpdatedLine path="/about" />
// 日付は scripts/page_dates.py が git の履歴から作った lib/page-dates.ts の値です（手で書きません）。
// path は PAGE_DATES にある頁の path だけ渡せます（型で守られます）。
//
// CSS の例（小さく・右寄せ・控えめに。既存の小さな文字の様式があればそれに合わせる）:
//   .updated-line { text-align: right; font-size: 0.8125rem; opacity: 0.7; }
import { PAGE_DATES, type PagePath } from "@/lib/page-dates";
import { SITE } from "@/lib/site";

export function UpdatedLine({ path }: { path: PagePath }) {
  const { modified } = PAGE_DATES[path];
  return (
    <p className="updated-line">
      {`${SITE.updatedLabel} `}
      <time dateTime={modified}>{modified}</time>
    </p>
  );
}
