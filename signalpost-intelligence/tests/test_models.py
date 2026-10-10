import pytest
from signalpost.models import normalize_orgno, valid_norwegian_orgno

def test_normalize_org_number():
    assert normalize_orgno(" 923 609 016 ") == "923609016"

def test_reject_bad_format():
    with pytest.raises(ValueError):
        normalize_orgno("1234")

def test_checksum_known_valid_example():
    assert valid_norwegian_orgno("923609016") is True

def test_checksum_rejects_mutated_digit():
    assert valid_norwegian_orgno("923609017") is False
