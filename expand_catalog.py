import os
import re
import json
import time
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

# 1. FONTS IN USE (fontsinuse.com)
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
                raw_title = img.get("alt") or img.get("title") or f"Fonts In Use Specimen {page}_{idx}"
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
    except Exception as e:
        print(f"FIU page {page} error: {e}", flush=True)
    return page, items

def index_fonts_in_use(max_pages=20):
    print(f"\n[1/4] Indexing Fonts In Use ({max_pages} pages in parallel)...", flush=True)
    items = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_fiu_page, p): p for p in range(1, max_pages + 1)}
        for fut in as_completed(futures):
            p, res = fut.result()
            items.extend(res)
            print(f"  Fonts In Use page {p} parsed | Total: {len(items)}", flush=True)
    return items

# 2. VICTORIA & ALBERT MUSEUM (api.vam.ac.uk)
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
    except Exception as e:
        print(f"V&A ({query} p{page}) error: {e}", flush=True)
    return items

def index_vam_museum():
    print("\n[2/4] Indexing Victoria & Albert Museum London (Posters, Graphic Design, Typography)...", flush=True)
    queries = [
        ("poster+graphic+design", 4),
        ("typography+lettering", 3),
        ("book+jacket+cover", 3),
        ("bauhaus+modernism", 2)
    ]
    items = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = []
        for q, pages in queries:
            for p in range(1, pages + 1):
                futures.append(ex.submit(fetch_vam_query, q, p))
        for fut in as_completed(futures):
            res = fut.result()
            items.extend(res)
            print(f"  V&A batch parsed | Current V&A total: {len(items)}", flush=True)
    return items

# 3. CLEVELAND MUSEUM OF ART OPEN ACCESS (openaccess-api.clevelandart.org)
def fetch_cma_query(query, skip=0):
    url = f"https://openaccess-api.clevelandart.org/api/artworks/?q={query}&has_image=1&cc0=1&limit=100&skip={skip}"
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for d in data:
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
    except Exception as e:
        print(f"CMA ({query}) error: {e}", flush=True)
    return items

def index_cleveland_museum():
    print("\n[3/4] Indexing Cleveland Museum of Art Open Access...", flush=True)
    queries = ["poster", "lithograph+advertising", "woodblock+japan", "modern+graphic", "bauhaus"]
    items = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_cma_query, q, 0) for q in queries]
        for fut in as_completed(futures):
            items.extend(fut.result())
            print(f"  Cleveland Museum batch parsed | Current total: {len(items)}", flush=True)
    return items

# 4. ARTVEE ILLUSTRATION & ABSTRACT (artvee.com)
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
    except Exception as e:
        print(f"Artvee {cat_slug} p{page} error: {e}", flush=True)
    return items

def index_artvee_extra():
    print("\n[4/4] Indexing Artvee Editorial Illustration & Modernist Abstract...", flush=True)
    items = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = []
        for p in range(1, 18):
            futures.append(ex.submit(fetch_artvee_cat_page, "illustration", "Illustration", p))
        for p in range(1, 15):
            futures.append(ex.submit(fetch_artvee_cat_page, "abstract", "Abstract", p))
        for fut in as_completed(futures):
            items.extend(fut.result())
            print(f"  Artvee extra batch parsed | Total: {len(items)}", flush=True)
    return items

def main():
    start = time.time()
    existing = []
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    print(f"Loaded existing catalog: {len(existing):,} items", flush=True)

    new_items = []
    new_items.extend(index_fonts_in_use(20))
    new_items.extend(index_vam_museum())
    new_items.extend(index_cleveland_museum())
    new_items.extend(index_artvee_extra())

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

    print("\n============================================================", flush=True)
    print(f"EXPANSION COMPLETE: {len(unique):,} TOTAL MASTER REFERENCES!", flush=True)
    print(f"Newly added unique references: {len(unique) - len(existing):,}", flush=True)
    print(f"Time elapsed: {time.time() - start:.1f}s", flush=True)
    print("============================================================", flush=True)

if __name__ == "__main__":
    main()
