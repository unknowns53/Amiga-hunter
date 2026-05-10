# 実機運用 Runbook

手元のマシンで Amiga / LightWave 系アーカイブから「おじさん」候補を発掘する
ための **操作手順** と、進行中に踏みやすい **懸念点・既知の落とし穴** をまとめる。

設計や API リファレンスは [README.md](../README.md) を参照。本ドキュメントは
「実機で回すときに何をどの順で叩くか」「どこで詰まりがちか」に絞る。

---

## 0. 事前準備

### 0.1 OS

Windows 10/11 を一次ターゲットにする。Linux/macOS でも動くが、Blender 用の
LWO/3DS コミュニティアドオンと 7-Zip の入手性が Windows のほうが高い。

### 0.2 必要ツール

| ツール | バージョン | 用途 | 備考 |
|---|---|---|---|
| Python | 3.10+ | 全 Python スクリプト | `Add python.exe to PATH` を有効に |
| 7-Zip | 23.x 以降推奨 | `.lha` `.lzh` `.lzx` `.7z` `.rar` 等 | 既定パスに入れれば自動検出。別パスは `SEVENZIP_PATH` |
| amitools (`xdftool`) | `pip install amitools` | `.adf` `.hdf` 展開 | `pip install -r requirements.txt` で入る |
| Blender | **4.5 LTS 推奨** / 5.x も可 | サムネイルレンダ | 後述「Blender バージョン選択」参照 |
| LWO アドオン | コミュニティ製 | `.lwo` `.lwob` インポート | 例: <https://github.com/koneight/blender-lwo>。**4.x 系の対応が安定** |
| 3DS アドオン | コミュニティ製 | `.3ds` インポート | Blender 4.x ではコアから外れている。Extensions プラットフォーム |

### 0.3 参照画像

`references/IMG_2211.png` （ または `references/ojisan.png` 等任意の名前）。
正面気味のカット推奨。背景は単色または近い色だと perceptual hash が効きやすい。

---

## 1. セットアップ

```cmd
git clone https://github.com/unknowns53/amiga-hunter.git
cd amiga-hunter
git checkout main
pip install -r requirements.txt
```

Blender アドオンの導入は GUI から：

1. アドオン zip を入手（LWO/3DS）
2. Blender → Edit → Preferences → Add-ons → "Install from disk"
3. チェックボックスで有効化（`blender_render.py` も自動有効化を試みるが、
   未インストールのものは有効化できない）

---

## 2. アーカイブ収集（`collect_aminet.py`）

### 2.1 まずキーワード絞り込みで様子見（推奨スタート）

```cmd
python collect_aminet.py --filter-readme
```

各 `.readme` を先読みし、`pipeline/config.py` の `KEYWORDS`
（`head` / `face` / `man` / `male` / `human` / `person` / `bust` / `demo` / `tutor`）
にヒットするアーカイブだけ落とす。既定取得先 `gfx/3d/`（約 413 本、
2026年5月時点）でヒット数が 0 〜 数十件程度に絞られる想定。

### 2.2 ヒットが薄い場合は全件取得

```cmd
python collect_aminet.py
```

`gfx/3d/` 全件。数百 MB、回線次第で数十分。

### 2.3 隣接ディレクトリへの拡張

既定の `gfx/3d/` は 3D アプリ本体（LightWave, Imagine, Real3D, Sculpt 等）に
**サンプルモデルが同梱されている**カテゴリ。ヒットが薄ければ別カテゴリも試す：

```cmd
python collect_aminet.py --dir mods/  --filter-readme
python collect_aminet.py --dir mags/  --filter-readme
```

Aminet のディレクトリ構成は時期によって変わる（旧 `gfx/3dobj/` は廃止、
旧 `dev/lwave/` も現存しない）。最新の全体構成は
<https://ftp.fau.de/aminet/TREE> または同 `INDEX` を参照。

### 2.4 取得停止と再開

`Ctrl+C` で中断可。再実行すると既存ファイルは `have:` で **スキップ**するので
何度でも安全に再開できる。

### 2.5 ローカル確認用

