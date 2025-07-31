#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: run_tests.sh [unit|integration|all|linux|coverage]"
    exit 1
fi

case "$1" in
    "unit")
        uv run pytest tests/ -v -m "unit"
        ;;
    "integration")
        uv run pytest tests/ -v -m "integration"
        ;;
    "all")
        uv run pytest tests/ -v
        ;;
    "linux")
        uv run pytest tests/ -v -m "not windows"
        ;;
    "coverage")
        uv run pytest tests/ --cov=okit --cov-report=html --cov-report=xml
        ;;
    *)
        echo "Unknown test type: $1"
        echo "Available types: unit, integration, all, linux, coverage"
        exit 1
        ;;
esac