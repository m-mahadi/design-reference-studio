import os
import sys
import json
import time
import shutil
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "design_catalog.json")
DEFAULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
MIN_FREE_DISK_GB = 3.0

def get_free_disk_gb(path):
    try:
        drive = os.path.splitdrive(os.path.abspath(path))[0] or path
        total, used, free = shutil.disk_usage(drive)
        return free / (1024 ** 3)
    except Exception:
        return 999.0

def download_single_item(item, output_dir):
    folder_name = item.get("folder", "general")
    target_folder = os.path.join(output_dir, folder_name)
    os.makedirs(target_folder, exist_ok=True)
    
    filename = item.get("filename") or f"{item.get('id', 'item')}.jpg"
    target_path = os.path.join(target_folder, filename)
    
    # Resume: if already downloaded and > 2KB, skip
    if os.path.exists(target_path) and os.path.getsize(target_path) > 2048:
        return {"status": "skipped", "size": os.path.getsize(target_path), "path": target_path, "item": item}
        
    url = item.get("image_url")
    if not url:
        return {"status": "error", "error": "No image URL", "item": item}
        
    # Free disk guard
    if get_free_disk_gb(output_dir) < MIN_FREE_DISK_GB:
        return {"status": "halted_disk_low", "item": item}
        
    tmp_path = target_path + ".tmp"
    try:
        # Use native curl for maximum compatibility and bypassing Cloudflare TLS fingerprint blocks
        cmd = ["curl.exe", "-s", "--max-time", "15", url, "-o", tmp_path]
        subprocess.run(cmd, capture_output=True, timeout=18)
        
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
            # Check for HTML challenge/stub (<4KB containing html)
            size = os.path.getsize(tmp_path)
            if size < 4096:
                with open(tmp_path, "rb") as check_f:
                    head = check_f.read(200)
                    if b"<!DOCTYPE" in head or b"<html" in head:
                        alt = item.get("thumbnail_url")
                        if alt and alt != url:
                            cmd_alt = ["curl.exe", "-s", "--max-time", "15", alt, "-o", tmp_path]
                            subprocess.run(cmd_alt, capture_output=True, timeout=18)
            
            size = os.path.getsize(tmp_path)
            if size > 1024:
                os.replace(tmp_path, target_path)
                return {"status": "success", "size": size, "path": target_path, "item": item}
                
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    except Exception as e:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass
        return {"status": "exception", "error": str(e), "item": item}
        
    return {"status": "failed", "item": item}

def run_downloader(catalog_path=CATALOG_PATH, output_dir=DEFAULT_DOWNLOAD_DIR, limit=None, workers=6, category=None):
    if not os.path.exists(catalog_path):
        print(f"Error: Catalog file not found at {catalog_path}")
        print("Please run fast_indexer.py first to build the catalog!")
        return
        
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    if category:
        cat_lower = category.lower()
        catalog = [it for it in catalog if cat_lower in it.get("category", "").lower() or cat_lower in it.get("folder", "").lower() or cat_lower in it.get("source", "").lower()]
        
    if limit and limit > 0:
        catalog = catalog[:limit]
        
    total_to_download = len(catalog)
    print("==================================================")
    print(f"DESIGN SCRAPER ROBUST CURL DOWNLOAD ENGINE")
    print(f"Total items in queue: {total_to_download:,}")
    print(f"Output directory:     {output_dir}")
    print(f"Concurrent workers:   {workers}")
    print(f"Disk free space:      {get_free_disk_gb(output_dir):.2f} GB")
    print("==================================================")
    
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    total_downloaded_bytes = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_single_item, item, output_dir): item for item in catalog}
        
        for idx, future in enumerate(as_completed(futures), 1):
            res = future.result()
            st = res.get("status")
            if st == "success":
                success_count += 1
                total_downloaded_bytes += res.get("size", 0)
            elif st == "skipped":
                skip_count += 1
            elif st == "halted_disk_low":
                print("\n[WARNING] Free disk space below safety threshold (3GB). Aborting further downloads.")
                break
            else:
                fail_count += 1
                
            if idx % 10 == 0 or idx == total_to_download:
                elapsed = max(time.time() - start_time, 0.001)
                mb = total_downloaded_bytes / (1024 * 1024)
                rate = mb / elapsed
                print(f"[{idx}/{total_to_download}] New: {success_count} | Cached: {skip_count} | Failed: {fail_count} | {mb:.1f} MB ({rate:.2f} MB/s)", end="\r")
                
    elapsed = max(time.time() - start_time, 0.001)
    mb = total_downloaded_bytes / (1024 * 1024)
    print("\n\n==================================================")
    print("DOWNLOAD RUN SUMMARY")
    print(f"Newly downloaded:    {success_count:,} images")
    print(f"Already existing:    {skip_count:,} images")
    print(f"Failed / unreachable: {fail_count:,} items")
    print(f"Total data received: {mb:.2f} MB in {elapsed:.1f}s")
    print(f"Storage location:    {output_dir}")
    print("==================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Source Design Reference Downloader")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of photos to download")
    parser.add_argument("--workers", type=int, default=6, help="Number of concurrent download threads")
    parser.add_argument("--output", type=str, default=DEFAULT_DOWNLOAD_DIR, help="Destination directory")
    parser.add_argument("--category", type=str, default=None, help="Filter by specific category or source")
    args = parser.parse_args()
    
    run_downloader(output_dir=args.output, limit=args.limit, workers=args.workers, category=args.category)
