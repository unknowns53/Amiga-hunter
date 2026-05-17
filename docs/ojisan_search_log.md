# ojisan 探索ログ

`references/ojisan/ojisan.png`（驚き顔のおじさん、PS1 用 RPG「アンシャントロマン」
1998 年 4 月 23 日発売・日本システム発売・風雅システム開発関与、由来の
3D モデル）の元データを掘り当てるためにこれまで何を回したか、何が
残っているか、を一枚にまとめる。

設計や API は [`README.md`](../README.md)、操作手順は
[`RUNBOOK.md`](RUNBOOK.md)。本ドキュメントは「探索の地図」に絞る。

---

## 1. 探索のターゲット

- 参照画像: `references/ojisan/ojisan.png`（および `_trimmed.png`）。くだん視覚比較用のキャプチャは `references/kudan/kudan{1,2,3}.{jpg,png}` に格納。
- 出所: **PlayStation 用 RPG「アンシャントロマン」**、1998 年 4 月 23 日発売、
  **日本システム** 発売、開発に **風雅システム** が一部関与。
  **PC-9821/Win95 ではない**（過去の PC ゲーム前提は破棄）。
- 特徴: 正面寄りの男性頭部、口を大きく開けた驚き顔、肌は明るい褐色寄り、髪は黒。
- **判定基準の修正**: 参照画像がスムースに見えるという「レンダリング質感」を
  Amiga/LightWave 初期素材の除外根拠にしてはいけない。判定は
  **メッシュ形状**、特に **頭髪形状・鼻・顎・頬・口周辺** の幾何で行う。
  低ポリでも該当形状なら本命の可能性あり。
- **CLIP 全体類似度の限界**: CLIP の全体類似度は「雰囲気」（暗肌・正面顔・
  暗髪 etc.）に引っ張られて、形状違いの偽陽性が top に並ぶ。最終判定で
  CLIP スコアを単独で使ってはならない。形状ベースの比較軸を併用する
  （詳細は 3.5）。
- 参照フレームを増やす方針は **低優先**: 原作 OP は静止ポーズから爆散
  するだけで、有効な別角度・別表情フレームは得られない見込み。
  代わりに **参照側の分割 ＋ 候補側の多角度レンダリング** で比較軸を増やす。
- 時代制約（**2026-05-11 修正**）: アンシャントロマンは 1998-04-23 発売だが、
  **1997 年中の体験版時点で既におじさんモデルが完成していた**ことが判明。
  したがって素材化は **〜1997-12-31** まで。媒体側のリリース日が 1998 年に
  食い込むものは（中身の LWO 日付が 1997 年でも）原則除外。
  例外は仕様変更前の cutoff に従って導入済みの v6 系 / 1998-03 LIGHT-ROM 6
  / Oh!X 1998 Spring 系で、いずれも体験版より後の媒体なので新規取得対象から
  外している。
- 目的: パイプラインで素材アーカイブを総ざらいし、CLIP 類似度＋目視で
  本人と思われる `.lwo` / `.lw` / `.obj` / `.3ds` などの 3D データを特定する。

---

## 2. 調査済みソース

### 2.1 Aminet（HTTP ミラー、`collect_aminet.py`）

| カテゴリ | アーカイブ数 | メモ |
|---|---|---|
| `gfx/3d/` | 約 413 | LightWave/Imagine の素材総合カテゴリ。フル展開済み |
| `pix/3dobj/` | 5（頭部関連） | Imagine TDDD 形式。`imagine_tddd_to_obj.py` で OBJ 化済み |

メモ: 既定ホスト `us.aminet.net` が現在動いていない件は
`memory/aminet_mirror.md`。実運用では別ミラーを差し替えるか、IA から
取り直す必要がある。

### 2.2 Internet Archive（`collect_internet_archive.py`）

`pipeline/config.py::INTERNET_ARCHIVE_IDENTIFIERS` に登録済みの
identifier すべて。

| Identifier | 種類 | サイズ感 | 主な中身 |
|---|---|---|---|
| `CommodoreAmigaApplicationsADF` | ADF 群 | 中 | LightWave 名義 65 ファイル |
| `commodore-amiga-applications-public-domain-adf` | ADF 群 | 中 | "A-Z of Lightwave Objects" 等 15 ファイル |
| `video-toaster-v4.0-intstallation-disk` | ADF 群 | 小 | Toaster 同梱 2 ファイル |
| `lightrom1` | ISO 1 枚 | 678 MB | 約 3000 Imagine TDDD ＋ 多数の LightWave LWO/LW（`LIGHTWAV/ANATOMY/`、`LIGHTWAV/SPACE/`、`LIGHTWAV/MISC_/` など） |

### 2.3 パイプライン処理結果（2026-05-10 時点）

- 候補抽出: **13157 件**（`output/candidate_models.csv`）
- レンダ済み: **4183 件**（`renders/<sha16>/{front,threequarter,side}.png`）
- レンダ不能で永続スキップ: 582 件（Blender が EXCEPTION_ACCESS_VIOLATION
  でクラッシュする LWO。`render_with_recovery.py` の sentinel ＋
  resume checkpoint で 26 パスかけて回収しきった）

### 2.4 CLIP 類似度ランキング（top）

| 順位 | スコア | 名前 | 出所 |
|---|---|---|---|
| #1 | 0.7335 | `womanhead.obj` | Aminet `gfx/3d/` Microbe3D-demo |
| #2-3 | 0.7168 | `HEAD.LW` | LIGHT-ROM 1 `LIGHTWAV/ANATOMY/DANCER`, `DANCER2` |
| #4 | 0.6633 | `ALIENPOD.LW` | LIGHT-ROM 1 `LIGHTWAV/SPACE`（CLIP 偽陽性、宇宙繭） |
| #5 | 0.6488 | `TEETH.LW` | LIGHT-ROM 1 `LIGHTWAV/MISC_/DENTAL`（歯列） |
| #6 | 0.6459 | `MANIKIN2.LW` | LIGHT-ROM 1 |
| #7-11 | 0.6450 | `HEAD.lw` | A-Z of Lightwave Objects Disk 3（複数経路） |
| #18/28/29 | 0.6224〜0.6125 | `head.obj` | Aminet `pix/3dobj/`（複数経路、Imagine TDDD 由来） |

### 2.5 視覚的判定

トップの `DANCER/HEAD.LW`（s=0.7168）は **女性顔・赤い唇** で性別と
顔立ちが参照と異なるため別物。CLIP は「正面・人間頭・暗髪」のセマンティックで
点を上げているだけ。

**判定基準の注意**: レンダリング質感（フラット低ポリ vs スムース）を
除外根拠に使ってはならない。同じメッシュでもレンダラ設定で見た目は
変わる。判定は **メッシュ形状**、特に **頭髪形状・鼻・顎・頬・口周辺**
の幾何（シルエットと立体構造）で行う。Amiga 期の低ポリモデルでも、
形状が一致するなら本命の可能性がある。CLIP 全体類似度は雰囲気に
引っ張られるので、最終判定では形状ベースの比較軸（次節 3.5 参照）を
併用する。

**結論: 現状の Amiga / Internet Archive 範囲には ojisan の本命は
存在しない。** 別ソースが要る。

---

## 3. 今後の探索対象

**時代制約: アンシャントロマンは 1998 年発売**。開発期間を加味しても、
モデルの素材化は **〜1998 年前半** までに流通していたはず。これより
新しい素材（LightWave 6 以降、Inspire 3D、3DS Max 3 以降など）は
タイムラインで除外。優先度は仮、IA に該当アイテムがあるか要調査。

### 取得状況メモ

2026-05-10 時点で：

- **Tier A 11 件**: 全件取得（最初 10 件、`inlw-3d-55` は 4 回目のリトライで成功）
- **Tier B 6 件**: 5 件取得（imagine-3D-for-DOS、Caligari_trueSpace-3、
  3-d-studio-viz-demo、caligari-truespace2-bible、3dsmax2.5）。
  **`3d-artist-volume-1` の 2.9 GB ISO は 5 回連続 HTTP 500** で持続失敗。
  メタデータは正常で、`discimagecreator logs.7z` (55 KB) は取得できる
  のに ISO だけ配信できない状態。IA 側のファイル単位の問題と思われる。
  代替案: torrent (`inlw-3d-55_archive.torrent` のような IA 配布 torrent)
  で取得 or 数日置いて再試行。

