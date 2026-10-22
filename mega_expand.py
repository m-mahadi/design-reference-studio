import os
import re
import json
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "design_catalog.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|]', '', str(name))
    clean = re.sub(r'\s+', '_', clean.strip())
    return clean[:70] if clean else "design_item"

def fetch_wp_page(base_url, page, per_page=50):
    url = f"{base_url}?per_page={per_page}&page={page}"
    try:
        res = subprocess.run(
            ["curl.exe", "-s", "--max-time", "20", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=25
        )
        if res.returncode == 0 and res.stdout.strip().startswith(("{", "[")):
            data = json.loads(res.stdout)
            if isinstance(data, list):
                return page, data
    except Exception:
        pass
    return page, []

# 1. DESIGN REVIEWED DEEP PAGES (Pages 51 to 170 -> ~6,000 items)
def expand_design_reviewed(start_page=51, end_page=170):
    print(f"\n[1/6] Harvesting Design Reviewed Pages {start_page}..{end_page}...", flush=True)
    items = []
    base_url = "https://designreviewed.com/wp-json/wp/v2/media"
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_wp_page, base_url, p, 50): p for p in range(start_page, end_page + 1)}
        done_count = 0
        for fut in as_completed(futures):
            done_count += 1
            page, data = fut.result()
            for d in data:
                if d.get("media_type") != "image":
                    continue
                title = BeautifulSoup(d.get("title", {}).get("rendered", "Design Reference"), "html.parser").text.strip()
                sizes = d.get("media_details", {}).get("sizes", {})
                img_url = (
                    sizes.get("2048x2048", {}).get("source_url") or
                    sizes.get("1536x1536", {}).get("source_url") or
                    sizes.get("large", {}).get("source_url") or
                    d.get("source_url")
                )
                thumb_url = sizes.get("medium_large", {}).get("source_url") or sizes.get("medium", {}).get("source_url") or img_url
                w = d.get("media_details", {}).get("width", 0)
                h = d.get("media_details", {}).get("height", 0)
                if w and w < 300 and h and h < 300:
                    continue
                fname = f"DR_{d.get('id', page*100)}_{sanitize_filename(title)}.webp"
                items.append({
                    "id": f"dr_{d.get('id')}",
                    "title": title,
                    "source": "Design Reviewed",
                    "category": "Editorial & Graphic Design",
                    "image_url": img_url,
                    "thumbnail_url": thumb_url,
                    "width": w,
                    "height": h,
                    "filename": fname,
                    "folder": "design_reviewed"
                })
            if done_count % 15 == 0 or done_count == (end_page - start_page + 1):
                print(f"  Design Reviewed progress: {done_count}/{end_page - start_page + 1} pages | +{len(items)} items", flush=True)
    return items

# 2. LETTERFORM ARCHIVE REMAINING PAGES (Pages 36 to 65 -> complete archive!)
def expand_letterform(start_page=36, end_page=65):
    print(f"\n[2/6] Harvesting Remaining Letterform Archive Pages {start_page}..{end_page}...", flush=True)
    items = []
    base_url = "https://letterformarchive.org/wp-json/wp/v2/media"
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_wp_page, base_url, p, 100): p for p in range(start_page, end_page + 1)}
        done_count = 0
        for fut in as_completed(futures):
            done_count += 1
            page, data = fut.result()
            for d in data:
                if d.get("media_type") != "image":
                    continue
                title = BeautifulSoup(d.get("title", {}).get("rendered", "Letterform Specimen"), "html.parser").text.strip()
                sizes = d.get("media_details", {}).get("sizes", {})
                img_url = (
                    sizes.get("1536x1536", {}).get("source_url") or
                    sizes.get("bc-large", {}).get("source_url") or
                    sizes.get("large", {}).get("source_url") or
                    d.get("source_url")
                )
                thumb_url = sizes.get("medium_large", {}).get("source_url") or sizes.get("bc-medium", {}).get("source_url") or img_url
                w = d.get("media_details", {}).get("width", 0)
                h = d.get("media_details", {}).get("height", 0)
                if w and w < 300 and h and h < 300:
                    continue
                fname = f"LFA_{d.get('id', page*100)}_{sanitize_filename(title)}.jpg"
                items.append({
                    "id": f"lfa_{d.get('id')}",
                    "title": title,
                    "source": "Letterform Archive",
                    "category": "Typography & Lettering",
                    "image_url": img_url,
                    "thumbnail_url": thumb_url,
                    "width": w,
                    "height": h,
                    "filename": fname,
                    "folder": "letterform_archive"
                })
            if done_count % 10 == 0 or done_count == (end_page - start_page + 1):
                print(f"  Letterform progress: {done_count}/{end_page - start_page + 1} pages | +{len(items)} items", flush=True)
    return items

