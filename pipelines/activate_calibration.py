#!/usr/bin/env python3
"""Activate Phase 1 calibration (param_id=8)"""

from dotenv import load_dotenv
import psycopg
import os
from datetime import datetime

load_dotenv()
conn = psycopg.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Deactivate all, then activate param_id=8
cur.execute('UPDATE calibration_params SET is_active = FALSE, activated_at = NULL;')
print('Deactivated all calibration parameters')

cur.execute(
    'UPDATE calibration_params SET is_active = TRUE, activated_at = %s WHERE param_id = 8;',
    (datetime.now(),)
)
print('✓ Activated param_id=8 (Phase 1: a=-0.2067, b=-0.3363)')

conn.commit()
conn.close()

print('\nVerify with: python -m pipelines.betting.show_calibration_progress')
