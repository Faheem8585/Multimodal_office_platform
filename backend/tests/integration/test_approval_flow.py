"""End-to-end exercise of the configurable approval engine via the API."""

import pytest

pytestmark = pytest.mark.integration


async def _create_expense_workflow(client, headers) -> None:
    res = await client.post(
        "/api/v1/approvals/workflows",
        headers=headers,
        json={
            "name": "Large expense",
            "department": "finance",
            "resource_type": "expense",
            "trigger": {">": [{"var": "amount"}, 1000]},
            "steps": [
                {
                    "order_index": 0,
                    "name": "Finance manager",
                    "required_role": "dept_manager",
                    "required_department": "finance",
                },
                {"order_index": 1, "name": "Admin sign-off", "required_role": "admin"},
            ],
        },
    )
    assert res.status_code == 201, res.text


async def test_small_expense_auto_approves(client, seeded, as_user):
    member = await as_user("finance_member")
    create = await client.post(
        "/api/v1/finance/expenses",
        headers=member,
        json={"merchant": "Cafe", "amount": 42.5, "category": "general"},
    )
    assert create.status_code == 201, create.text
    expense_id = create.json()["id"]

    submit = await client.post(f"/api/v1/finance/expenses/{expense_id}/submit", headers=member)
    # No workflow matches amount<=1000 -> auto-approved.
    assert submit.status_code == 200
    assert submit.json()["status"] == "approved"


async def test_large_expense_two_step_approval(client, seeded, as_user):
    manager = await as_user("finance_manager")
    admin = await as_user("admin")
    member = await as_user("finance_member")

    await _create_expense_workflow(client, manager)

    create = await client.post(
        "/api/v1/finance/expenses",
        headers=member,
        json={"merchant": "Laptop Inc", "amount": 2500, "category": "general"},
    )
    expense_id = create.json()["id"]
    submit = await client.post(f"/api/v1/finance/expenses/{expense_id}/submit", headers=member)
    assert submit.json()["status"] == "submitted"  # awaiting approval

    # Step 1: finance manager approves -> advances to admin step.
    pending = await client.get("/api/v1/approvals/requests/pending", headers=manager)
    assert pending.status_code == 200
    request_id = pending.json()[0]["id"]
    step1 = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers=manager,
        json={"approve": True, "comment": "ok"},
    )
    assert step1.json()["status"] == "pending"
    assert step1.json()["current_step"] == 1

    # A non-eligible approver (finance member) cannot decide the admin step.
    forbidden = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers=member,
        json={"approve": True},
    )
    assert forbidden.status_code == 403

    # Step 2: admin approves -> request approved, finalizer marks expense approved.
    step2 = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers=admin,
        json={"approve": True},
    )
    assert step2.json()["status"] == "approved"

    listing = await client.get("/api/v1/finance/expenses", headers=member)
    target = next(e for e in listing.json()["items"] if e["id"] == expense_id)
    assert target["status"] == "approved"


async def test_rejection_terminates_request(client, seeded, as_user):
    manager = await as_user("finance_manager")
    member = await as_user("finance_member")
    await _create_expense_workflow(client, manager)

    create = await client.post(
        "/api/v1/finance/expenses",
        headers=member,
        json={"merchant": "Yacht", "amount": 99999, "category": "general"},
    )
    expense_id = create.json()["id"]
    await client.post(f"/api/v1/finance/expenses/{expense_id}/submit", headers=member)

    pending = await client.get("/api/v1/approvals/requests/pending", headers=manager)
    request_id = pending.json()[0]["id"]
    rejected = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers=manager,
        json={"approve": False, "comment": "too much"},
    )
    assert rejected.json()["status"] == "rejected"