# 3. FONTS IN USE DEEP PAGES (Pages 21 to 70 -> ~2,950 items)
def fetch_fiu_page(page):
    url = f"https://fontsinuse.com/?page={page}"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for idx, img in enumerate(soup.find_all("img")):
                src = img.get("src") or ""
                if "use-media-items" not in src:
                    continue
                srcset = img.get("srcset") or ""
                hi_url = src
                if "@2x" in srcset:
                    parts = [p.strip().split(" ")[0] for p in srcset.split(",") if "@2x" in p]
                    if parts:
                        hi_url = parts[0]
                raw_title = img.get("alt") or img.get("title") or f"Fonts In Use {page}_{idx}"
                title = BeautifulSoup(raw_title, "html.parser").text.strip()
                ext = ".png" if hi_url.lower().endswith(".png") else ".jpg"
                fname = f"FIU_p{page}_{idx}_{sanitize_filename(title)}{ext}"
                items.append({
                    "id": f"fiu_{page}_{idx}",
                    "title": title,
                    "source": "Fonts In Use",
                    "category": "Typography in Action & Branding",
                    "image_url": hi_url,
                    "thumbnail_url": src,
                    "width": 1000,
                    "height": 1300,
                    "filename": fname,
                    "folder": "fonts_in_use"
                })
    except Exception:
        pass
    return items

def expand_fonts_in_use(start_page=21, end_page=70):
    print(f"\n[3/6] Harvesting Fonts In Use Pages {start_page}..{end_page}...", flush=True)
    items = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(fetch_fiu_page, p) for p in range(start_page, end_page + 1)]
        done = 0
        for fut in as_completed(futures):
            done += 1
            items.extend(fut.result())
            if done % 10 == 0 or done == len(futures):
                print(f"  Fonts In Use progress: {done}/{len(futures)} pages | +{len(items)} items", flush=True)
    return items

# 4. V&A MUSEUM DEEP QUERIES
def fetch_vam_query(query, page):
    url = f"https://api.vam.ac.uk/v2/objects/search?q={query}&images_exist=1&page_size=100&page={page}"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            records = r.json().get("records", [])
            for rec in records:
                img_id = rec.get("_primaryImageId")
                if not img_id:
                    continue
                sys_num = rec.get("systemNumber", img_id)
                title = rec.get("_primaryTitle") or rec.get("objectType") or "V&A Design Object"
                maker = rec.get("_primaryMaker", {}).get("name", "")
                date_str = rec.get("_primaryDate", "")
                full_title = f"{title} — {maker} ({date_str})".strip(" —()")
                hi_url = f"https://framemark.vam.ac.uk/collections/{img_id}/full/!1200,1200/0/default.jpg"
                thumb_url = f"https://framemark.vam.ac.uk/collections/{img_id}/full/!600,600/0/default.jpg"
                fname = f"VAM_{sys_num}_{sanitize_filename(full_title)}.jpg"
                items.append({
                    "id": f"vam_{sys_num}",
                    "title": full_title,
                    "source": "V&A Museum London",
                    "category": "Posters, Packaging & Graphic Art",
                    "image_url": hi_url,
                    "thumbnail_url": thumb_url,
                    "width": 1200,
                    "height": 1200,
                    "filename": fname,
                    "folder": "vam_museum"
                })
    except Exception:
        pass
    return items

def expand_vam_deep():
    print("\n[4/6] Harvesting V&A Museum London Deep Design Collections...", flush=True)
    queries = [
        ("poster", 10),
        ("graphic+design", 8),
        ("packaging+label", 5),
        ("magazine+editorial", 5),
        ("art+deco+print", 5),
        ("art+nouveau+poster", 5),
        ("woodblock+japanese+print", 5),
        ("album+cover+music", 4),
        ("typeface+specimen", 4)
    ]
    items = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = []
        for q, max_p in queries:
            for p in range(1, max_p + 1):
                futures.append(ex.submit(fetch_vam_query, q, p))
        done = 0
        for fut in as_completed(futures):
            done += 1
            items.extend(fut.result())
            if done % 10 == 0 or done == len(futures):
                print(f"  V&A progress: {done}/{len(futures)} batches | +{len(items)} items", flush=True)
    return items

