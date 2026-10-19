"""Bounded retries and safe error context for read-only polling."""

from requests.exceptions import ConnectionError, HTTPError, Timeout


class PollError(Exception):
    """An endpoint failed without exposing headers, payloads or credentials."""


def error_reason(error):
    if isinstance(error, HTTPError):
        response = error.response
        return f"HTTP {response.status_code}" if response is not None else "HTTPError"
    return type(error).__name__


def retryable(error):
    if isinstance(error, (ConnectionError, Timeout)):
        return True
    return (isinstance(error, HTTPError) and error.response is not None
            and error.response.status_code in (502, 503, 504))


async def poll_data(hass, server):
    """Retry only transient reads once; never retry a control command."""
    data = {}
    for key, method, expected in (
        ("server", server.getStatus, dict),
        ("nodes", server.getNodes, dict),
        ("stats", server.getStats, dict),
        ("staged", server.getStaged, dict),
        ("libraries", server.getLibraries, list),
        ("globalsettings", server.getSettings, dict),
    ):
        for attempt in range(2):
            try:
                value = await hass.async_add_executor_job(method)
                if not isinstance(value, expected):
                    raise PollError(f"{method.__name__}: unexpected response type")
                if isinstance(value, dict) and value.get("status") == "ERROR":
                    status = value.get("status_code")
                    if attempt == 0 and status in (502, 503, 504):
                        continue
                    # Only emit numeric status codes, never the raw server body.
                    detail = f"HTTP {status}" if isinstance(status, int) else "server error"
                    raise PollError(f"{method.__name__}: {detail}")
                data[key] = value
                break
            except PollError:
                raise
            except Exception as err:
                if attempt == 0 and retryable(err):
                    continue
                raise PollError(f"{method.__name__}: {error_reason(err)}") from err
    return data
