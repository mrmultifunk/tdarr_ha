"""The Tdarr integration."""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from .presentation import device_info

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    MANUFACTURER,
    SERVERIP,
    SERVERPORT,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_DEFAULT,
    COORDINATOR,
    APIKEY
)

from .tdarr import Server
from .polling import poll_data, PollError

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor", "switch", "button"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tdarr component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tdarr Server from a config entry."""
    serverip = entry.data[SERVERIP]
    serverport= entry.data[SERVERPORT]
    apikey = entry.options.get(APIKEY, entry.data.get(APIKEY, ""))
    update_interval = entry.options.get(
        UPDATE_INTERVAL, entry.data.get(UPDATE_INTERVAL, UPDATE_INTERVAL_DEFAULT)
    )

    #for ar in entry.data:
        #_LOGGER.debug(ar)

    coordinator = TdarrDataUpdateCoordinator(hass, serverip, serverport, update_interval, apikey)

    coordinator.entry_id = entry.entry_id
    host = f"[{serverip}]" if ":" in serverip and not serverip.startswith("[") else serverip
    coordinator.web_url = entry.options.get("web_url") or f"http://{host}:{serverport}"
    await coordinator.async_refresh()  # Get initial data
       # Registers update listener to update config entry when options are updated.
    #_LOGGER.debug(coordinator.data)
    # Register the listener after the first successful refresh.

   

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    tdarr_options_listener = entry.add_update_listener(options_update_listener)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR : coordinator,
        "tdarr_options_listener": tdarr_options_listener
    }
        


    server_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, serverip)},
        name=f"Tdarr Server ({serverip})",
        manufacturer=MANUFACTURER,
        configuration_url=coordinator.web_url,
    )
    coordinator.server_device_id = server_device.id
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_refresh_library_service(service_call):
        await hass.async_add_executor_job(
            refresh_library, hass, service_call, coordinator
        )

    hass.services.async_register(
        DOMAIN,
        "refresh_library", 
        async_refresh_library_service
    )


    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    #_LOGGER.debug(hass.data[DOMAIN][entry.entry_id])
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id]["tdarr_options_listener"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

def refresh_library(hass, service, coordinator):
    libraryid = service.data.get("library", "")
    mode = service.data.get("mode", "scanFindNew")
    folderpath = service.data.get("folderpath", "")
    status = coordinator.tdarr.refreshLibrary(libraryid, mode, folderpath)
    if "ERROR" in status:
        _LOGGER.debug(status)
        raise HomeAssistantError(status["ERROR"])

async def options_update_listener(
    hass: HomeAssistant,  entry: ConfigEntry 
    ):
        _LOGGER.debug("OPTIONS CHANGE")
        await hass.config_entries.async_reload(entry.entry_id)

class TdarrDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to handle fetching new data about the Tdarr Controller."""

    def __init__(self, hass, serverip, serverport, update_interval, apikey):
        """Initialize the coordinator and set up the Controller object."""
        self._hass = hass
        self.serverip = serverip
        self.serverport = serverport
        self.tdarr = Server(serverip, serverport, apikey)
        self._available = True

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch data from Tdarr Server."""
        try:
            return await poll_data(self._hass, self.tdarr)
        except PollError as err:
            # The coordinator logs failures/recovery. Avoid a duplicate warning
            # on every poll and never include request headers or response bodies.
            raise UpdateFailed(f"Tdarr {self.serverip}: {err}") from err

    async def reloadentities(self):
        _LOGGER.debug("Reloading?")
        current_entries = self._hass.config_entries.async_entries(DOMAIN)
        

        reload_tasks = [
            self._hass.config_entries.async_reload(entry.entry_id)
            for entry in current_entries
        ]

        await asyncio.gather(*reload_tasks)

class TdarrEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(
            self, *, device_id: str, name: str, coordinator: TdarrDataUpdateCoordinator
    ):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self.coordinator.serverip}-{self._device_id}"

    @property
    def device_info(self):
        return device_info(self)
