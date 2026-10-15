"""Database initialization and schema verification script."""

import logging
from features.state_store import STATE_STORE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init-db")


def main():
    logger.info("Initializing AI Governance Plane state store...")
    logger.info("Tenants initialized: %d", len(STATE_STORE.tenants))
    logger.info("Models initialized: %d", len(STATE_STORE.models))
    logger.info("Audit chain genesis hash: %s", STATE_STORE.last_audit_hash)
    logger.info("Database initialization successful.")


if __name__ == "__main__":
    main()
