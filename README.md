# CS2 Inventory Tracker

A free, open-source Windows desktop app that pulls your CS2 inventory and compares prices, and shows the total value of your inventory across **Steam Market**, **CSFloat**, and **Buff163** side by side — so you can instantly see where to buy or sell for the best deal.

---

## Download

Grab the latest `CS2InventoryTracker.exe` from the [Releases](../../releases) page.
No installation needed — just double-click and go.

---

## Features

### Price Comparison Across Three Markets
The app fetches the lowest listing price for every item in your inventory from up to three sources:
- **Steam Community Market** — the default marketplace built into CS2
- **CSFloat** — a popular third-party marketplace with lower fees
- **Buff163** — a Chinese marketplace, often the cheapest globally (prices converted from CNY to USD in real time)

Each row shows all three prices. A green **BEST** tag marks whichever market has the lowest price. The **Diff** and **Savings %** columns compare Steam's price against the cheapest alternative (CSFloat or Buff163, whichever is lower), so you can see exactly how much you'd save.

### Search & Filtering
- **Search bar** — type any part of an item name to instantly filter the list
- **Category pills** — filter by item type (Rifle, Pistol, Knife, Gloves, Sticker, Case, etc.) with multi-select
- **"Cheaper on CSFloat"** filter with an adjustable minimum savings % slider
- **"Cheaper on Steam"** and **"Cheaper on Buff"** filters
- **Sort dropdown** — sort by any price column, name, or category
- **Column header sorting** — click any header to sort ascending/descending

### Favorites & Notes
- **Star any item** to pin it to the top of the list — favorites persist across sessions
- **Add notes** to any item (click the pencil icon) — notes persist across sessions
- Both stored locally in your browser's localStorage, never sent anywhere

### Float Value Display
For items with CSFloat listings, the app shows:
- The exact float value (e.g. 0.0712)
- A color-coded gradient bar showing where the float falls on the Factory New → Battle-Scarred scale
- Wear name (Factory New, Minimal Wear, Field-Tested, Well-Worn, Battle-Scarred)

### Trade Lock Countdown
Items with an active trade cooldown show a countdown badge like **"7d left"** or **"3d left"** instead of a generic lock icon. This tells you exactly when the item becomes tradable. Items that aren't marketable at all (tournament coins, etc.) show a separate **Not Marketable** badge.

### Hover Preview
Hover over any row to see a floating card with:
- Full item image
- Wear name and exact float value (6 decimal places)
- Float gradient bar with position marker
- Pattern seed / paint index

### Right-Click Menu
Right-click any row for:
- **Inspect in Game** — opens the CS2 inspect link so you can view the exact item in-game
- **Price History** — opens a chart showing Steam Market price history

### Price History Chart
- Daily average Steam Market sale prices plotted over time
- Blue line = raw daily price, lighter line = 7-day moving average
- Toggle between **30 day**, **90 day**, and **All time** views
- Press **Escape** or the close button to dismiss

### Smart Steam ID Input
You can enter your Steam identity in any of these formats — the app figures it out:
- A 17-digit Steam ID64 (e.g. `76561198012345678`)
- A vanity URL name (e.g. `myusername`)
- A full Steam profile URL (e.g. `https://steamcommunity.com/id/myusername`)
- A full Steam profile URL with ID (e.g. `https://steamcommunity.com/profiles/76561198012345678`)

