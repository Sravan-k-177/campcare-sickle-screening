# CampCare — Sickle Cell Camp Screening

Mobile-first Streamlit app for sickle-cell screening at field medical camps.
Registration + queue, vitals triage, CurveCircleNet AI microscopy screening
with explainability, records, and CSV exports. Offline-first: data lives in a
local SQLite database (`camp_screenings.db`, created on first launch).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Requires `curvecirclenet_sickle_best.pth` next to `app.py` (included in repo).

## Deploy notes (CPU servers)

`requirements.txt` installs the default PyTorch wheel (CUDA bundled, ~2 GB).
On CPU-only hosts (Streamlit Cloud, Hugging Face Spaces, Render) use the CPU
wheel instead — replace the `torch` line with:

```
--extra-index-url https://download.pytorch.org/whl/cpu
torch>=2.0.0
```

Everything else installs from standard PyPI. `opencv-python-headless` is used
so no system display libraries are needed.
