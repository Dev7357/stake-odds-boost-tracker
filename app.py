import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import requests
import streamlit as st

st.set_page_config(page_title="Stake Soccer Boost Monitor", page_icon="🟡", layout="wide")

API_BASE = "https://odds-data.stake.com"
TIMEOUT = 20


def secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "")).strip()


API_KEY = secret("STAKE_API_KEY")

st.title("🟡 Stake Soccer Boost Monitor")
st.caption("Phone-friendly tracker — reports only boosts explicitly exposed by an authorized data source.")

with st.expander("🔐 Safety & data-source rules", expanded=True):
    st.markdown(
        """
- **Never enter a Stake password, browser cookie, session token, or account API token here.**
- This app accepts only the separate `STAKE_API_KEY` secret intended for the Stake Sports Data API.
- A price change, shorter odds, or an unusually high/low price is **not** treated as a boost.
- A match appears in **Confirmed boosts** only if the API response explicitly contains boost/promotion metadata.
- If the authorized API does not expose that metadata, the app deliberately returns **No confirmed boosts** rather than guessing.
        """
    )

if not API_KEY:
    st.warning("No authorized Sports Data API key is configured yet.")
    st.info(
        "Go to your hosting platform's Secrets settings and add only `STAKE_API_KEY` if you have an authorized Stake Sports Data API key. "
        "Do not use the token from Stake account Settings → API."
    )
    st.stop()

# The public Sports Data API documents an apiKey security scheme. X-API-Key is used here.
HEADERS = {"X-API-Key": API_KEY, "Accept": "application/json"}


def get(path: str) -> Any:
    url = API_BASE + path
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if response.status_code in (401, 403):
        raise RuntimeError(
            "The Sports Data API rejected the key (401/403). Check that this is an authorized Sports Data API key, "
            "not a Stake account/session token."
        )
    response.raise_for_status()
    return response.json()


