"""Test wallet monitoring flow (including pagination)."""
import time

from src.config_loader import load_config
from src.in_memory_activity_queue import InMemoryActivityQueue
from src.wallet_monitor import WalletMonitor
from src.logger import log


def test_monitor():
    """Test wallet monitoring with the current WalletMonitor API."""
    config = load_config("config.yaml")

    wallets = config['monitoring']['wallets']
    batch_size = config['monitoring'].get('batch_size', 10)
    api_config = config.get('polymarket_api', {})

    log.info(f"Starting monitor test with batch size: {batch_size}")

    activity_queue = InMemoryActivityQueue(max_workers=1)
    monitor = WalletMonitor(
        wallets=wallets,
        poll_interval=300,
        activity_queue=activity_queue,
        batch_size=batch_size,
        proxy=api_config.get('proxy'),
        timeout=api_config.get('timeout', 30.0),
        verify_ssl=api_config.get('verify_ssl', True),
    )

    monitor.start()

    log.info("Waiting for the first monitoring round to complete...")
    time.sleep(10)

    monitor.stop()
    activity_queue.shutdown()
    log.info("Monitor test complete")


if __name__ == "__main__":
    test_monitor()
