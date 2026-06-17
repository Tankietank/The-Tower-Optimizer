## Tower Optimizer v2.0.0-preview.6

First complete public source release for [The-Tower-Optimizer](https://github.com/Tankietank/The-Tower-Optimizer).

### Highlights

- Full runnable application (`tower_optimizer` package, assets, tests, docs, CI)
- One-click **Import report(s)** workflow with batch preview and duplicate detection
- GT/BH/DW sync visualization, progression planner, battle-learning, and whole-account recommendations

### Install

```powershell
git clone https://github.com/Tankietank/The-Tower-Optimizer.git
cd The-Tower-Optimizer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
.\run_optimizer.ps1
```

### Verify

```powershell
.\run_public_checks.ps1
```

### Notes

Preview software: back up profiles before upgrades. Calculations marked **strategic** or **heuristic** are not exact game formulas.

See [CHANGELOG.md](CHANGELOG.md) for full details.