```cmd
python collect_aminet.py --limit 5
```

---

## 3. 展開 → 走査 → 候補抽出（`run_pipeline.py`）

```cmd
python run_pipeline.py
```

- Step 1: `archives_raw/*.{zip,lha,lzx,adf,hdf,...}` を `extracted/` 以下に展開
  （`.readme` 等のサイドカーは自動でスキップ）
- Step 2: `extracted/` 全ファイルを走査して `output/scan_results.csv`
- Step 3: 候補抽出 → `output/candidate_models.csv`（スコア順）

### 候補スコアの大まかな目安

| match_reasons の組み合わせ | 期待される強さ |
|---|---|
| `sig:LWOB` | ★★★★★ 最強。FORM+LWOB をオフセット 0/8 に持つ確定 LightWave Object |
| `sig:LWO2` | ★★★★ 同上、LWO2 形式 |
| `ext:.lwo` / `ext:.lwob` + `name:*` | ★★★★ 拡張子 + ファイル名キーワード |
| `contains:LWOB` | ★★★ 中に LWOB が埋まっている（バンドル品） |
| `ext:.obj` / `ext:.3ds` | ★★ 拡張子のみ |
| `name:*` のみ | ★ 名前のキーワードだけ。誤検出多め |

---

## 4. サムネイル生成（`blender_render.py`）

```cmd
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" ^
    --background --python blender_render.py
```

各候補について `front` / `threequarter` / `side` の3アングル PNG を
`renders/<sha16>/` に出す。

### 進捗確認

```cmd
type logs\render.log | more
type logs\render_errors.log
```

`render_errors.log` には **インポート失敗** と **ジオメトリ無し** が
別個に記録される。LWOB 古形式やコミュニティアドオン未対応バリアントは
ここに溜まる。

---

## 5. 類似度ランキング（`compare_renders.py`）

```cmd
python compare_renders.py --reference references\IMG_2211.png --top 30
```

- `output/similarity_ranking.csv` に距離昇順で書き出し
- 上位 N 件はコンソールにも出力
- 候補が多い場合は `--method dhash` や `--method whash` も試す価値あり

### Hamming 距離の目安（phash 64bit）

| 距離 | 解釈 |
|---|---|
| 0–6 | ほぼ同一画像 |
| 6–14 | 同じ被写体・別アングル可能性大 |
| 14–22 | 似ている部分はあるが要目視確認 |
| 22+ | 別物の可能性が高い |

低ポリ vs 写実的レンダ、白背景 vs グラデ背景の差で **下駄が乗る**ので、
絶対値より「上位がどこに固まるか」を見る。

---

## 6. 結果のレビューフロー

1. `output/similarity_ranking.csv` を Excel/エディタで開く
2. 上位 30〜50 件の `sha_prefix` を辿って `renders/<sha16>/` の PNG を目視
3. 当たりっぽいものは `source_path` を控え、元アーカイブごと別フォルダへ退避
4. 残骸は `extracted/` 配下にあるので、より精細にレンダしたい場合は手動で
   Blender に投げ直す

---

## 懸念点・既知の落とし穴

### A. 対象モデルのスタイル不一致リスク

提供されている参照画像（IMG_2211.png）の **シェーディングが滑らかすぎる**。
質感的には Amiga LightWave (1991–1993) より新しい：

- LightWave **PC 版 5.x / 6.x**（1996–2000）の可能性が高い
- 場合によっては Softimage 3D / 3D Studio Max / 自社ツール

**Aminet `gfx/3d/` で該当が出ない場合の Plan B**：

1. Aminet 内の隣接カテゴリ（`mods/`、`mags/`、`demo/`、`game/` など）まで
   `--dir` で広げる。最新のディレクトリ構成は
   <https://ftp.fau.de/aminet/TREE> を参照（旧 `gfx/3dobj/` は廃止）。
2. それでも無ければ Aminet 範囲外。**Internet Archive** の
   - LightWave PC チュートリアル CD（"NewTek Inspire 3D" 等）
   - 雑誌付録の素材集（CG WORLD, 3D World, Amiga Format カバーディスク）
   などを別ルートで取得する必要あり。これは現スクリプトの守備範囲外。
