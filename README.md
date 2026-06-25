# Digital Risk Transaction System

A robust, idempotent transaction processing backend and live dashboard frontend built with FastAPI and PostgreSQL. 

This project demonstrates strong API design, strict concurrency controls, a modular Domain-Driven Design (DDD) architecture, and a multi-factor ranking system that resists gaming and manipulation.

## Technical Stack
* **Backend:** FastAPI (Python), SQLAlchemy 2.0 (async), Pydantic v2
* **Database:** PostgreSQL (Neon) with `asyncpg` driver
* **Frontend:** Vanilla HTML/CSS/JS (Single Page Application)

---

## Deployment Stack

This project is built to be easily deployed using modern serverless and cloud platforms:
- **Backend API:** Render.
- **Frontend Dashboard:** Vercel (Static Site), requiring zero build configuration.
- **Database:** Neon PostgreSQL (Serverless Database).

---

## How to Run Locally (Development)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your local DATABASE_URL
uvicorn app.main:app --reload
```
API runs at `http://127.0.0.1:8000`.

### 2. Frontend Setup
Run a local HTTP server in the frontend directory:
```bash
cd frontend
python -m http.server 3000
```
View at `http://localhost:3000`.

### 3. Seeding Data
Populate the DB with test users and transactions:
```bash
cd backend
python seed.py
```

---

## API Reference

### 1. `POST /transaction`
Processes a financial transaction safely.
* **Idempotency:** Re-submitting the exact same `transaction_id` and payload will return a `200 OK` with `status: "already_processed"`, protecting against network retries.
* **Conflict Prevention:** Submitting the same `transaction_id` with a *different* payload returns `409 Conflict`.
* **Concurrency:** Uses database transactions and atomic conditional updates to prevent race conditions during concurrent debits.

### 2. `GET /summary/{user_id}`
Returns aggregated statistics for a user, including total credits, debits, transaction count, and account age.

### 3. `GET /ranking`
Returns the global leaderboard of users based on a multi-factor scoring algorithm.

---

## Core Engineering Solutions

### How Duplicate Requests are Prevented
Duplicates are handled via **true idempotency** enforced at the database level.
1. The client generates a unique UUID (`transaction_id`) before the request.
2. The `transactions` table has a `UNIQUE` constraint on `transaction_id`.
3. Before calculating balances, the system explicitly starts a PostgreSQL **Savepoint** (`begin_nested()`) and attempts to `INSERT` the transaction. 
4. If an `IntegrityError` is thrown, the savepoint rolls back safely. The system checks if the payload matches the original, and if so, returns the original successful result instead of processing it again. 
5. This makes network retries 100% safe.

### How Concurrency is Handled
If two requests try to withdraw funds simultaneously:
1. The user's account is upserted and locked via a `SELECT ... FOR UPDATE` query. 
2. The actual balance change is executed atomically using an `UPDATE ... WHERE balance >= amount` guard.
3. If the row isn't updated (because the condition fails), the system immediately aborts the transaction, preventing overdrafts.

### How Ranking is Calculated (Anti-Gaming)
The ranking is not based purely on balance or transaction volume, which are easily manipulated. It uses a **4-Factor Formula**, normalized to `[0.0, 1.0]`:

1. **Balance (50%):** Net worth matters most.
2. **Activity (20%):** Uses a logarithmic scale capped at ~50 transactions. This means submitting 1000 tiny transactions gives no more score than submitting 50, preventing spam.
3. **Longevity (20%):** Days active on the platform. Brand new accounts cannot immediately top the list.
4. **Abuse Penalty (-10%):** Users with a high number of failed/rejected transactions receive a penalty deduction.

### Money Representation
All monetary values (`amount`, `balance`) are stored and calculated as **integer cents (BIGINT)** in the database and API. This completely eliminates floating-point precision errors (e.g., `0.1 + 0.2 = 0.30000000000000004`). The frontend parses these values dynamically and formats them cleanly back into readable dollars.
