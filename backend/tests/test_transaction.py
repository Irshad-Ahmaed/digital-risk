import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_concurrent_debits(client):
    import asyncio
    
    # 1. Setup user with 10000 cents credit
    user_id = "concurrent_user"
    await client.post("/transaction", json={
        "user_id": user_id,
        "transaction_id": str(uuid.uuid4()),
        "type": "credit",
        "amount": 10000
    })
    
    # 2. Fire 2 concurrent debits of 8000 cents
    # Only one should succeed
    async def make_debit():
        return await client.post("/transaction", json={
            "user_id": user_id,
            "transaction_id": str(uuid.uuid4()),
            "type": "debit",
            "amount": 8000
        })

    results = await asyncio.gather(make_debit(), make_debit())
    
    successes = [r for r in results if r.status_code == 200]
    failures = [r for r in results if r.status_code == 422]
    
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].json()["error"] == "INSUFFICIENT_FUNDS"

@pytest.mark.asyncio
async def test_idempotent_retry(client):
    user_id = "idempotent_user"
    tx_id = str(uuid.uuid4())
    
    payload = {
        "user_id": user_id,
        "transaction_id": tx_id,
        "type": "credit",
        "amount": 5000
    }
    
    r1 = await client.post("/transaction", json=payload)
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"
    
    r2 = await client.post("/transaction", json=payload)
    assert r2.status_code == 200
    assert r2.json()["status"] == "already_processed"
    
    summary = await client.get(f"/summary/{user_id}")
    assert summary.json()["balance"] == 5000

@pytest.mark.asyncio
async def test_conflict_different_payload(client):
    user_id = "conflict_user"
    tx_id = str(uuid.uuid4())
    
    await client.post("/transaction", json={
        "user_id": user_id,
        "transaction_id": tx_id,
        "type": "credit",
        "amount": 5000
    })
    
    r2 = await client.post("/transaction", json={
        "user_id": user_id,
        "transaction_id": tx_id, # same ID
        "type": "credit",
        "amount": 9999 # different amount
    })
    
    assert r2.status_code == 409
    assert r2.json()["error"] == "TRANSACTION_CONFLICT"
