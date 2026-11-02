# ☀️ zynsolar CRM — Solar Operations & Commercial Pipeline System

**zynsolar CRM** is an end-to-end operations and business intelligence platform engineered specifically for **Solar EPCs, Rooftop Installers, and Clean Energy Distributors**. It bridges the gap between lead acquisition, engineering site surveys, field crew deployments, DISCOM/KSEB net-metering approvals, and financial receivables.

---

## 🚀 Key Features

* **Dynamic Milestone Stepper & Pipeline:** Seamless progression through configured operational milestones:
  * `New Lead` → `Site Survey` → `Installation Scheduled` → `Installation in Progress` → `Installed` → `KSEB / Net-Metering` → `Handover Complete`.
* **Field Workforce & Team Operations:** Crew assignment, specialized field deployment units (Alpha, Beta, Omega), team workload visibility, and dedicated team workspaces.
* **Financial & Commercial Tracking:** Real-time visibility into total contract values, advance collections, pending receivables, and payment vouchers.
* **Catalog & Equipment Masters:** Granular control over solar panel brands, cell technologies, inverter ratings, mounting structures, and safety accessories.
* **Executive Dashboards & BI Reports:** Company-wide volume trends, stage distribution analytics, staff sales directories, and print/export utilities (Excel/CSV/PDF).

---

## 🛠️ Built With

* **Backend:** Python 3, Django 5 (CBVs, ORM, Custom Middleware)
* **Frontend:** HTML5, Modern CSS Variables, Bootstrap 5, Bootstrap Icons
* **Database:** SQLite (Development) / PostgreSQL (Production ready)
* **Automation & Testing:** Playwright End-to-End Test Suite

---

## ⚡ Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/botgiptb/zynsolar.git
cd zynsolar
```

### 2. Set up virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
python manage.py migrate
```

### 5. Seed initial demo data (Optional)
```bash
python manage.py seed_data
```

### 6. Start the development server
```bash
python manage.py runserver 127.0.0.1:3000
```
Visit `http://127.0.0.1:3000` in your browser.

---

## 📄 License
Copyright © 2026 zynsolar CRM. All rights reserved.
Unauthorized copying, distribution, or commercial use of this codebase is strictly prohibited.
