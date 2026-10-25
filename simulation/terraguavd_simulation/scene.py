"""Read-only Gazebo world pose bridge. No commands or sensor images."""
import json
import math
import subprocess
import threading
import time


def decode_pose(line):
    data = json.loads(line)
    model = next((p for p in data.get('pose', []) if p.get('name') == 'x500_0'), None)
    if model is None:
        return None
    position = [float(model.get('position', {}).get(k, 0)) for k in ('x', 'y', 'z')]
    quaternion = [float(model.get('orientation', {}).get(k, 1 if k == 'w' else 0)) for k in ('x', 'y', 'z', 'w')]
    if not all(math.isfinite(v) for v in position + quaternion):
        raise ValueError('Invalid Gazebo pose')
    if sum(v*v for v in quaternion) < .01:
        raise ValueError('Invalid Gazebo orientation')
    return {'name': 'x500_0', 'position': position, 'quaternion': quaternion,
            'simulation_time': data.get('header', {}).get('stamp', {})}


class SceneBridge:
    def __init__(self):
        self.process = None
        self.thread = None
        self.lock = threading.Lock()
        self.pose = None
        self.updated = 0

    def start(self):
        self.stop()
        process = subprocess.Popen(['gz', 'topic', '-e', '-t', '/world/default/pose/info', '--json-output'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.process = process
        self.thread = threading.Thread(target=self.receive, args=(process,), daemon=True)
        self.thread.start()

    def receive(self, process):
        for line in process.stdout:
            try:
                pose = decode_pose(line)
                if pose is not None:
                    with self.lock:
                        self.pose = pose
                        self.updated = time.monotonic()
            except (ValueError, TypeError, KeyError):
                continue

    def snapshot(self):
        with self.lock:
            age = time.monotonic()-self.updated
            live = bool(self.process and self.process.poll() is None and self.pose and age < 3)
            return {'runtime': 'px4-gazebo', 'simulated': True, 'source': 'gazebo-world-pose',
                    'world': 'default', 'frame': 'Gazebo world ENU, meters, quaternion xyzw',
                    'live': live, 'pose': self.pose if live else None}

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.thread:
            self.thread.join(timeout=3)
        self.process = None
        with self.lock:
            self.pose = None
            self.updated = 0
