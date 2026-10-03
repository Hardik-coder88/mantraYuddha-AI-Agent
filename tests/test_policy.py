from app.policy import refund_cap

def test_cap_never_exceeds_order_value():
    assert refund_cap(10000, 2499) == 2499

def test_cap_with_restocking():
    assert refund_cap(None, 1000, 10) == 900

def test_cap_respects_lower_request():
    assert refund_cap(500, 2499) == 500

def test_cap_never_negative():
    assert refund_cap(100, 0) == 0
