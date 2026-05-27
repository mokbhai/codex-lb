from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anyio
from sqlalchemy import select

from app.core.crypto import TokenEncryptor
from app.db.models import Account
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AccountRoutingConfig:
    account_id: str
    custom_api_key: str | None
    custom_base_url: str | None
    model_mapping: dict[str, str]


class AccountRoutingConfigStore:
    def __init__(self) -> None:
        self._entries: dict[str, AccountRoutingConfig] = {}
        self._lock = anyio.Lock()

    def get(self, account_id: str) -> AccountRoutingConfig | None:
        return self._entries.get(account_id)

    async def replace_all(self, entries: dict[str, AccountRoutingConfig]) -> None:
        async with self._lock:
            self._entries = entries

    def clear(self) -> None:
        self._entries = {}


def normalize_model_mapping(value: dict[str, str] | None) -> dict[str, str]:
    if value is None:
        return {}
    normalized: dict[str, str] = {}
    for key, mapped in value.items():
        source = key.strip()
        target = mapped.strip()
        if not source or not target:
            continue
        normalized[source] = target
    return normalized


def serialize_model_mapping(value: dict[str, str]) -> str | None:
    normalized = normalize_model_mapping(value)
    if not normalized:
        return None
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True)


def parse_model_mapping(raw: str | None) -> dict[str, str]:
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, mapped in parsed.items():
        if not isinstance(key, str) or not isinstance(mapped, str):
            continue
        source = key.strip()
        target = mapped.strip()
        if not source or not target:
            continue
        normalized[source] = target
    return normalized


_store = AccountRoutingConfigStore()


def get_account_routing_config_store() -> AccountRoutingConfigStore:
    return _store


async def refresh_account_routing_config_store() -> None:
    encryptor = TokenEncryptor()
    entries: dict[str, AccountRoutingConfig] = {}
    async with SessionLocal() as session:
        result = await session.execute(
            select(
                Account.id,
                Account.custom_api_key_encrypted,
                Account.custom_base_url,
                Account.custom_model_mapping_json,
            )
        )
        for account_id, api_key_encrypted, custom_base_url, model_mapping_json in result.all():
            custom_api_key: str | None = None
            if api_key_encrypted is not None:
                try:
                    custom_api_key = encryptor.decrypt(api_key_encrypted)
                except Exception:
                    logger.warning(
                        "Failed to decrypt custom API key for account %s; ignoring custom key",
                        account_id,
                        exc_info=True,
                    )
            model_mapping = parse_model_mapping(model_mapping_json)
            if custom_api_key is None and custom_base_url is None and not model_mapping:
                continue
            entries[account_id] = AccountRoutingConfig(
                account_id=account_id,
                custom_api_key=custom_api_key,
                custom_base_url=custom_base_url.strip() if isinstance(custom_base_url, str) else None,
                model_mapping=model_mapping,
            )
    await get_account_routing_config_store().replace_all(entries)