候補数の推移：
- 開始（LIGHT-ROM 1 まで）: 13157
- Tier A 完了: 20143（+6986）
- LWAPPLIED 修復: 20820（+677）
- Tier B + inlw-3d-55: 21500（+680）
- 3dsmax2.5: 21531（+31、`.max` 未対応のため少なめ）

### 中間 CLIP 結果（render 6047/21531 = 28%）

GPU CLIP 51 秒で 21820 枚 encode、top スコア前進：

時代制約 OK：
- **#1-2 NURBNERD.LWO (s=0.7564)** — New Tekniques Subscriber Content CD (1997)
  `LIGHTROM/LW3_5/OBJECTS/ANATOMY/NURBNERD/`。**前回最高 0.7335 を大幅更新**。
  視覚確認: 滑らかな男性ヘッド・髪なし・無表情・目だけ青色。
  ojisan の驚き顔・髪あり・褐色肌・大きく開いた口とは **別物**。
- **#3 FACE2.LWO (s=0.7428)** — Inside LightWave 5.5 (1998) 練習教材
  視覚確認: 細長い女性顔・大きな目・赤い唇のコミック調。**別物**。
- #26 DRAGFACE.LWO (s=0.6957) — Inside LightWave 5.5

時代制約 NG（除外、CLIP の偽陽性として参考のみ）：
- LightWave 7.5 (2001) Content の Asian_Female / Asian_Male / Asian_Child /
  Caucasian_Child / African_Child / Frankenstein / TaronHead / GradientHead
  などが top に多数。CLIP は名前ラベルを見ているわけではないが、これらは
  PC 期スムースシェーディング・正面顔のセマンティックで自然に高スコアを
  取る。本命候補ではない。

**現時点の判定**: Render は 28% 完了、残り 15484 件未処理。これまでの
top 候補はすべて視覚的に ojisan と異なる。残りの render 完了後に
再ランキングが必要。

### 最終 CLIP 結果（render 全件 8860 sentinel / 10279 対象、24552 image encode）

51 passes で render 完了。GPU CLIP 1 分で再ランキング。

時代制約 OK の上位、視覚確認結果：
- **#1-2 NURBNERD.LWO (s=0.7564)** ← New Tekniques 1997。**別物**（髪なし、無表情）
- **#3 FACE2.LWO (s=0.7428)** ← Inside LW 5.5。**別物**（コミック調女性顔）
- **#4 womanhead.obj (s=0.7335)** ← Aminet 既知
- **#7 head.lwo (s=0.7185)** ← TaftDemos (Worley)
- **#10-11 HEAD.LW (s=0.7168)** ← LIGHT-ROM 1
- **#28 DRAGFACE.LWO (s=0.6957)** ← Inside LW 5.5
- **#34-36 CAPTAIN.LWO (s=0.6946)** ← LWAPPLIED + New Tekniques 1997 の **ANATOMY/CAPTAIN/**。男性キャプテン全身
- **#39 MAN_ANCHOR.LWO (s=0.6876)** ← Inside LW 5.5
- **#42 MANNURBCLSD.LWO (s=0.6870)** ← Inside LW 5.5
- **#43 BIO_FACE.LWO (s=0.6847)** ← Bonus Content 1997 の Biomech
- **#46-48 HEAD_C.LWO (s=0.6831)** ← **男性・暗肌・黒髪オールバック・無表情**。
  特徴一部一致だが**別人**（驚き顔ではない、髪型違う）。

時代制約 NG の偽陽性（除外）：LightWave 7 (2001) Content の Asian_Female /
Asian_Male / Asian_Child / Frankenstein / TaronHead など多数。

### 重要な発見

**CAPTAIN フォルダ**（`LIGHTROM/OBJECTS/ANATOMY/CAPTAIN/`）は男性
キャラ「キャプテン」の全パーツセット：CAPTAIN.LWO（全身）、HEAD_C.LWO
（頭部）、LHAND_C / R_HAND_C（手）、BLASTER（武器）、TORSO_C / TORSO1_C
（胴体）、L_EYE_C / R_EYE_C（目玉）、LEFT_T_1 / RIGHT_1 / RIGHT_2 等
（パーツ）。

ojisan とは別人だが、**「PC 期スムースシェーディング・暗肌・黒髪・
男性キャラの素材集」という同系統の素材集**である可能性が高い。
アンシャントロマンの素材も LIGHTROM 系の **派生ライブラリ**から来て
いる可能性。

### ROMAN.LWO 解決（2026-05-10）

`LWAPPLIED/LIGHTROM/OBJECTS/ANATOMY/ROMAN/ROMAN.LWO`（55273 verts /
83914 polys、LWOB 形式）。Blender LWO アドオンが C-level クラッシュ
する件は `pipeline/convert.py` に独立 LWOB→OBJ パーサ
（`parse_lwob` / `_parse_lwob_pnts` / `_parse_lwob_pols` / `_triangulate`）
を実装して解決。OBJ 経由で Blender 5.1 が問題なく取り込めた。

レンダ結果（`renders/1c76530595d330a2/`）：
- **コリント様式ヘルメット＋甲冑＋スカート＋槍を持った古代ローマ兵士の
  全身像**。ANATOMY/ROMAN/ は字義通り「ローマ兵士の解剖学アセット」。
- 「アンシャントロマン」のタイトルとは無関係（命名の偶然一致）。
- 全身像で頭部は遠く、ojisan の褐色肌・驚き顔とは完全に別物。

**結論: ROMAN.LWO は本命候補から除外**。

### import_failed 由来 OBJ の bulk render 結果（2026-05-10）

LWOB パーサが副産物として救済した OBJ のうち、元 LWO が `import_failed`
sentinel を持っていた 1014 件を `build_import_failed_subset.py` で抽出し、
`render_with_recovery.py --candidates output/candidate_models_import_failed_subset.csv`
で render 実行。1008 件 success、6 件は既 render（ROMAN.LWO.obj 等）。
Blender クラッシュゼロ、9 分で完走。

CLIP 再ランキング（27579 image encode、GPU 1 分）：

- **subset OBJ 1014 件のうち、CLIP top 100 入りはゼロ**
- subset OBJ の最高スコアは `DAN_CLOSED.LWO.obj` / `DIGITALDAN.LWO.obj`
  が同点 0.6327（rank 124）。Inside LightWave 5.5 (1998) Ch14 の
  「DigitalDan」キャラクター。視覚確認: 表面に黒い穴（目と口）の
  あいた**宇宙人風アバター**で ojisan とは別物。
- top 100 の下限 0.6459、subset OBJ 最高 0.6327 の間に約 0.013 のギャップ。

**結論: LWOB 救済では ojisan の本命は見つからなかった**。CAPTAIN/HEAD_C
系や ROMAN 系を含む import_failed 群は、Blender が C-level クラッシュで
read 失敗していたとはいえ、CLIP セマンティック上はいずれも本命に近くない
ことが確定した。Tier A + B + LWOB 救済まで含めた素材ソースで本命未発見。

### 3.1 LightWave 同梱サンプル（Tier A）

LightWave コンテンツ系。**1998 年 4 月までにリリースされた版** に絞る。
**質感での絞り込みは行わない**（メッシュ形状の判定が正）。Amiga 期 LightWave
素材も除外せず、PC 版と同列に扱う。

- **NewTek LightWave 3D 4.0**（1995）の Content CD
- **NewTek LightWave 3D 5.0**（1996）の Content CD
- **NewTek LightWave 3D 5.5**（1997）の Content CD
- **NewTek LightWave 3D 5.6**（1998）の Content CD（時代的にギリギリ）
- 解説書付録の Companion CD（"Inside LightWave 3D 5.5"、"LightWave 3D
  Applied 5.6" など）
- 参考までに除外: LightWave 6（2000）以降、Inspire 3D（2000）、
  LightWave 7/8/9。発売年がアンシャントロマンより後のため本命では
  ありえない（ただし CLIP の偽陽性検証用には流しても害はない）

調査メモ: `archive.org/details/?query=lightwave+content` や
`?query=newtek+lightwave+3d+5` で identifier を探す →
`INTERNET_ARCHIVE_IDENTIFIERS` に追加するだけでパイプラインは流せる
（拡張子は既定で `.lwo` `.lwob` `.lw` `.iso` 対応済み）。

### 3.2 雑誌付録 CD（Tier A）

3DCG 雑誌・CG ムック付録 CD のサンプルモデル。アンシャントロマンが
**1998 年 4 月 23 日** 発売であることから、**1998 年 4 月以前に発行**
されたものに絞る。**1997 年以前の日本系 CG ムック付録 CD を最優先**。

