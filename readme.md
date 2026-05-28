# 🌿 Breathe ESG Backend

Backend API service for the Breathe ESG platform.

Built with Django REST Framework, this service ingests ESG emissions datasets from SAP exports, utility bills, and corporate travel systems, normalizes them into kgCO₂e records, and provides analyst review workflows with immutable audit tracking.

---

# 🚀 Features

* 📥 ESG data ingestion APIs
* 🏢 Multi-tenant architecture
* 📊 Emissions normalization to kgCO₂e
* ✅ Analyst review & approval workflow
* 🔒 Immutable audit trail
* 📄 SAP flat file parsing
* ⚡ Utility CSV ingestion
* ✈️ Corporate travel emissions processing
* 📈 Dashboard & reporting endpoints
* 🌐 RESTful API with Django REST Framework

---

# 🛠 Tech Stack

* Python 3.11+
* Django 4.2
* Django REST Framework
* SQLite (development)
* PostgreSQL (production)
* Pandas
* pdfplumber
* WhiteNoise
* Gunicorn

---

# 📂 Project Structure

```text id="7j5zcg"
backend/
├── breathe/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── ingestion/                # Main ESG ingestion app
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── parsers/
│   │   ├── sap_parser.py
│   │   ├── utility_parser.py
│   │   └── travel_parser.py
│   └── management/commands/
│       └── seed.py
│
├── sample_data/
├── requirements.txt
├── manage.py
└── runtime.txt
```

---

# ⚙️ Local Development Setup

## 1. Clone Repository

```bash id="8j8bh4"
git clone <your-repo-url>
cd backend
```

## 2. Create Virtual Environment

### Windows

```powershell id="mj1b4x"
py -3.11 -m venv venv
.\venv\Scripts\activate
```

### macOS / Linux

```bash id="r0r2oi"
python3.11 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash id="29bb4f"
pip install -r requirements.txt
```

---

## 4. Run Migrations

```bash id="2ixx0r"
python manage.py migrate
```

---

## 5. Seed Demo Data

```bash id="udj1ib"
python manage.py seed
```

Creates:

* Demo tenant
* Analyst user
* Sample ESG records

---

## 6. Start Development Server

```bash id="x4w9ci"
python manage.py runserver
```

API runs at:

```text id="1k9jlwm"
http://localhost:8000
```

---

# 🔑 Demo Credentials

| Type             | Value                                  |
| ---------------- | -------------------------------------- |
| Tenant ID        | `00000000-0000-0000-0000-000000000001` |
| Analyst Username | `analyst`                              |
| Analyst Password | `analyst123`                           |

Django Admin:

```text id="9fg1wo"
http://localhost:8000/admin
```

---

# 📡 API Endpoints

| Method | Endpoint                     | Description            |
| ------ | ---------------------------- | ---------------------- |
| POST   | `/api/ingest/`               | Upload ESG dataset     |
| GET    | `/api/dashboard/`            | Dashboard metrics      |
| GET    | `/api/records/`              | List emission records  |
| PATCH  | `/api/records/{id}/edit/`    | Edit emission record   |
| POST   | `/api/records/{id}/approve/` | Approve record         |
| POST   | `/api/records/{id}/reject/`  | Reject record          |
| POST   | `/api/records/{id}/lock/`    | Lock approved record   |
| GET    | `/api/records/{id}/history/` | Audit history          |
| GET    | `/api/batches/`              | List ingestion batches |

---

# 📁 Sample Data

Use files from:

```text id="ob3iut"
backend/sample_data/
```

Supported sources:

| File               | Source Type |
| ------------------ | ----------- |
| sap_sample.txt     | SAP         |
| utility_sample.csv | Utility     |
| travel_sample.csv  | Travel      |

---

# 🧪 Example API Usage

## Upload Utility Data

```bash id="9czgic"
curl -X POST http://localhost:8000/api/ingest/ \
  -F "tenant_id=00000000-0000-0000-0000-000000000001" \
  -F "source_type=UTILITY" \
  -F "file=@sample_data/utility_sample.csv"
```

## Dashboard Summary

```bash id="c21a0k"
curl http://localhost:8000/api/dashboard/?tenant=00000000-0000-0000-0000-000000000001
```

## List Pending Records

```bash id="wvnklw"
curl "http://localhost:8000/api/records/?tenant=00000000-0000-0000-0000-000000000001&status=PENDING"
```

---

# ☁️ Deployment

## Vercel

Create:

```text id="gsl8gz"
runtime.txt
```

Content:

```text id="ow9cg9"
python-3.11
```

Example `vercel.json`:

```json id="54e8i4"
{
  "builds": [
    {
      "src": "breathe/wsgi.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "breathe/wsgi.py"
    }
  ]
}
```

---

# 🔐 Environment Variables

Create `.env`:

```env id="r3xq1s"
SECRET_KEY=your_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

Production example:

```env id="pzjlwm"
DEBUG=False
ALLOWED_HOSTS=.vercel.app
```

---

# 📜 License

MIT License
