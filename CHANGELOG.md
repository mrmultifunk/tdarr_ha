# Changelog

## 1.21.1

- Fix server update entity registration: use Home Assistant's `UpdateEntityFeature` flag type for read-only updates. Plain integer zero fails the framework's feature membership checks.
- Explicit entity refresh checks both the running server version and official releases.
- Remove the redundant raw server status sensor and its exact registry entry. Use **Server connection**, which carries the status and version attributes. Update dashboard/automation references to the removed sensor.
- Replace the repository landing page with installation, configuration and usage documentation. Move release history here.

## 1.21.0

- Read-only **Server update** entity using the official Tdarr stable release manifest every six hours; installation remains external.
- **Server connection** binary sensor independent of statistics endpoint failures, with safe diagnostic attributes.
- **Processing active** per node using workers' boolean `idle` flags.
- HACS display name **Tdarr — mrmultifunk** and fork maintainer metadata.

## 1.20.1

- English entity names, settings and messages in all included translations.
- Preserve user-assigned names and entity IDs.

## 1.20.0

- Separate server, library and node devices with short entity names.
- Diagnostic/configuration categories, display precision and configurable web interface links.
- Device grouping preserves entity identities; device/area automation targets may need adjustment.

## 1.19.1

- Use configured node names instead of temporary session IDs to prevent duplicate entities after node restarts.
- Reuse the oldest unambiguous matching node entity. Existing duplicates are not automatically deleted.
- Retry transient reads once, sanitize polling errors and avoid duplicate error logging. Commands are not retried.

## 1.19.0

- Per-library processing switches and separate statistics sensors.
- Dynamic entity discovery and library identities based on library IDs.
- Fix options persistence, API-key logging and current Home Assistant options-flow compatibility.
- Add request timeouts and exact library matching for the legacy refresh action.
- Node identity handling in this version was superseded by 1.19.1.

## 1.18.1

- Per-library **Scan for new files** buttons.
