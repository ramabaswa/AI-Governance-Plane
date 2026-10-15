"""Asynchronous background worker for drift detection and agentgateway reconciliation."""

import asyncio
import logging
import os
import signal
from integrations.agentgateway.reconciler import AgentgatewayReconciler
from features.state_store import STATE_STORE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reconciliation-worker")


class ReconciliationWorker:
    """Periodically queries agentgateway health and verifies runtime configuration match."""

    def __init__(self, interval_seconds: int = 15):
        self.interval = interval_seconds
        self.reconciler = AgentgatewayReconciler()
        self.is_running = False

    async def run_loop(self):
        self.is_running = True
        logger.info("Reconciliation worker started (polling every %ds)...", self.interval)
        while self.is_running:
            try:
                status = await self.reconciler.check_drift()
                if status["drift_detected"]:
                    logger.warning("Configuration drift detected! Triggering automatic resync...")
                    res = await self.reconciler.reconcile_desired_state(
                        routes=list(STATE_STORE.routes.values()),
                        models_by_id=STATE_STORE.models,
                        virtual_keys=[
                            {"id": vk.id, "key_hash": vk.key_hash, "quota": 1_000_000}
                            for vk in STATE_STORE.virtual_keys.values()
                            if not vk.is_revoked
                        ],
                    )
                    logger.info("Automatic resync complete: %s", res)
                else:
                    logger.debug("Drift check passed: runtime in sync with desired state.")
            except Exception as e:
                logger.error("Error during drift reconciliation cycle: %s", str(e))

            await asyncio.sleep(self.interval)

    def stop(self):
        logger.info("Stopping reconciliation worker...")
        self.is_running = False


async def main():
    worker = ReconciliationWorker(interval_seconds=int(os.getenv("RECONCILE_INTERVAL", "15")))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass

    await worker.run_loop()


if __name__ == "__main__":
    asyncio.run(main())
