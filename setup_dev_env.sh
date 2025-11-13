#!/bin/bash
pip install -r requirements.txt --upgrade
maturin build --release
pip install ./target/wheels/q565_rust-0.1.0-cp312-cp312-win_amd64.whl --force-reinstall