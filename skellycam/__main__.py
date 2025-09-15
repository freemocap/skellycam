"""
Simplified main entry point for SkellyCam server.
Uses asyncio and proper signal handling without extra threads.
"""
import asyncio
import logging
import multiprocessing
import sys

from skellycam.skellycam_app.skellycam_runner import SkellyCamRunner

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run the application
    runner = SkellyCamRunner()

    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()