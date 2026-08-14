import os
from PIL import Image, ImageDraw, ImageFont
import textwrap

def create_eyecatch_image(title_text: str, output_path: str = "eyecatch.png") -> str:
    """
    1280px x 670px のアイキャッチ画像を完全0円で自動生成する関数
    """
    # 1. キャンバスサイズ（1280 x 670 固定）
    WIDTH = 1280
    HEIGHT = 670
    
    # 2. ベース背景画像の読み込み（無ければダークサイバー風グラデーションをコード生成）
    bg_path = "assets/bg_template.png"
    if os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((WIDTH, HEIGHT))
    else:
        # 背景画像がない場合のフォールバック（漆黒〜ダークブルーのグラデーション）
        img = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 15, 28))
        draw_bg = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            r = int(10 + (y / HEIGHT) * 15)
            g = int(15 + (y / HEIGHT) * 25)
            b = int(28 + (y / HEIGHT) * 45)
            draw_bg.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)

    # 3. フォントの設定（システムフォントまたはNoto Sans等を使用）
    # GitHub Actions(Ubuntu)の標準日本語フォントパスを指定
    font_path = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" # 代替パス
        
    try:
        font = ImageFont.truetype(font_path, 48)
        tag_font = ImageFont.truetype(font_path, 24)
    except Exception:
        # フォント読み込み失敗時はデフォルトフォント
        font = ImageFont.load_default()
        tag_font = font

    # 4. タグ（ヘッダーバッジ）の描画
    tag_text = "【日刊】AI Tech Intelligence"
    draw.rectangle([80, 80, 480, 120], fill=(0, 200, 255))
    draw.text((100, 88), tag_text, fill=(10, 15, 28), font=tag_font)

    # 5. タイトル文字の自動改行処理（全角20文字程度で折り返し）
    wrapped_lines = textwrap.wrap(title_text, width=18)
    
    # 6. 中央寄せで描画（ネオンホワイト文字＋ドロップシャドウ）
    y_text = 220
    for line in wrapped_lines:
        # 影（シャドウ効果）
        draw.text((102, y_text + 2), line, fill=(0, 0, 0), font=font)
        # 本文（白）
        draw.text((100, y_text), line, fill=(255, 255, 255), font=font)
        y_text += 65  # 行間

    # 7. 画像の保存
    img.save(output_path, "PNG")
    return output_path
