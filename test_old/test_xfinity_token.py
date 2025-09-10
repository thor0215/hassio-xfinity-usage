import pytest
from xfinity_token import XfinityOAuthToken

xfinityToken = XfinityOAuthToken()

def test_read_token_code_file_data(xfinityToken):
    xfinityToken.read_token_code_file_data()
    assert False
