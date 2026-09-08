"""Build docs/slides.pdf from per-slide screenshots of the running deck.

    uv run marimo run agent.py --port 2771 --headless --no-token &
    uv run --with playwright --with pymupdf python tools/slides_pdf.py
"""
import time, glob, os
from playwright.sync_api import sync_playwright
import pymupdf
out = "/tmp/slides-deck"; os.makedirs(out, exist_ok=True)
for f in glob.glob(out + "/*.png"): os.remove(f)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.goto("http://127.0.0.1:2771/", wait_until="networkidle", timeout=120000)
    # wait until the section count is stable for 20 s (chat demo cell must finish)
    last, stable, t0 = -1, 0, time.time()
    while stable < 4 and time.time() - t0 < 240:
        time.sleep(5); n = pg.evaluate("document.querySelectorAll('.reveal .slides section').length")
        stable = stable + 1 if n == last and n > 20 else 0; last = n
    print("sections:", last, "after", round(time.time()-t0), "s")
    pg.keyboard.press("Home"); time.sleep(1)
    for i in range(last):
        pg.screenshot(path=f"{out}/{i:02d}.png"); pg.keyboard.press("ArrowRight"); time.sleep(0.7)
    b.close()
doc = pymupdf.open()
for f in sorted(glob.glob(out + "/*.png")):
    img = pymupdf.open(f); rect = img[0].rect
    page = doc.new_page(width=rect.width, height=rect.height); page.insert_image(rect, filename=f)
doc.set_metadata({"title": "How to create a local agent", "author": "Aral de Moor"})
doc.save("docs/slides.pdf", deflate=True)
print("pdf pages:", len(doc))
