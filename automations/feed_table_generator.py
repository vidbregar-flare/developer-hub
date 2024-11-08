import json
import logging
import sys
from pathlib import Path

import requests
from pycoingecko import CoinGeckoAPI
from web3 import Web3

# Configuration
# Configuration
RPC_URL = "https://songbird-api.flare.network/ext/C/rpc"
FAST_UPDATER_ADDRESS = "0x70e8870ef234EcD665F96Da4c669dc12c1e1c116"
EXPLORER_API_URL = "https://songbird-explorer.flare.network/api"
BLOCK_LATENCY_FEEDS_PATH = Path("block_latency_feeds.json")
ANCHOR_FEEDS_PATH = Path("anchor_feeds.json")
logging.basicConfig(
    encoding="utf-8",
    level=logging.INFO,
    handlers=[logging.StreamHandler(stream=sys.stdout)],
    handlers=[logging.StreamHandler(stream=sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_contract_abi(contract_address: str) -> dict:
    """Get the ABI for a contract from the Chain Explorer API."""
    """Get the ABI for a contract from the Chain Explorer API."""
    params = {"module": "contract", "action": "getabi", "address": contract_address}
    headers = {"accept": "application/json"}

    try:
        response = requests.get(
            EXPLORER_API_URL, params=params, headers=headers, timeout=10
        )
        response.raise_for_status()
        result = response.json().get("result")
        return json.loads(result)
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        logger.exception("Error fetching ABI for contract")
        sys.exit(1)


def get_feed_id(category: str, feed_name: str) -> str:
    """Convert a feed name to its structured encoded feed ID."""
    hex_feed_name = feed_name.encode("utf-8").hex()
    padded_hex_string = (category + hex_feed_name).ljust(42, "0")
    return f"0x{padded_hex_string}"


def write_data_to_file(file_path: Path, data: list[dict]) -> None:
    """Write a markdown table to a file."""
    try:
        with file_path.open("w") as f:
            json.dump(data, f, indent=4)
        logger.info("Successfully wrote data to %s", file_path)
    except OSError:
        logger.exception("Failed to write to %s: ", file_path)


def get_coins_list(pages: list) -> list[dict]:
    """Get the top 500 coins from CoinGecko."""
    cg = CoinGeckoAPI()
    coins = []
    try:
        for page in pages:
            coins += cg.get_coins_markets(vs_currency="usd", per_page=250, page=page)
    except Exception:
        logger.exception("Error fetching coins from CoinGecko")
        sys.exit(1)
    else:
        return coins


def find_coin_by_symbol(coins: list[dict], symbol: str) -> dict | None:
    """Find a coin in the list by its symbol."""
    return next(
        (coin for coin in coins if coin["symbol"].lower() == symbol.lower()), None
    )


def generate_feed_data(
    feed_names: list[str],
    decimals: list[int],
    coins: list[dict],
    include_index: bool = False,  # noqa: FBT001,FBT002
) -> list[dict]:
    """Generate a list of dictionaries based on feed data."""
    data = []
    for idx, (name, decimal) in enumerate(zip(feed_names, decimals, strict=True)):
        feed_id = get_feed_id("01", name)
        coin = find_coin_by_symbol(coins, name.split("/")[0])
        if not coin:
            logger.warning("Coin %s not found in CoinGecko data", name)
            continue

        if include_index:
            feed_data = {
                "feed_name": name,
                "feed_index": idx,
                "feed_id": feed_id,
                "decimals": decimal,
                "base_asset": coin["name"],
                "category": "Crypto",
            }
        else:
            feed_data = {
                "feed_name": name,
                "feed_id": feed_id,
                "decimals": decimal,
                "base_asset": coin["name"],
                "category": "Crypto",
            }
        data.append(feed_data)
    return data


if __name__ == "__main__":
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    logger.info("Connected to RPC `%s`", RPC_URL)

    # Set up contract
    # Set up contract
    fast_updater = w3.eth.contract(
        address=Web3.to_checksum_address(FAST_UPDATER_ADDRESS),
        abi=get_contract_abi(FAST_UPDATER_ADDRESS),
    )
    logger.info("Connected to FastUpdater contract `%s`", FAST_UPDATER_ADDRESS)

    # Query block latency feeds
    block_latency_feeds = fast_updater.functions.fetchAllCurrentFeeds().call()
    feed_names = [
        feed[1:].decode("utf-8").rstrip("\x00") for feed in block_latency_feeds[0]
        feed[1:].decode("utf-8").rstrip("\x00") for feed in block_latency_feeds[0]
    ]
    decimals = block_latency_feeds[2]
    logger.info("Found %d block-latency feeds", len(feed_names))

    # Query CoinGecko for top 500 coins
    coins_list = get_coins_list(pages=[1, 2])

    # Write block-latency feeds to file
    block_latency_data = generate_feed_data(
        feed_names, decimals, coins_list, include_index=True
    )
    write_data_to_file(BLOCK_LATENCY_FEEDS_PATH, block_latency_data)

    # Write anchor feeds to file
    anchor_data = generate_feed_data(feed_names, decimals, coins_list)
    write_data_to_file(ANCHOR_FEEDS_PATH, anchor_data)
