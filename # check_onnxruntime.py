import traceback
import io
from PIL import Image, ImageDraw
import ddddocr

print("=== ddddocr 測試工具 ===")

# 顯示版本
try:
    import pkg_resources
    version = pkg_resources.get_distribution("ddddocr").version
    print(f"[INFO] ddddocr 版本: {version}")
except Exception:
    print("[ERROR] 無法取得 ddddocr 版本")

# 嘗試初始化 (含 show_ad 參數)
try:
    ocr = ddddocr.DdddOcr(show_ad=False)
    print("[OK] 成功用 show_ad 初始化 ddddocr ✅")
except TypeError as e:
    print("[WARN] 你的 ddddocr 不支援 show_ad，改用預設初始化 ⚠️")
    try:
        ocr = ddddocr.DdddOcr()
        print("[OK] 成功用預設初始化 ddddocr ✅")
    except Exception:
        print("[ERROR] 無法初始化 ddddocr ❌")
        traceback.print_exc()
        exit(1)
except Exception:
    print("[ERROR] 無法初始化 ddddocr ❌")
    traceback.print_exc()
    exit(1)

# 建立一張測試圖片 (內容 "1234")
try:
    img = Image.new("RGB", (120, 40), "black")
    draw = ImageDraw.Draw(img)
    draw.text((10, 5), "1234", fill="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    result = ocr.classification(img_bytes)
    print(f"[TEST] OCR 輸出結果: {result}")

    if result:
        print("[OK] ddddocr 運作正常 ✅")
    else:
        print("[WARN] ddddocr 啟動成功，但辨識結果為空 ⚠️")

except Exception:
    print("[ERROR] 測試圖片辨識失敗 ❌")
    traceback.print_exc()
