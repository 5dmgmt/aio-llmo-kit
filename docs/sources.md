# 出どころ

このキットの考え方の土台にした資料です。**一次**は各社の公式文書、**二次**は他者の解説です。要点は自分の言葉でまとめています。正確な内容と最新の状態は、原文で確かめてください（文書は予告なく変わります）。原文を確認した日は 2026-11-08 です。

## 一次資料

| 資料 | URL | このキットが使っている要点 |
|---|---|---|
| Google「Optimizing your website for generative AI features on Google Search」 | https://developers.google.com/search/docs/fundamentals/ai-optimization-guide | AI Overview と AI モードに載る頁の前提（索引に入り、スニペット付きで表示できる）。効くこととして挙げられているのは、書き手自身の経験や専門から出た一次情報、読者に伝わる構成、画像・動画の基本、クロールできる・速いなどの検索の基本。AI 向けの特別な対策は求められていない。llms.txt のような AI 向けの機械可読ファイル、文を細切れにすること、AI 向けの書き直しは不要という趣旨。検索のバリエーションごとに頁を量産するのはスパムにあたる |
| Google「AI features and your website」 | https://developers.google.com/search/docs/appearance/ai-features | AI 機能の説明と、サイト運営者ができること |
| Google Search Console ヘルプ「Search generative AI control」 | https://support.google.com/webmasters/answer/16908024 | 自分のサイトを生成 AI の機能に含めるかを決める設定。既定は含める。除外しても検索の順位には影響しないと説明されている。学習の可否は Google-Extended で指定する |
| Google Search Console ヘルプ「Generative AI performance report (Search)」 | https://support.google.com/webmasters/answer/16984139 | 生成 AI の機能での表示回数などを見るレポート。Discover 向けは別のレポート（https://support.google.com/webmasters/answer/16983858） |
| Google の robots meta タグと X-Robots-Tag の説明 | https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag | `noindex`・`nosnippet`・`max-snippet` の意味。meta タグとレスポンスヘッダーの両方で指定できる |
| OpenAI の巡回 bot の説明 | https://developers.openai.com/api/docs/bots | GPTBot は学習用、OAI-SearchBot は検索用、ChatGPT-User は利用者の操作。OAI-SearchBot を断ると ChatGPT の検索結果に出なくなる |
| Anthropic の巡回 bot の説明（ヘルプ） | https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler | ClaudeBot は学習用、Claude-SearchBot は検索用、Claude-User は利用者の操作 |
| Perplexity の巡回 bot の説明 | https://docs.perplexity.ai/guides/bots | PerplexityBot は検索用で、学習には使わないと説明されている。Perplexity-User は利用者の操作で、robots.txt を原則として無視する |
| Apple の Applebot の説明 | https://support.apple.com/en-us/119829 | Applebot は検索用。Applebot-Extended は学習に使うかどうかの意思表示だけで、検索の順位には影響しない。AI の回答の文脈に使わせたくない頁は、`nosnippet` で指定する |
| IndexNow | https://www.indexnow.org/documentation | 更新した URL を検索エンジンへ知らせる仕組み。任意 |

## 二次資料

一次資料で確かめていない主張を含みます。数字は使っていません。

- Google のガイドの解説: https://www.searchenginejournal.com/google-says-llms-txt-is-purely-speculative-for-now/575026/ ・ https://previsible.io/seo-ai-news/google-published-its-first-guide-to-ai-search-optimization/
- AI の巡回 bot の一覧: https://www.searchenginejournal.com/ai-crawler-user-agents-list/558130/ ・ https://momenticmarketing.com/blog/ai-search-crawlers-bots
- 国内の点検表（民間）: https://news.mynavi.jp/article/llmo_guide-1/ ・ https://funnel-ai.jp/media/ai-search-site-design-checklist/

## 確かめられていないこと

- Search Console の日本語の画面での名称。
- FAQPage のリッチリザルトの表示が縮小・終了したという情報（二次情報のみ）。
- ChatGPT の検索が Bing の索引を使うこと（二次情報のみ）。
- 各社が bot の名前や挙動を変える時期。点検表の項目 10 を使う前に、上の一次資料で最新の状態を確かめてください。