- **3D Artist**（米、1990 年代前半〜中盤）。Vol.1 の 2.9 GB ISO は IA で
  HTTP 500 失敗中。**年代は ISO 内のラベル・ファイル日付で確認するまで
  中立扱い**（Vol.1 全体が 1998 年以前とは限らない）。
- **3D Design**（米、1990 年代前半〜中盤）
- **Computer Graphics World**（米、付録 CD 多数、1990 年代）
- **3D World Magazine**（英、創刊 1997 年）。初期号のみ該当
- **DTPWORLD** / **MdN**（日、3DCG 特集回の付録、〜1998 年 3 月の号）
- **CG ムック・別冊本**の付録 CD（日、1995〜1997 年。"3D グラフィックス
  パーフェクトガイド" など）
- **Amiga Format** 付録 CD（〜1998、Amiga 期だがクロス確認用）
- **除外**: **CGWORLD** は **1998 年 7 月創刊**で、ゲーム発売（1998 年 4 月）
  に間に合わない。素材元候補から外す。

検索キー: `archive.org/details/?query=3d+artist+magazine+cd`、
`?query=3d+graphics+japan+1997` など、年代を絞るのが重要。

### 3.3 他の 3D ツールのサンプル（Tier B）

LightWave 以外の経路の可能性。**〜1998 年版** に絞る。

- **Imagine PC 版**（Impulse、`.iob` 形式が中心、〜1996 まで）
- **3D Studio R3 / R4**（DOS、1993〜1995）/ **3D Studio MAX 1.x / 2.x**
  （Windows、1996〜1997）。`.3ds` / `.max`
- **Softimage 3D**（〜1998）チュートリアルアセット
- **Real 3D v2**（〜1995）/ **Real 3D 3**
- **trueSpace 2 / 3**（Caligari、1995〜1997）
- **Strata Studio Pro**（Mac、1990 年代中盤）

メモ: `.iob`（Imagine PC）と `.max` は現状パイプラインで未対応。`.3ds` は
Blender アドオン経由で読めるので問題ない。`Softimage 3D` の `.hrc`
シーンも未対応だが、書き出しの `.obj` があれば問題ない。

### 3.4 ゲーム由来の流通モデル（Tier B）

「アンシャントロマン」（**PlayStation 用 RPG**、1998 年 4 月 23 日発売、
日本システム発売、開発に風雅システム関与）が他作品やフリー素材集の
モデルを流用しているなら、ゲーム本体や同時代のファンアーカイブが本命の
可能性。

- **アンシャントロマン**自体の解析（PS1 ディスクからの抽出、元データ取得は
  著作権上グレー、要相談）
- 当時の「3D モデル素材集」CD-ROM（日本ではボーンデジタル、グラフィック社、
  ソフトバンク等が 1995〜1998 に出していた）
- 同時期の **日本システム / 風雅システム** の他作品の素材確認
- Vector / 窓の杜の 1998 年以前のフリー 3D モデル配布

### 3.5 次の重点（2026-05-10、ChatGPT 助言反映）

これまでの探索で本命未発見。前提修正（PS1 用 RPG、日本国内向け、1998 年 4 月）
を踏まえて、優先順位を以下に組み直す。**判定品質の向上（A 系）と素材
ソースの追加（B 系）を並走**させる。

#### A. 判定品質の向上（参照側分割＋候補側多角度）

参照フレームを増やす方針は破棄（OP は静止ポーズ→爆散で別角度/別表情が
取れない）。代わりに以下で比較軸を増やす。

- **A1. 参照画像の分割マスク作成（2026-05-10 完了）**:
  `build_reference_variants.py` で `ojisan_trimmed.png` を flood-fill 背景
  分離 → 縦バンド分割（HAIR 22% / FACE 50% / TORSO 28% of fg bbox）→
  各バンドのグレースケール・Canny edges・silhouette・全体 Otsu binary を
  `references/ojisan/ojisan_*.png` に書き出した（26 ファイル）。所見：
  - **silhouette は弱い**: trimmed 画像は既に頭部クローズアップ寄りで
    人物が画面 66% を占めるため、silhouette がほぼ正方形に近く形状軸
    として識別力が低い。**全身体型比較は不可**と確定。
  - **edges 系は決定的に有効**: `head_edges.png` で髪の生え際・頭部輪郭・
    両耳・眉・目・鼻・口・顎のラインがすべて鮮明。`hair_edges.png` で
    髪型の特徴（頂上の丸み・両側の張り出し・水平な生え際）が明確。
    形状ベース判定の主軸はこれら edges 派生。
  - **binary も有効**: Otsu 二値化で陰影が明暗分離され、立体構造の手
    がかり（頬骨・鼻筋・口の影）が残る。光の当たり方の特徴量として
    機能。
  - 派生一覧: `ojisan_{head,hair,face,torso,all}.png`（RGB 切り抜き）
    と `_gray.png` `_edges.png` `_silhouette.png`、加えて `ojisan_binary.png`
    （全体 Otsu）。
- **A2. CLIP の使い方の修正（2026-05-10 完了）**:
  `compare_renders_shape.py` で Canny edges IoU（dilated, 2px）＋
  symmetric chamfer の合成スコア（0.5 IoU + 0.5 chamfer）を実装。
  reference は `ojisan_head_edges.png`、候補は各 render の foreground
  bbox を 256x256 正方化してから edge 化。
  - **CLIP top 200 への適用結果**: 上位は head.obj (Aminet, 0.4392) /
    Skull_High / Caucasian_Male / HEAD_C.LWO / FACE.LWO / BIO_HEAD /
    DRAGFACE / FACE2.LWO / womanhead / DigitalDan / NURBNERD など。
    時代制約 OK で未確認だった BIFF_HEA.LWO（Inside LW 5.5 Ch07、
    禿頭の男性）と Face2.iob.obj（Anatomy アーカイブ、Imagine PC、
    髪なし渋面）も視覚確認 → **両方とも髪なしで別物**。
  - **形状 top の全候補が「髪なし or 髪型違い or 口閉じ」** で、
    ojisan の「短黒髪・水平生え際・大きく開いた驚き口」と
    一致するものは無し。**CLIP top 200 内に本命なし** が確定。
  - **全件 9193 件への shape 適用は失敗**: 全件 ranking では top 30 が
    建物（EPCOT.LW、SchoolhouseShell、CITYGRID）・家具（DRESSER、
    Dartboard）・地図（NEBRASKA）・ロゴ・木・タイヤ等で埋まる。
    Canny edges のIoU+chamfer は **エッジ分布の一致** しか見ないので
    人間頭部ですら絞れない。**形状ベースは CLIP 二段フィルタとして
    機能、CLIP 圏外救出には使えない**。
  - 結論: CLIP top 200 内には本命未発見、shape 単独では救出不能。
    既存データセット内には ojisan の本命は存在しない可能性が高い。
    **本質的問題は CLIP の雰囲気バイアスではなく素材ソース不足**で
    あり、B 系（素材ソース追加）に重心を移すべき。
- **A3. 候補モデル側の多角度・多条件レンダリング（A2 結論で優先度
  低下）**: A2 で CLIP top 200 内には本命なし、全件 shape は使えないと
  判明したため、A3（追加 render）も既存データに対しては効果が薄い。
  新規取得した素材（B 系）に対してから着手する方が効率的。
- **A4. 既存 top 候補の再評価（A2 で実施済み）**: 形状ベース shape
  ランキングで順位は劇的に変わったが、結論は不変。CLIP top の
  「同系統だが別人」評価は形状ベースでも変わらない。

#### B. 素材ソースの追加（日本国内流通寄り）

- **B1. DiscMaster による CD-ROM 横断検索**（discmaster.textfiles.com）。
  1990 年代の CD-ROM のファイル名・拡張子を横断 grep できるサービス。
  "head" "face" "man" などのキーワード＋ `.lwo` `.3ds` `.obj` `.iob`
  拡張子で 1997 年以前の CD-ROM をピンポイントで探す。
- **B2. D-Storm / 国内 LightWave 流通 CD**。D-Storm は日本における LightWave
  公式代理店で、国内向けに独自の Content CD やチュートリアル CD を出して
  いた。**PS1 ゲーム＋日本制作の組み合わせから本命候補として最有力**。
- **B3. 1997 年以前の日本 CG ムック付録 CD**。CG ムック・別冊本（"3D
  グラフィックスパーフェクトガイド" 系、ボーンデジタル / グラフィック社 /
  ソフトバンク刊）の付録。CGWORLD は 1998 年 7 月創刊で間に合わないので
  **対象外**。
