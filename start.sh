#!/bin/bash
source venv/bin/activate
python -m flask run --host=0.0.0.0 --port=${PORT:-5000}
