# uota.github.io

Jekyllで生成した静的サイトを、Cloudflare Workers Static Assetsで配信する構成です。

## ローカルでの確認

Node.jsとRuby/Bundlerを用意してから、次を実行します。

```powershell
npm install
bundle install
npm run build
npm run dev
```

`bundle install` はRubyの依存関係を準備します。`npm run build` はJekyllで `_site/` を生成します。`npm run dev` はその成果物をWorkersのローカル開発サーバーで配信します。

Cloudflareへ手動で反映する場合は、ログイン済みの環境で次を実行します。

```powershell
npm run deploy
```

プレビュー専用のWorkerバージョンを発行する場合は次を使います。

```powershell
npm run deploy:preview
```

## Cloudflare Workers Buildsの設定

CloudflareダッシュボードでGitHubリポジトリを接続する際は、`wrangler.jsonc` の `name` と同じ **`uota-preview`** というWorkerを選びます。既存Workerを使う場合は、先に `wrangler.jsonc` の `name` をそのWorker名に変更してください。

| 設定 | 値 |
| --- | --- |
| Build command | `npm run build` |
| Production deploy command | `npx wrangler deploy` |
| Non-production deploy command | `npx wrangler versions upload` |
| Production branch | `main` |
| Preview branches | `develop` を含む非本番ブランチ |

非本番ブランチのビルドを有効にすると、`develop` へのpushごとに本番を切り替えないプレビューURLがCloudflareのビルド詳細とGitHubのチェックに表示されます。
