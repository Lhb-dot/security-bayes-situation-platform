from PIL import Image
import os

base = r"C:\Users\11543\.workbuddy-ai\clipboard-images"
files = {
    "img1_修改密码": "clipboard-2026-09-16T10-18-19-275Z-de5a27fc.png",
    "img2_测试连通性_编辑": "clipboard-2026-09-16T10-18-19-279Z-d03723b9.png",
    "img3_提示文本": "clipboard-2026-09-16T10-18-19-281Z-f424fc4e.png",
}

for name, fn in files.items():
    p = os.path.join(base, fn)
    im = Image.open(p).convert("RGB")
    w, h = im.size
    print(f"\n=== {name}  size={w}x{h} ===")
    # print a coarse color grid to locate buttons
    for y in range(0, h, max(1, h // 14)):
        row = []
        for x in range(0, w, max(1, w // 12)):
            r, g, b = im.getpixel((x, y))
            row.append(f"{r:02x}{g:02x}{b:02x}")
        print(f"y={y:4d} " + " ".join(row))
