import json
import time
import unittest
from unittest.mock import Mock
from terraguavd_simulation.scene import SceneBridge, decode_pose


class SceneTests(unittest.TestCase):
    def test_only_world_uav_pose_is_selected(self):
        pose=decode_pose(json.dumps({'pose':[
            {'name':'rotor_0','position':{'x':9}},
            {'name':'x500_0','position':{'x':2,'z':5},'orientation':{'w':1}}]}))
        self.assertEqual(pose['position'],[2,0,5])
        self.assertEqual(pose['quaternion'],[0,0,0,1])
        self.assertIsNone(decode_pose('{"pose":[]}'))
        with self.assertRaises(ValueError):
            decode_pose('{"pose":[{"name":"x500_0","position":{"x":"nan"}}]}')

    def test_stale_or_stopped_pose_is_not_live(self):
        bridge=SceneBridge()
        bridge.process=Mock()
        bridge.process.poll.return_value=None
        bridge.pose={'position':[1,2,3]}
        bridge.updated=time.monotonic()
        self.assertTrue(bridge.snapshot()['live'])
        bridge.updated-=4
        self.assertFalse(bridge.snapshot()['live'])
        self.assertIsNone(bridge.snapshot()['pose'])
        bridge.updated=time.monotonic()
        bridge.process.poll.return_value=0
        self.assertFalse(bridge.snapshot()['live'])


if __name__=='__main__':
    unittest.main()
