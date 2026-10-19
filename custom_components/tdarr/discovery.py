"""Entity discovery and migration without changing existing entity IDs."""

from collections import Counter

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def repair_node_identity(registry, entry, entity, domain):
    """Reuse the oldest matching node entity, never delete duplicate entries."""
    if not getattr(entity, "session_unique_prefix", None):
        return
    if registry.async_get_entity_id(domain, DOMAIN, entity.unique_id):
        return
    matches = []
    for old in er.async_entries_for_config_entry(registry, entry.entry_id):
        if old.platform != DOMAIN or old.entity_id.split(".", 1)[0] != domain:
            continue
        legacy_match = old.unique_id == entity.legacy_unique_id
        session_match = (
            old.unique_id.startswith(entity.session_unique_prefix)
            and old.unique_id.endswith(entity.session_unique_suffix)
            and old.original_name == entity.legacy_name
        )
        if legacy_match or session_match:
            matches.append(old)
    if matches:
        oldest = min(matches, key=lambda old: (str(old.created_at), old.entity_id))
        registry.async_update_entity(oldest.entity_id, new_unique_id=entity.unique_id)


def register_entities(hass, entry, coordinator, async_add_entities, factory, domain):
    """Discover by stable ID and migrate only unambiguous legacy identities."""
    known = set()

    @callback
    def discover():
        candidates = list(factory())
        legacy_counts = Counter(getattr(entity, "legacy_unique_id", None) for entity in candidates)
        identity_counts = Counter(entity.unique_id for entity in candidates)
        registry = er.async_get(hass)
        new = []
        for entity in candidates:
            if identity_counts[entity.unique_id] != 1:
                continue
            if entity.unique_id in known:
                continue
            repair_node_identity(registry, entry, entity, domain)
            legacy = getattr(entity, "legacy_unique_id", None)
            if legacy and legacy != entity.unique_id and legacy_counts[legacy] == 1:
                old_id = registry.async_get_entity_id(domain, DOMAIN, legacy)
                existing = registry.async_get_entity_id(domain, DOMAIN, entity.unique_id)
                if old_id and not existing:
                    old = registry.async_get(old_id)
                    if old.config_entry_id == entry.entry_id:
                        registry.async_update_entity(old_id, new_unique_id=entity.unique_id)
            known.add(entity.unique_id)
            new.append(entity)
        if new:
            async_add_entities(new)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
