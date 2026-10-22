import os
import sys
import json
import subprocess
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_catalog.json")

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|]', '', name)
    clean = re.sub(r'\s+', '_', clean.strip())
    return clean[:70] if clean else "design_item"

def fetch_wp_page(base_url, page, per_page=100):
    url = f"{base_url}?per_page={per_page}&page={page}"
    try:
        res = subprocess.run(
            ["curl.exe", "-s", url],
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
    except Exception as e:
        print(f"Error fetching page {page} of {base_url}: {e}", flush=True)
    return page, []

def get_design_reviewed_items(max_pages=50):
    print(f"\n[1/4] Indexing Design Reviewed ({max_pages} pages @ 50 items/page)...", flush=True)
    items = []
    base_url = "https://designreviewed.com/wp-json/wp/v2/media"
    
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_wp_page, base_url, p, 50): p for p in range(1, max_pages + 1)}
        for fut in as_completed(futures):
            page, data = fut.result()
            for d in data:
                if d.get("media_type") != "image":
                    continue
                title = d.get("title", {}).get("rendered", "Design Reference")
                title = BeautifulSoup(title, "html.parser").text.strip()
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
            print(f"  Design Reviewed page {page} parsed | Current total: {len(items)}", flush=True)
    return items

def get_letterform_items(max_pages=30):
    print(f"\n[2/4] Indexing Letterform Archive ({max_pages} pages in parallel)...", flush=True)
    items = []
    base_url = "https://letterformarchive.org/wp-json/wp/v2/media"
    
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_wp_page, base_url, p): p for p in range(1, max_pages + 1)}
        for fut in as_completed(futures):
            page, data = fut.result()
            for d in data:
                if d.get("media_type") != "image":
                    continue
                title = d.get("title", {}).get("rendered", "Letterform Archive Specimen")
                title = BeautifulSoup(title, "html.parser").text.strip()
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
            print(f"  Letterform Archive page {page} parsed | Current total: {len(items)}", flush=True)
    return items

def fetch_artvee_page(page):
    url = f"https://artvee.com/c/posters/page/{page}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    items = []
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="product-grid-item") or soup.find_all("article")
            for c in cards:
                img_tag = c.find("img")
                title_tag = c.find(["h2", "h3", "h4", "span"])
                title = title_tag.text.strip() if title_tag else "Vintage Poster"
                if not img_tag:
                    continue
                src = img_tag.get("src") or img_tag.get("data-src")
                if not src or "mdl.artvee.com" not in src:
                    continue
                fname = f"ARTVEE_{page}_{sanitize_filename(title)}.jpg"
                items.append({
                    "id": f"artvee_{page}_{len(items)+1}",
                    "title": title,
                    "source": "Artvee",
                    "category": "Vintage Posters & Art",
                    "image_url": src,
                    "thumbnail_url": src,
                    "width": 1200,
                    "height": 1600,
                    "filename": fname,
                    "folder": "artvee_posters"
                })
    except Exception as e:
        print(f"Error Artvee page {page}: {e}", flush=True)
    return page, items

def get_artvee_items(max_pages=15):
    print(f"\n[3/4] Indexing Artvee Posters ({max_pages} pages in parallel)...", flush=True)
    items = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_artvee_page, p): p for p in range(1, max_pages + 1)}
        for fut in as_completed(futures):
            page, p_items = fut.result()
            items.extend(p_items)
            print(f"  Artvee page {page} parsed | Total: {len(items)}", flush=True)
    return items

