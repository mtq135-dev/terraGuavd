"""Run with the simulator's Python environment; no aircraft is started."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from terraguavd_simulation import server


class PrearmTests(unittest.TestCase):
    def test_unknown_profile_is_rejected_before_process_launch(self):
        with patch.object(server.subprocess,'Popen') as launch:
            with self.assertRaises(server.HTTPException):server.Vehicle().start('physical-or-unknown')
            launch.assert_not_called()
    def test_profile_switch_while_armed_never_stops_or_launches_process(self):
        self.vehicle.snapshot=Mock(return_value={'armed':True})
        self.vehicle.stop=Mock()
        with patch.object(server.subprocess,'Popen') as launch:
            with self.assertRaises(server.HTTPException) as error:self.vehicle.start('px4-x500-lidar-down')
            self.assertEqual(error.exception.status_code,409)
            self.vehicle.stop.assert_not_called()
            launch.assert_not_called()

    def test_origin_switch_while_armed_is_rejected(self):
        self.vehicle.snapshot=Mock(return_value={'armed':True})
        self.vehicle.stop=Mock()
        with patch.object(server.subprocess,'Popen') as launch:
            with self.assertRaises(server.HTTPException):self.vehicle.start('px4-x500',{'latitude':22.77,'longitude':47.16})
            launch.assert_not_called();self.vehicle.stop.assert_not_called()

    def test_geographic_origin_is_passed_only_to_isolated_process_environment(self):
        vehicle=server.Vehicle();vehicle.scene=Mock()
        with patch.object(server,'SceneBridge',return_value=Mock()),patch.object(server.mavutil,'mavlink_connection',return_value=Mock()),patch.object(server.threading,'Thread',return_value=Mock()),patch.object(server.subprocess,'Popen',return_value=Mock()) as launch,patch('builtins.open',return_value=Mock()):
            vehicle.start('px4-x500',{'latitude':22.77,'longitude':47.16})
            environment=launch.call_args.kwargs['env']
            self.assertEqual(environment['PX4_HOME_LAT'],'22.77')
            self.assertEqual(environment['PX4_HOME_LON'],'47.16')
            self.assertEqual(environment['PX4_HOME_ALT'],'488')

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
