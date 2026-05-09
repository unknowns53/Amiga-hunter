# Amiga / LightWave 3Dモデル探索パイプライン

古いAmiga / LightWave系の3Dアーカイブ群から、特定の低ポリ頭部モデル
（例: アンシャントロマン冒頭のおじさんの元素材）を発掘するための
調査パイプラインです。

> **実機運用のフル手順と既知の落とし穴は [`docs/RUNBOOK.md`](docs/RUNBOOK.md) を参照。**

## 何ができるか

1. `archives_raw/` に置いた `zip` / `lha` / `lzx` / `adf` / `hdf` などを展開
2. `extracted/` 以下の全ファイルを走査して `output/scan_results.csv` に書き出し
3. LightWave Object 候補を抽出して `output/candidate_models.csv` に書き出し
4. (任意) Blender で候補を一括インポートし、正面・斜め・横の3アングルで
   サムネイルレンダリング → `renders/<sha>/`

## ディレクトリ構成

```
amiga_hunter/
├── README.md
├── requirements.txt
├── run_pipeline.py        # 展開→走査→候補抽出（Pythonで実行）
├── collect_aminet.py      # Aminet から .lha を一括取得（Pythonで実行）
├── blender_render.py      # サムネイル生成（Blenderで実行）
├── compare_renders.py     # 参照画像とのperceptual hash比較（Pythonで実行）
├── pipeline/
│   ├── config.py          # 候補拡張子・キーワード等の設定
│   ├── extract.py
│   ├── scan.py
│   └── identify.py
├── references/            # ← 探したい「おじさん」画像を置く
├── archives_raw/          # ← ここにアーカイブを入れる
├── extracted/             # 自動生成
├── output/                # CSV出力
├── renders/               # サムネイル
└── logs/
```

## 必要環境（Windows優先）

### 1. Python 3.10 以上

