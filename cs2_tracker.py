"""
CS2 Inventory Price Tracker
Flask backend + HTML/CSS/JS frontend launched in Edge app mode.
"""
import threading
import requests
import time
import json
import os
import sys
import re
import random
import webbrowser
import queue
import socket
import subprocess
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, Response, request, jsonify, send_from_directory


# ── Config ───────────────────────────────────────────────────────────────────

def _config_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")

def _load_config():
    try:
        with open(_config_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ── Constants ─────────────────────────────────────────────────────────────────

STEAM_INV_URL     = "https://steamcommunity.com/inventory/{steam_id}/730/2"
STEAM_PRICE_URL   = "https://steamcommunity.com/market/priceoverview/"
STEAM_HISTORY_URL = "https://steamcommunity.com/market/pricehistory/"
CSFLOAT_URL       = "https://csfloat.com/api/v1/listings"
BUFF_URL          = "https://buff.163.com/api/market/goods"
BUFF_EXCHANGE_URL = "https://api.exchangerate-api.com/v4/latest/CNY"
STEAM_CDN         = "https://community.akamai.steamstatic.com/economy/image/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── Flask app ─────────────────────────────────────────────────────────────────

app          = Flask(__name__, static_folder=None)
_config      = _load_config()
_history_cache: dict = {}   # name -> (fetched_at_timestamp, data)
_buff_rate_cache: tuple = (0, 0.0)  # (fetched_at, cny_to_usd_rate)
_buff_session: requests.Session | None = None  # reused across Buff calls in one fetch
_fetch_id    = 0
_fetch_lock  = threading.Lock()
_sse_queues: list = []        # one per connected /api/events client
_sse_lock    = threading.Lock()
_shutdown_ev = threading.Event()


def _push(event_type: str, data):
    """Push a JSON event to all connected SSE clients."""
    payload = json.dumps({"type": event_type, "data": data})
    with _sse_lock:
        for q in list(_sse_queues):
            try:
                q.put_nowait(payload)
            except Exception:
                pass


def _resource_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return send_from_directory(os.path.join(_resource_path(), "ui"), "index.html")


@app.route("/api/events")
def sse():
    """Server-Sent Events stream — pushes live progress to the browser."""
    q = queue.Queue(maxsize=200)
    with _sse_lock:
        _sse_queues.append(q)

    def generate():
        try:
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_queues:
                    _sse_queues.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "steam_id":          _config.get("steam_id", ""),
        "csfloat_key":       _config.get("csfloat_key", ""),
        "steam_cookie":      _config.get("steam_cookie", ""),
        "buff_cookie":       _config.get("buff_cookie", ""),
        "save_credentials":  _config.get("save_credentials", True),
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    body = request.get_json(force=True, silent=True) or {}
    save = bool(body.get("save_credentials", True))
    _config["save_credentials"] = save
    if save:
        _config["steam_id"]     = body.get("steam_id", "")
        _config["csfloat_key"]  = body.get("csfloat_key", "")
        _config["steam_cookie"] = body.get("steam_cookie", "")
        _config["buff_cookie"]  = body.get("buff_cookie", "")
    else:
        _config["steam_id"]     = ""
        _config["csfloat_key"]  = ""
        _config["steam_cookie"] = ""
        _config["buff_cookie"]  = ""
    _save_config(_config)
    return jsonify({"ok": True})


@app.route("/api/fetch", methods=["POST"])
def start_fetch():
    global _fetch_id
    body = request.get_json(force=True, silent=True) or {}
    steam_id     = (body.get("steam_id", "") or "").strip()
    csfloat_key  = (body.get("csfloat_key", "") or "").strip()
    steam_cookie = (body.get("steam_cookie", "") or "").strip()
    buff_cookie  = (body.get("buff_cookie", "") or "").strip()
    with _fetch_lock:
        _fetch_id += 1
        fid = _fetch_id
    threading.Thread(
        target=_fetch_all,
        args=(steam_id, csfloat_key, steam_cookie, buff_cookie, fid),
        daemon=True,
    ).start()
    return jsonify({"fetch_id": fid})


@app.route("/api/history")
def price_history():
    name         = request.args.get("name", "")
    steam_cookie = request.args.get("cookie", "")
    if not name:
        return jsonify({"error": "no name"})
    CACHE_TTL = 3600  # 1 hour
    if name in _history_cache:
        cached_at, cached_data = _history_cache[name]
        if time.time() - cached_at < CACHE_TTL:
            return jsonify(cached_data)
    try:
        cookies = {"steamLoginSecure": steam_cookie} if steam_cookie else {}
        r = requests.get(
            STEAM_HISTORY_URL,
            params={"appid": 730, "currency": 1, "market_hash_name": name},
            headers=HEADERS, cookies=cookies, timeout=20,
        )
        if r.status_code != 200:
            return jsonify({"error": f"HTTP {r.status_code}"})
        raw = r.json().get("prices", [])
        daily = defaultdict(list)
        for entry in raw:
            try:
                dt  = datetime.strptime(entry[0][:11].strip(), "%b %d %Y")
                key = dt.strftime("%Y-%m-%d")
                daily[key].append(float(entry[1]))
            except Exception:
                continue
        result = [{"date": k, "price": sum(v) / len(v)}
                  for k, v in sorted(daily.items())]
        _history_cache[name] = (time.time(), result)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)[:120]})