3. または対象が **オリジナル制作素材**（流用なし）の場合、Aminet 探索は徒労。

### B. 展開系の不安定性

- **LZX**: Amiga 固有圧縮。Windows 環境の 7-Zip でも展開失敗するケースあり。
  失敗時は Aminet の `unlzx` を別途入手し、手動で `.lzx` を展開してから
  `extracted/<archive_stem>__<hash>/` に中身を投入し、`run_pipeline.py` を
  Step 2 から再開（=普通に再実行で OK、Step 1 で同じ展開先に当たれば再展開は
  スキップされず上書き試行になるので、**手動展開分を上書きされたくない場合は
  該当 .lzx を `archives_raw/` から退避してから再実行**）。
- **ADF/HDF**: 古い OFS/FFS イメージで `xdftool unpack` が失敗することあり。
  失敗時はログを見て、別の Amiga エミュレータ（FS-UAE など）でマウントして
  手動コピーが必要。
- **LHA**: 大半は 7-Zip で問題ないが、稀にメンバ名がエンコーディング不明
  （Amiga 由来のラテン拡張）で文字化けすることがある。展開はできるので無視で OK。

### C. Blender インポート・レンダ周り

#### Blender バージョン選択

| 選択肢 | サポート | LWO/3DS アドオン | 推奨度 |
|---|---|---|---|
| **4.5 LTS** | 〜2027年7月 | 実績豊富、フォーク多数 | ◎ 一次推奨 |
| **5.0 / 5.1** | 5.0=2025年11月以降, 5.1=2026年3月以降 | アドオン未追従の可能性大 | △ 試して動けば可 |
| 3.6 LTS | EOL（2025年6月終了） | 過去資産あり | ✕ 非推奨 |

Blender 5.0 で EEVEE のエンジン識別子が `BLENDER_EEVEE_NEXT` → `BLENDER_EEVEE` に
改名（旧 EEVEE は `BLENDER_EEVEE_LEGACY`）。`blender_render.py` は両方を順に試す
fallback 実装なので、エンジン名の差は気にしなくて良い。

**5.x が既に手元にある場合の運用**:

