"""Run with the simulator's Python environment; no aircraft is started."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from terraguavd_simulation import server


class PrearmTests(unittest.TestCase):
    def setUp(self):
        self.vehicle = server.Vehicle()
        self.vehicle.process = Mock()
        self.vehicle.process.poll.return_value = None
        self.vehicle.last_heartbeat = time.monotonic()
        self.vehicle.last_position = time.monotonic()
        self.vehicle.last_health = time.monotonic()
        self.flag = server.mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK

    def test_position_alone_cannot_authorize_arm(self):
        self.assertTrue(self.vehicle.ready())
        self.assertFalse(self.vehicle.armable())
        self.vehicle.messages['SYS_STATUS'] = SimpleNamespace(
            onboard_control_sensors_present=0, onboard_control_sensors_health=0)
        self.assertFalse(self.vehicle.armable())
        self.vehicle.messages['SYS_STATUS'].onboard_control_sensors_health = self.flag
        self.assertTrue(self.vehicle.armable())
        self.vehicle.last_health -= 5
        self.assertFalse(self.vehicle.armable())

    def test_failed_preflight_never_sends_arm(self):
        self.vehicle.total = 5
        self.vehicle.wait = Mock(side_effect=RuntimeError('timeout'))
        self.vehicle.command = Mock()
        self.vehicle.status_texts.append('Preflight Fail: system power unavailable')
        with patch.object(server, 'vehicle', self.vehicle):
            with self.assertRaises(server.HTTPException) as error:
                server.mission_command('start')
        self.assertIn('system power unavailable', error.exception.detail)
        self.vehicle.command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