[python.org](https://www.python.org/) からインストーラを取得。
インストール時に「Add python.exe to PATH」にチェックを入れる。

```cmd
python --version
pip install -r requirements.txt
```

### 2. 7-Zip （LHA / LZX / RAR / 7Z 展開用）

[https://www.7-zip.org/](https://www.7-zip.org/) からインストール。
規定パス（`C:\Program Files\7-Zip\7z.exe`）にインストールすれば自動検出される。

別の場所に入れた場合は環境変数で指定：

```cmd
set SEVENZIP_PATH=D:\tools\7z\7z.exe
```

> **注意:** Amiga LZX は7-Zipでも展開できないケースあり。その場合は
> Aminetの `unlzx` を別途入手し、手動で展開してから `extracted/` に
> 中身を置いてください（その場合 `run_pipeline.py` の Step 2 から再実行）。

### 3. amitools （ADF / HDF 展開用）

```cmd
pip install amitools
```

`xdftool` コマンドが PATH に通る。

### 4. Blender （サムネイル生成、任意）

[https://www.blender.org/](https://www.blender.org/) から **3.6 LTS または 4.x**
を入手。Windows既定の場所例：

```
C:\Program Files\Blender Foundation\Blender 4.2\blender.exe
```

#### LWO / 3DS インポーター

Blender 4.x ではLWO・3DSがコアから外れているため、コミュニティアドオンが必要：

- **LWO**: 例 [github.com/koneight/blender-lwo](https://github.com/koneight/blender-lwo)
  （フォークが複数あるので、自分のBlenderバージョンに合うものを）
- **3DS**: 同様にコミュニティアドオン
  ([Extensions プラットフォーム](https://extensions.blender.org/) 等で配布)

アドオン導入手順：

1. zipを取得
2. Blender → Edit → Preferences → Add-ons → "Install from disk"
3. 導入後にチェックボックスで有効化（`blender_render.py` 側でも自動有効化を試みるが、
   未インストールのものは有効化できない）

## 使い方

```cmd
:: 1) アーカイブを置く（手動でコピーするか、Aminet から取得）
copy yourstuff.lha amiga_hunter\archives_raw\
copy demo.adf      amiga_hunter\archives_raw\

:: 1b) もしくは Aminet gfx/3dobj/ を一括取得（数百MB注意）
cd amiga_hunter
python collect_aminet.py
:: README に head/face/man 等のキーワードがあるものだけに絞る場合
python collect_aminet.py --filter-readme

:: 2) 展開・走査・候補抽出
python run_pipeline.py

:: 3) 候補CSVを確認
notepad output\candidate_models.csv

:: 4) Blenderでサムネイル一括生成
"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --background --python blender_render.py

:: 5) 参照画像との類似度ランキング
python compare_renders.py --reference references\ojisan.png
:: 上位だけ確認したいとき
python compare_renders.py --reference references\ojisan.png --top 30
```

## 出力ファイル

| パス | 内容 |
|------|------|
| `output/scan_results.csv`        | 全ファイルのスキャン結果（パス・サイズ・SHA256・先頭バイト・抽出文字列） |
| `output/candidate_models.csv`    | 候補のみ（マッチ理由つき・スコア順ソート） |
| `output/similarity_ranking.csv`  | 参照画像との perceptual-hash 距離ランキング（compare_renders.py） |
| `renders/<sha16>/*.png`          | 各候補の正面 / 斜め / 横サムネイル |
| `renders/<sha16>/info.json`      | 元ファイルパス・SHA256・レンダ結果 |
| `logs/pipeline.log`              | 実行ログ |
| `logs/render.log`                | Blender実行ログ |
| `logs/render_errors.log`         | レンダリング失敗の詳細（インポート失敗・ジオメトリ無し等） |

## 候補判定ロジック

以下のいずれかにヒットしたファイルを候補として拾う：

- **拡張子**: `.lwo` `.lwob` `.obj` `.geo` `.3ds` `.iff` `.lws`
- **ファイル名**（大小無視で部分一致）: `head` `face` `man` `male` `human` `person` `bust` `demo` `tutor`
- **バイナリ内の magic**: `FORM` / `LWOB` / `LWO2`
  - `FORM` だけは IFF全般（音声等）でも踏むので、拡張子が `.iff` `.lwo` `.lwob` か無拡張のときだけ採用
  - `FORM ... LWOB` / `FORM ... LWO2` のオフセット8シグネチャは強い証拠として `lwo_signature` 列に記録

スコア順（強いシグネチャ→ファイル名一致 の順）でソートして出力。

## カスタマイズ

- 候補拡張子・キーワードは `pipeline/config.py` の `CANDIDATE_EXTENSIONS` / `KEYWORDS`
- スキャン上限バイト数は同 `SCAN_BYTES` （デフォルト1MB）
- 抽出文字列のフィルタは `pipeline/scan.py` の `INTERESTING_TOKENS`

## 制約事項・既知の問題

- **LZX**: Amiga固有圧縮。Windows環境での解凍は不安定。失敗時は手動展開推奨
- **ADF/HDF**: 中身がAmigaの独自ファイルシステム（OFS/FFS等）。`xdftool unpack` は
  ファイルシステムの破損率が高めの古いイメージで失敗することがある
- **LWOB**: 1990年代前半のフォーマット。コミュニティアドオンによっては
  古すぎるバリエーションを読めないものもある
- **EEVEE_NEXT**: Blender 4.2以降。それ以前は自動的にEEVEEへフォールバック

## 類似度ランキング（compare_renders.py）

`renders/` に揃った PNG を perceptual hash で参照画像（おじさん）と
比較し、距離が小さい順にランキング。

```cmd
python compare_renders.py --reference references\ojisan.png \
    --method phash --views front threequarter side --top 50
```

- 出力: `output/similarity_ranking.csv`
  - 列: `rank`, `sha_prefix`, `best_view`, `best_distance`,
    `d_front` / `d_threequarter` / `d_side`, `name`, `source_path`, `match_reasons`
- 距離は **Hamming 距離（ビット差）**。0 が完全一致、数値が小さいほど似ている
- 各候補で **最も似ている角度** を `best_view` として代表値にする
- `--method` は `phash`（既定）/ `dhash` / `whash` / `average_hash`
- 精度が出ない場合は CLIP embedding ベース（`open_clip_torch` 等）への
  差し替えを検討（重い代わりにセマンティック類似度に強い）
