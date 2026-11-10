import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'phase7_live_smoke.py'
spec = importlib.util.spec_from_file_location('phase7_live_smoke', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ContractTests(unittest.TestCase):
    def test_real_health_response(self):
        mod.validate_health(200, {'status': 'ok', 'service': 'reqflow-api'})

    def test_invalid_health_reports_actionable_message(self):
        with self.assertRaisesRegex(ValueError, '/health: expected status=ok'):
            mod.validate_health(200, {'status': 'failed'})

    def test_wrong_health_status(self):
        with self.assertRaisesRegex(ValueError, 'expected HTTP 200'):
            mod.validate_health(503, {'status': 'ok'})

if __name__ == '__main__': unittest.main()
