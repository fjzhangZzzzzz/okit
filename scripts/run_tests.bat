@echo off
setlocal

if "%1"=="" (
    echo Usage: run_tests.bat [unit^|integration^|all^|windows^|coverage]
    exit /b 1
)

if "%1"=="unit" (
    uv run pytest tests/ -v -m "unit"
) else if "%1"=="integration" (
    uv run pytest tests/ -v -m "integration"
) else if "%1"=="all" (
    uv run pytest tests/ -v
) else if "%1"=="windows" (
    uv run pytest tests/ -v -m "not (ssh or linux)"
) else if "%1"=="coverage" (
    uv run pytest tests/ --cov=okit --cov-report=html --cov-report=xml
) else (
    echo Unknown test type: %1
    echo Available types: unit, integration, all, windows, coverage
    exit /b 1
)