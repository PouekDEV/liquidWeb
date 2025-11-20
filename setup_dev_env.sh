#!/bin/bash
pip install -r requirements.txt --upgrade
maturin build --release
filename=$(find ./target/wheels/*.whl)
pip install $filename --force-reinstall