README_DEV.md

（復帰用・最小メモ）

全体構造（まずここを思い出す）

CSS
	•	CSSは 分割ファイル管理
	•	assets/css/ 配下の 個別CSSを編集
	•	build 時に1ファイルへ結合
	•	本番は結合後CSSを参照

Partials
	•	ヘッダー / フッター / トップ説明文
	•	assets/partials/ 内のファイルを編集

⸻

Python スクリプト構成（重要）

build.py
	•	HTML生成のメイン
	•	ページ生成 / CSS結合 / 出力担当

その他3本
	•	入力：_work/gallery_block.txt
	•	処理：
	•	block → CSV
	•	CSV → items.json
	•	ギャラリー更新用の補助スクリプト群

⸻

ギャラリー本番データ投入（最小・安全手順）

事前準備（表示確認用サーバー）

cd /Users/saitomirei/mireisfolder/Projects/raralabjp/site
python3 -m http.server 8000

cd /Users/saitomirei/mireisfolder/Projects/raralabjp


⸻

0. 前提（忘れたらここを見る）
	•	CSV：assets/data/items.csv
	•	表示用：assets/data/items.json
	•	CSV更新後は必ず import
	•	表示は JSON を参照

⸻

1. 入力ブロック作成（1件ずつ）

_work/gallery_block.txt に 1件だけ 書く。

最低限テンプレ：

URLs: shop=; video=★ht./iframe
image_order:
process_image_order:
Title JP:
Stone:
Facet Design:
design_is_named: 1
modification_note:
Faceted by Rara Lab
Designed by
Carat:
Size:
Origin:
Treatment:
Clarity:
image_order:
process_image_order:

入力ルール（固定）
	•	日本語タイトル：Title JP:
	•	引用符あり表示 → design_is_named: 1
	•	引用符なし → 0

⸻

2. 画面出力で確認（CSVには入れない）

python3 tools_from_block.py --date 2025-12-02 < _work/gallery_block.txt

確認点（これだけ）
	•	slug が自然
	•	stone が 英語名
	•	title_jp が 日本語

※ "" は CSV エスケープ。無視してOK。

⸻

3. CSVに登録（置き換え方式・安全）

python3 tools_from_block.py --date 2025-12-02 < _work/gallery_block.txt \
  2>> _work/logs/warn_from_block.log \
  | python3 tools_upsert_csv.py assets/data/items.csv

	•	同一 slug は 自動置き換え
	•	重複事故なし

確認したいとき：

tail -n 3 assets/data/items.csv


⸻

4. items.json 更新（必須）

python3 tools_import_csv.py && python3 build.py

期待：

items.json 更新: XXX 件


⸻

5. ビルド＆表示確認

python3 build.py

ハードリロード：
	•	Mac：Cmd + Option + R
	•	モバイル：Cmd + Ctrl + R

⸻

トラブル時の判断

WARN が出た
	•	CSVが出ていれば 基本OK
	•	後で直せるものは後回し

即修正が必要
	•	title_jp が空
	•	slug が空

後回し可
	•	origin_en
	•	clarity

⸻

事故防止ルール（最重要）
	•	1件ずつ入れる
	•	毎回この順番を固定：

from_block
→ upsert
→ import
→ build

	•	CSVは直接編集しない

⸻

GitHub バックアップ

cd /Users/saitomirei/mireisfolder/Projects
git add .
git commit -m "site update"
git push


⸻

最後に（安心ポイント）
	•	覚えるのは「構造」だけでいい
	•	詳細は忘れてOK
	•	困ったらこの README を ChatGPT に貼れば復帰可能

⸻
