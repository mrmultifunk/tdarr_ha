# Tdarr for Home Assistant

Monitor your Tdarr server, nodes and libraries, scan for new files and control processing from Home Assistant.

Maintained by [mrmultifunk](https://github.com/mrmultifunk), based on the original integration by [itchannel](https://github.com/itchannel/tdarr_ha). Integration-provided names and settings are in English. Your own names are preserved.

## Features

| Device | Controls and information |
| --- | --- |
| Server | Connection, server update availability, global pause, ignore schedules, queue/error counts, total speed and aggregate statistics |
| Each node | Pause processing, processing active, status and speed |
| Each library | Scan for new files, processing enabled, files, space saved, transcodes and health checks |

Devices link to the Tdarr web interface. New nodes and libraries are discovered automatically.

## Installation with HACS

1. In HACS, open the menu and select **Custom repositories**.
2. Add `https://github.com/mrmultifunk/tdarr_ha` with type **Integration**.
3. Find **Tdarr — mrmultifunk** in HACS and download it.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Tdarr** and enter your server connection details.

This fork uses the same `tdarr` domain as the original integration. Install only one version. When switching from the original, preserve the existing Home Assistant integration configuration; do not remove and re-add it just to change the HACS source.

### Manual installation

Copy `custom_components/tdarr` from a [release](https://github.com/mrmultifunk/tdarr_ha/releases) into `/config/custom_components/tdarr`, restart Home Assistant and add the integration as above.

## Configuration

- **Server IP / host:** the Tdarr server address reachable from Home Assistant.
- **Port:** the exposed Tdarr API port (default `8265`). Use your mapped port if different.
- **API key:** configure it in the integration options if your server requires one.
- **Polling interval:** default 60 seconds; minimum 5 seconds. Longer intervals reduce server load.
- **Web interface URL:** optional URL for device links, useful when the web UI uses a different port or a reverse proxy. This does not change the API connection.

Change options through **Settings → Devices & services → Tdarr → Configure**. Assign the server, node and library devices to the desired rooms. Give each Tdarr node a unique, stable name to preserve its entities across restarts.

## Using the integration

### Libraries

**Scan for new files** runs Tdarr's **Scan (Find new)** for the selected library's configured folder. It finds new files and removes records for missing files. It does not run **Scan (Fresh)** or reset the library database. A successful press confirms acceptance, not completion.

**Processing enabled** controls the library's `processLibrary` setting. On allows processing; off disables it. This is not an immediate worker kill and does not alter plugins or flows.

Library statistics expose file count, space saved in GB, transcodes and health checks. Savings can be negative, and counts can reset. Missing values appear as unknown. The Files sensor also includes codec, container and resolution details.

### Nodes and global controls

**Pause processing** on means paused; off resumes processing. Global pause applies across nodes. **Ignore schedules** controls Tdarr's scheduling override.

**Processing active** uses the workers' `idle` flags, so work with zero FPS still counts as active. No workers means off. Unsupported or missing activity data means unknown; a missing node becomes unavailable.

### Server connection

**Server connection** uses the connectivity device class:

- `on`: the server status API responded successfully.
- `off`: the status request failed or returned an invalid/error response.

Attributes include raw status, version, uptime in seconds, OS, last successful contact and a sanitized error. On a failed check, details remain from the last successful response. A lightweight status request runs at the configured interval independently of library/statistics polling.

This is the replacement for the old raw **Server status** sensor, which is removed on upgrade. Move any dashboard or automation references to the binary sensor. Read its `status` attribute if you need Tdarr's raw status value.

### Updates

There are two separate update paths:

- **Integration:** HACS downloads releases from this repository. Restart Home Assistant after installing.
- **Tdarr server:** the **Server update** entity checks [Tdarr's official stable release manifest](https://storage.tdarr.io/versions.json) every six hours. It shows installed/latest versions and update availability. It has no Install action: update your Docker Compose stack or other Tdarr deployment manually.

Find **Server update** under the server device's diagnostic entities, or filter **Settings → Devices & services → Entities** by integration **Tdarr** and domain **update**. The generated entity ID depends on device naming and existing customizations; it is not guaranteed to be `update.tdarr_server`.

The release check needs outbound HTTPS access to `storage.tdarr.io`. If it fails, only the server update entity becomes unavailable; local controls continue to work. Development version strings are not compared with stable releases. The `homeassistant.update_entity` action on the update entity requests a fresh version check.

## Troubleshooting

- **New release missing in HACS:** select the repository's **Update information**, then **Redownload** and choose the release. Confirm the repository link points to `mrmultifunk/tdarr_ha`.
- **Entity missing after an upgrade:** restart Home Assistant, check the Entities list including disabled entities, and check the Home Assistant log for `custom_components.tdarr` errors.
- **Controls/statistics unavailable but connection on:** a different Tdarr API endpoint may have failed. The log identifies the endpoint and safe error type.
- **Old duplicate node entities:** keep node names unique and stable. Verify which entities are active before manually removing obsolete duplicates. Do not edit `.storage` files.
- **Removed library/node:** its entities become unavailable. Remove unused entries manually once they are no longer referenced.

For problems, [open an issue](https://github.com/mrmultifunk/tdarr_ha/issues) with integration, Home Assistant and Tdarr versions and the relevant error. Do not include API keys.

## Release history and development

See [CHANGELOG.md](CHANGELOG.md) for version history and [GitHub Releases](https://github.com/mrmultifunk/tdarr_ha/releases) for downloads.

Run `python -m unittest discover -s tests -v` with `requests` and `voluptuous` installed. Tests isolate HTTP and Home Assistant dependencies; they do not replace testing against a running Home Assistant and Tdarr server.