@app.route("/api/open-url", methods=["POST"])
def open_url():
    url = (request.get_json(force=True, silent=True) or {}).get("url", "")
    # Allow http/https and steam:// (inspect links use steam:// protocol)
    if url and url.startswith(("http://", "https://", "steam://")):
        webbrowser.open(url)
    return jsonify({"ok": True})


@app.route("/api/close", methods=["POST"])
def close_app():
    _shutdown_ev.set()
    return jsonify({"ok": True})


# ── Price-fetch worker ────────────────────────────────────────────────────────

def _fetch_all(steam_id, csfloat_key, steam_cookie, buff_cookie, fid):
    global _fetch_id

    # Parse Steam profile URLs — accept full URLs, vanity names, or raw ID64
    m = re.match(r'https?://steamcommunity\.com/profiles/(\d{17})', steam_id)
    if m:
        steam_id = m.group(1)
    else:
        m = re.match(r'https?://steamcommunity\.com/id/([^/\s?#]+)', steam_id)
        if m:
            steam_id = m.group(1)

    # Validate / resolve Steam ID
    if not re.fullmatch(r"\d{17}", steam_id):
        _push("status", f"Resolving '{steam_id}'…")
        resolved = _resolve_vanity(steam_id)
        if resolved:
            steam_id = resolved
        else:
            _push("error", "Could not resolve that Steam ID. Enter a 17-digit Steam ID64 (find yours at steamid.io).")
            return

    _push("status", "Fetching inventory…")
    counts = _fetch_inventory(steam_id, steam_cookie, fid)
    if counts is None:
        return

    unique = list(counts.items())
    total  = len(unique)
    _push("status", f"Fetching prices for {total} items…")
    _push("fetch_start", total)

    done_counter = [0]
    lock = threading.Lock()

    def fetch_one(pair):
        name, info = pair
        if fid != _fetch_id:
            return

        steam_price = _get_steam_price(name, steam_cookie)
        cf_data     = _get_csfloat_price(name, csfloat_key) if csfloat_key else None

        diff = diff_pct = None
        if steam_price and cf_data and cf_data.get("price"):
            diff     = steam_price - cf_data["price"]
            diff_pct = (diff / steam_price) * 100

        row = {
            "name":        name,
            "category":    info.get("type", "Other"),
            "qty_avail":   info.get("available", 0),
            "qty_cd":      info.get("cooldown",  0),
            "has_market":  info.get("has_market", False),
            "steam_price": steam_price,
            "cf_price":    cf_data["price"]            if cf_data else None,
            "cf_float":    cf_data.get("float_value")  if cf_data else None,
            "cf_inspect":  cf_data.get("inspect_link", "") if cf_data else "",
            "cf_seed":     cf_data.get("paint_seed")   if cf_data else None,
            "icon_url":    (cf_data.get("icon_url", "") if cf_data else "") or info.get("steam_icon", ""),
            "trade_lock":  info.get("trade_lock"),
            "buff_price":  None,
            "diff":        diff,
            "diff_pct":    diff_pct,
        }

        with lock:
            done_counter[0] += 1
            done = done_counter[0]

        _push("item", {"row": row, "done": done, "total": total})

    with ThreadPoolExecutor(max_workers=4) as ex:
        ex.map(fetch_one, unique)

    if fid == _fetch_id:
        _push("fetch_complete", total)

    # ── Buff163 sequential pass (rate-limited, runs after Steam/CSFloat) ──────
    if buff_cookie and fid == _fetch_id:
        _push("status", "Connecting to Buff163…")
        buff_sess  = _init_buff_session(buff_cookie)
        cny_rate   = _get_cny_rate()
        buff_done  = 0
        login_ok   = True
        for name, _ in unique:
            if fid != _fetch_id:
                break
            buff_price = _get_buff_price(name, buff_sess, cny_rate)
            buff_done += 1
            # Detect invalid session on first call
            if buff_done == 1 and buff_price is None:
                # Quick check: try one more to distinguish "item not found" from "login failed"
                test_r = buff_sess.get(BUFF_URL, params={"game": "csgo", "search": "AK-47", "page_num": 1, "page_size": 1}, timeout=10)
                if "Login Required" in test_r.text:
                    _push("error", "Buff163 session cookie is invalid or expired — re-enter it from buff.163.com")
                    login_ok = False
                    break
            _push("item_buff", {"name": name, "buff_price": buff_price})
            if buff_done % 5 == 0 or buff_done == total:
                _push("status", f"Fetching Buff163 prices ({buff_done}/{total})…")
            if buff_done < total:
                time.sleep(random.uniform(1.5, 2.5))
        if fid == _fetch_id and login_ok:
            _push("buff_complete", buff_done)


