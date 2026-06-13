import asyncio

from tonflow import TonClient


async def main() -> None:
    client = TonClient(endpoint="https://example-ton-api.invalid")
    transactions = await client.get_transactions("EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    print(transactions)


if __name__ == "__main__":
    asyncio.run(main())
