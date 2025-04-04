#!/bin/bash
python -m pytest tests/test_client.py::TestClientE2E::test_cache_control -v --log-cli-level=INFO
