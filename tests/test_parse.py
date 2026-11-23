"""Lettura di prezzi e disponibilita' dal testo."""

import pytest

from custom_components.changedetection_ha_sensors.api import normalize_url
from custom_components.changedetection_ha_sensors.parse import clean_text, extract_price, extract_stock, trend


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("In Stock: True - Price: 319.95", 319.95),
        ("In Stock: True - Price: 0.59", 0.59),
        ("Price: 12", 12.0),
        ("€22.79 €11.40", 22.79),
        ("€74.28", 74.28),
        ("Prezzo 1.299,00 €", 1299.0),
        ("49,99 €", 49.99),
        ("$1,299.50", 1299.5),
        ("Nessun prezzo qui", None),
        ("Versione 2.0 rilasciata", None),
        ("", None),
        (None, None),
    ],
)
def test_extract_price(text, price):
    assert extract_price(text) == price


def test_extract_stock():
    assert extract_stock("In Stock: True - Price: 1") is True
    assert extract_stock("In Stock: False - Price: 1") is False
    assert extract_stock("€10.00") is None


def test_trend():
    assert trend(10, 12) == "down"
    assert trend(12, 10) == "up"
    assert trend(10, 10) is None
    assert trend(10, None) is None


def test_clean_text():
    assert clean_text("a\n  b\tc", 100) == "a b c"
    assert clean_text("abcdef", 3) == "abc"


@pytest.mark.parametrize(
    "url", ["http://h:5000", "http://h:5000/", "http://h:5000/api/v1", "http://h:5000/api/v1/", "h:5000"]
)
def test_normalize_url(url):
    assert normalize_url(url) == "http://h:5000"