def get_curated_specials():
    print("\n[4/4] Indexing Milton Glaser, Vol.co & Gurafiku...", flush=True)
    items = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Milton Glaser
    try:
        sva_url = "https://sva.edu/features/in-remembrance-milton-glaser-1929-2020"
        r = requests.get(sva_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for idx, img in enumerate(soup.find_all("img")):
            src = img.get("src")
            alt = img.get("alt", f"Milton Glaser Work {idx+1}")
            if src and "assets.sva.edu" in src and not any(ext in src for ext in [".svg", "logo"]):
                fname = f"GLASER_{idx+1}_{sanitize_filename(alt)}.jpg"
                items.append({
                    "id": f"glaser_{idx+1}",
                    "title": f"Milton Glaser: {alt}",
                    "source": "SVA Milton Glaser Archive",
                    "category": "Master Designer Showcase",
                    "image_url": src,
                    "thumbnail_url": src,
                    "width": 1200,
                    "height": 1600,
                    "filename": fname,
                    "folder": "milton_glaser"
                })
    except Exception as e:
        print(f"Glaser error: {e}", flush=True)

    # 2. Vol.co Design Reviewed book plates
    try:
        vol_url = "https://vol.co/collections/design-reviewed"
        r = requests.get(vol_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        seen_vol = set()
        v_idx = 1
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and "cdn/shop" in src and not any(ext in src for ext in [".svg", "icon"]):
                if src.startswith("//"):
                    src = "https:" + src
                high_src = re.sub(r'&width=\d+', '&width=2000', src)
                base = high_src.split("?")[0]
                if base in seen_vol:
                    continue
                seen_vol.add(base)
                fname = f"VOL_DR_Plate_{v_idx}.jpg"
                items.append({
                    "id": f"vol_dr_{v_idx}",
                    "title": f"Design Reviewed Book Plate {v_idx}",
                    "source": "Vol.co Design Reviewed Edition",
                    "category": "Curated Design Archive",
                    "image_url": high_src,
                    "thumbnail_url": src,
                    "width": 1600,
                    "height": 1200,
                    "filename": fname,
                    "folder": "vol_co"
                })
                v_idx += 1
    except Exception as e:
        print(f"Vol.co error: {e}", flush=True)

    # 3. Gurafiku Japanese Graphic Design RSS
    try:
        r = requests.get("https://gurafiku.tumblr.com/rss", headers=headers, timeout=10)
        if r.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            g_idx = 1
            for it in root.findall(".//item"):
                title = it.find("title").text if it.find("title") is not None else f"Gurafiku Graphic {g_idx}"
                desc = it.find("description").text if it.find("description") is not None else ""
                match = re.search(r'src="(https://\d+\.media\.tumblr\.com/[^"]+)"', desc)
                if match:
                    t_url = match.group(1)
                    hi_url = re.sub(r'_\d+\.(jpg|png|jpeg)', r'_1280.\1', t_url)
                    fname = f"GURAFIKU_{g_idx}_{sanitize_filename(title)}.jpg"
                    items.append({
                        "id": f"gurafiku_{g_idx}",
                        "title": title,
                        "source": "Gurafiku Japanese Graphic Design",
                        "category": "Japanese Modernism & Posters",
                        "image_url": hi_url,
                        "thumbnail_url": t_url,
                        "width": 1280,
                        "height": 1800,
                        "filename": fname,
                        "folder": "gurafiku"
                    })
                    g_idx += 1
    except Exception as e:
        print(f"Gurafiku error: {e}", flush=True)

    print(f"  Specials total: {len(items)} items", flush=True)
    return items

def main():
    start = time.time()
    print("==================================================", flush=True)
    print("FAST CONCURRENT DESIGN CATALOGUER (TARGET: 5,000+)", flush=True)
    print("==================================================", flush=True)
    
    all_items = []
    
    # 1. Design Reviewed
    dr = get_design_reviewed_items(max_pages=50)
    all_items.extend(dr)

    # 2. Letterform Archive
    lfa = get_letterform_items(max_pages=35)
    all_items.extend(lfa)

    # 3. Artvee
    artvee = get_artvee_items(max_pages=20)
    all_items.extend(artvee)
    
    # 4. Specials
    spec = get_curated_specials()
    all_items.extend(spec)
    
    # Deduplicate
    unique = []
    seen = set()
    for it in all_items:
        u = it.get("image_url")
        if u and u not in seen:
            seen.add(u)
            unique.append(it)
            
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)
        
    duration = time.time() - start
    print("\n==================================================", flush=True)
    print(f"SUCCESS: CATALOGUED {len(unique):,} CURATED MASTER DESIGN WORKS", flush=True)
    print(f"Time taken: {duration:.1f} seconds", flush=True)
    print(f"Saved to: {CATALOG_PATH}", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    main()