- **B4. 3D Artist Vol.1 の年代確認**。HTTP 500 でリトライ後、ISO を取得
  できた時点で **ISO 内のラベル・ファイル日付** を見て、1998 年 4 月以前
  の素材が含まれるかを確認する。Vol.1 = 古い、と即断しない（Vol.1 という
  ナンバリングは必ずしも年代古さを意味しない）。

A 系は既存データに対して即実施可能。B 系は IA / DiscMaster での新規取得が
必要で、A 系の判定品質が上がれば既存データから本命が浮上する可能性も
あるため、A 系を先に走らせるのが効率的。

**着手順（2026-05-10 確定）**: A 系完了 → 既存データに本命なしと確定したので
B 系に完全移行。**B1 (DiscMaster 横断検索) → B2 (D-Storm 国内 LightWave CD)**
の順。B1 が広範囲を一度に当たれて identifier 候補を多数生み出せるため先行、
B2 は B1 の結果から国内 CG 系の identifier が得られなかった場合に
日本国内向け公式チャネルから直接当たる。B3/B4 は B1/B2 の進捗次第。

#### B1 結果（2026-05-11、cutoff 1997-12-31）

DiscMaster の HTTP form は `q=` `extension=` `tsMax=YYYYMMDD` `outputAs=json`
等で叩ける。`output/discmaster/*.json` に head/face/man/male/portrait/character
/atama/kao/kubi/Knight/Hero × .lwo/.lws/.3ds/.obj/.iob のクエリ結果を保存。

**前提修正の経緯**: 当初 cutoff を 1998-04 にして 70+ itemid を集計、上位に
Oh!X 1998 Spring (`Nova_OhX1998Spring_Japan`)、Oh!X 1999 Spring
(`Nova_OhX1999Spring_Japan`)、LIGHT-ROM 6 (`light-rom-6`)、LIGHT-ROM 8
(`light-rom-08`) などを追加候補にしていた。
*ユーザー指摘で 1997 年中の体験版に既におじさんモデルが存在することが判明**
（2026-05-11）。媒体側のリリース日が 1998 年に食い込むものは中身の LWO 日付
が 1997 でも除外、cutoff を **〜1997-12-31** に縮めた。Oh!X 1998 Spring も
発売は 1998-04 のため、本来の本命候補から却下。Light ROM Gold (1998 compilation)
と Best of LIGHT-ROM 1-5 (2000 compilation) も同様に却下（前者・後者ともに
LIGHT-ROM 1/3/4/5 を直接取れば代用可能）。

**新規追加 IA identifier（pipeline/config.py に登録済み）**:

| Identifier | リリース | サイズ | 主な中身 |
|---|---|---|---|
| `light-rom-3` | 1995 | ~1.9 GB (3 discs) | `objects/objects/anatomy/man.lwo` 76 KB、`sit_man.lwo` 147 KB、`guy_face.lwo` 14 KB、`acuris/man_hand.lwo`、`acuris/japan.lwo` 233 KB 等 |
| `light-rom-4` | 1996 | ? | `lw3_5/objects/anatomy/angel/face.lwo` 524 KB、`f_maturi/robotech/head.lwo` 等 |
| `lightrom5` | 1997 | 3 discs | **最有力**。`mikebeal/captain/head_c.lwo`、`jamicope/walk/head.lwo`、`anatomy/walk/head.lwo`、`anatomy/hero/hero.lwo` 388 KB 等 |
| `lightwavinmagazine_issue02` | 1997-01 | ~266 MB | `article/charactr/objects/heads/head.lwo` |
| `LWPRO-Book-CD` | 1997 | ? | "The Lightwave 3D Book - Tips, Techniques & Ready-To-Use Objects"。`objects/bodypart/head.lwo` |
| `US3DEXTREME1` | 1996 | ~599 MB | `plugins.lw/anatomy/man.lwo` 468 KB |

**却下した候補と理由**:

| Identifier | 却下理由 |
|---|---|
| `Nova_OhX1998Spring_Japan` | リリース 1998-04（体験版より後）。中身は MODEL/Knight/Obj/GRA-KAO.LWO（顔）、TAU-ATAMA（頭）、WD-KUBI（首）など日本語ローマ字命名のインディーゲーム "BLACK" 素材で興味深いが、媒体リリース日基準でアウト |
| `Nova_OhX1999Spring_Japan` | リリース 1999（体験版より大幅に後） |
| `light-rom-6` | リリース 1998-03（体験版より後） |
| `light-rom-08` | リリース 1999 |
| `LightROMGold` | 1998 compilation。LIGHT-ROM 1/3/4/5 を直接取れば代用可能 |
| `the-best-of-light-rom-1-thru-5` | 2000 compilation。同上 |

**保留**:
- ibm1210-1219 / ibm1480-1489（McDonald's Farm content from LWBONUS1）は
  既存 `newtek_bonuscontentforlightwave3d` と中身重複の可能性が高く、二重
  取得する価値は低い。優先順位下位。
- `Hot Mix 14` / devcon CD / `Shareware cdrom prog 53` などの大型シェアウェア
  コンピレーションは head/man/face といった汎用キーワードでヒットするが
  内容ノイズが多い。LIGHT-ROM 系を回しきってから検討。

**B1 後の次着手**: 上記 6 identifier を `collect_internet_archive.py` で取得 →
パイプライン展開・レンダ → CLIP 再ランキング。それでも本命未発見なら B2
（D-Storm 国内 LightWave CD）に進む。

#### B1.5〜B1.8 実行結果（2026-05-11、本命未発見）

実行サマリ:
- **取得（B1.5）**: 11 ISO / 6.67 GB を `archives_raw/ia/` に追加。途中
  `archive.org/download/` の redirect 先 CDN ノード `dn7****.ca.archive.org`
  系で広域 HTTP 500 を踏んだので、`collect_internet_archive.py` に
  `direct_url_from_meta()` を追加して metadata API の `workable_servers`
  経由で `ia****.us.archive.org` 直叩きに切り替えて回避（詳細は memory
  `ia_mirror_workaround.md`）。
- **展開・スキャン・識別（B1.6）**: `run_pipeline.py` で展開 1077 アーカイブ、
  scan 171711 ファイル、candidate 87968 件（増分 +59004）。`extracted/` は
  8.3 → 18 GB に膨張。
- **レンダ（B1.7）**: `render_with_recovery.py` で 63350 candidate（24618 件は
  unsupported-extension で skip）を attempt。Pass 70 で Blender 4.5 が
  4.5 時間連続クラッシュなく走り、Pass 71 で checkpoint 完走。
  fully-completed render 25897 件、`info.json` 50287 件、`.render_attempted`
  sentinel 49534 件。残りは LW2 形式や Blender import 不能形式で、形状
  情報が取り出せず CLIP 対象外。
- **CLIP 再ランキング（B1.8）**: 全 163956 render image を RTX 2070 SUPER の
  ViT-B-32 で 10 分でエンコード。`output/clip_similarity_ranking.csv`
  54652 rows。**top スコアは前回と完全に同じ 0.7564（NURBNERD.LWO）**、
  新規 6 identifier 由来で top 60 に入ったのは LIGHT-ROM 4 Disc 1 の
  `MARK.LWO`（rank 16, s=0.7171）と、他は既知素材の別配布経路
  （NURBNERD/HEAD/CAPTAIN/HEAD_C 等が LIGHT-ROM 3/4/5/LightWavin'#2 にも
  同梱）のみ。新規由来 top 候補の視覚確認: MARK.LWO は全身灰色服無表情の
  男性で別人、MALE.LWO は頭部すらない 4 体の torso、HEAD2.LWO はゴーグル
  付きヘルメット — いずれも ojisan の驚き顔おじさんとは形状・素材・
  キャラクター完全に別物。

**結論（2026-05-11）**: LIGHT-ROM 3/4/5 + LightWavin' Magazine #2 + LWPRO Book
CD + US3DEXTREME1 まで含めても本命は出ない。**LIGHT-ROM 系および北米
LightWave 雑誌系の素材ライブラリ全体に ojisan のおじさんは存在しない**
ことが確定。前回確定した「素材ソース不足」の見立てが裏付けられた形。
次は B2 (D-Storm 国内 LightWave CD) に進む。B1 で日本国内由来の identifier
は Oh!X 1998/1999 Spring しか出てこなかったが、それらは体験版（1997 年中）
より後の媒体で却下済み。D-Storm 国内 Content CD（D-Storm Vision、JP LW
体験版など）と 1997 以前の日本 CG ムック付録 CD に当たる必要がある。

