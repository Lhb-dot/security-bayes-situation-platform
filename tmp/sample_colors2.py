from PIL import Image
from collections import Counter
import os

base = r"C:\Users\11543\.workbuddy-ai\clipboard-images"
files = {
    "img1": "clipboard-2026-09-16T10-18-19-275Z-de5a27fc.png",
    "img2": "clipboard-2026-09-16T10-18-19-279Z-d03723b9.png",
    "img3": "clipboard-2026-09-16T10-18-19-281Z-f424fc4e.png",
}

for name, fn in files.items():
    im = Image.open(os.path.join(base, fn)).convert("RGB")
    w, h = im.size
    print(f"\n=== {name} {w}x{h} ===")
    # find bounding boxes of "saturated blue" pixels (button fills)
    px = im.load()
    pts = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if b > 110 and b - r > 45 and g > 60:
                pts.append((x, y))
    if not pts:
        print("no blue pixels")
        continue
    # cluster crudely by x ranges
    xs = sorted(set(p[0] for p in pts))
    clusters = []
    cur = [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] <= 12:
            cur.append(x)
        else:
            clusters.append((cur[0], cur[-1]))
            cur = [x]
    clusters.append((cur[0], cur[-1]))
    for (x0, x1) in clusters:
        sub = [p for p in pts if x0 <= p[0] <= x1]
        ys = [p[1] for p in sub]
        y0, y1 = min(ys), max(ys)
        if (x1 - x0) < 30 or (y1 - y0) < 15:
            continue
        # dominant color inside
        cnt = Counter(px[x, y] for y in range(y0, y1 + 1, 3) for x in range(x0, x1 + 1, 3))
        top = cnt.most_common(3)
        print(f"  region x[{x0}-{x1}] y[{y0}-{y1}]  size {x1-x0}x{y1-y0}  top={[('#%02x%02x%02x' % c, n) for c, n in top]}")
