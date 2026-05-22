"""Tests for the product matcher engine."""

import pytest
from matcher.engine import clean_name, extract_size, extract_brand, match_score


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("LAIT 2% 4L | 2% MILK 4L", "2% MILK 4L"),
        ("BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G", "JERK CHICKEN BURGERS  852 G"),
        ("PAIN, 600 G OU BAGEL, 6 UN. COUNTRY HARVEST | BREAD OR BAGELS", "BREAD OR BAGELS"),
        ("", ""),
        ("SIMPLE FRENCH NAME", "SIMPLE FRENCH NAME"),
        ("ENGLISH ONLY", "ENGLISH ONLY"),
    ],
)
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G", "852 G"),
        ("LAIT 2% 4L | 2% MILK 4L", "4L"),
        ("SAC D'AVOCAT 5 CT", "5 CT"),
        ("NO SIZE HERE", None),
        ("PAIN, 600 G", "600 G"),
        ("BARRES DE CHOCOLAT CADBURY, 90-105 G", "105 G"),
    ],
)
def test_extract_size(raw, expected):
    assert extract_size(raw) == expected


def test_match_score_exact():
    assert match_score("2% MILK 4L", "LAIT 2% 4L | 2% MILK 4L") >= 80


def test_match_score_different():
    score = match_score(
        "BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G",
        "LAIT 2% 4L | 2% MILK 4L",
    )
    assert score < 60


def test_match_score_similar():
    """Two similar items should score high."""
    score = match_score(
        "JERK CHICKEN BURGERS 852 G",
        "CHICKEN BURGERS JERK 852G",
    )
    assert score >= 70


def test_match_score_empty():
    assert match_score("", "") == 0.0
    assert match_score("", "SOMETHING") == 0.0


def test_extract_brand_pc():
    name = "BURGERS DE POULET JERK PC | JERK CHICKEN BURGERS, 852 G"
    brand = extract_brand(name)
    assert brand == "Pc"


def test_extract_brand_cadbury():
    name = "BARRES DE CHOCOLAT CADBURY, 90-105 G"
    brand = extract_brand(name)
    assert brand == "Cadbury"


def test_extract_brand_none():
    name = "CHOUX DE BRUXELLES | BRUSSELS SPROUTS, 454 G"
    brand = extract_brand(name)
    assert brand is None
