"""Tests for customer model and CRUD."""
import os

import pytest

def test_create_customer():
    from core.customer import create_customer, get_customer
    c = create_customer("Test Corp", "TC", industry="制造", contact="张三")
    assert c.customer_id.startswith("CUST_")
    assert c.customer_name == "Test Corp"
    assert c.industry == "制造"
    fetched = get_customer(c.customer_id)
    assert fetched is not None
    assert fetched.customer_name == "Test Corp"

def test_create_customer_empty_name_raises():
    from core.customer import create_customer
    with pytest.raises(ValueError):
        create_customer("", "TC")

def test_list_customers():
    from core.customer import create_customer, list_customers
    create_customer("A Corp", "AC")
    create_customer("B Corp", "BC")
    customers = list_customers()
    assert len(customers) >= 2

def test_update_customer():
    from core.customer import create_customer, update_customer
    c = create_customer("Old Name", "ON")
    updated = update_customer(c.customer_id, customer_name="New Name")
    assert updated is not None
    assert updated.customer_name == "New Name"

def test_delete_customer():
    from core.customer import create_customer, delete_customer, get_customer
    c = create_customer("To Delete", "TD")
    delete_customer(c.customer_id)
    assert get_customer(c.customer_id) is None
