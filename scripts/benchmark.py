#!/usr/bin/env python
"""Benchmark project discovery against the real configuration.

Run with: uv run scripts/benchmark.py
"""

import time

from multi_sessionizer import config, discovery

cfg = config.load_config()
t0 = time.perf_counter()
dirs = discovery.collect_dirs(cfg)
elapsed = time.perf_counter() - t0
print(f"collected {len(dirs)} dirs in {elapsed:.4f}s")