1. まず 5.x で `python blender_render.py` を試す
2. `logs/render_errors.log` に LWO インポート失敗が並ぶようなら 4.5 LTS
   ポータブル版 (<https://www.blender.org/download/lts/>) を別ディレクトリに展開
3. レンダ用コマンドを 4.5 LTS の `blender.exe` に切替

Blender はインストーラ版とポータブル版が共存可能。

#### その他のクセ

- **LWO アドオンのバージョン依存**: Blender 4.x で動くフォークと 3.x 用が
  別。複数フォークが共存するなら片方だけ有効化する。
- **LWOB（初期形式, 1990 年代前半）**: 一部のアドオンは LWO2 のみ対応。
  LWOB は読めないことがある。`logs/render_errors.log` で確認。
- **3DS アドオン**: Blender 4.x ではコアから外れた。Extensions プラットフォーム
  から入れる。
- **無限ループ・ハング**: 巨大シーンや破損モデルで `bpy.ops.render.render` が
  返らないことがある。Blender プロセスごと kill して、当該候補を
  `output/candidate_models.csv` から除外して再実行。

### D. 候補抽出ロジックの既知のクセ

- **キーワード "man" の過剰一致**: `human` `german` `manage` 等もヒットする。
  ヒット件数を絞りたい場合は `pipeline/config.py` の `KEYWORDS` から `man` を
  外し、代わりに `_man_` `man.` 等の境界付き正規表現に書き換える。
- **`identify.py` のスコアの偏り**: スコア関数は `.lwo` / `.lwob` 拡張子と
  シグネチャ・ファイル名にしか加点しない。`.obj` / `.3ds` / `.geo` / `.lws`
  はキーワード一致と同等の重みなので、上位ソート結果が偏ることがある。
  気になる場合は `pipeline/identify.py` の `score()` を編集。
- **`.iff` の FORM 検出**: IFF は音声（8SVX）・画像（ILBM）でも `FORM` 始まり。
  音声サンプルが混入することがあるので、`source_path` のディレクトリを
  目視確認するクセを付ける。

### E. 類似度判定の限界

- **背景・ライティング差**: imagehash は画像全体の構造を見るので、
  - 参照画像の背景（緑のラジアル）と
  - レンダ画像の背景（透明 or 単色）

  の差がそのまま距離に乗る。**前処理で参照画像を切り抜く / 単色背景に置く**
  と劇的に改善することがある。
- **アングル差**: LightWave 素材の正面と参照画像の正面が一致しない場合、
  `threequarter` のほうが距離が小さく出ることがある。`best_view` を
  ちゃんと見る。
- **解像度・色味**: 512×512 PNG のレンダ vs 元画像（解像度・色域不明）の
  差が phash の 4–8 ビット程度に乗ることがある。
- **より強い手段**: phash で絞り込めない場合は **CLIP embedding** に切り替え。
  `open_clip_torch` と参照画像 / レンダ画像の cos 類似度比較に差し替えれば
  「驚いた表情の頭部モデル」のような **意味的類似度** で取れるようになる。
  ただし依存が重く、CPU でも動くが GPU があるとずっと速い。

### F. ストレージ・運用

- **ディスク容量**:
  - `archives_raw/` (`gfx/3d/` 全件で 数百 MB)
  - `extracted/` (展開後は元の 2–3 倍に膨らむ可能性)
  - `renders/` (1候補 3 PNG × 数百候補 = 数百 MB)
  - **合計で 1〜2 GB 程度**を目安に空きを確保
- **ネットワークマナー**: `--sleep` のデフォルトは 0.5 秒。**短くしすぎない**
  （ミラーに迷惑、403 食らうリスク）。
- **中断・再開**: `collect_aminet.py` は冪等。`run_pipeline.py` も再実行で
  既存ファイルは re-scan されるが副作用は無い（CSV 上書き）。
  `blender_render.py` は **既存 PNG を上書きする**ので、再開は `info.json` を
  見て手動で済んだ候補を `candidate_models.csv` から外す。

### G. このリポジトリでカバーしていないこと

- アーカイブ取得元の **Aminet 以外への拡張**（Internet Archive、雑誌カバー
  ディスク、NewTek 公式素材等）
- **CLIP / 深層モデルによる類似度判定**（imagehash ベースのみ）
- **モデルの構造的解析**（ポリゴン数・頂点数・トポロジ等）
- **アーカイブの法的取り扱い**（再配布可否はアーカイブごと別）

---

## クイックリファレンス

```cmd
:: 0. 環境
pip install -r requirements.txt

:: 1. 収集（推奨スタート）
python collect_aminet.py --filter-readme

:: 1b. 別カテゴリへ拡張（必要なら）
python collect_aminet.py --dir mods/ --filter-readme

:: 2. 展開・走査・候補抽出
python run_pipeline.py

:: 3. レンダ
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --python blender_render.py

:: 4. 類似度ランキング
python compare_renders.py --reference references\IMG_2211.png --top 30

:: 5. 確認
notepad output\similarity_ranking.csv
explorer renders
```

---

## 上手くいかなかったときの判断フロー

```
collect_aminet.py で 0件 ────────────► A. 対象モデルのスタイル不一致 (上記)
                                        ─→ Plan B (Internet Archive 等)へ

run_pipeline.py の候補が 0 件 ──────► KEYWORDS / CANDIDATE_EXTENSIONS を見直し
                                        scan_results.csv を直接 grep してみる

候補は出るが Blenderインポート全滅 ─► LWO アドオンのバージョン不一致
                                        render_errors.log を確認

レンダはできるが類似度上位が雑音 ──► 参照画像の背景除去・正方形クロップ
                                        --method を dhash/whash に切替
                                        さらに駄目なら CLIP に差し替え

そもそも全部回しても本命が出ない ──► 対象が Amiga/LightWave 系でない可能性
                                        プロジェクトの前提から見直す
```
