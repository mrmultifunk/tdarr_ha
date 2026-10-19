"""Independent, lightweight server connectivity checks."""

from datetime import datetime, timezone
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .polling import error_reason


class ServerStatusCoordinator(DataUpdateCoordinator):
    """Keep connectivity independent of library/statistics endpoint failures."""

    def __init__(self, hass, coordinator):
        super().__init__(hass, logging.getLogger(__name__), name="tdarr_server_status",
                         update_interval=coordinator.update_interval)
        self.local = coordinator
        self.details = dict(coordinator.data.get("server", {}))
        self.last_success = datetime.now(timezone.utc).isoformat()
        self.async_set_updated_data(self.snapshot(True, None))

    def snapshot(self, connected, error):
        return {"connected": connected, "error": error,
                "last_success": self.last_success, "details": dict(self.details)}

    async def _async_update_data(self):
        try:
            result = await self.hass.async_add_executor_job(self.local.tdarr.getStatus)
            if not isinstance(result, dict) or not isinstance(result.get("status"), str):
                return self.snapshot(False, "Invalid status response")
            if result["status"] == "ERROR":
                return self.snapshot(False, "Server error")
            self.details = result
            self.last_success = datetime.now(timezone.utc).isoformat()
            return self.snapshot(True, None)
        except Exception as err:
            # A disconnected server is a valid measurement, not unavailable.
            return self.snapshot(False, error_reason(err))
