# references/

参照画像（探したい「おじさん」の見本画像）を置く場所。

`compare_renders.py` の `--reference` 引数で指定する。

## 推奨

- 顔が中央、背景は単色か近い色だと imagehash の精度が出やすい
- `front` ビュー（正面）と比較するので、なるべく正面寄りのカットを選ぶ
- 複数アングルがある場合は別ファイルで保存し、ファイル名で区別（例 `ojisan_front.png`、`ojisan_threequarter.png`）

## 使用例

```cmd
python compare_renders.py --reference references/ojisan.png
python compare_renders.py --reference references/ojisan_front.png --method dhash --top 30
```
