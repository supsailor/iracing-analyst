<p align="center">
  <img src="docs/assets/hero.svg" alt="iRacing Analyst — turn telemetry into your next action" width="100%">
</p>

<p align="center">
  <a href="docs/README.ru.md">Русская версия</a> ·
  <a href="https://github.com/supsailor/iracing-analyst/releases/latest">Download for Windows</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

# Turn telemetry into your next action

iRacing Analyst is a local-first lap analysis app for iRacing. It compares your best lap with your typical pace, shows where the difference was made, and turns telemetry into a short, measurable plan for the next run.

No account. No cloud upload. No subscription. Your telemetry stays on your PC.

## What you get

- **Best vs Median** — understand what actually changed on your fastest lap.
- **Actionable coaching** — get up to three measurable priorities instead of generic advice.
- **Evidence you can inspect** — verify every insight on the track map, racing line and synchronized speed, throttle, brake, steering and delta charts.
- **Your achievable potential** — Sector Optimal is built from segments you have already driven.
- **Session clarity** — inspect clean laps, incidents, out laps, in laps and incomplete laps.
- **Zero-setup workflow** — run the portable Windows app before driving or import an iRacing `.ibt` file.

## See the lap, understand the difference

### Find where the time came from

![Track map and ranked lap insights](docs/assets/report-overview.png)

The report connects ranked insights to the same corner on the map, corner cards and telemetry charts.

### Compare laps and driving inputs

![Corner and telemetry comparison](docs/assets/lap-comparison.png)

Switch between Best and Median, select any valid lap, and inspect braking, minimum speed, throttle application, exit speed and steering corrections.

### Leave with a plan

![Prioritized recommendations for the next run](docs/assets/next-run-actions.png)

Recommendations show the expected opportunity, the relevant corner and the brake–apex–throttle phases to reproduce.

> Screenshots use anonymous deterministic demonstration data.

## Install in three steps

1. Open the [latest release](https://github.com/supsailor/iracing-analyst/releases/latest) and download `iracing-analyst-v0.2.0-windows-x64.zip`.
2. Extract the archive to a folder you can keep. Do not run the executable from inside the ZIP.
3. Start `iracing-analyst.exe`, then launch iRacing and drive. The report opens locally in your browser.

To analyze an existing session, enable iRacing disk telemetry with `Alt+L`, then import the resulting `.ibt` file in the app.

### Windows security notice

The MVP executable is not code-signed, so Microsoft Defender SmartScreen may show an unknown-publisher warning. Only run builds downloaded from this repository's Releases page and verify the published SHA-256 checksum.

## Supported in v0.2.0

- Windows 10/11 x64.
- Road layouts and the local player's telemetry.
- Automatic live capture through the local iRacing SDK.
- Offline `.ibt` import.
- Separate Practice, Qualify and Race reports with multiple stints.
- Curated Spa corner names; unknown layouts use automatically detected zones.
- English and Russian interface.

## MVP boundaries

- Oval, dirt and rain-specific coaching are not included yet.
- Other drivers, replay analysis, setup advice, cloud sync and live coaching are out of scope.
- Sector Optimal combines the best valid semantic segments; it is not a physically stitched micro-optimal lap.
- Coaching is deterministic and omitted when the evidence is weak.

## Privacy

All session data is processed and stored locally in the application data directory. The runtime does not use iRacing Data API, OAuth, an LLM, analytics or any cloud service.

## Development

Requirements: Python 3.11+ and Node.js 20+.

```bash
python -m venv .venv
.venv/Scripts/pip install -e "backend[dev]"
cd frontend && npm ci && npm run build
cd .. && python scripts/copy_frontend.py
iracing-analyst
```

Generate anonymous demo telemetry without iRacing:

```bash
iracing-analyst generate-demo data/spa-demo.npz
iracing-analyst analyze data/spa-demo.npz
```

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for runtime dependencies.

## License and trademark notice

Released under the [MIT License](LICENSE).

iRacing is a trademark of iRacing.com Motorsport Simulations, LLC. This independent project is not affiliated with, endorsed by, or sponsored by iRacing.com Motorsport Simulations.
