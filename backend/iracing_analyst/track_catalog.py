from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogCorner:
    number: int
    name: str
    start_pct: float
    end_pct: float


# Boundaries are our own initial telemetry-oriented annotation, not copied iRacing map assets.
# They deliberately cover the whole lap so segment times sum back to the lap time.
SPA_CORNERS = (
    "La Source", "Eau Rouge", "Raidillon 1", "Raidillon 2", "Les Combes 1",
    "Les Combes 2", "Malmedy", "Bruxelles", "No Name", "Pouhon 1", "Pouhon 2",
    "Fagnes 1", "Fagnes 2", "Campus", "Stavelot", "Paul Frère", "Blanchimont",
    "Bus Stop 1", "Bus Stop 2",
)
SPA_BOUNDARIES = (
    0.0, 0.070, 0.110, 0.145, 0.235, 0.265, 0.300, 0.345, 0.395, 0.475,
    0.515, 0.575, 0.615, 0.670, 0.725, 0.790, 0.845, 0.910, 0.955, 1.0,
)


def catalog_for(metadata: dict[str, object]) -> list[CatalogCorner] | None:
    if str(metadata.get("simulator", "iracing")).lower() != "iracing":
        return None
    identity = " ".join(str(metadata.get(key, "")) for key in ("track", "track_name", "layout")).lower()
    turns = _int(metadata.get("official_turns"))
    if "spa" in identity and (turns in {None, 19}):
        return [
            CatalogCorner(index + 1, name, SPA_BOUNDARIES[index], SPA_BOUNDARIES[index + 1])
            for index, name in enumerate(SPA_CORNERS)
        ]
    return None


def _int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