def _resolve_vanity(name):
    # Use the XML profile endpoint — no API key required
    try:
        r = requests.get(
            f"https://steamcommunity.com/id/{name}/?xml=1",
            headers=HEADERS, timeout=10,
        )
        if r.status_code == 200:
            m = re.search(r"<steamID64>(\d{17})</steamID64>", r.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _fetch_inventory(steam_id, steam_cookie, fid):
    global _fetch_id
    cookies = {"steamLoginSecure": steam_cookie} if steam_cookie else {}
    url = STEAM_INV_URL.format(steam_id=steam_id)
    all_assets, desc_map = [], {}
    last_assetid = None
    page = 0

    while True:
        if fid != _fetch_id:
            return None
        page += 1
        _push("status", f"Fetching inventory page {page}…")
        params = {"l": "english", "count": 1000}
        if last_assetid:
            params["start_assetid"] = last_assetid

        try:
            resp = requests.get(url, params=params,
                                headers=HEADERS, cookies=cookies, timeout=20)
        except requests.exceptions.ConnectionError:
            _push("error", "No internet connection.")
            return None

        if resp.status_code == 403:
            _push("error", "Inventory is private. Set it to Public in Steam → Edit Profile → Privacy.")
            return None
        if resp.status_code == 429:
            _push("error", "Steam rate-limited the request. Wait a minute and try again.")
            return None
        if resp.status_code in (400, 500):
            _push("error",
                f"Steam returned HTTP {resp.status_code}. "
                "Check your Steam ID64 at steamid.io (must be 17 digits starting with 7656119).")
            return None
        if resp.status_code != 200:
            _push("error", f"Steam returned HTTP {resp.status_code}.")
            return None

        data = resp.json()
        if not data or "assets" not in data:
            if page == 1:
                _push("error", "Inventory is empty or could not be loaded.")
                return None
            break

        all_assets.extend(data.get("assets", []))
        for d in data.get("descriptions", []):
            desc_map[f"{d['classid']}_{d['instanceid']}"] = d
            if d["classid"] not in desc_map:
                desc_map[d["classid"]] = d

        if data.get("more_items"):
            last_assetid = data.get("last_assetid")
            time.sleep(1.5)
        else:
            break

    counts = {}
    for asset in all_assets:
        classid    = str(asset.get("classid", ""))
        instanceid = str(asset.get("instanceid", "0"))
        desc = (desc_map.get(f"{classid}_{instanceid}") or
                desc_map.get(f"{classid}_0") or
                desc_map.get(classid))
        if not desc:
            continue
        name = (desc.get("market_hash_name") or desc.get("name", "")).strip()
        if not name:
            continue
        if name not in counts:
            itype = "Other"
            for tag in desc.get("tags", []):
                if tag.get("category") == "Type":
                    itype = tag.get("localized_tag_name", "Other")
                    break
            steam_icon = desc.get("icon_url", "")
            counts[name] = {"available": 0, "cooldown": 0,
                            "type": itype, "has_market": False,
                            "steam_icon": (STEAM_CDN + steam_icon) if steam_icon else "",
                            "trade_lock": None}
        tradable   = desc.get("tradable",   0)
        marketable = desc.get("marketable", 0)
        if tradable == 1 and marketable == 1:
            counts[name]["available"]  += 1
            counts[name]["has_market"]  = True
        elif marketable == 1:
            # Trade-locked: marketable but not yet tradable (e.g. recently received)
            counts[name]["cooldown"]   += 1
            counts[name]["has_market"]  = True
            # Parse trade lock expiry from owner_descriptions
            if not counts[name]["trade_lock"]:
                for od in desc.get("owner_descriptions", []):
                    val = od.get("value", "")
                    tl_match = re.search(r"Tradable After (.+?)(?:\s*GMT)?$", val)
                    if tl_match:
                        tl_str = tl_match.group(1).strip()
                        for fmt in ("%b %d, %Y (%H:%M:%S)", "%B %d, %Y (%H:%M:%S)",
                                    "%A, %B %d, %Y (%H:%M:%S)"):
                            try:
                                tl_dt = datetime.strptime(tl_str, fmt)
                                counts[name]["trade_lock"] = tl_dt.isoformat()
                                break
                            except ValueError:
                                continue
                        break
        # Non-marketable items: has_market stays False, no cooldown increment.
        # The "⛔ Not Marketable" badge is driven by has_market=False, not qty_cd.

    if not counts:
        _push("error", "No CS2 items found in this inventory.")
        return None
    return counts


def _get_steam_price(name, steam_cookie=""):
    try:
        cookies = {"steamLoginSecure": steam_cookie} if steam_cookie else {}
        r = requests.get(STEAM_PRICE_URL,
                         params={"appid": 730, "currency": 1,
                                 "market_hash_name": name},
                         headers=HEADERS, cookies=cookies, timeout=10)
        if r.status_code == 200:
            d   = r.json()
            raw = d.get("lowest_price") or d.get("median_price", "")
            if raw:
                cleaned = raw.replace("$", "").replace(",", "").strip()
                return float(cleaned) if cleaned else None
    except Exception:
        pass
    return None


def _get_csfloat_price(name, api_key):
    try:
        r = requests.get(CSFLOAT_URL,
                         params={"market_hash_name": name, "limit": 1,
                                 "sort_by": "lowest_price", "type": "buy_now"},
                         headers={"Authorization": api_key},
                         timeout=10)
        if r.status_code in (401, 403):
            return None
        if r.status_code == 429:
            time.sleep(5)
            return None
        if r.status_code == 200:
            listings = r.json().get("data", [])
            if listings:
                l    = listings[0]
                item = l.get("item", {})
                icon = item.get("icon_url", "")
                return {
                    "price":        l["price"] / 100.0,
                    "float_value":  item.get("float_value"),
                    "inspect_link": item.get("inspect_link", ""),
                    "icon_url":     (STEAM_CDN + icon) if icon else "",
                    "paint_seed":   item.get("paint_seed"),
                }
    except Exception:
        pass
    return None


def _get_cny_rate() -> float:
    """Fetch live CNY→USD rate, cached for 1 hour. Falls back to a hardcoded rate."""
    global _buff_rate_cache
    cached_at, cached_rate = _buff_rate_cache
    if cached_rate > 0 and time.time() - cached_at < 3600:
        return cached_rate
    try:
        r = requests.get(BUFF_EXCHANGE_URL, timeout=5)
        rate = float(r.json()["rates"].get("USD", 0))
        if rate > 0:
            _buff_rate_cache = (time.time(), rate)
            return rate
    except Exception:
        pass
    return 0.138   # hardcoded fallback — update if wildly stale


def _init_buff_session(session_cookie: str) -> requests.Session:
    """
    Create a requests.Session pre-loaded with Buff's required cookies.
    Buff needs csrf_token + Device-Id + client_id (obtained by visiting the site)
    PLUS the user's session cookie for authenticated API access.
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Referer":    "https://buff.163.com/market/csgo",
        "Accept":     "application/json",
    })
    # Visit Buff to acquire csrf_token, Device-Id, client_id cookies
    try:
        s.get("https://buff.163.com/", timeout=10)
    except Exception:
        pass
    # Inject the user's session cookie and set the CSRF header
    s.cookies.set("session", session_cookie, domain="buff.163.com")
    csrf = s.cookies.get("csrf_token", "")
    if csrf:
        s.headers["X-CSRFToken"] = csrf
    return s


def _get_buff_price(name: str, session: requests.Session, cny_rate: float):
    """
    Return the lowest Buff163 sell listing price for an item, in USD.
    Returns a float price or None if not found / error.
    """
    try:
        r = session.get(
            BUFF_URL,
            params={"game": "csgo", "search": name, "page_num": 1, "page_size": 10},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        if "Login Required" in r.text:
            return None
        data = r.json()
        if data.get("code") != "OK":
            return None
        target = name.strip().lower()
        for item in data.get("data", {}).get("items", []):
            # Buff primary name is Chinese; match on market_hash_name (English)
            item_name = (item.get("market_hash_name") or item.get("name", "")).strip().lower()
            if item_name == target:
                price_cny = float(item.get("sell_min_price", 0))
                if price_cny > 0:
                    return round(price_cny * cny_rate, 2)
    except Exception:
        pass
    return None


# ── Launch browser ────────────────────────────────────────────────────────────

def _free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _open_browser(port):
    url = f"http://127.0.0.1:{port}"
    # Try Edge in app mode first (clean app window, no browser chrome)
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    launched = False
    for path in edge_candidates:
        if os.path.exists(path):
            try:
                subprocess.Popen([
                    path,
                    f"--app={url}",
                    "--window-size=1380,880",
                    "--disable-extensions",
                    "--no-first-run",
                    "--disable-background-networking",
                ])
                launched = True
                break
            except Exception:
                pass

    if not launched:
        # Try Chrome
        chrome_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in chrome_candidates:
            if os.path.exists(path):
                try:
                    subprocess.Popen([path, f"--app={url}", "--window-size=1380,880"])
                    launched = True
                    break
                except Exception:
                    pass

    if not launched:
        webbrowser.open(url)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    port = _free_port()
    # Start Flask in background thread (threaded=True for SSE)
    flask_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port,
                               debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    flask_thread.start()
    time.sleep(0.8)   # let Flask bind before opening browser
    _open_browser(port)

    # Block until /api/close is called or user Ctrl+Cs
    try:
        _shutdown_ev.wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