def walk(obj: Any, path: str = "root"):
    """Yield (path, key, value) for every nested field."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield path, str(key), value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from walk(value, f"{path}[{i}]")


BOOST_KEY_WORDS = ("boost", "boosted", "promotion", "promoted")
BOOST_VALUE_WORDS = ("boost", "boosted", "promotion", "promoted", "enhanced")


def explicit_boost_metadata(obj: Any) -> List[Dict[str, Any]]:
    """Return only fields whose key/value explicitly signals a boost/promotion."""
    hits: List[Dict[str, Any]] = []
    for path, key, value in walk(obj):
        key_l = key.lower()
        value_l = str(value).lower() if isinstance(value, (str, int, float, bool)) else ""
        if any(word in key_l for word in BOOST_KEY_WORDS) or any(word in value_l for word in BOOST_VALUE_WORDS):
            hits.append({"path": path, "field": key, "value": value})
    return hits


def flatten_fixtures(obj: Any) -> List[Dict[str, Any]]:
    """Find fixture-shaped dictionaries anywhere in a response."""
    found = []
    for _, _, value in walk(obj):
        if isinstance(value, dict) and {"id", "name"}.issubset(value.keys()):
            if any(k in value for k in ("startTime", "date", "status", "tournament")):
                found.append(value)
    # de-duplicate by id/slug
    seen = set()
    out = []
    for item in found:
        ident = item.get("id") or item.get("slug") or repr(item)
        if ident not in seen:
            seen.add(ident)
            out.append(item)
    return out


def soccer_slug(sports: List[Dict[str, Any]]) -> str | None:
    for sport in sports:
        slug = str(sport.get("slug", "")).lower()
        name = str(sport.get("name", "")).lower()
        if slug in {"soccer", "football"} or "soccer" in name or "football" in name:
            return sport.get("slug")
    return None


def scan_soccer() -> tuple[list[dict], list[dict], str]:
    """Scan available soccer hierarchy and inspect fixture odds for explicit boost metadata."""
    sports = get("/sports")
    if not isinstance(sports, list):
        raise RuntimeError("Unexpected /sports response format.")

    slug = soccer_slug(sports)
    if not slug:
        return [], [], "Soccer/football was not returned by the authorized API."

    fixture_candidates: List[Dict[str, Any]] = []
    # The category/tournament hierarchy can be large. Use the sport subcategory endpoint first.
    sport_index = get(f"/sport/{slug}/fixture")
    fixture_candidates.extend(flatten_fixtures(sport_index))

    # Also accept fixtures surfaced directly in the response.
    fixture_candidates.extend(flatten_fixtures(get(f"/sport/{slug}/category"))) if False else None

    # De-duplicate.
    seen = set()
    fixtures = []
    for f in fixture_candidates:
        ident = f.get("id") or f.get("slug")
        if ident and ident not in seen:
            seen.add(ident)
            fixtures.append(f)

    confirmed: List[Dict[str, Any]] = []
    checked = 0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    horizon_ms = now_ms + 48 * 60 * 60 * 1000

    for fixture in fixtures:
        start = fixture.get("startTime", fixture.get("date"))
        if isinstance(start, (int, float)) and start < now_ms - 2 * 60 * 60 * 1000:
            continue
        if isinstance(start, (int, float)) and start > horizon_ms:
            continue
        fixture_key = fixture.get("slug") or fixture.get("id")
        if not fixture_key:
            continue
        try:
            odds = get(f"/odds/{fixture_key}")
            checked += 1
        except Exception:
            continue
        hits = explicit_boost_metadata(odds)
        if hits:
            confirmed.append({"fixture": fixture, "metadata": hits, "odds": odds})

    return confirmed, fixtures, f"Scanned {checked} soccer fixtures in the next 48 hours."


st.subheader("Daily confirmed-boost list")

if st.button("🔄 Scan now", use_container_width=True):
    with st.spinner("Checking authorized Stake Sports Data API…"):
        try:
            confirmed, fixtures, status = scan_soccer()
            st.session_state["scan_result"] = (confirmed, fixtures, status, datetime.now(timezone.utc))
        except Exception as exc:
            st.session_state["scan_error"] = str(exc)

if "scan_error" in st.session_state:
    st.error(st.session_state.pop("scan_error"))

if "scan_result" not in st.session_state:
    st.info("Tap **Scan now** to generate today's confirmed list. The app will not guess boosts from odds movement.")
else:
    confirmed, fixtures, status, scanned_at = st.session_state["scan_result"]
    st.caption(f"Last scan: {scanned_at.astimezone().strftime('%d %b %Y, %I:%M %p')} — {status}")
    if confirmed:
        st.success(f"{len(confirmed)} confirmed boost item(s) found.")
        for item in confirmed:
            fixture = item["fixture"]
            st.markdown(f"### 🟡 {fixture.get('name', 'Unknown fixture')}")
            st.write(f"Tournament: {fixture.get('tournament', '—')} | Category: {fixture.get('category', '—')}")
            st.json(item["metadata"])
    else:
        st.success("No confirmed boosted selections found in the scanned window.")
        st.caption("This is intentionally conservative: no boost metadata = no boost claim.")

st.divider()
st.subheader("What this app can and cannot confirm")
st.markdown(
    """
**Can confirm:** an explicit boost/promotion flag or metadata returned by the authorized Sports Data API.

**Cannot confirm:** the yellow visual marker shown in Stake's normal website/app UI if that marker is not present in the API response. 
The app therefore does **not** scrape the logged-in Stake website, use browser cookies, or impersonate a user session.

**Automatic daily operation:** Streamlit Cloud runs the app when opened/restarted; it is not a guaranteed 24/7 scheduler. 
For a true once-per-day background scan, connect the same read-only API logic to a legitimate scheduler/cron service later.
"""
)

with st.expander("Technical diagnostics"):
    st.write("API base:", API_BASE)
    st.write("Key configured:", bool(API_KEY))
    st.write("Boost metadata rule:", "explicit boost/promotion metadata only")

st.caption("Never enter or store a Stake password, private session cookie, or Stake account token in this app.")