### Completion Notification
When all prices finish loading, the app:
- Plays a short audio tone so you know it's done (even if you're in another window)
- Shows a browser notification if the tab is in the background (you'll be asked for permission once)

### Resizable Columns
Drag the right edge of any column header to resize it.

### Remember Credentials
Toggle the **Remember** switch to save your credentials locally between sessions. When unchecked, all credential fields are cleared from disk so the app opens blank next time.

### Footer Totals
The bottom bar shows totals for all currently visible (filtered) items:
- **Steam Value** — sum of all Steam Market prices
- **CSFloat Value** — sum of all CSFloat prices
- **Buff Value** — sum of all Buff163 prices
- **Potential Savings** — total you'd save buying each item at its cheapest alternative market instead of Steam

---

## Setup

### Step 1 — Get your Steam ID64 (required)

This is how the app knows which inventory to load. Your Steam ID64 is a 17-digit number.

1. Go to [steamid.io](https://steamid.io)
2. Paste your Steam profile URL
3. Copy the **steamID64** value (starts with `7656119...`)

**Why the app needs this:** Steam's inventory API requires a numeric ID to look up items. This is the same ID visible on any public Steam profile. The app only reads your inventory — it cannot modify anything.

### Step 2 — Get a CSFloat API Key (optional)

Without this, the app only shows Steam prices. With it, you also get CSFloat prices, float values, and inspect links.

1. Log in at [csfloat.com](https://csfloat.com)
2. Go to **Settings → Developer → API Keys**
3. Create a new key and copy it

**Why the app needs this:** CSFloat's public API requires an API key to return listing data. The key is free and only grants read access to public listings. It does not give access to your CSFloat account.

### Step 3 — Get your Steam Cookie (optional)

This enables price history charts. Without it, most features still work fine.

1. Open [steamcommunity.com](https://steamcommunity.com) in your browser and log in
2. Press **F12** → **Application** tab → **Cookies** → `steamcommunity.com`
3. Find the cookie named **`steamLoginSecure`** and copy its value

**Why the app needs this:** Steam rate-limits price history requests from unauthenticated clients. Providing your session cookie lets the app fetch history data the same way your browser does. The cookie is only sent to `steamcommunity.com` — nowhere else.

**Note:** Steam cookies expire periodically. If price history stops working, grab a fresh cookie.

### Step 4 — Get your Buff163 Session Cookie (optional)

This enables Buff163 price comparison. Without it, the Buff163 column stays empty.

1. Log in at [buff.163.com](https://buff.163.com)
2. Press **F12** → **Application** tab → **Cookies** → `buff.163.com`
3. Find the cookie named **`session`** and copy its value

**Why the app needs this:** Buff163's API requires an authenticated session to return any search results. The session cookie proves you have a Buff163 account. It is only sent to `buff.163.com` — nowhere else.

**Note:** Buff sessions expire after a while. If Buff prices stop appearing, grab a fresh session cookie.

### Step 5 — Run the app

1. Open `CS2InventoryTracker.exe`
2. Paste your credentials into the fields at the top
3. Click **Fetch & Compare**
4. Prices stream in as they're fetched — large inventories may take a few minutes

---

## Privacy & Safety

**This app is fully local and open-source. Your data never leaves your computer** except for direct API calls to Steam, CSFloat, and Buff163 — the same requests your browser makes when you visit those sites.

### What the app connects to

| Domain | Why | What is sent |
|---|---|---|
| `steamcommunity.com` | Fetch your inventory and market prices | Your Steam ID64, and optionally your Steam cookie |
| `csfloat.com` | Fetch CSFloat listing prices and float data | Your CSFloat API key + item names |
| `buff.163.com` | Fetch Buff163 listing prices | Your Buff session cookie + item names |
| `api.exchangerate-api.com` | Get the current CNY→USD exchange rate | Nothing (public API, no auth) |

### What the app does NOT do
- Does **not** access your Steam account, wallet, or trade offers
- Does **not** place orders, make trades, or modify anything on any platform
- Does **not** send data to any analytics service, telemetry endpoint, or third-party server
- Does **not** expose any network port to the internet — the local server binds to `127.0.0.1` only
- Does **not** run in the background after you close the window

### Where credentials are stored

If you enable the **Remember** toggle, credentials are saved to `config.json` in the same folder as the exe. This file stays on your computer and is never transmitted anywhere except to the APIs listed above. If you disable Remember, the file is overwritten with empty values.

Favorites and notes are stored in your browser's `localStorage` (tied to `127.0.0.1`). They never leave your machine.

### How it works internally

The app runs a local web server on `127.0.0.1` (localhost) on a random port. It opens a browser window pointed at that local address. The browser renders the UI; the Python backend handles API calls. When you close the window, the server shuts down.

All source code is in two files: `cs2_tracker.py` (backend) and `ui/index.html` (frontend). You can read every line to verify exactly what the app does.

---

## Building from Source

If you want to build the exe yourself instead of using the pre-built binary:

**Requirements:** Python 3.9+

```
1. Install Python from https://python.org
2. Double-click build.bat
```

That's it. `build.bat` installs all dependencies (`requests`, `flask`, `pyinstaller`) and builds `CS2InventoryTracker.exe` into the `dist/` folder.

### Manual build

```bash
pip install requests flask pyinstaller
pyinstaller --onefile --windowed --name "CS2InventoryTracker" --add-data "ui;ui" --icon "ui/icon.ico" cs2_tracker.py
```

---

## Troubleshooting

**"Inventory is private"**
Set your Steam inventory to Public: Steam → Edit Profile → Privacy Settings → Inventory → Public.

**No prices showing for some items**
Items not on the Steam Market (non-marketable items) won't have Steam prices. CSFloat only shows prices for items with active Buy Now listings. Buff163 only shows prices for items with active sell listings.

**Buff163 prices not showing**
Make sure you copied the correct cookie. Buff163 requires the `session` cookie from `buff.163.com`. Sessions expire — if it stops working, grab a fresh cookie.

**Price history not loading**
Price history requires the Steam cookie (`steamLoginSecure`). If it expired, grab a new one from your browser.

**App opens a browser tab instead of a clean window**
The app tries Edge first, then Chrome, then your default browser. If neither Edge nor Chrome is installed, it opens as a regular browser tab. Everything works the same — it just won't have the borderless app window look.

**Prices are slow to load**
Steam rate-limits market requests. The app fetches up to 4 items in parallel with spacing to stay within limits. A large inventory (100+ items) takes a few minutes. Buff163 prices are fetched sequentially after Steam/CSFloat to avoid rate limits.

---

## Tech Stack

- **Backend:** Python (Flask, requests)
- **Frontend:** HTML / CSS / JavaScript (vanilla, no frameworks)
- **Charts:** Chart.js
- **Packaging:** PyInstaller

---

## License

MIT — free to use, modify, and distribute.
