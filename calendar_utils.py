"""Gregorian/Jalali date conversion helpers."""

from __future__ import annotations

from datetime import date

import jdatetime


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_digits(value: str) -> str:
    """Convert Persian and Arabic-Indic digits to ASCII digits."""
    return value.translate(_DIGIT_TRANSLATION)


def to_jalali(value: date) -> jdatetime.date:
    return jdatetime.date.fromgregorian(date=value)


def format_persian_digits(value: str) -> str:
    return value.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def parse_date(value: str, calendar: str) -> date:
    """Parse a date entered in the currently selected calendar."""
    text = normalize_digits(value).strip().replace("-", "/").replace(".", "/")
    parts = text.split("/")
    if len(parts) != 3 or any(not part.strip() for part in parts):
        raise ValueError("Enter the date as year/month/day.")

    try:
        year, month, day = (int(part) for part in parts)
        if calendar == "Gregorian":
            return date(year, month, day)
        if calendar == "Persian":
            return jdatetime.date(year, month, day).togregorian()
    except (ValueError, OverflowError) as exc:
        raise ValueError("That date is not valid in the selected calendar.") from exc

    raise ValueError("Unknown calendar type.")
