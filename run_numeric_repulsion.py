#!/usr/bin/env python3
"""Standalone launcher: numeric task with WOLFPACK_REPULSION_ENABLED=True, full 8000-cycle run,
same seed/methodology as every other comparison tonight."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
sc.WOLFPACK_REPULSION_ENABLED = True
import lucy_original_numeric_task as m
m.main()
