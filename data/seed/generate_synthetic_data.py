import random
from datetime import date, timedelta

import psycopg
from faker import Faker

from app.config import settings

fake = Faker()
random.seed(42)  # reproducible data across runs

CLAIM_TYPES = ["auto", "property", "liability"]
LOSS_TYPE_BY_CLAIM_TYPE = {
    "auto": "property",
    "property": "property",
    "liability": "liability",
}
STATUSES = ["open", "closed", "reopened"]
TENANTS = ["tenant_alpha", "tenant_beta", "tenant_gamma"]

# top-level transaction type
TRAN_TYPES = ["Loss Reserve", "Loss Payment"]
# sub-type, used with either tran type
TRAN_SUBTYPES = ["Claim Expense", "Legal Expense", "Mitigation", "Reset Reserves", "LAE"]

NUM_CLAIMS = 200


def random_date_between(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def generate_claim(claim_index: int) -> dict:
    claim_type = random.choice(CLAIM_TYPES)
    date_of_loss = random_date_between(date(2024, 1, 1), date(2026, 6, 1))
    status = random.choice(STATUSES)
    date_close = None
    if status == "closed":
        date_close = date_of_loss + timedelta(days=random.randint(20, 180))

    return {
        "claim_no": f"CLM-{2024 + claim_index // 100}-{claim_index:05d}",
        "risk_id": f"POL-{random.randint(10000, 99999)}",
        "date_of_loss": date_of_loss,
        "insured_name": fake.name(),
        "agency_name": fake.company(),
        "claim_type_code": claim_type,
        "loss_type_code": LOSS_TYPE_BY_CLAIM_TYPE[claim_type],
        "amount_claimed": round(random.uniform(1000, 50000), 2),
        "claim_status_code": status,
        "claim_substatus_code": str(random.randint(1, 6)),
        "date_close": date_close,
        "catastrophe_yn": "Y" if random.random() < 0.05 else "N",
        "event_name": fake.word().title() if random.random() < 0.05 else None,
        "tenant_id": random.choice(TENANTS),
        "inserted_userid_fk": random.randint(1, 20),
    }


def generate_reserve_transactions(claim_id: int, date_of_loss: date) -> list[dict]:
    """
    Generates a realistic ledger for one claim using the two-level
    tran_type_code / tran_subtype_code classification.
    """
    transactions = []
    active_subtypes = random.sample(TRAN_SUBTYPES, k=random.randint(1, 3))

    for subtype in active_subtypes:
        reserve_date = date_of_loss + timedelta(days=random.randint(1, 5))
        initial_amount = round(random.uniform(500, 20000), 2)

        transactions.append({
            "tran_type_code": "Loss Reserve",
            "tran_subtype_code": subtype,
            "reserve_description": f"Initial {subtype} reserve",
            "amount": initial_amount,
            "gross_amount": initial_amount,
            "tax_amount": 0.00,
            "payment_approved": None,
            "status": "active",
            "reserve_date": reserve_date,
        })

        # ~40% chance of a reserve reset/revision
        current_amount = initial_amount
        if random.random() < 0.4:
            change_date = reserve_date + timedelta(days=random.randint(10, 60))
            change_amount = round(current_amount * random.uniform(0.7, 1.5), 2)
            transactions.append({
                "tran_type_code": "Loss Reserve",
                "tran_subtype_code": "Reset Reserves",
                "reserve_description": f"Reserve revision for {subtype}",
                "amount": change_amount,
                "gross_amount": change_amount,
                "tax_amount": 0.00,
                "payment_approved": None,
                "status": "active",
                "reserve_date": change_date,
            })
            current_amount = change_amount

        # ~50% chance of one or more payments against this subtype
        if random.random() < 0.5:
            for _ in range(random.randint(1, 3)):
                pay_date = reserve_date + timedelta(days=random.randint(15, 90))
                gross = round(current_amount * random.uniform(0.1, 0.4), 2)
                tax = round(gross * 0.05, 2)
                transactions.append({
                    "tran_type_code": "Loss Payment",
                    "tran_subtype_code": subtype,
                    "reserve_description": f"Payment against {subtype}",
                    "amount": gross + tax,
                    "gross_amount": gross,
                    "tax_amount": tax,
                    "payment_approved": "Y",
                    "status": "active",
                    "reserve_date": pay_date,
                })

    return transactions


def main():
    conn = psycopg.connect(settings.database_url)
    cur = conn.cursor()

    print(f"Generating {NUM_CLAIMS} claims...")

    for i in range(NUM_CLAIMS):
        claim_data = generate_claim(i)

        cur.execute(
            """
            INSERT INTO claims
                (claim_no, risk_id, date_of_loss, insured_name, agency_name,
                 claim_type_code, loss_type_code, amount_claimed,
                 claim_status_code, claim_substatus_code, date_close,
                 catastrophe_yn, event_name, tenant_id, inserted_userid_fk)
            VALUES (%(claim_no)s, %(risk_id)s, %(date_of_loss)s, %(insured_name)s,
                    %(agency_name)s, %(claim_type_code)s, %(loss_type_code)s,
                    %(amount_claimed)s, %(claim_status_code)s,
                    %(claim_substatus_code)s, %(date_close)s, %(catastrophe_yn)s,
                    %(event_name)s, %(tenant_id)s, %(inserted_userid_fk)s)
            RETURNING claim_id
            """,
            claim_data,
        )
        claim_id = cur.fetchone()[0]

        transactions = generate_reserve_transactions(claim_id, claim_data["date_of_loss"])
        true_total_paid = 0.0

        for txn in transactions:
            txn["claim_id"] = claim_id
            txn["inserted_userid_fk"] = claim_data["inserted_userid_fk"]
            cur.execute(
                """
                INSERT INTO claim_reserves
                    (claim_id, reserve_date, tran_type_code, tran_subtype_code,
                     reserve_description, amount, gross_amount, tax_amount,
                     payment_approved, status, inserted_userid_fk)
                VALUES (%(claim_id)s, %(reserve_date)s, %(tran_type_code)s,
                        %(tran_subtype_code)s, %(reserve_description)s, %(amount)s,
                        %(gross_amount)s, %(tax_amount)s, %(payment_approved)s,
                        %(status)s, %(inserted_userid_fk)s)
                """,
                txn,
            )
            if txn["tran_type_code"] == "Loss Payment":
                true_total_paid += txn["amount"]

        # Simulate the denormalized cache: ~85% of the time it's correct,
        # ~15% of the time it's stale/drifted (a realistic bug pattern).
        if random.random() < 0.85:
            cached_total = round(true_total_paid, 2)
        else:
            cached_total = round(true_total_paid * random.uniform(0.7, 0.95), 2)

        cur.execute(
            "UPDATE claims SET total_paid_amount = %s WHERE claim_id = %s",
            (cached_total, claim_id),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()