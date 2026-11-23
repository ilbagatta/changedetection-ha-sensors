"""Lettura del testo delle rilevazioni (funzioni pure, senza HA)."""

from __future__ import annotations

import re

# "In Stock: True - Price: 319.95" (processore restock_diff)
_PRICE_LABEL = re.compile(r"Price:\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
# Primo importo con due decimali, con o senza simbolo: "€22.79", "1.299,00 €", "49,99"
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,\s]\d{3})+|\d+)[.,](\d{2})(?!\d)")
_STOCK = re.compile(r"In Stock:\s*(True|False)", re.IGNORECASE)


def extract_price(text: str | None) -> float | None:
    """Prezzo dal testo della rilevazione: prima `Price: x`, poi il primo importo con due decimali."""
    if not text:
        return None
    if match := _PRICE_LABEL.search(text):
        return float(match.group(1).replace(",", "."))
    if match := _AMOUNT.search(text):
        integer = re.sub(r"[.,\s]", "", match.group(1))
        return float(f"{integer}.{match.group(2)}")
    return None


def extract_stock(text: str | None) -> bool | None:
    """Disponibilita' (solo per i watch restock, `In Stock: True/False`)."""
    if not text or not (match := _STOCK.search(text)):
        return None
    return match.group(1).lower() == "true"


def clean_text(text: str | None, limit: int) -> str:
    """Testo su una riga, accorciato."""
    if not text:
        return ""
    return " ".join(text.split())[:limit]


def trend(price: float | None, old_price: float | None) -> str | None:
    """`down` / `up` / None."""
    if price is None or old_price is None or price == old_price:
        return None
    return "down" if price < old_price else "up"
