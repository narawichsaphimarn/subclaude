import pytest

from app.adapters.inbound.http.auth import AuthenticationFailed, make_verify_api_key


async def test_verify_api_key_accepts_valid_x_api_key():
    verify = make_verify_api_key(["secret-key"])
    await verify(x_api_key="secret-key", authorization=None)


async def test_verify_api_key_accepts_valid_bearer_token():
    verify = make_verify_api_key(["secret-key"])
    await verify(x_api_key=None, authorization="Bearer secret-key")


async def test_verify_api_key_rejects_missing_credentials():
    verify = make_verify_api_key(["secret-key"])
    with pytest.raises(AuthenticationFailed):
        await verify(x_api_key=None, authorization=None)


async def test_verify_api_key_rejects_wrong_key():
    verify = make_verify_api_key(["secret-key"])
    with pytest.raises(AuthenticationFailed):
        await verify(x_api_key="wrong", authorization=None)


async def test_verify_api_key_accepts_any_of_multiple_configured_keys():
    verify = make_verify_api_key(["key-a", "key-b"])
    await verify(x_api_key="key-b", authorization=None)
