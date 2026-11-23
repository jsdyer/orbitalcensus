# Orbital Census

Explore CelesTrak's satellite catalogue by name, NORAD number, owner, object type and launch cohort. Retain dated source editions and compare catalogue changes without making every visitor query CelesTrak.

<!-- coolcode:guide -->
Search **RADARSAT**, **25544**, or an international designator; filters cover the complete retained catalogue, including payloads, rocket bodies and debris. **Canadian objects** is a starting search, not the only supported owner. Select an object for source fields and its CelesTrak record. A blank decay date does not establish that an object is still in Earth orbit. **Dated captures** compares matching coverage across source editions; the first capture establishes a baseline. Save capture JSON or export the filtered CSV to keep evidence, and import saved JSON or JSON.gz captures locally. Default comparisons cover identity and status; orbital measurements are optional and can vary without proving a manoeuvre.
<!-- /coolcode:guide -->

## How to use it

1. Open [Orbital Census](https://coolcode.ca/orbitalcensus/) and search any object in the retained catalogue. Search covers names, international designators, NORAD IDs and known owner labels. All owner codes in the capture appear in the selector.
2. Filter by type, reported state and launch year. Counts and charts reflect the filtered rows. Launch-cohort charts count objects associated with a launch decade; the distinct-launch count groups international designators by `YYYY-NNN`.
3. Open a name to inspect all 17 retained source fields. **Decay recorded** means a nonempty `DECAY_DATE` or status `D`; **active payload** follows CelesTrak's `+`, `P`, `B`, `S`, `X` definition. This includes standby, spare and extended-mission payloads.
4. Select a retained capture and an earlier baseline to inspect additions, absences and changed values. Comparisons use complete captures, independently of search filters. Different configured coverage cannot be compared as if it were the same population.
5. **Save capture JSON** downloads a regular decompressed JSON receipt. **Export filtered CSV** downloads the current selection; formula-leading text is prefixed with an apostrophe for spreadsheet safety. **Import capture** accepts the receipt JSON or original `.json.gz`; imported data exists only in this tab and is not uploaded or permanently saved.

## Sources and interpretation

- [CelesTrak SATCAT](https://celestrak.org/satcat/search.php) and its [official downloadable CSV](https://celestrak.org/pub/satcat.csv).
- [SATCAT format and queries](https://celestrak.org/satcat/satcat-format.php), [operational status](https://celestrak.org/satcat/status.php), [owner code definitions](https://celestrak.org/satcat/sources.php).
- [CelesTrak usage policy](https://celestrak.org/usage-policy.php), checked 2026-11-23. The source is available without registration. Attribute CelesTrak when sharing its data; source records remain subject to the provider's applicable usage terms.

The initial retained source edition is **2026-11-22 21:56:02 UTC**, containing **71,423 catalogue objects** (full CSV coverage). Capture time is **2026-11-23 10:53:43 UTC**. These are a documented initial capture, not permanent limits or values hardcoded into the interface.

SATCAT is not a real-time position feed, a complete census of physical objects in space, or a collision assessment. It can include Earth, other-body, docked, landing and impact records. Objects can be catalogued long after launch. No decay date is not proof of continued orbit. A record absent from a newer capture is a catalogue difference, not an independently verified decay. Some source fields are missing or uncertain; they are not converted into zero. Owner codes can describe organizations and joint programmes, not just countries.

Period is minutes; inclination is degrees; apogee/perigee are kilometres; radar cross section is square metres. These source values have no independently supplied per-row element epoch here, so changing them does not alone establish a manoeuvre. Default capture comparison excludes these continuously varying fields. Original source field values are preserved as strings.

## Capture workflow

`Orbital Census · Refresh catalogue` runs daily at **10:17 UTC**, on manual dispatch, and when collector/configuration files change on `main`. It first checks the official `jsonDir.php`, at most once per hour locally. If the source edition and coverage have not changed, it updates `checkedAt` without downloading the CSV again. It requests gzip compression, makes at most one CSV download, and stops without retry or redirect following on HTTP errors. No per-visitor CelesTrak API requests are made.

The full source must have required fields, unique 1–9 digit NORAD IDs, recognized types, valid nonempty dates and the configured minimum row count. A drop below the configured previous-catalogue fraction fails validation. A failed fetch/validation leaves the last good committed data and deployment in place; the failed Actions run is the signal to investigate. Source `FILE_MTIME`, capture time and successful-check time remain separate. No synthetic history is generated.

A successful collection commits `web/data/`; a `workflow_run` then checks/builds/publishes the current `main`. Ordinary source pushes build offline from the last capture. The Pages workflow cancels superseded runs and its deployment job serializes deployments. GitHub schedules may be delayed or disabled after inactivity; the visible dates show what is actually retained.

Fourteen source captures are retained by default in the site; older files are removed from its current tree but remain available through Git history. Download a capture for independent retention. Captures use gzip to keep the complete catalogue practical; the page uses the browser's native `DecompressionStream` (a current mainstream browser is required). Regular JSON imports do not require gzip support.

## Expand or customize

Edit **`web/config.json`**:

| Setting | Meaning |
| --- | --- |
| `coverage.owners` | Owner codes to retain, or `[]` for all. Example `["CA", "US", "ESA"]`. |
| `coverage.objectTypes` | `PAY`, `R/B`, `DEB`, `UNK`, or `[]` for all. |
| `presets` | Convenience buttons. Each supports `label`, `query`, `owner`, `yearMin`, `yearMax`; all are optional except a useful label. |
| `pageSize` | Rows per table page (UI bounds 10–200). |
| `retainedCaptures` | Number of compressed captures retained (2–60). |
| `comparisonFields` | Source field names compared by default. The UI can include all orbital measurements. |
| `minimumRecords` | Minimum full-source row count, default 1,000; validation guard, not a display limit. |
| `minimumRetainedFraction` | Reject a suspicious source-size drop compared with the previous source catalogue (default 0.95). |
| `maxSourceBytes` | Source download/decompression bound, default 25 MB. |

For a new button, append—for example—`{"label":"Landsat", "query":"LANDSAT", "owner":""}` to `presets`. The search itself already accepts that input. Adding an owner code requires no UI edits; the owner selector derives from the selected capture.

Commit and push configuration changes. They trigger **Refresh catalogue**, then **Check and publish**. A successful source check less than an hour old suppresses another request; if necessary wait until that hour has elapsed, then run **Actions → Orbital Census · Refresh catalogue → Run workflow**. Coverage changes preserve older receipts with their original coverage and deliberately prevent misleading cross-coverage removal counts. `[]` already retains all owners and types, so no code change is needed to inspect objects beyond the starting presets.

Run locally with:

```sh
python3 scripts/refresh.py
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

The collector's `--source-stamp 'YYYY-MM-DD HH:MM:SS UTC'` option is for bootstrapping from a directory response already retrieved within the current hour; ordinary runs should not use it. The source endpoints are constants in `scripts/refresh.py`, not arbitrary visitor-controlled URLs. Never change them to unverified proxies.

## Privacy and implementation

App source lives in `web/`, the collector/builder in `scripts/`, and meaningful tests in `tests/`. No runtime dependencies, API keys, backend, third-party map tiles or visitor uploads are needed. Inputs, imported files and selections stay in memory; only your explicit downloads leave a local copy. CoolCode's shared aggregate visit counter may run separately and does not receive tool inputs. Source links open CelesTrak only when selected.

The initial `.json.gz` keeps the exact normalized source columns plus SHA-256 of the original CSV, source URL, edition time and retrieval time. `web/data/index.json` lists retained captures and counts. Update only validated source data; never fabricate a historical capture to populate the comparison panel.

See also [Launch Ledger](https://coolcode.ca/launchledger/) and [Satellite Pass](https://coolcode.ca/satpasses/).
