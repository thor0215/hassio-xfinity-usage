from pytest_mock import MockFixture
from const import LOAD_KEY_TEST, ENCRYPT_TEST_MESSAGE
from xfinity_helper import *

def test_load_key():
    assert load_key() == LOAD_KEY_TEST


def test_encrypt_message():
    assert isinstance(encrypt_message(ENCRYPT_TEST_MESSAGE), bytes)


def test_decrypt_message():
    assert decrypt_message(encrypt_message(ENCRYPT_TEST_MESSAGE)) == ENCRYPT_TEST_MESSAGE
