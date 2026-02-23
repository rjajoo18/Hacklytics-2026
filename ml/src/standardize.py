"""
Country name normalization and sector keyword mapping.
"""

import re

# ---------------------------------------------------------------------------
# Country aliases: keys are variants (uppercased, stripped), values are canonical
# ---------------------------------------------------------------------------
COUNTRY_ALIASES: dict[str, str] = {
    # Special tariff-tracker spellings
    "CÔTE D'IVOIRE": "IVORY COAST",
    "CÔTE D`IVOIRE": "IVORY COAST",
    "COTE D'IVOIRE": "IVORY COAST",
    "COTE DIVOIRE": "IVORY COAST",
    "DEMOCRATIC REPUBLIC OF THE CONGO": "CONGO DRC",
    "CONGO, DEMOCRATIC REPUBLIC OF THE": "CONGO DRC",
    "REPUBLIC OF KOREA": "SOUTH KOREA",
    "KOREA, REPUBLIC OF": "SOUTH KOREA",
    "KOREA, SOUTH": "SOUTH KOREA",
    "KOREA": "SOUTH KOREA",
    "UNITED KINGDOM": "UK",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "EUROPEAN UNION": "EU",
    "PEOPLE'S REPUBLIC OF CHINA": "CHINA",
    "CHINA, MAINLAND": "CHINA",
    "CHINA, PEOPLES REPUBLIC": "CHINA",
    "VIET NAM": "VIETNAM",
    "TÜRKIYE": "TURKEY",
    "TURKIYE": "TURKEY",
    "TÜRKIYE": "TURKEY",
    "HONG KONG SAR": "HONG KONG",
    "HONG KONG, CHINA": "HONG KONG",
    "MACAO SAR": "MACAU",
    "MACAO, CHINA": "MACAU",
    "TAIWAN, PROVINCE OF CHINA": "TAIWAN",
    "CHINESE TAIPEI": "TAIWAN",
    "RUSSIA": "RUSSIA",
    "RUSSIAN FEDERATION": "RUSSIA",
    "IRAN, ISLAMIC REPUBLIC OF": "IRAN",
    "IRAN (ISLAMIC REPUBLIC OF)": "IRAN",
    "SYRIAN ARAB REPUBLIC": "SYRIA",
    "LAO PEOPLE'S DEMOCRATIC REPUBLIC": "LAOS",
    "KYRGYZ REPUBLIC": "KYRGYZSTAN",
    "CZECH REPUBLIC": "CZECHIA",
    "SLOVAK REPUBLIC": "SLOVAKIA",
    "NORTH MACEDONIA": "NORTH MACEDONIA",
    "MOLDOVA, REPUBLIC OF": "MOLDOVA",
    "VENEZUELA, BOLIVARIAN REPUBLIC OF": "VENEZUELA",
    "TANZANIA, UNITED REPUBLIC OF": "TANZANIA",
    "BOLIVIA, PLURINATIONAL STATE OF": "BOLIVIA",
    "BRUNEI DARUSSALAM": "BRUNEI",
    "MYANMAR": "MYANMAR",
    "BURMA": "MYANMAR",
    "ESWATINI": "SWAZILAND",
    "TIMOR-LESTE": "EAST TIMOR",
    "BOSNIA AND HERZEGOVINA": "BOSNIA",
    "FALKLAND ISLANDS (MALVINAS)": "FALKLAND ISLANDS",
    "SAINT KITTS AND NEVIS": "ST KITTS AND NEVIS",
    "SAINT LUCIA": "ST LUCIA",
    "SAINT VINCENT AND THE GRENADINES": "ST VINCENT",
    "TRINIDAD AND TOBAGO": "TRINIDAD",
    "ANTIGUA AND BARBUDA": "ANTIGUA",
    "GLOBAL": "GLOBAL",
    "WORLD": "GLOBAL",
}


