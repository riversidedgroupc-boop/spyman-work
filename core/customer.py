"""Customer management data model and operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.id_utils import generate_id
from core.storage import fetch_all, fetch_one, insert, update


@dataclass
class Customer:
    customer_id: str
    customer_name: str
    short_name: str
    industry: str | None = None
    contact: str | None = None
    location: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.customer_name.strip():
            raise ValueError("customer_name 不能为空")
        if not self.short_name.strip():
            raise ValueError("short_name 不能为空")

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "short_name": self.short_name,
            "industry": self.industry,
            "contact": self.contact,
            "location": self.location,
            "notes": self.notes,
            "created_at": self.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Customer:
        return cls(
            customer_id=d["customer_id"],
            customer_name=d["customer_name"],
            short_name=d["short_name"],
            industry=d.get("industry"),
            contact=d.get("contact"),
            location=d.get("location"),
            notes=d.get("notes"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


def _gen_id() -> str:
    return generate_id("CUST")


def create_customer(
    customer_name: str,
    short_name: str,
    industry: str | None = None,
    contact: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> Customer:
    c = Customer(
        customer_id=_gen_id(),
        customer_name=customer_name,
        short_name=short_name,
        industry=industry,
        contact=contact,
        location=location,
        notes=notes,
    )
    insert("customers", c.to_dict())
    return c


def get_customer(customer_id: str) -> Customer | None:
    row = fetch_one("customers", customer_id)
    return Customer.from_dict(row) if row else None


def list_customers() -> list[Customer]:
    rows = fetch_all("customers", where="1 ORDER BY created_at DESC")
    return [Customer.from_dict(r) for r in rows]


def update_customer(customer_id: str, **kwargs) -> Customer | None:
    existing = get_customer(customer_id)
    if not existing:
        return None
    for k, v in kwargs.items():
        if hasattr(existing, k) and v is not None:
            setattr(existing, k, v)
    update("customers", customer_id, existing.to_dict())
    return existing


def delete_customer(customer_id: str) -> None:
    from core.project_cascade import delete_customer_cascade

    delete_customer_cascade(customer_id)
