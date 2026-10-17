#!/usr/bin/env python3
"""Standalone launcher: bit-level task with LATERAL_INHIBITION_ENABLED=True, full 8000-cycle run,
same seed/methodology as every other comparison tonight."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
sc.LATERAL_INHIBITION_ENABLED = True
import lucy_favorite_color_core_bitlevel as m
m.main()
