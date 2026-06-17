$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m streamlit run app.py