#### B2 phase: PS1 SCE 公式開発ツール（2026-05-11 開始）

B2 の方向転換: 当初想定の「D-Storm 国内 LightWave Content CD」は、
D-Storm（NewTek 日本代理店、株式会社ディストーム）が独自ブランドで
1997 年以前に CD-ROM を出していた形跡が Web 検索でほぼ無く、現代も
LightWave 本体のサポートとセミナーが中心。**代わりに SCE 公式の PS1
開発ツール群に重心を移した**。決め手は、アンシャントロマンの開発体制が
「日本システムは本作製作のために設立された会社、開発メンバーは全員
ゲーム制作未経験」（楓牙 X ポスト・ピクシブ百科事典 / ニコ大）と明確で、
ゼロからモデリングする能力が無い素人集団なら **SCE 公式の素材ツールに
同梱されたサンプル 3D モデルをほぼそのまま流用した可能性が極めて高い**
という推定。ojisan はネット上で「**理不尽にも吹き飛んだおっさん**」
としてミーム化（pixiv ID 112794307 等、関連タグ 173 件）しており、
出典が PS1『アンシャントロマン』OP の爆発おじさんと既に広く認知済み。

Tier 6 として `pipeline/config.py` に 3 identifier 追加（cutoff 1997-12-31
内、合計 ~155 MB）：
- `LightwaveForPlayStation` (~58 MB): LightWave 3D 4.0 Intell Rev. C
  Japan、SCE がネットやろうぜ向けに割引配布した本体（1995-1996）。
  examples フォルダにサンプル素材が入ってる可能性。
- `redump-id-69352` (~24 MB BIN/CUE): Graphic Artist Tools Release 1.8
  Japan DTL-S220。DTL-S220 無印 (3D Graphics Tool 1.0) → 1.8 (本物) →
  2.0 (DTL-S220A) → 2.2E (1998-11) の系統の中間バージョン、おそらく
  1996〜1997 中盤リリース。中身は PS1 開発向け 3D 素材ツール ISO。
- `NetYarozeSoftwareDevelopmentDiscs` (~71 MB): DTL-S3040 Japan
  (3.6 MB) + DTL-S3045 EU/USA (67 MB)。1996-06 Japan、1997 EU/USA
  リリース。Net Yaroze 同梱の SDK Disc、3D サンプル素材含む可能性大。

加えて、`ps1_sdks` collection (8.3 GB 全体) 内の単独識別子なしファイル
**`PlayStation Artist Tool - 2D & 3D Graphics Tool (Japan)_redump.zip`
(15.1 MB)** だけを `ia801000.us.archive.org` から `curl` 直叩きで
`archives_raw/ia/ps1_artist_tool_dtls250/` に取得。これは DTL-S250、
DTL-S220 系の後継統合ツールで 1997 中盤推定。collector の identifier
機構を経由しないので、`config.py` には NOTE コメントとして記録。

取得状況: 2026-05-11 10:18 時点で PS1 Artist Tool zip 完了
（15124558 bytes）、残り 3 identifier の collector ジョブが background
で稼働中（log: `logs/ia_b2_acquisition.log`）。完了後は B1 と同じ手順で
extract / scan / render / CLIP rerank を回す。

##### B2 acquisition + extract 結果（2026-05-11 10:20-10:50）

acquisition:
- `LightwaveForPlayStation` (60.8 MB) ✅
- `redump-id-69352` Graphic Artist Tools (.bin + .cue 23.8 MB) ✅
- `NetYarozeSoftwareDevelopmentDiscs` 本家 identifier は HTTP 403/401 ❌
  → ps1_sdks 内ファイル直 URL 取得で 3 つ確保: Net Yaroze 起動ディスク
  Japan (1.37 MB), 本物 SDK Japan (5.71 MB), SDK USA/Europe (78.14 MB) ✅
- ps1_sdks 内 `PlayStation Artist Tool 2D & 3D` 直取得 (15.1 MB) ✅
- 合計 ~200 MB / 4 system + 2 boot disc 取得。

extract（PS1 BIN/ISO 全部 Mode 2 Form 1 raw image で 7-Zip 標準では開けず）:
- `bin2iso.py` を新規実装。2352 B/sector → 2048 B/sector の user-data
  だけを抜き出して標準 ISO 9660 化。Mode 2 Form 2 audio/streaming
  sector は skip、Mode 1 / Mode 2 Form 1 のみ書き出す。
- `extract_b2_ps1_discs.py` で 6 ディスクを一括変換 + 7z 展開:
  - LightWave 3D 4.0 Intell Rev. C Japan: **1526 files extracted** ✅
    （`extracted/_ps1_lightwave_4_jp/contents/CONTENT/OBJECTS/` 配下に
    APEBOT/COWBOY/JUN-Y/HUMAN/BERETTA/AVIATION 等 53 カテゴリ、計 734 LWO）
  - Graphic Artist Tools 1.8 Japan DTL-S220: **564 files extracted** ✅
    （`extracted/_ps1_graphic_artist_tools_1_8_jp/contents/` に
    3RDPARTY/LIGHTWAV/LW3D_PS.ZIP, ALIASWAV/ALIAS.LZH 含む。中身は
    LightWave → PS1 RSD converter プラグインと Alias|Wavefront PSX 用 doc 群、
    3D サンプル素材は TMD 3 file のみ）
  - Net Yaroze SDK Japan DTL-S3040: **291 files extracted** ✅
    （GNU + PSX dir のみ、3D 素材 0）
  - PS1 Artist Tool DTL-S250: ❌ cd_image.iso が ISO 9660 ではなく
    PSX-EXE 単独構成、7-Zip 不可。中身は専用 reader 必要。
  - Net Yaroze Kidou Disc 1.0 Japan: ❌ 起動 PSX-EXE のみ、ファイル
    システム無し。
  - Net Yaroze SDK USA/Europe DTL-S3045: ❌ 同上。

候補数の変化と本命可能性:
- pipeline.scan/identify を skip-extract で再走 → scan 174143 (+2427)、
  candidates 89220 (+1252)。新規 candidate は LightWave 4.0 Japan 由来。
