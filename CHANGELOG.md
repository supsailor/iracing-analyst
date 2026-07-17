# Changelog

All notable changes to iRacing Analyst are documented here.

## [0.2.1] - 2026-07-17

### Fixed

- Recover overlapping live capture fragments after reconnect, tow and reset without mixing laps.
- Treat repeated iRacing lap numbers as separate physical lap instances.
- Reject zero or inconsistent segment times and hide implausible potential calculations.
- Reset incident baselines between capture epochs instead of reporting impossible incident totals.
- Rebuild track maps only from continuous valid laps.
- Automatically reanalyze legacy local reports while leaving source telemetry files unchanged.

## [0.2.0] - 2026-07-17

### Added

- Automatic local iRacing telemetry capture and offline `.ibt` import.
- Stable Practice, Qualify and Race reports with reconnect and stint grouping.
- Best, Median and Sector Optimal lap analysis.
- Spa corner catalog, track map and racing-line comparison.
- Ranked corner insights linked to synchronized telemetry charts.
- Selectable lap table with incidents, pit, out, in and incomplete lap states.
- Rule-based recommendations with expected gains and driving phases.
- Portable Windows x64 build and English/Russian interface.

### Privacy

- All telemetry remains local; no account, cloud service, OAuth or LLM is used.

[0.2.1]: https://github.com/supsailor/iracing-analyst/releases/tag/v0.2.1
[0.2.0]: https://github.com/supsailor/iracing-analyst/releases/tag/v0.2.0
