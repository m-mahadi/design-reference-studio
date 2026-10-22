import os
import re
import json
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE_DIR, "design_catalog.json")

# Junk / non-design-reference patterns (e.g. website UI banners, author portraits, event photos)
JUNK_PATTERNS = re.compile(
    r"(author[-_ ]?photo|headshot|portrait[-_ ]of|staff[-_ ]photo|logo[-_ ]?white|logo[-_ ]?black|"
    r"placeholder|banner[-_ ]?ad|icon[-_ ]|avatar|profile[-_ ]pic|webcam|screenshot|"
    r"novel-gothic\.png|event[-_ ]photo|classroom|workshop[-_ ]photo|installation[-_ ]view)",
    re.I
)

def classify_item(item):
    title = (item.get("title") or "").lower()
    source = (item.get("source") or "").lower()
    cat = (item.get("category") or "").lower()
    fname = (item.get("filename") or "").lower()
    text = f"{title} {source} {cat} {fname}"

    types = []

    # 1. Japanese Design & Prints
    if any(k in text for k in ["japan", "japanese", "tokyo", "gurafiku", "ukiyo", "woodblock", "kanto", "shibuya", "kyoto", "osaka", "showa", "meiji", "hokusai", "hiroshige", "kuniyoshi"]):
        types.append("Japanese Design & Prints")

    # 2. Album Covers & Music
    if any(k in text for k in ["album", "record", "vinyl", "lp ", "single", "sleeve", "soundtrack", "music", "band", "concert", "jazz", "symphony", "opera", "disc", "track", "dylan", "orchestra", "festival"]):
        types.append("Album Covers & Music")

    # 3. Books & Editorial
    if any(k in text for k in ["book", "magazine", "journal", "editorial", "spread", "issue", "vol.", "volume", "no.", "number ", "the face", "oase", "penguin", "pelican", "catalog", "catalogue", "brochure", "pamphlet", "zine", "publication", "cover", "dust jacket", "novel", "poetry", "almanac", "manual", "directory", "annual", "report", "newspaper", "page"]):
        types.append("Books & Editorial")

    # 4. Packaging, Logos & Ephemera
    if any(k in text for k in ["packaging", "package", "label", "tin", "box", "bottle", "can", "wrapper", "matchbox", "ticket", "lottery", "stamp", "postage", "postcard", "card", "invoice", "receipt", "letterhead", "stationery", "menu", "identity", "logo", "trademark", "monogram", "emblem", "crest", "sign", "badge", "calendar", "ephemera", "currency", "banknote", "bag"]):
        types.append("Packaging, Logos & Ephemera")

    # 5. Swiss, Bauhaus & Abstract
    if any(k in text for k in ["bauhaus", "swiss", "constructivis", "modernis", "abstract", "geometric", "karel martens", "neville brody", "wim crouwel", "josef muller", "müller-brockmann", "max bill", "jan tschichold", "paul rand", "milton glaser", "saul bass", "massimo vignelli", "grid", "kinetic", "concrete", "avant-garde", "dada", "futuris", "de stijl", "suprematis", "kandinsky", "mondrian", "klee", "moholy-nagy", "lissitzky", "herb lubalin"]):
        types.append("Swiss, Bauhaus & Abstract")

    # 6. Posters & Flyers
    if any(k in text for k in ["poster", "flyer", "placard", "handbill", "broadside", "billboard", "exhibition", "theatre", "theater", "cinema", "film", "movie", "travel", "railway", "airline", "propaganda", "war ", "tour", "show", "fair", "expo", "olympic", "affiche"]):
        types.append("Posters & Flyers")

    # 7. Typography & Type Specimens
    if any(k in text for k in ["type", "typography", "typeface", "font", "lettering", "letterform", "calligraphy", "specimen", "alphabet", "glyph", "script", "sans", "serif", "gothic", "grotesk", "grotesque", "italic", "bold", "wood type", "metal type", "foundry", "inscription", "cipher", "initial"]):
        types.append("Typography & Type Specimens")

    # 8. Illustration & Vintage Art
    if any(k in text for k in ["illustration", "lithograph", "etching", "engraving", "drawing", "sketch", "botanical", "flora", "fauna", "art nouveau", "art deco", "victorian", "woodcut", "print", "plate", "caricature", "cartoon", "comic", "painting", "watercolor", "gouache", "pastel"]):
        types.append("Illustration & Vintage Art")

    # Default fallbacks by source if no keyword matched
    if not types:
        if "fonts in use" in source:
            types.append("Typography & Type Specimens")
        elif "letterform" in source:
            types.append("Typography & Type Specimens")
        elif "design reviewed" in source or "vol.co" in source:
            types.append("Books & Editorial")
            types.append("Swiss, Bauhaus & Abstract")
        elif "artvee posters" in source or source == "artvee":
            types.append("Posters & Flyers")
        elif "artvee abstract" in source:
            types.append("Swiss, Bauhaus & Abstract")
        elif "artvee illustration" in source or "botanical" in source:
            types.append("Illustration & Vintage Art")
        elif "v&a" in source:
            types.append("Posters & Flyers")
        elif "cleveland" in source:
            types.append("Illustration & Vintage Art")
        elif "gurafiku" in source:
            types.append("Japanese Design & Prints")
        else:
            types.append("Posters & Flyers")

    # Primary type is the first matched type, and store all matched types in `design_types`
    return types[0], types

def main():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    cleaned = []
    removed_count = 0
    type_counter = Counter()

    for it in catalog:
        w = it.get("width") or 0
        h = it.get("height") or 0
        title = it.get("title") or ""
        url = it.get("image_url") or ""

        # Filter out extreme thin banner strips or tiny UI elements
        if w > 0 and h > 0:
            ratio = w / h
            if ratio > 3.2 or ratio < 0.25 or w < 320 or h < 320:
                removed_count += 1
                continue

        if JUNK_PATTERNS.search(title) or JUNK_PATTERNS.search(url):
            removed_count += 1
            continue

        primary_type, all_types = classify_item(it)
        it["design_type"] = primary_type
        it["design_types"] = all_types
        it["category"] = primary_type

        for t in all_types:
            type_counter[t] += 1

        cleaned.append(it)

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print(f"Cleaned out {removed_count} banner/UI junk items.")
    print(f"Remaining high-quality references: {len(cleaned):,}")
    print("\nBreakdown by Design Type (items can belong to multiple relevant types):")
    for k, v in type_counter.most_common():
        print(f"  {k}: {v:,}")

if __name__ == "__main__":
    main()
