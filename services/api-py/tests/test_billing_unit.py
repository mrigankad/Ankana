"""Billing pieces that need no database: GSTIN, tax split, FY, plans, signatures."""

from datetime import UTC, datetime

import pytest

from app.billing import gst
from app.billing.invoice import inr
from app.billing.plans import GST_RATE_BP, catalogue, next_plan_with
from app.billing.provider import sign_body, verify_signature


def make_gstin(state: str, pan: str = "AAPFU0939F", entity: str = "1") -> str:
    first14 = f"{state}{pan}{entity}Z"
    return first14 + gst.gstin_checksum(first14)


def test_gstin_known_valid_and_checksum():
    assert gst.validate_gstin("27AAPFU0939F1ZV") == "27AAPFU0939F1ZV"
    assert gst.validate_gstin(" 27aapfu0939f1zv ") == "27AAPFU0939F1ZV"  # normalised
    assert make_gstin("29") == gst.validate_gstin(make_gstin("29"))


@pytest.mark.parametrize("bad", [
    "", "27AAPFU0939F1ZX",  # wrong check character
    "27AAPFU0939F1Z",  # too short
    "00AAPFU0939F1ZV",  # no such state
    "27AAPFU0939F0ZV",  # entity code 0 is not allowed
    "27AAPFU09391FZV",  # letter and digit swapped
])
def test_gstin_rejects(bad):
    with pytest.raises(gst.GstError):
        gst.validate_gstin(bad)


def test_state_code_validation():
    assert gst.validate_state_code("29") == "29"
    with pytest.raises(gst.GstError):
        gst.validate_state_code("25")  # merged into 26


def test_split_intra_and_inter_state():
    intra = gst.split_inclusive(70_682, GST_RATE_BP, "29", "29")
    assert (intra.taxable, intra.cgst, intra.sgst, intra.igst) == (59_900, 5_391, 5_391, 0)
    assert intra.total == 70_682 and intra.intra_state
    inter = gst.split_inclusive(70_682, GST_RATE_BP, "29", "27")
    assert (inter.taxable, inter.cgst, inter.sgst, inter.igst) == (59_900, 0, 0, 10_782)
    assert not inter.intra_state


def test_split_always_sums_to_total_and_odd_paisa_goes_to_sgst():
    for total in (1, 117, 118, 119, 99_999, 12_345_678):
        s = gst.split_inclusive(total, GST_RATE_BP, "29", "29")
        assert s.taxable + s.cgst + s.sgst == total
        assert s.sgst - s.cgst in (0, 1)
        i = gst.split_inclusive(total, GST_RATE_BP, "29", "07")
        assert i.taxable + i.igst == total


def test_catalogue_prices_split_evenly():
    """Every catalogue amount gives CGST == SGST exactly (no odd paisa)."""
    for plan in catalogue().values():
        for interval in ("month", "year"):
            total = plan.total_paise(interval)
            if total:
                s = gst.split_inclusive(total, GST_RATE_BP, "29", "29")
                assert s.cgst == s.sgst and s.taxable == plan.price_paise(interval)


def test_plan_totals_and_upgrade_hint():
    assert catalogue()["solo"].total_paise("month") == 70_682
    assert catalogue()["studio"].total_paise("year") == 1_769_882
    assert next_plan_with("ai_asks", "free") == "solo"
    assert next_plan_with("clients", "solo") == "studio"
    assert next_plan_with("ai_asks", "studio") is None


def test_financial_year_boundary_in_ist():
    assert gst.financial_year(datetime(2027, 3, 31, 18, 29, tzinfo=UTC)) == "2627"  # 23:59 IST
    assert gst.financial_year(datetime(2027, 3, 31, 18, 31, tzinfo=UTC)) == "2728"  # 00:01 IST 1 Apr
    assert gst.financial_year(datetime(2026, 4, 1, 0, 0, tzinfo=UTC)) == "2627"
    assert gst.financial_year_long("2728") == "2027-28"


def test_inr_indian_grouping():
    assert inr(70_682) == "706.82"
    assert inr(12_345_678) == "1,23,456.78"
    assert inr(100_000_000) == "10,00,000.00"


def test_signature_hmac_sha256():
    body = b'{"event":"payment.failed"}'
    sig = sign_body("whsec", body)
    assert len(sig) == 64 and verify_signature("whsec", body, sig)
    assert not verify_signature("other", body, sig)
    assert not verify_signature("whsec", body + b" ", sig)
    assert not verify_signature("whsec", body, None)
    assert not verify_signature("", body, sign_body("", body))  # unset secret never verifies
