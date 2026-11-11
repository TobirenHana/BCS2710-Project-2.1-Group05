@echo off
pushd "%~dp0"
python parallax_system.py --input-mode simulated %*
if errorlevel 1 pause
popd
