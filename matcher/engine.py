"""
Product name normalization and fuzzy matching engine.
Handles the bilingual mess of Canadian grocery flyers.
"""
import re

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore[assignment]


def clean_name(raw: str) -> str:
    """
    Normalize a flyer product name for comparison.
    Handles bilingual names like:
      'LAIT 2% 4L | 2% MILK 4L'
      'BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G'
    """
    if not raw:
        return ""

    # Split on the bilingual separator
    parts = raw.split("|")
    # Use the English half if available, otherwise French
    name = parts[1].strip() if len(parts) > 1 else parts[0].strip()

    # Normalize
    name = name.upper()
    name = re.sub(r"[.,;:()\[\]]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name


def extract_size(raw: str) -> str | None:
    """Extract size from name like '852 G' or '4L' or '6 UN.'"""
    match = re.search(
        r"(\d+[\.,]?\d*\s*(?:G|KG|LB|L|ML|UN\.?|EA|CT|OZ|PAQUET|SAC))",
        raw.upper(),
    )
    return match.group(1) if match else None


def extract_brand(name: str) -> str | None:
    """Try to extract brand from the product name."""
    # Known brands in Quebec grocery flyers
    known = [
        "PC", "LE CHOIX DU PRÉSIDENT", "SANS NOM", "NO NAME",
        "IRRÉSISTIBLE", "IRRESISTIBLE", "SÉLECTION MÉRITE", "MERIT SELECTION",
        "COMPLIMENTS", "CADBURY", "KRAFT", "CHRISTIE", "DARE",
        "QUÉBON", "NATREL", "LACTANTIA", "PARMALAT", "SAPUTO",
        "BLACK DIAMOND", "CRACKER BARREL", "NESTLÉ", "NESTLE",
        "KELLOGG'S", "GENERAL MILLS", "NATURE VALLEY", "QUAKER",
        "BECEL", "HELLMANN'S", "FRENCH'S", "HEINZ",
        "COUNTRY HARVEST", "BON MATIN", "DEMPSTER'S", "POM",
        "OASIS", "TROPICANA", "MINUTE MAID", "COCA-COLA", "PEPSI",
        "FANTA", "SPRITE", "DASANI", "EVIAN",
        "TIDE", "CASCADE", "DAWN", "PALMOLIVE",
        "ROYALE", "CASHMERE", "CHARMIN", "BOUNTY",
        "COLGATE", "CREST", "ORAL-B", "GILLETTE",
        "MAYBELLINE", "L'ORÉAL", "LOREAL", "COVERGIRL",
        "MAPLE LEAF", "OLYMEL", "FLAMINGO", "JANES",
        "LEAN CUISINE", "STOUFFER'S", "MICHELINA'S",
        "HÄAGEN-DAZS", "BEN & JERRY'S", "BREYERS",
        "DR. OETKER", "MCCAIN", "CAVENDISH",
        "VH", "BLUE DRAGON", "A. VOGEL", "FONTAINE SANTÉ",
        "PLANTFUL", "BEYOND MEAT", "GARDEIN", "YVES VEGGIE",
        "LE PETIT CHARcutIER", "THE DELI-SHOP",
        "PRESIDENT'S CHOICE", "OUR COMPLIMENTS",
        "GADOUA", "WESTON", "VILLAGGIO",
    ]
    upper = name.upper()
    for brand in known:
        if brand in upper:
            return brand.title()
    return None


def match_score(name_a: str, name_b: str) -> float:
    """
    Return a 0-100 fuzzy match score between two product names.
    >80 = likely the same product
    >60 = possibly the same
    <50 = different products
    """
    a = clean_name(name_a)
    b = clean_name(name_b)
    if not a or not b:
        return 0.0

    # Exact match
    if a == b:
        return 100.0

    if fuzz is not None:
        token_score = fuzz.token_sort_ratio(a, b)
        partial_score = fuzz.partial_ratio(a, b)
        return max(token_score, partial_score)

    # Fallback: basic word overlap scoring
    a_words = set(a.split())
    b_words = set(b.split())
    if not a_words or not b_words:
        return 0.0
    overlap = a_words & b_words
    return (len(overlap) / max(len(a_words), len(b_words))) * 100.0


def group_similar(items: list[dict], threshold: float = 75.0) -> dict[str, list[dict]]:
    """
    Group flyer items into similar-product clusters.
    Returns {canonical_name: [items]} where each group contains the same product
    across different stores/prices.
    """
    groups = {}
    used = set()

    for i, item in enumerate(items):
        if i in used:
            continue
        name = item.get("product_name", item.get("name", ""))
        group_key = clean_name(name)
        group = [item]
        used.add(i)

        for j, other in enumerate(items):
            if j in used:
                continue
            other_name = other.get("product_name", other.get("name", ""))
            if match_score(name, other_name) >= threshold:
                group.append(other)
                used.add(j)

        groups[group_key] = group

    return groups
