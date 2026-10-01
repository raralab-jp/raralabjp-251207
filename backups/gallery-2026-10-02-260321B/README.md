# Gallery作業スナップショット — 2026-10-02 / 260321B

## どの場所を何に使うか

| 場所 | 役割 |
|---|---|
| Macの `Projects/raralabjp` | 日常の作業用。既存Python・既存テンプレートでGalleryを生成する場所 |
| GitHub `raralab-jp/raralabjp-251207` → `awai-prelaunch` → `backups/gallery-2026-10-02-260321B/` | 作業内容の保存用。本番配信パスとは別のフォルダ |
| 同じGitHubリポジトリの `site-v2` → `raralabjp/site` | 意図した本番公開先。Cloudflareで本番自動デプロイ有効を確認 |

このスナップショットは保存用です。商品260321Bを公開する操作は別途承認が必要です。準備時点で260321Bの本番公開は実行していません。このフォルダのHTMLには本番ドメインの候補URLが含まれますが、URLの記載は公開完了を意味しません。

**保存用ブランチにも自動プレビューがある場合、pushは公開を起こします。** 今回の保存は、Cloudflare PreviewをNoneへ変更して保存されたことを確認してから行う方針です。意図する設定はProduction branch=`site-v2`、本番自動デプロイ有効、Preview=Noneです。保存直前にユーザー提供の再読込後の画面でProduction branch=`site-v2`・本番自動デプロイ有効・Preview=Noneを確認しました。今後の設定変更には注意してください。フォルダを分けることだけでは公開防止を保証できません。

## 中身

`raralabjp/` に全40商品のGalleryデータ・対応画像・生成ページ・必要な既存Pythonとテンプレートを保存しています。今回以前の未保存作業も含む、現在の作業状態のコピーです。トップページのNews表示を保持するため、公開済みNewsの関連入力・画像・ページも含みます。

- `assets/data/items.csv` / `items.json`: 商品データ
- `assets/images/`: 商品写真・Making写真・WebP・トップ画像
- `assets/partials/`, `assets/css/`, `assets/js/`等: 既存テンプレートと表示部品
- `site/gallery/`, `site/index.html`, `site/assets/`: 保存時点の生成物
- `_work/260321B.txt` / `260321B_gallery_row.csv`: 今回商品の再実行入力
- Python8ファイル: 生成・取り込み・写真検証と必要な共通部品
- `MANIFEST.json`: 相対パス、容量、SHA256による正確な一覧

Squareの輸出・取込CSV、商品マスタ下書き、認証設定、外部原ログ、古いバックアップ、無関係な作業は含みません。Square設定がなくてもGalleryを生成できます。GemDiary・About等を含む全サイトの復元用ではありません。

## 復元・ローカル確認

既存作業フォルダを上書きせず、この中の `raralabjp/` を新しいローカル作業フォルダへコピーします。Python3を使用し、WebPを再生成する場合はPillowが必要です。既存WebPは保存済みです。

コピー先の `raralabjp/` で実行します。

```sh
python3 tools_validate_gallery_images.py
python3 build.py
python3 -m http.server 8764 --bind 127.0.0.1 --directory site
```

ブラウザで `http://127.0.0.1:8764/gallery/` を開きます。buildはコピー先のCSS・画像・`site/assets`・ページを再生成します。元作業フォルダや本番公開用コピーで、復元テストとして直接実行しないでください。

既存の入力→生成の手順を再利用する場合は、コピー先で次の順序です。通常のGallery再表示だけなら、入力の再取り込みは不要です。

```sh
python3 tools_from_block.py < _work/260321B.txt > /tmp/260321B-restored-row.csv
python3 tools_upsert_csv.py assets/data/items.csv < /tmp/260321B-restored-row.csv
python3 tools_import_csv.py --slug montana-sapphire-0119ct-baguette-cut-for-sapphire
python3 tools_validate_gallery_images.py --slug montana-sapphire-0119ct-baguette-cut-for-sapphire
python3 build.py
```

入力の登録日を固定する必要があれば、`tools_from_block.py --date`へ保存CSVのdate値を指定してください。未指定では実行日の値になります。

## 確認済みと残作業

隔離した復元コピーで既存buildが成功し、40商品の詳細ページを生成。Gallery・トップの画像等の参照欠落は0件でした。

Squareの最新全件エクスポートでの照合、Square登録、購入URL反映、本番公開と相互リンク確認は別の作業です。この保存は、それらの完了を表すものではありません。
