# iRacing Analyst

Local-first telemetry analysis for iRacing. The MVP captures the player's live telemetry on Windows, imports `.ibt` files, finds representative laps and corners, and explains the largest opportunities using deterministic rules.

Version 0.2 groups reconnects and stints by iRacing session identity, separates Practice/Qualify/Race, adds Spa corner metadata, racing-line maps, annotated insights, and explicit data-sufficiency states.

## Development

Requirements: Python 3.11+, Node.js 20+.

```bash
python -m venv .venv
.venv/Scripts/pip install -e "backend[dev]"   # Windows
cd frontend && npm install && npm run build
cd .. && python scripts/copy_frontend.py
iracing-analyst
```

On macOS/Linux use `.venv/bin/pip`. Open <http://127.0.0.1:8765>. API documentation is at `/docs`.

Generate and analyze a deterministic fixture without iRacing:

```bash
iracing-analyst generate-fixture data/demo.npz
iracing-analyst analyze data/demo.npz
```

In iRacing, start the app before driving. On Windows it waits for the simulator and automatically stores each connected run. For offline analysis, enable iRacing disk telemetry with `Alt+L` and import the resulting `.ibt` in the UI.

## MVP limitations

- Road layouts and the local player's telemetry only.
- Automatically detected segments are intentionally named T1, T2, ….
- Sector Optimal combines the best detected segment times; it is not a physically stitched micro-optimal lap.
- Advice is rule-based and omitted when evidence is weak.

## Data and privacy

All data remains in the local application data directory. No account, cloud service, iRacing Data API, OAuth, or LLM is used.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for runtime dependencies.
