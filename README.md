# CoreInventory 📦

**Odoo × Indus University Hackathon '26**

CoreInventory is a modular, real-time Inventory Management System built to replace paper registers, Excel sheets, and scattered tracking with one clean, fast, browser-based app. Everything from receiving stock to dispatching deliveries is tracked, logged, and visible in real time.

---

## Getting Started

You need Python 3.10+ and pip installed. That's it — no database servers, no cloud setup, no configuration files.

```bash
git clone https://github.com/YOUR_USERNAME/coreinventory.git
cd coreinventory
pip install -r requirements.txt
python app.py
```

Then open your browser and go to **http://localhost:5000**

The app seeds itself with sample data on the first run, so you'll see products, a warehouse, and locations ready to go immediately.

---

## Login Credentials

Two accounts are ready to use out of the box:

**Admin Account (default)**
| Field | Value |
|-------|-------|
| Login ID | `admin` |
| Password | `Admin@123` |

**Owner Account**
| Field | Value |
|-------|-------|
| Login ID | `Owner1` |
| Password | `New@2026` |
| Email | `infinitymusic125@gmail.com` |

> The Owner account email is also used for the Forgot Password / OTP reset flow. If you forget your password, enter your Login ID and this email to receive an OTP.

> **Note:** Every time you restart the server with `python app.py`, all active sessions are cleared. Everyone needs to log in again — this is intentional for security.

---

## What This App Does

CoreInventory covers the full lifecycle of warehouse stock operations.

**Authentication** — Users sign up with a Login ID (6–12 characters), a valid email, and a strong password (8+ characters, must include uppercase, lowercase, and a special character). Forgot your password? Enter your Login ID and registered email, and an OTP gets sent to your inbox. In development mode the OTP also prints in the terminal so you never get locked out.

**Dashboard** — The first thing you see after logging in. Two big cards show your Receipt and Delivery situation at a glance — how many are pending, how many are late (scheduled before today), how many are waiting for stock, and how many are upcoming. A low-stock alert fires automatically if any product drops below its reorder level. The recent activity feed shows the last 10 stock movements and refreshes on its own every 15 seconds.

**Receipts** — When goods arrive from a vendor, you create a receipt. The reference is auto-generated in `WH/IN/0001` format. The status moves Draft → Ready → Done. Clicking "Mark as Ready" confirms the items are physically present. Clicking "Validate" does the actual work — it increases each product's stock and logs every movement to the ledger. Once Done, a Print button appears so you can generate a clean printable receipt.

**Deliveries** — When stock goes out to a customer, you create a delivery. Reference format is `WH/OUT/0001`. The status flow here is longer: Draft → Waiting → Ready → Done. Waiting means you're holding because some items aren't in stock yet — the delivery items table highlights those rows in red and shows an alert. Ready means everything is available. Validate then deducts stock and logs the movements. If you try to validate without enough stock, the system blocks it and tells you exactly which product failed and by how much.

**Stock Page** — A clean view of every product showing Per Unit Cost, On Hand quantity, and Free to Use quantity. Free to Use is On Hand minus whatever is reserved in pending deliveries — so you always know what's actually available to commit. You can update stock directly from this page for physical count corrections.

**Move History** — The complete ledger of every single stock movement. Incoming moves show in green, outgoing in red. Each row shows Reference, Date, Contact, From location, To location, Quantity, and Status. You can switch between a list view and a kanban view grouped by status. Search works across both reference numbers and contact names.

**Adjustments** — For fixing mismatches between what the system shows and what a physical count reveals. You pick a product, enter the correct quantity, add a reason, and the system calculates and logs the difference.

**Settings** — Manage your warehouses (Name, Short Code, Address) and the locations inside them (Rack A, Production Floor, Cold Storage, etc.). Every location is linked to a warehouse and shows up in the Move History From/To columns.

**Intelligence** — An AI-powered page that reads your current inventory data and gives you four specific, data-driven insights and recommendations. Powered by Claude (Anthropic).

**Dark Mode** — Click the moon icon in the top right to switch. The preference sticks across pages and browser sessions.

---

## Tech Stack

| Part | What We Used |
|------|-------------|
| Backend | Python + Flask |
| Database | SQLite via Flask-SQLAlchemy |
| Frontend | Bootstrap 5 + Vanilla JavaScript |
| Icons | Bootstrap Icons |
| Fonts | DM Sans (Google Fonts) |
| AI | Claude API by Anthropic |

We chose SQLite deliberately — the system works completely offline with zero configuration, which matters for warehouses where internet can be unreliable.

---

## Project Structure

