"""TON blockchain parsing and local indexing toolkit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tonflow")
except PackageNotFoundError:
    __version__ = "0.0.0"

from tonflow.addresses import (
    is_raw_address,
    is_user_friendly_address,
    normalize_address,
    validate_address,
)
from tonflow.backfill import backfill_transactions
from tonflow.cache import (
    AsyncJSONCache,
    AsyncRedisCache,
    InMemoryCache,
    JSONCache,
    RedisCache,
    SQLiteCache,
)
from tonflow.client import TonClient
from tonflow.confirm import send_and_confirm
from tonflow.dex import (
    OP_DEDUST_SWAP_JETTON,
    OP_DEDUST_SWAP_NATIVE,
    OP_DEDUST_SWAP_POOL,
    OP_STONFI_PAY_TO,
    OP_STONFI_SWAP,
    decode_dedust_swap,
    decode_stonfi_swap,
    extract_dex_swaps,
    is_dedust_swap,
    is_dex_swap,
    is_stonfi_swap,
)
from tonflow.exceptions import TonflowExpiredError, TonflowTimeoutError
from tonflow.export import (
    jetton_transfers_to_csv,
    jetton_transfers_to_json,
    jetton_transfers_to_sql,
    transactions_to_csv,
    transactions_to_json,
    transactions_to_sql,
)
from tonflow.jettons import (
    decode_jetton_burn,
    decode_jetton_mint,
    decode_jetton_transfer,
    extract_jetton_burns,
    extract_jetton_mints,
    extract_jetton_transfers,
    is_jetton_burn,
    is_jetton_mint,
    is_jetton_transfer,
    is_jetton_transfer_notification,
    normalize_amount,
)
from tonflow.models import (
    Balance,
    DexName,
    DexSwap,
    JettonBurn,
    JettonMint,
    JettonTransfer,
    Message,
    MessageDirection,
    NftAttribute,
    NftMetadata,
    NftTransfer,
    RawPayload,
    TonflowModel,
    Transaction,
    TransactionStatus,
)
from tonflow.nfts import (
    decode_nft_transfer,
    extract_nft_transfers,
    is_nft_ownership_assigned,
    is_nft_transfer,
)
from tonflow.providers import FailoverProvider, Provider, TonAPIProvider, TonCenterProvider
from tonflow.stream import watch_address, watch_addresses
from tonflow.websocket import stream_transactions_ws

__all__ = [
    "__version__",
    "AsyncJSONCache",
    "AsyncRedisCache",
    "Balance",
    "DexName",
    "DexSwap",
    "NftAttribute",
    "NftMetadata",
    "FailoverProvider",
    "OP_STONFI_SWAP",
    "OP_STONFI_PAY_TO",
    "OP_DEDUST_SWAP_NATIVE",
    "OP_DEDUST_SWAP_JETTON",
    "OP_DEDUST_SWAP_POOL",
    "decode_stonfi_swap",
    "decode_dedust_swap",
    "extract_dex_swaps",
    "is_stonfi_swap",
    "is_dedust_swap",
    "is_dex_swap",
    "InMemoryCache",
    "NftTransfer",
    "decode_nft_transfer",
    "extract_nft_transfers",
    "is_nft_transfer",
    "is_nft_ownership_assigned",
    "JSONCache",
    "JettonBurn",
    "JettonMint",
    "JettonTransfer",
    "RedisCache",
    "Message",
    "MessageDirection",
    "RawPayload",
    "Provider",
    "TonAPIProvider",
    "TonCenterProvider",
    "watch_addresses",
    "TonClient",
    "TonflowModel",
    "Transaction",
    "TransactionStatus",
    "SQLiteCache",
    "decode_jetton_burn",
    "decode_jetton_mint",
    "decode_jetton_transfer",
    "extract_jetton_burns",
    "extract_jetton_mints",
    "extract_jetton_transfers",
    "is_jetton_burn",
    "is_jetton_mint",
    "is_jetton_transfer",
    "is_jetton_transfer_notification",
    "normalize_amount",
    "send_and_confirm",
    "TonflowExpiredError",
    "TonflowTimeoutError",
    "watch_address",
    "stream_transactions_ws",
    "backfill_transactions",
    "jetton_transfers_to_csv",
    "jetton_transfers_to_json",
    "jetton_transfers_to_sql",
    "transactions_to_csv",
    "transactions_to_json",
    "transactions_to_sql",
    "is_raw_address",
    "is_user_friendly_address",
    "normalize_address",
    "validate_address",
]