def normalize_country(name: str) -> str:
    """Return a canonical uppercased country name, resolving known aliases."""
    if not isinstance(name, str):
        return "UNKNOWN"
    clean = name.strip().upper()
    # Remove parenthetical notes like "(MAINLAND)" or "(SAR)"
    clean = re.sub(r'\s*\(.*?\)', '', clean).strip()
    return COUNTRY_ALIASES.get(clean, clean)


def normalize_with_map(name: str, std_map: dict) -> str:
    """
    Normalize a country name to country_std.
    Applies normalize_country() first, then looks up the result in std_map
    (keyed by uppercase country_raw).  Falls back to the normalize_country()
    result if no entry is found in the map.
    """
    normalized = normalize_country(name)
    return std_map.get(normalized, normalized)


# ---------------------------------------------------------------------------
# Sector keywords: key = substring to match (lowercase), value = sector label
# ---------------------------------------------------------------------------
_SECTOR_KEYWORDS: list[tuple[str, str]] = [
    ("steel", "Steel & Aluminum"),
    ("aluminum", "Steel & Aluminum"),
    ("aluminium", "Steel & Aluminum"),
    ("automobile", "Automotive"),
    ("automotive", "Automotive"),
    ("vehicle", "Automotive"),
    ("truck", "Automotive"),
    ("car ", "Automotive"),
    ("semiconductor", "Semiconductor"),
    ("pharmaceutical", "Pharmaceutical"),
    ("pharma", "Pharmaceutical"),
    ("drug", "Pharmaceutical"),
    ("medicine", "Pharmaceutical"),
    ("solar", "Energy"),
    ("polysilicon", "Energy"),
    ("oil", "Energy"),
    ("energy", "Energy"),
    ("lumber", "Lumber"),
    ("timber", "Lumber"),
    ("wood", "Lumber"),
    ("copper", "Metals"),
    ("mineral", "Minerals"),
    ("critical mineral", "Minerals"),
    ("maritime", "Maritime"),
    ("shipbuilding", "Maritime"),
    ("ship", "Maritime"),
    ("drone", "Aerospace"),
    ("aircraft", "Aerospace"),
    ("jet engine", "Aerospace"),
    ("potash", "Agriculture"),
    ("agricultural", "Agriculture"),
    ("agriculture", "Agriculture"),
    ("soy", "Agriculture"),
    ("grain", "Agriculture"),
    ("textile", "Textiles"),
    ("apparel", "Textiles"),
    ("clothing", "Textiles"),
    ("usmca", "General"),
    ("reciprocal", "General"),
    ("fentanyl", "General"),
    ("opioid", "General"),
    ("illicit drug", "General"),
    ("synthetic opioid", "General"),
    ("low value", "General"),
    ("de minimis", "General"),
]


def derive_sector(target_text: str) -> str:
    """Infer sector label from the tariff tracker's 'Target' description."""
    if not isinstance(target_text, str):
        return "General"
    t = target_text.lower()
    for kw, sector in _SECTOR_KEYWORDS:
        if kw in t:
            return sector
    return "General"


# ---------------------------------------------------------------------------
# Sector normalization: tariff-tracker sector_std -> canonical label
# ---------------------------------------------------------------------------
_SECTOR_STD_TO_LABEL: dict[str, str] = {
    "GENERAL":         "General",
    "OTHER":           "General",
    "STEEL_ALUMINUM":  "Steel & Aluminum",
    "AUTOMOTIVE":      "Automotive",
    "ENERGY":          "Energy",
    "MARITIME":        "Maritime",
    "AEROSPACE":       "Aerospace",
    "AGRICULTURE":     "Agriculture",
    "METALS":          "Metals",
    "LUMBER":          "Lumber",
    "MINERALS":        "Minerals",
    "SEMICONDUCTORS":  "Semiconductor",
    "PHARMACEUTICALS": "Pharmaceutical",
    "TEXTILES":        "Textiles",
}


def normalize_sector(sector_std: str) -> str:
    """Map tariff tracker's UPPERCASE sector_std to the canonical sector label."""
    if not isinstance(sector_std, str):
        return "General"
    return _SECTOR_STD_TO_LABEL.get(sector_std.strip().upper(), "General")
