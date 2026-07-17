from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "frontend" / "dist"
target = root / "backend" / "iracing_analyst" / "static"
if not source.exists():
    raise SystemExit("Run `npm run build` in frontend first")
if target.exists():
    shutil.rmtree(target)
shutil.copytree(source, target)
print(target)

