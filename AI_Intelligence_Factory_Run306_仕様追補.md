# AI Intelligence Factory Run306 仕様追補

## Eyecatch Adaptive Typography Baseline

Run306では、note公開用アイキャッチの2〜3行キャッチコピーについて、固定Y座標とモデル提示フォントサイズへの依存を廃止し、実描画量に応じた決定論的レイアウトへ更新する。

### 1. フォントサイズ

- 通常タイトルの最大値は **72px**。
- 72pxは、人間監査済みNetflix GenRecアイキャッチの現行通常文字サイズを基準とする。
- 短いコピーは72pxまで使用可能。
- 長いコピーはPillowで実際の文字幅・文字高を測定し、既存の横幅・縦安全領域へ収まるまで1px単位で縮小する。
- 最小フォントは48px。
- Gemini/Run180が返す`title_font_size`は互換フィールドとして保持するが、最終描画サイズのauthorityにはしない。

### 2. オレンジ強調

- Run182の強調フレーズ選択を維持する。
- Run183の20%拡大を維持する。
- Run306では強調文字の最大値を **86px** とし、Netflix監査済み見本を超えて肥大化させない。

### 3. 縦方向の重心

旧仕様では、2行タイトル開始Y=234、3行タイトル開始Y=226で固定されており、3行のほうが上へ寄る構造だった。

Run306では、

- 共通視覚中心：**Y=370**
- 実測タイトルブロック高を計算
- `370 - block_height / 2`を開始Y候補とする
- 既存safe areaの上端・下端でclampする

方式へ変更する。

これにより2行・3行とも同じ視覚重心を持ち、文字量が増えても上寄りにならない。

### 4. 維持する仕様

- 2行を第一選択、必要時のみ3行というRun180 semantic layoutは維持。
- Run296の複合語分断禁止を維持。
- 1280×670、ブランド、カテゴリタグ、右側ネットワーク図、フッターは変更しない。
- 下部説明コピーはRun296どおり非表示。
- Evidence / Decision / Article Quality Gateへの変更なし。
- Gemini/model request追加なし。
- note自動公開なし。公開は人間のみ。
- Scheduled DailyはPAUSEDを維持。

### 5. 実装authority

- `run296_editorial_format_v2.py`
  - `RUN306_TITLE_MAX_FONT = 72`
  - `RUN306_HIGHLIGHT_MAX_FONT = 86`
  - `RUN306_TITLE_MIN_FONT = 48`
  - `RUN306_VISUAL_CENTER_Y = 370`
  - `adaptive_title_top()`
  - `_install_run306_adaptive_typography()`
- `run181_eyecatch_visual_balance.py`の既存rendererを、Run296の最終production eyecatch layerから決定論的にrefineする。

### 6. コスト

Run306追加Gemini API利用：**0 requests**。
