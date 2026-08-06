# concept-tracking-api-CICD

## Code Structure

```
concept-tracking-api/
│   main.py
│   README.md
│   requirements.txt
│   .env.example
│   .env
│   .gitignore
│
├───app/
│   ├───api/
│   │   ├───auth_callback.py
│   │   ├───clients_approval.py
│   │   ├───concept_by_user.py
│   │   ├───concepts.py
│   │   ├───create_concept.py
│   │   ├───dashboard.py
│   │   ├───delete_attachment.py
│   │   ├───download_attachment.py
│   │   ├───latest_updates.py
│   │   ├───login.py
│   │   ├───master_data.py
|   |   ├───status.py
|   |   ├───upload_supporting_docs.py
│   │   └───__init__.py
│   ├───core/
│   │   ├───authenticate.py
│   │   ├───config.py
│   │   ├───logger_config.py
│   │   ├───oauth.py
|   |   ├───sql_connection.py
│   │   └───__init__.py
│   ├───utils/
│   │   ├───concept_helpers.py
│   │   └───status_permissions.py
│   └───services/
│       ├───concept_queries.py
│       ├───file_handler.py
│       ├───file_handlers.py
│       └───pydantic_schemas.py
│
├───logs
```

## Installation

```bash
git clone <repo-url>
cd concept-tracking-api
pip install -r requirements.txt
```

---

## Environment Setup

```bash
cp .env.example .env
```

Fill in the values in `.env`.

---

## Running Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 6200 --reload
```

API docs available at `http://localhost:6200/docs`

---

## For hosting the backend to access the endpoints
```bash
uvicorn main:app --host 0.0.0.0 --port 6200 --ssl-keyfile "C:\certs\privatekey_nopass.pem" --ssl-certfile "C:\certs\certificate.pem"
```
