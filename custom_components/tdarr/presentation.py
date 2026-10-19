"""Device grouping and display metadata, independent of entity identity."""

from .const import DOMAIN, MANUFACTURER


def device_info(entity):
    coordinator = entity.coordinator
    library_id = getattr(entity, "_library_id", None)
    library_name = getattr(entity, "_library_name", None)
    node_name = getattr(entity, "_node_name", None)
    if getattr(entity, "type", None) == "library":
        library_id = entity.sensor.get("_id")
        library_name = entity.sensor["name"]
    info = {
        "manufacturer": MANUFACTURER,
        "configuration_url": coordinator.web_url,
    }
    if library_id:
        library = next((lib for lib in coordinator.data["libraries"]
                        if lib.get("_id") == library_id), {})
        info.update(
            identifiers={(DOMAIN, f"{coordinator.entry_id}_library_{library_id}")},
            name=f"Tdarr · {library.get('name', library_name)}",
            model="Library",
        )
    elif node_name:
        info.update(
            identifiers={(DOMAIN, f"{coordinator.entry_id}_node_name_{node_name}")},
            name=f"Tdarr · {node_name}",
            model="Node",
        )
    else:
        # Preserve the original server device and its area/user customizations.
        info.update(
            identifiers={(DOMAIN, coordinator.serverip)},
            name=f"Tdarr Server ({coordinator.serverip})",
            sw_version=coordinator.data["server"].get("version", "Unknown"),
        )
        return info
    info["via_device_id"] = coordinator.server_device_id
    return info