# 5. CLEVELAND MUSEUM DEEP QUERIES
def fetch_cma_batch(query, skip):
    url = f"https://openaccess-api.clevelandart.org/api/artworks/?q={query}&has_image=1&cc0=1&limit=100&skip={skip}"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for d in r.json().get("data", []):
                web_img = d.get("images", {}).get("web", {}).get("url")
                if not web_img:
                    continue
                oid = d.get("id")
                title = d.get("title", "Cleveland Art Print")
                date_txt = d.get("creation_date", "")
                full_title = f"{title} ({date_txt})" if date_txt else title
                fname = f"CMA_{oid}_{sanitize_filename(full_title)}.jpg"
                items.append({
                    "id": f"cma_{oid}",
                    "title": full_title,
                    "source": "Cleveland Museum Open Access",
                    "category": "Fine Prints, Lithographs & Posters",
                    "image_url": web_img,
                    "thumbnail_url": web_img,
                    "width": 1200,
                    "height": 1500,
                    "filename": fname,
                    "folder": "cleveland_museum"
                })
    except Exception:
        pass
    return items

def expand_cleveland_deep():
    print("\n[5/6] Harvesting Cleveland Museum Fine Prints, Lithographs & Woodblocks...", flush=True)
    queries = [
        ("lithograph", 6),
        ("woodblock", 6),
        ("screenprint", 3),
        ("graphic", 3),
        ("book+illustration", 4),
        ("calligraphy", 3)
    ]
    items = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = []
        for q, pages in queries:
            for p in range(pages):
                futures.append(ex.submit(fetch_cma_batch, q, p * 100))
        for fut in as_completed(futures):
            items.extend(fut.result())
    print(f"  Cleveland Museum harvested: +{len(items)} items", flush=True)
    return items

# 6. ARTVEE DEEP PAGES
def fetch_artvee_cat_page(cat_slug, cat_label, page):
    url = f"https://artvee.com/c/{cat_slug}/page/{page}/"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="product-grid-item") or soup.find_all("article")
            for idx, c in enumerate(cards):
                img_tag = c.find("img")
                title_tag = c.find(["h2", "h3", "h4", "span"])
                title = title_tag.text.strip() if title_tag else f"Artvee {cat_label}"
                if not img_tag:
                    continue
                src = img_tag.get("src") or img_tag.get("data-src")
                if not src or "mdl.artvee.com" not in src:
                    continue
                fname = f"ARTVEE_{cat_slug.upper()}_{page}_{idx}_{sanitize_filename(title)}.jpg"
                items.append({
                    "id": f"artvee_{cat_slug}_{page}_{idx}",
                    "title": title,
                    "source": f"Artvee {cat_label}",
                    "category": f"{cat_label} & Modernist Art",
                    "image_url": src,
                    "thumbnail_url": src,
                    "width": 1200,
                    "height": 1600,
                    "filename": fname,
                    "folder": f"artvee_{cat_slug}"
                })
    except Exception:
        pass
    return items

def expand_artvee_deep():
    print("\n[6/6] Harvesting Artvee Deep Pages (Posters, Illustration, Abstract, Botanical, Drawings)...", flush=True)
    items = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = []
        for p in range(21, 55):
            futures.append(ex.submit(fetch_artvee_cat_page, "posters", "Posters", p))
        for p in range(18, 45):
            futures.append(ex.submit(fetch_artvee_cat_page, "illustration", "Illustration", p))
        for p in range(15, 35):
            futures.append(ex.submit(fetch_artvee_cat_page, "abstract", "Abstract", p))
        for p in range(1, 15):
            futures.append(ex.submit(fetch_artvee_cat_page, "botanical", "Botanical", p))
        for fut in as_completed(futures):
            items.extend(fut.result())
    print(f"  Artvee deep harvested: +{len(items)} items", flush=True)
    return items

def main():
    start = time.time()
    existing = []
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    print(f"Starting from {len(existing):,} existing items...", flush=True)

    new_items = []
    new_items.extend(expand_design_reviewed(51, 170))
    new_items.extend(expand_letterform(36, 65))
    new_items.extend(expand_fonts_in_use(21, 70))
    new_items.extend(expand_vam_deep())
    new_items.extend(expand_cleveland_deep())
    new_items.extend(expand_artvee_deep())

    combined = existing + new_items
    unique = []
    seen = set()
    for it in combined:
        u = it.get("image_url")
        if u and u not in seen:
            seen.add(u)
            unique.append(it)

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(CATALOG_PATH) / (1024 * 1024)
    print("\n============================================================", flush=True)
    print(f"MEGA EXPANSION COMPLETE: {len(unique):,} TOTAL MASTER REFERENCES!", flush=True)
    print(f"Newly added unique references: +{len(unique) - len(existing):,}", flush=True)
    print(f"Catalog JSON size: {size_mb:.2f} MB (Fits easily on Vercel!)", flush=True)
    print(f"Time elapsed: {time.time() - start:.1f}s", flush=True)
    print("============================================================", flush=True)

if __name__ == "__main__":
    main()
