"""Tests for the tonflow CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tonflow.cli import _build_parser


def _parse(*args: str):
    return _build_parser().parse_args(args)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def test_scan_defaults():
    args = _parse("scan", "EQA123")
    assert args.command == "scan"
    assert args.address == "EQA123"
    assert args.limit == 10
    assert args.provider == "tonapi"
    assert args.endpoint == "https://tonapi.io"
    assert args.api_key is None


def test_scan_custom_flags():
    args = _parse("scan", "EQA123", "--limit", "5", "--provider", "toncenter", "--api-key", "k")
    assert args.limit == 5
    assert args.provider == "toncenter"
    assert args.api_key == "k"


def test_balance_defaults():
    args = _parse("balance", "EQA123")
    assert args.command == "balance"
    assert args.address == "EQA123"
    assert args.provider == "tonapi"


def test_balance_toncenter():
    args = _parse("balance", "EQA123", "--provider", "toncenter")
    assert args.provider == "toncenter"


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_scan_prints_transactions(capsys):
    from tonflow.cli import _cmd_scan
    from tonflow.models import Transaction

    tx = Transaction.model_validate(
        {"hash": "abcdef1234567890", "lt": 42000, "account": "EQA", "status": "success"}
    )

    args = _parse("scan", "EQA123")
    with patch("tonflow.cli._make_client") as mock_make:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_transactions = AsyncMock(return_value=[tx])
        mock_make.return_value = mock_client

        await _cmd_scan(args)

    out = capsys.readouterr().out
    assert "abcdef1234567890"[:16] in out
    assert "42000" in out


@pytest.mark.asyncio
async def test_cmd_scan_empty(capsys):
    from tonflow.cli import _cmd_scan

    args = _parse("scan", "EQA123")
    with patch("tonflow.cli._make_client") as mock_make:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_transactions = AsyncMock(return_value=[])
        mock_make.return_value = mock_client

        await _cmd_scan(args)

    assert "No transactions found" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cmd_balance_prints_ton(capsys):
    from tonflow.cli import _cmd_balance

    args = _parse("balance", "EQA123")
    with patch("tonflow.cli._make_client") as mock_make:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_balance = AsyncMock(return_value=5_000_000_000)
        mock_make.return_value = mock_client

        await _cmd_balance(args)

    out = capsys.readouterr().out
    assert "5.000000000 TON" in out
    assert "5000000000" in out