```
coreinventory/
├── app.py                      ← Everything backend: models, APIs, page routes
├── requirements.txt
├── README.md
│
├── templates/
│   ├── base.html               ← Sidebar, topbar, dark mode, toast system
│   ├── login.html
│   ├── signup.html
│   ├── forgot_password.html
│   ├── dashboard.html          ← Receipt + Delivery KPI cards
│   ├── receipts.html           ← List view + Kanban view
│   ├── receipt_detail.html     ← Draft → Ready → Done flow
│   ├── deliveries.html         ← List view + Kanban view
│   ├── delivery_detail.html    ← Draft → Waiting → Ready → Done
│   ├── stock.html              ← On Hand + Free to Use
│   ├── products.html           ← Full catalog management
│   ├── move_history.html       ← Ledger with IN/OUT coloring
│   ├── adjustments.html
│   ├── settings.html           ← Warehouses + Locations
│   └── intelligence.html       ← AI insights
│
└── static/
    ├── css/style.css           ← Design system
    └── js/
        ├── dashboard.js
        ├── products.js
        ├── operations.js       ← Shared receipt/delivery logic
        ├── move_history.js
        └── intelligence.js
```

---

## Database Tables

| Table | What it stores |
|-------|---------------|
| `users` | Login accounts |
| `products` | Product catalog with stock levels |
| `operations` | Receipts and deliveries |
| `operation_items` | Individual product lines per operation |
| `stock_ledger` | Every stock movement ever made |
| `warehouses` | Warehouse definitions |
| `locations` | Sub-locations inside warehouses |

---

## API Overview

All frontend pages communicate with the backend through these REST endpoints.

**Dashboard:** `GET /api/dashboard`

**Products:** `GET/POST /api/products` · `PUT/DELETE /api/products/<id>` · `POST /api/products/<id>/adjust` · `GET /api/stock-summary`

**Operations:** `GET/POST /api/operations` · `POST /api/operations/<id>/items` · `POST /api/operations/<id>/waiting` · `POST /api/operations/<id>/ready` · `POST /api/operations/<id>/validate` · `POST /api/operations/<id>/cancel`

**Ledger:** `GET /api/stock-ledger`

**Auth:** `POST /api/signup` · `POST /api/login` · `POST /api/logout` · `GET /api/me` · `POST /api/otp/send` · `POST /api/otp/verify` · `POST /api/reset-password`

**Settings:** `GET/POST /api/warehouses` · `PUT/DELETE /api/warehouses/<id>` · `GET/POST /api/locations` · `PUT/DELETE /api/locations/<id>`

---

## Sample Data (Auto-seeded on First Run)

| Product | Quantity | Status |
|---------|----------|--------|
| Steel Rods | 150 kg | ✅ Healthy |
| Office Chairs | 40 units | ✅ Healthy |
| Copper Wire | 8 meters | ⚠️ Low Stock |
| Cardboard Boxes | 500 units | ✅ Healthy |
| Laptop Stand | 5 units | ⚠️ Low Stock |

Default Warehouse: **Main Warehouse (WH)** — Indus University, Ahmedabad

Default Locations: WH/Stock · WH/PROD · WH/RACK-A

---

## Judging Criteria

| Criterion | How we meet it |
|-----------|---------------|
| Dynamic Data | Every number on screen comes live from the database. No static JSON anywhere in the final build. |
| Clean UI | DM Sans font, consistent emerald + slate color system, fully responsive, dark mode. |
| Robust Validation | Stock is checked before every delivery validation. SKUs must be unique. Passwords require complexity. Forms validate client and server side. |
| Intuitive UX | Sidebar navigation, status flow indicators on detail pages, toast notifications, empty states, auto-refresh. |
| Version Control | Git repository with commits from all four team members throughout development. |
| Full Stack | Flask REST API + SQLAlchemy ORM + SQLite + Bootstrap frontend with vanilla JS. |
| AI Adaptation | Claude AI powers the Intelligence page. Every line of AI-generated code was read, understood, and adapted — not blindly copied. |
| Offline Capability | SQLite means the entire system runs without any internet connection or cloud services. |

---

## Team

| Role | What they built |
|------|----------------|
| UI/UX Lead | All HTML pages, Bootstrap styling, Chart.js, dashboard design, demo video |
| Backend Lead | Flask APIs, SQLite schema, stock validation logic, OTP system |
| Integration | JavaScript fetch() calls, form validation, API-to-UI wiring |
| DevOps & Docs | GitHub management, README, portal submission, version control |

---

## Notes

To completely reset the app and start fresh, delete the `instance/coreinventory.db` file and restart. The database recreates itself with fresh sample data.

OTP emails require SMTP credentials configured in `app.py`. Without them, the OTP is printed directly to the terminal — useful for testing and demos.

Built entirely during the hackathon sprint. No pre-built or reused projects.

---

*Odoo × Indus University Hackathon '26 — CODE. CREATE. CONQUER. 🚀*
