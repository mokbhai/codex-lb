from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.crypto import TokenEncryptor
from app.core.openai.requests import ResponsesRequest
from app.db.models import Account, AccountStatus
from app.modules.proxy.account_routing_config import AccountRoutingConfig, get_account_routing_config_store
from app.modules.proxy.repo_bundle import ProxyRepositories
from app.modules.proxy.service import ProxyService

pytestmark = pytest.mark.unit


def _make_account(account_id: str) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        chatgpt_account_id=f"workspace-{account_id}",
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("oauth-access-token"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=datetime.now(tz=timezone.utc),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


@asynccontextmanager
async def _repo_factory() -> AsyncIterator[ProxyRepositories]:
    yield ProxyRepositories(
        accounts=AsyncMock(),
        usage=AsyncMock(),
        request_logs=AsyncMock(),
        sticky_sessions=AsyncMock(),
        api_keys=AsyncMock(),
        additional_usage=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_custom_routing_model_mapping_rewrites_payload_model() -> None:
    service = ProxyService(_repo_factory)
    account = _make_account("acc-custom")
    await get_account_routing_config_store().replace_all(
        {
            account.id: AccountRoutingConfig(
                account_id=account.id,
                custom_api_key="sk-custom",
                custom_base_url="https://api.custom-provider.com/v1",
                model_mapping={"gpt-5.5": "deepseek-v4-pro"},
            )
        }
    )

    payload = ResponsesRequest(model="gpt-5.5", input="hello")
    mapped = service._mapped_payload_for_account(account, payload)

    assert mapped.model == "deepseek-v4-pro"
    assert payload.model == "gpt-5.5"


@pytest.mark.asyncio
async def test_custom_routing_skips_token_refresh_path() -> None:
    @asynccontextmanager
    async def _failing_repo_factory() -> AsyncIterator[ProxyRepositories]:
        raise AssertionError("repo_factory should not be used for custom API key routing")
        yield

    service = ProxyService(_failing_repo_factory)
    account = _make_account("acc-custom-refresh")
    await get_account_routing_config_store().replace_all(
        {
            account.id: AccountRoutingConfig(
                account_id=account.id,
                custom_api_key="sk-custom",
                custom_base_url=None,
                model_mapping={},
            )
        }
    )

    refreshed = await service._ensure_fresh_with_budget(account, timeout_seconds=1)

    assert refreshed is account