- **重大発見**: LightWave 4.0 Japan 版の `OBJECTS/` 配下は北米版
  LightWave 5.0 Companion (LW50C) / Full (LW50FULL) と sha256 が広範に
  一致。**JUN-Y フォルダ (CHAMO/CHARA1/CHEST/CHAMOU 等の "日本人っぽい
  作者名" カテゴリ) も既に LW50C 経由で取得済みで render+CLIP 適用済み**。
  CHAMO.LWO は rank 1301 (s=0.5879)、CHAMOU は rank 22790 (s=0.5188) で
  ojisan とは似ても似つかず。**JUN-Y は日本独自素材ではなく、北米
  LightWave 5.0 にも継承された汎用 user contribution だった**。
- 真に sha unique で B2 新規な candidate は 259 件のみ（COWBOY/COWBOY.LWO
  含む、LW4.0 Japan 独自バイト列の素材）。`output/candidate_subset_b2_truly_new.csv`
  に抽出し、`render_with_recovery.py --candidates <subset>` で render 中。

PSX-EXE のみ系 3 ディスク（PS1 Artist Tool / Net Yaroze Kidou / SDK USA）
は ISO 9660 ファイルシステムを持たず、3D サンプルが含まれる場合は PSX
binary 内 data section に embedded されている可能性。専用 reader
（jpsxdec / psximager / ghidra）が必要なため、優先度を下げて先に LW4.0
Japan 独自 259 件の render 結果を確認する。

##### B2 render + CLIP rerank 結果（2026-05-11 11:05-11:17、本命未発見）

- **render（B2 phase）**: `render_with_recovery.py --candidates output/candidate_subset_b2_truly_new.csv` を Pass 3 で完走。Blender 4.5 の LWOB v1 importer は LW4.0 Japan 系で連発失敗するが、render_with_recovery の sentinel 機構で 3 pass で確実に全 259 件を attempt 化。
- **CLIP 再ランキング（B2 phase）**: RTX 2070 SUPER ViT-B-32 で 165324 image を 10 分でエンコード。`output/clip_similarity_ranking.csv` 55108 rows（+456）。
- **Top 30 は前回 B1.8 と完全に同一の顔ぶれと数値**:
  - #1-#8 NURBNERD.LWO (s=0.7564)、#9 FACE2.LWO (0.7428)、#10 womanhead.obj
    (0.7335)、#11-12 GradientHead/TaronHead (0.7250)、#13 TaftDemos head.lwo
    (0.7185)、#14-15 dis_hair.lwo (0.7178)、#16-19 MARK.LWO (0.7171)、
    #20-23 LIGHT-ROM 1/3 DANCER HEAD.LWO (0.7168)、#24-25 LW75 Asian_Female
    (0.7106)、#26-27 LW75 Asian_Child (0.7091)、#28 TaronHead_DSS (0.7063)、
    #29-30 LW75 Caucasian_Child (0.7046)。
- **`_ps1_*` 由来 (B2 新規 sha) は top 200 にゼロ**。LightWave 4.0 Japan の
  独自バイト列差分 259 件はいずれも ojisan と CLIP 類似度で勝負にならず。

**結論（2026-05-11、B2 完了）**: **SCE 公式 PS1 開発ツール群（LightWave 4.0
Japan + Graphic Artist Tools 1.8 + Net Yaroze SDK + 取れた範囲の Artist
Tool）を全部展開・render・CLIP しても、ojisan のおじさんは現れない**。
B1 で確定した「LIGHT-ROM 系 + 北米 LightWave 雑誌系には居ない」と合わせて、
**「北米 LightWave 系素材ライブラリ + SCE 公式 PS1 開発ツール由来素材」
の公開アーカイブ範囲では ojisan のおじさんは未発見**（IA に無い国内物理
メディア・個人配布は別途残る）。残る可能性は B3（1997 以前の日本 CG ムック
付録 CD）か、せがれいじり「くだん」共通メッシュ仮説 (C 系)、国内物理メディア
の民俗学調査、開発チームの自作モデル仮説。なお top 24-27 に LW75 の Asian_Female /
Asian_Child が来ているのは CLIP の「アジア人風顔特徴」セマンティクスで
本命に寄っている兆候で、ojisan のおじさんが東アジア系顔立ちであること
の傍証にはなる（ただし LW75 は 2002 リリースで cutoff 超え、素材ソースと
しては失格）。

#### B3 phase: 1997 以前の日本 CG ムック・素材 CD（2026-05-11 開始）

B3 として「1997-12-31 以前に日本国内で流通した CG ムック / 雑誌付録 /
ロイヤリティフリー素材 CD」を IA から漁る方向に進む。最初の網羅検索で
分かったこと：

- **Digital DNA 「3DCG 専門誌 総まとめ」** によると 1990-1997 創刊の日本
  3DCG/VFX 専門誌は **PIXEL（〜1995-02 休刊）** と **Win Graphic（1997 創刊）**
  の 2 誌のみ。CGWORLD は 1998-06 創刊で cutoff 外。
- **Japan Mix 倒産で 3 号廃刊** の "日本初 3DCG & デジタルアニメ専門誌"
  は誌名特定できず、IA 在庫もない。
- **3D WORKSHOP テキストブック 編1（エヴァを動かす、Media JuGGLer）** は
  発売 1998-12-01 で cutoff 外、サキエル + 初号機の素体のみ → 本命外。
- **DOS/V Power Report** 付録 CD は 1996-1997 で 19 号が IA に丸ごと残って
  いるが 1 号 1.3 GB × 19 = 24.7 GB、内容は PC 一般誌（シェアウェア・
  ドライバ・IE/VRML add-in 中心）で 3DCG モデル素材収録は明示されておらず
  優先度は低め。
- **NOURS Magazine** は Namco 発行のアーケード／エンタメ誌で 3DCG 専門誌
  ではない → 除外。
- **A&P CO-ORDINATOR JAPAN（GU/Super GU/Photo Mantan）** は 26 件あるが
  全て **背景写真コレクション** で 3D モデルは含まない → 除外。

IA 在庫を creator 名で精査して残った 1996-1997 日本系 CG 素材は以下 3 件:

| identifier | タイトル | 発売 | サイズ | 形式 |
|---|---|---|---|---|
| KHN-3DGraphic5 | Royalty Free 3D Computer Graphic Vol.5 - Image | 1996-07-11 | 157 MB ISO | BMP 100 枚 + viewer |
| KHN-3DGraphic11 | Royalty Free 3D Computer Graphic Vol.11 | 1997-01-08 | 196 MB ISO | BMP 127 枚 + viewer |
| KHN-Photo-1 | Photo Vol.1 - Joy, Anger, Sadness | 1996-08-06 | 928 MB BIN/CUE | Photo CD 人物表情写真集 |

##### B3 acquisition + extract 結果（2026-05-11 11:25-11:35）

- KHN-3DGraphic5：archive.org 直叩きで完走。`extracted/_b3_khn_3dgraphic_5/`
  に展開（BMP 100 枚 + BMG.EXE/HLP/DLL viewer、各 BMP は 640×480×24bit
  ＝固定 921656 bytes）。
- KHN-3DGraphic11：初回 archive.org/download/ が CDN 500 を返して 170 bytes
  で切れたため `ia_mirror_workaround.md` の手順で `ia800400.us.archive.org`
  直叩きに切り替えて完走。`extracted/_b3_khn_3dgraphic_11/` に BMP 127 枚 +
  viewer を展開（命名は `RFxxx.BMP`＝Royalty Free 連番）。
- KHN-Photo-1 PCD0214.BIN：同じく CDN 500 → `ia800407.us.archive.org` 直叩き
  で再 download 中（執筆時点で取得進行中）。

##### B3 CLIP rerank 結果（2026-05-11 11:33-11:34、本命未発見）

新規 helper `clip_2d_image_match.py` を作って、3D render を経由せず BMP
画像を直接 CLIP ViT-B-32 にかける軸を追加。`renders/<sha16>/` を持たない
2D 画像コレクションは既存の `compare_renders_clip.py` では扱えないため。

- **KHN-3DGraphic 5（100 枚 BMP）**: top1 K3_045.BMP s=0.6083、top10 を
  mosaic で目視すると全て **人体の 3DCG 全身レンダリング（ヌード／ポーズ
  違い）**。「驚き顔のおじさん顔」のような **顔アップ画像は皆無**。
- **KHN-3DGraphic 11（127 枚 BMP）**: top1 RF089 s=0.5781、top10 は
  ボウリングピン・3D ロケット・抽象オブジェクト・卵型・トーラス等で
  **人物すら出てこない**（事前情報通り "space themed"）。
- B1 の最高 0.7564（NURBNERD.LWO render）と直接比較はできない（写真と
  3D render は分布が違う）が、いずれにせよ視覚的に**完全外れ**。

KHN シリーズが CG 静止画レンダリングの **テクスチャ／壁紙素材** であり
3D モデルファイルを含まないことが確定。`_b3_khn_3dgraphic_*` は
「アンシャントロマンの 2D テクスチャ参照元」シナリオも含めて 0 ヒット。

##### B3 KHN-Photo-1 acquisition + 中身判明（2026-05-11 11:36-11:40、本命外）

- IA item title は "Photo Vol. 1 - Joy, Anger, Sadness" だが、IA に preview として
  公開済みのジャケット JPG（sample_1.jpg / SCNIMG_0001.jpg / SCNIMG_0031.jpg）
  を取って `khn_photo1_preview_mosaic.png` で目視した結果、**実際の収録テーマは
  「楽（喜び）」のみ**（"ROYALTY FREE 基礎感情 Series Vol.1 楽"、KN3CG-001、
  KHN Corporation Japan 1996-08）。「Joy, Anger, Sadness」というメタ description
  は誤誘導で、Vol.1 = 喜び単独。Vol.2/Vol.3 以降（怒・哀・驚き）の存在は IA で
  確認できず（creator search は KHN-Photo-1 のみ返却）。
- PCD0214.BIN (487 MB) を `bin2iso` → 7z 展開して `extracted/_b3_khn_photo_1/`
  に 105 枚の `IMG*.PCD`（Kodak Photo CD）+ CDI app を取得。標準 ISO 9660
  経由で取れたので bin2iso ロジック自体は OK。
- ただし PCD は **YCbCr Image Pac で先頭に PCD_OPA ヘッダがない形式**
  （`PCD_IPI` シグネチャはファイル末尾 offset 0x3e3000 に存在）で、Pillow は
  PCD 未対応、ImageMagick 7.1.1 も `improper image header` で reject。CDI フォルダ
  と共存する disc 構造から、これは **Philips CD-i player 向けにカスタマイズされた
  非標準 Image Pac**（OPA を省いて先頭から pixel data 直書き、IPI は末尾）と推定。
- **完遂用に raw Y plane decoder を実装**: ファイル先頭 24576 bytes (192×128) を
  PIL の `Image.frombytes('L', ...)` で grayscale として読む 1 行 fallback。
  99 枚の `IMG*.PCD` 全部を JPG 化し（残り 6 枚は `CDI_APPL.PCD` 等の CDI 用擬似
  拡張子 file で除外）、`extracted/_b3_khn_photo_1_jpg/` に出力。
- **CLIP rerank**: top1 = IMG0010.jpg s=**0.4972**、top10 範囲 0.46-0.50。
  `khn_photo1_top10_mosaic.png` を目視すると Photo CD の delta encoding 由来の
  stripe noise はあるものの、top1-3 に**人物の顔・首・肌のシルエット**が確かに
  浮かぶ → KHN-Photo-1 は人物写真集として実体は正しい。
- それでも:
  (a) スコア帯 0.46-0.50 は B1 最高 0.7564 / KHN-3DGraphic5 最高 0.6083 より
      圧倒的に低く、**CLIP は ojisan と意味的に類似と見做していない**。
  (b) ジャケットから確定の収録テーマは「**楽（喜）**」で、ojisan の「**驚き**
      顔の中年男性」とは感情カテゴリも被写体性別/年齢層も合致しない。
  (c) top1-3 の人物像は CLIP の grayscale × 192×128 制約下でもおじさんとは
      明らかに別物。
  → **KHN-Photo-1 は negative 確定**として B3 phase を閉じる。

**結論（2026-05-11、B3 完了）**: **IA に在庫がある 1997-12-31 以前の日本系 CG
ロイヤリティフリー素材（KHN Corporation Japan の 3DGraphic Vol.5 / Vol.11 と
Photo Vol.1 = 楽）全部を取得・展開・rerank しても、ojisan のおじさんは
現れない**。これで「北米 LightWave 系素材ライブラリ + SCE 公式 PS1 開発ツール
+ IA 在庫の 1996-1997 日本 CG ロイヤリティフリー素材」の **公開アーカイブ範囲**
が clear。IA 在庫の cutoff 内日本 3DCG 媒体は事実上ゼロだが、**IA に存在しない
国内物理メディア（D-Storm 講習 CD、MdN / DTP WORLD / PIXEL / Win Graphic 付録、
ボーンデジタル/グラフィック社/ソフトバンク刊 LightWave 解説本付録）は未検証**で、
これは IA / DiscMaster の自動収集では届かない領域。
次に進むなら以下のいずれか：

1. **PSX-EXE 内 embedded extraction**: B2 で展開できなかった PS1 Artist Tool
   2D&3D / Net Yaroze USA SDK / Net Yaroze 起動 disc の PSX-EXE から、
   jpsxdec で TIM 画像 + TMD モデルを抽出する。可能性は薄いが SCE 純正開発
   ディスクで唯一未確認の領域。
2. **DOS/V Power Report 1996-1997 サンプル取得**: 1 号 (1.3 GB) だけ取って
   付録 CD の 3D サンプル収録の有無を実地検証。クロでない確証が取れたら降りる。
3. **方針転換**: 自動収集型の総当たりから (a) せがれいじり「くだん」共通メッシュ
   仮説の検証、(b) 国内物理メディアのタイトル単位民俗学調査、(c) 自作仮説の
   3 並列ルートへ。CLIP 上位は LW75 Asian_Female といったアジア顔 detector
   ノイズで、市販素材との真の一致は最後まで現れず、これは「公開アーカイブの
   範囲では」見つからないという事実であって「存在しない」ではない。

#### B5 phase: PSX-EXE 内 embedded extraction（2026-05-11 11:50-12:06、本命未発見）

B3 まで terminate した段階で、B2 で「PSX-EXE only、ISO 9660 ファイルシステム
無し」と切った 3 ディスク（PS1 Artist Tool 2D&3D Japan DTL-S250 / Net Yaroze
SDK USA-EU DTL-S3045 / Net Yaroze Kidou Disc Japan）を再訪。実は **jpsxdec
v2.0** にかければ ISO 9660 ディレクトリ構造ごと取れた（bin2iso + 7z 経路では
拾えていなかっただけ）。

##### B5 取得・展開フロー

1. Java 8+ 必須なので Adoptium Temurin JRE 21（Windows x64 portable zip 49 MB）
   を `tools/jre/jdk-21.0.11+10-jre/` に展開（conda openjdk は init 反応薄で断念）。
2. jpsxdec v2.0 を `tools/jpsxdec/jpsxdec_v2.0/` に展開、`jpsxdec.jar` を
   `java -jar` 直接呼びで起動。
3. 3 disc に対して index 作成: **PS Artist Tool 1110 items / Net Yaroze
   Kidou 272 items / Net Yaroze SDK USA 1109 items（計 2491）**。Type 分布は
   File 2297 + Tim 194。
4. `-all image` で TIM 194 → PNG、`-all file` で全 file 抽出。PS Artist Tool
   は GIF 319 / RSD 106 / PLY 106 / MAT 98 / GRP 98 / TIM 49 / TMD 24 / DXF 19、
   Net Yaroze は MODEL/{AP01, CAR, PGIRL, PMAN} 各種で DXF/PLY/RSD/TMD セット。

##### B5 大発見その 1: MEDITOR チュートリアル GIF に「顔モデルの作り方」

PS Artist Tool GIF 319 枚を `clip_2d_image_match.py` で rerank 後、top10 mosaic
（`b5_ps_artist_gif_top10_mosaic.png`）を目視。MEDTUF29 / MEDREN1 / MEDTUF28-34
で **人間の頭部 low-poly モデルの組み立て手順スクリーンショット**（顔の前面・
後面メッシュ、目・鼻・口の各部品、矢印付き組み立て図解）が連続して出てきた。
このチュートリアルは「MEDITOR で人間の顔モデルを作る」教程で、**完成モデル
自体は同梱されていないが、組み立て手順は完全に図解されている**。

→ アンシャントロマンの素人開発陣がこのチュートリアルを参考に自作したシナリオを
強く示唆。

##### B5 大発見その 2: PS1 / Net Yaroze 専用 3D フォーマットの decoder 実装

DXF (StudioPro™ 3d 1.5 の "Flat DXF" 出力、3DFACE entity のみ) と SCE rsdform
PLY (`@PLY940102` magic, v/n/p の 3 block) を独自パーサで OBJ 化:

- `dxf3dface_to_obj.py`: tab/newline 混在の Flat DXF を tokenize、group codes
  10-13 / 20-23 / 30-33 から quad を抽出。31 ファイル変換完走。
- `sce_ply_to_obj.py`: `@PLY940102` magic ＋ `# block counts` + `# vertices` /
  `# normals` / `# polygons` 構造を読む。polygon は `type v1 v2 v3 0 n1 n2 n3 0`
  (9 ints = triangle) または 11 ints = quad の two-cases。102 ファイル変換完走。

合計 133 OBJ を `output/candidate_subset_b5_psx_all.csv` に登録、Blender 4.5.9
+ `render_with_recovery.py` で render → `compare_renders_clip.py` で CLIP
rerank。

##### B5 結果（本命未発見）

CLIP top 20 帯（ojisan 比類似度）:

- #1-2 **PMAN01.obj** (Polygon Man) s=0.5938 view=threequarter
- #3-4 **PGIRL01.obj** (Polygon Girl) s=0.5864 view=front
- #5-6 TIRE.obj s=0.5542
- #7 OBJ5_2.sceply (TUTORIAL/ANIM/TRY3) s=0.5491
- #8 HELI1.obj s=0.5362
- #10 SPHERE.obj s=0.5271
- #16-17 **BOW.sceply.obj** s=0.5165
- #18-19 TAIL.sceply.obj s=0.5148

**スコア帯 0.51-0.59 は B1 最高 0.7564 / B2 最高 0.7565 と比較で圧倒的に低い**。
mosaic 目視判定:

- PMAN01 / PGIRL01: **暗灰色の超ローポリ「棒人間 dummy」**（頭・胴・腕・脚の
  単純構成）、Net Yaroze の puppet sample。顔のクローズアップではない。
- BASE / BLINK / BOW (MIME, MIMEWAVE tutorial): **ワニ・爬虫類モデル**！
  「ミミックアニメーション」のキャラクターは人間ではなく爬虫類のサンプル。
- BOXER00-04: render が真っ黒（material が全黒で出てる、ボクサー全身像のはず）。
- OBJ5_1/2/3: 真っ黒 render（同じく material 問題）。

**B5 結論（2026-05-11 12:06、本命未発見）**: PS1 開発ツール 3 ディスクから抽出
できた 194 TIM + 133 ベクター 3D モデル + 319 GIF いずれにも ojisan の「驚き
顔のおじさん」と一致するモデルや写真は存在しない。TIM は技術 sample（球体・
ボール・ヘリ・コックピット・**猫の目**・"丸"・"1234"）、3D ベクターはアニメ
チュートリアル用 dummy（PMAN/PGIRL/AP01 棒人間、BASE/BLINK/BOW ワニ、BOXER）、
GIF は MEDITOR の操作ガイドキャプチャ。

ただし **MEDITOR チュートリアル GIF に "人間の顔モデルの作り方" の完全な
図解（前面・後面メッシュ、目・鼻・口の各部品、矢印付き組み立て図解）が
ある**ことが判明。これは **自作系シナリオ全般（チュートリアル参考自作 /
MEDITOR サンプル流用改変 / ゼロから自作）の有力傍証**となる（流用元の完成
モデル自体は PS1 開発ツール内に無いため「公式サンプルそのまま流用」とは
言えない点に注意）。

### 3.6 残る検証ルート（"打ち止め" ではなく方針転換、2026-05-11 ChatGPT 助言反映）

公開アーカイブ範囲（Aminet + IA + LIGHT-ROM 1-5 + 北米 LW + SCE 公式 PS1
開発ツール + IA cutoff 内日本 3DCG 3 件）が空振りに終わったとはいえ、
「存在しない」ではなく **「取得・展開・レンダリング・比較できた公開アーカイブ
範囲では未発見」**。未収載の国内 CD、個人配布、雑誌付録、改変後で見た目が
大きく違うケースは依然残る。残る検証ルートは 3 つ並列に存在する。

#### 3.6.1 くだん共通メッシュ仮説（C 系、2026-05-11 一次調査完了）

初期手がかり「**せがれいじり**（1999-06 ENIX 発売、
BRAIN DOCK + NEMESYS 開発、秋元きつね原作・CG・音楽・演出一手担当）の
**くだん**（人面牛、頭部入れ替わり設定）と ojisan が同系統」を未検証の
まま放置していたので C 系として一次調査を実施。

**C2 — 公開キャプチャ取得**: YouTube `qqf88J_3mQg`「おれ..くだん！よろしくな！！」
のサムネイルを `references/kudan/youtube_qqf88_kudan_thumb.jpg` に保存。
くだんの正面寄り頭部 + 牛胴体が明瞭に写った高品質キャプチャ。プレイ動画
全体プレイ動画 (`4cjZZMnE16I`) とエンディング集 (`PFgqaXAAAIo`) のサムネ
も保存。

**C3 — 視覚比較結果**: 両者の頭部メッシュ特徴を直接比較した結論：

共通点（同系統テイスト）：
- 黒髪・横分け、額が広い、髪の生え際が水平〜緩いアーチ
- 太眉、眉間に寄ってる
- 見開いた目（白目大きく出てる）
- 真っ直ぐな鼻筋
- 明るい肌色〜薄褐色
- 低〜中ポリ、スムースシェーディング
- 90s 後半・「素人っぽいリアル系人間頭部」テイスト全般

差異点：
- 頭頂部の丸み（ojisan）vs ややシャープ（くだん）
- 顎の輪郭の細さ（ojisan は縦長、くだんはやや丸い）
- ojisan は驚き口、くだんは閉じ口＋鼻輪

**結論**: 完全同一メッシュとは断言できないが、**同じ流通レイヤー（同じ
素材集 / 同じ解説本付録 / 同じチュートリアル素材）から派生した可能性が
極めて高い**。

**秋元きつね個人サイトの決定打** (`kitune.donburako.com/kitune/AMIGA.html`):
- **Amiga 500/2000/1200/4000 ＋ LightWave 3D / Imagine / TurboSilver / Sculpt 3D**
  で作品制作
- **「ウゴウゴルーガ」「せがれいじり」共に Lightwave + Video Toaster で制作** と明記
- **人物頭部モデル制作にも言及あり**
- Wikipedia 補強: 19 歳で平沢進のもとで Amiga を学ぶ → 秋元きつねは
  **Amiga + LightWave 系 3DCG クリエイター** で確定

**本命シナリオ（C3 結論、2026-05-11）**:
アンシャントロマン側（1997 開発、日本システム新設、ゲーム制作未経験）と
秋元きつね側（独立した個人作家、Amiga + LightWave 熟練者）が
**同じ Amiga + LightWave 系の人間頭部 LWO 素材を流用** した可能性が
極めて高い。我々が掘ってきた Aminet + LIGHT-ROM 1-5 はまさにこの
レイヤーなのに見つからない → **未収載の個人配布 / 国内講習 CD /
LightWave 解説本付録 CD** が抜けている可能性。

**副次的観察**: 秋元きつねの個人サイトドメインが `kudanwork.wixsite.com/kitune/`
で、**彼自身の工房名が「くだん」**。妖怪くだんに由来する作家性の強い記号で、
これとアンシャントロマンの ojisan が直接結びつく証拠は無いが、両者の
「**90s 後半・Amiga + LightWave・ローポリ人間頭部**」共通性は確かに
存在する。次に進むべきは 3.6.2 の国内物理メディア民俗学調査で、
そこで秋元きつねが言及した解説本・講習素材を物理タイトル単位で
特定していく。

#### 3.6.2 国内物理メディアの民俗学調査

IA / DiscMaster の自動収集では届かない国内流通 CD-ROM。タイトル単位で
「このムックに 3D モデル収録あり」を一件ずつ確認する必要がある：

- **D-Storm 講習 / セミナー CD**: 日本における LightWave 公式代理店の独自
  Content CD・チュートリアル CD。Web 検索では 1997 以前の痕跡が薄いが、
  中古市場・国会図書館で物理本として残る可能性。
- **MdN / DTP WORLD / PIXEL / Win Graphic** の 3DCG 特集回付録 CD。
- **ボーンデジタル / グラフィック社 / ソフトバンク刊の LightWave 解説本**
  付録 CD（1995-1997）。
- 個人配布 / 同人 CD。

#### 3.6.3 自作モデル仮説

B5 で SCE 公式 PS Artist Tool MEDITOR チュートリアル GIF に「顔モデルの
完全な作り方図解」が存在することが判明した点を踏まえて、3 種類のサブ仮説：

- (i) **公式チュートリアル参考自作**: MEDITOR の頭部モデリング手順をなぞって
  類似メッシュをゼロから作った。
- (ii) **MEDITOR サンプル流用 + 表情改変**: 同梱サンプルの頭部を流用し、口を
  開かせて表情だけ変えた（ただしサンプル本体は B5 範囲内に出現せず）。
- (iii) **完全自作**: チュートリアルも参照せずスクラッチから。

3.6.1 と 3.6.2 が空振りなら最終的にここに収束する見込み。

#### 3.6.4 優先度低（コスト対効果で当面保留）

- **アンシャントロマン本体解析**: OP がプリレンダ動画なら元 3D モデルではなく
  動画フレームしか得られない。
- **DOS/V Power Report 全号取得**: 24 GB でドライバ・シェアウェア中心、
  3D 素材期待値低。

---

## 4. パイプラインへの組み込み手順（Tier A 拡張時）

1. IA で identifier を見つける（例: `lightwave-content-cd-5`）。
2. `pipeline/config.py::INTERNET_ARCHIVE_IDENTIFIERS` に追加。
3. `python collect_internet_archive.py --identifier <new-id> --list-only` で
   ファイル一覧を確認。サイズ感が想定通りなら `--list-only` を外して取得。
4. `python run_pipeline.py` で展開→スキャン→識別。
5. `python render_with_recovery.py` でレンダ（クラッシュ耐性ラッパ）。
6. `python compare_renders_clip.py --reference references/ojisan/ojisan_trimmed.png
   --device auto --batch-size 64 --num-workers 4 --top 30` で再ランキング。
   GPU が効けば 4000 枚 × 3 ビューで CPU 25 分 → ~30 秒。
7. 上位 30 件を `renders/<sha16>/front.png` と並べて目視判定。

---

## 5. 関連メモリ

- `memory/ojisan_search_exhausted.md` — 公開アーカイブ範囲での探索進捗
  サマリ。本ドキュメントと内容は重なるが、メモリ側は要約・本側は詳細という
  役割分担。"打ち止め" ではなく方針転換ステータスを保持。
- `memory/next_format_converters.md` — Real 3D v2 / anim1.4 / easyhead 等の
  未対応コンバータ。Tier B の Real 3D v2 を進める場合に参照。
- `memory/aminet_mirror.md` — Aminet の既定ホストが死んでいる件。
