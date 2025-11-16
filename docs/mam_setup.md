# MyAnonamouse Session Setup

These instructions mirror the guidance that Jackett surfaces for MyAnonamouse so you can recreate a long-lived session cookie for mamlarr.

## Create a dedicated session (Security Preferences → Session Creation)

1. Log into [MyAnonamouse](https://www.myanonamouse.net/) in a desktop browser.
2. Open **My Account → Security → Security Preferences** or go directly to [`https://www.myanonamouse.net/preferences/index.php?view=security`](https://www.myanonamouse.net/preferences/index.php?view=security).
3. Scroll to the **Session Creation** panel.
4. Enter a descriptive name (for example, `mamlarr` or the hostname of the box that will run mamlarr) and, if you have a static IP, add it to the "Allowed IP" field. Leave the IP blank when the server uses a residential or dynamic address so the cookie stays usable.
5. Click **Create Session**.
6. Copy the newly created `mam_id` value that appears in the session list and paste it into `MAM_SERVICE_MAM_SESSION_ID` (or update the Mamlarr UI settings page).
7. Restart mamlarr (or reload the settings page) so the new cookie is picked up.

> ⚠️ **Account inactivity** – To prevent your account from being disabled for inactivity, you must log in and use the tracker on a regular basis. If you know you will not be able to log in for an extended period, park your account in your MyAnonamouse preferences so it does not get disabled.

## Search filter environment variables

Mamlarr exposes the same search filters that Jackett offers for MyAnonamouse. Configure them through environment variables or the settings UI:

| Variable | Default | Description |
| --- | --- | --- |
| `MAM_SERVICE_SEARCH_TYPE` | `all` | Matches Jackett's search type choices (`all`, `active`, `fl`, `fl-VIP`, `VIP`, `nVIP`). Controls which torrents the search endpoint requests. |
| `MAM_SERVICE_SEARCH_IN_DESCRIPTION` | `false` | Include matches found only inside the torrent description text. |
| `MAM_SERVICE_SEARCH_IN_SERIES` | `true` | Include matches based on the "series" metadata field (series, collection, box set names). |
| `MAM_SERVICE_SEARCH_IN_FILENAMES` | `false` | Allow filename-only matches. Slightly slower but can catch scene releases with sparse descriptions. |
| `MAM_SERVICE_SEARCH_LANGUAGES` | *(empty)* | Comma-separated list of language IDs from MyAnonamouse (for example, `1,43` for English + Italian). Leave blank to search all languages.

These defaults are also emitted by the FastAPI `GET /config` helper so downstream UIs can display the current values and associated help text.
