"""Isolated container-only PX4/Gazebo runtime. No exposed MAVLink transport."""
import math
import os
import signal
import subprocess
import threading
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pymavlink import mavutil
from .scene import SceneBridge


class Vehicle:
    def __init__(self):
        self.process = None
        self.link = None
        self.cv = threading.Condition()
        self.command_lock = threading.Lock()
        self.messages = {}
        self.requests = deque()
        self.ack = None
        self.mission_ack = None
        self.last_heartbeat = 0
        self.last_position = 0
        self.last_health = 0
        self.status_texts = deque(maxlen=8)
        self.receiver = None
        self.speed_m_s = 2
        self.started_at = 0
        self.completed_sequence = -1
        self.total = 0
        self.scene = SceneBridge()

    def start(self):
        if self.process and self.process.poll() is None:
            return
        self.messages.clear()
        self.last_heartbeat = 0
        self.last_position = 0
        self.last_health = 0
        self.status_texts.clear()
        self.completed_sequence = -1
        self.total = 0
        self.link = mavutil.mavlink_connection("udpin:127.0.0.1:14540", source_system=245)
        log = open('/tmp/terraguavd-px4.log', 'ab', buffering=0)
        self.process = subprocess.Popen(["px4-gazebo", "-d"], stdout=log, stderr=log,
                                        env={**os.environ, "HEADLESS": "1", "PX4_SIM_MODEL": "gz_x500"}, start_new_session=True)
        self.started_at = time.monotonic()
        self.receiver = threading.Thread(target=self.receive, daemon=True)
        self.receiver.start()
        self.scene.start()

    def receive(self):
        last_sent = 0
        while self.process and self.process.poll() is None:
            if time.monotonic()-last_sent >= 1:
                self.link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
                last_sent = time.monotonic()
            msg = self.link.recv_match(blocking=True, timeout=.5)
            if msg is None or msg.get_srcSystem() != 1:
                continue
            kind = msg.get_type()
            with self.cv:
                self.messages[kind] = msg
                if kind == 'HEARTBEAT':
                    self.last_heartbeat = time.monotonic()
                elif kind == 'GLOBAL_POSITION_INT':
                    self.last_position = time.monotonic()
                elif kind == 'SYS_STATUS':
                    self.last_health = time.monotonic()
                elif kind == 'STATUSTEXT':
                    self.status_texts.append(str(msg.text))
                elif kind == 'COMMAND_ACK':
                    self.ack = (msg.command, msg.result)
                elif kind in ('MISSION_REQUEST_INT', 'MISSION_REQUEST'):
                    self.requests.append(msg.seq)
                elif kind == 'MISSION_ACK':
                    self.mission_ack = msg.type
                elif kind == 'MISSION_ITEM_REACHED':
                    self.completed_sequence = max(self.completed_sequence, msg.seq)
                self.cv.notify_all()

    def wait(self, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        with self.cv:
            while not predicate():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('PX4 response timed out')
                self.cv.wait(min(remaining, 1))

    def ready(self):
        return bool(self.process and self.process.poll() is None and
                    time.monotonic() - self.last_heartbeat < 4 and time.monotonic()-self.last_position < 4)

    def command(self, command, *params):
        self.ack = None
        self.link.mav.command_long_send(1, 1, command, 0, *(list(params) + [0] * (7-len(params))))
        self.wait(lambda: self.ack is not None and self.ack[0] == command)
        if self.ack[1] not in (mavutil.mavlink.MAV_RESULT_ACCEPTED, mavutil.mavlink.MAV_RESULT_IN_PROGRESS):
            raise RuntimeError(f'PX4 rejected command {command}: result {self.ack[1]}; ' + '; '.join(self.status_texts))

    def armable(self):
        health = self.messages.get('SYS_STATUS')
        flag = mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
        return bool(self.ready() and health and time.monotonic()-self.last_health < 4
                    and health.onboard_control_sensors_health & flag)

    def snapshot(self):
        p = self.messages.get('GLOBAL_POSITION_INT')
        battery = self.messages.get('SYS_STATUS')
        heartbeat = self.messages.get('HEARTBEAT')
        return {'runtime': 'px4-gazebo', 'simulated': True, 'ready': self.ready(),
                'running': bool(self.process and self.process.poll() is None),
                'armed': bool(heartbeat and heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED),
                'latitude': p.lat / 1e7 if p else None, 'longitude': p.lon / 1e7 if p else None,
                'altitude_m': p.relative_alt / 1000 if p else None,
                'speed_m_s': math.hypot(p.vx, p.vy) / 100 if p else None,
                'battery_percent': battery.battery_remaining if battery and battery.battery_remaining >= 0 else None,
                'reached': self.completed_sequence, 'total': self.total,
                'flight_mode': mavutil.mode_string_v10(heartbeat) if heartbeat else 'DISCONNECTED'}

    def upload(self, body):
        # Fixed simulator-only allowlist: takeoff, speed, geographic waypoints, RTL.
        self.requests.clear()
        self.mission_ack = None
        self.completed_sequence = -1
        lat, lon = body.waypoints[0][1], body.waypoints[0][0]
        self.speed_m_s = body.speed_m_s
        unused = 2147483647
        items = [(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, float('nan'), int(lat*1e7), int(lon*1e7), body.altitude_m)]
        items += [(mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED, 1, body.speed_m_s, -1, 0, unused, unused, 0)]
        items += [(mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 1, 0, float('nan'), int(y*1e7), int(x*1e7), body.altitude_m) for x, y in body.waypoints]
        items += [(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, 0, 0, 0, 0, unused, unused, 0)]
        self.total = len(items)
        self.link.mav.mission_count_send(1, 1, len(items))
        deadline = time.monotonic() + 30
        while self.mission_ack is None:
            self.wait(lambda: bool(self.requests) or self.mission_ack is not None, max(.1, deadline-time.monotonic()))
            if self.mission_ack is not None:
                break
            index = self.requests.popleft()
            if not 0 <= index < len(items):
                raise RuntimeError('Invalid mission item requested')
            command, p1, p2, p3, p4, x, y, z = items[index]
            frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT if command in (mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,mavutil.mavlink.MAV_CMD_NAV_WAYPOINT) else mavutil.mavlink.MAV_FRAME_MISSION
            self.link.mav.mission_item_int_send(1, 1, index, frame,
                command, 1 if index == 0 else 0, 1, p1, p2, p3, p4, x, y, z)
        if self.mission_ack != mavutil.mavlink.MAV_MISSION_ACCEPTED:
            raise RuntimeError(f'Mission upload rejected: {self.mission_ack}; last requested item {index}')

    def stop(self):
        self.scene.stop()
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
        if self.link:
            if self.receiver:
                self.receiver.join(timeout=2)
            self.link.close()
        self.process = None


vehicle = Vehicle()


@asynccontextmanager
async def lifespan(app):
    yield
    vehicle.stop()


def authorized(authorization: str = Header(default='')):
    import secrets
    expected = os.environ.get('SIMULATION_SECRET', '')
    if not expected or not secrets.compare_digest(authorization, f'Bearer {expected}'):
        raise HTTPException(401, 'Runtime authentication required')


app = FastAPI(lifespan=lifespan, dependencies=[Depends(authorized)])


class FlightPlan(BaseModel):
    waypoints: list[tuple[float, float]] = Field(min_length=2, max_length=100)
    altitude_m: float = Field(ge=2, le=8)
    speed_m_s: float = Field(ge=.5, le=3, allow_inf_nan=False)


@app.get('/status')
def status():
    return vehicle.snapshot()


@app.get('/scene')
def scene():
    return vehicle.scene.snapshot()


@app.post('/runtime/start')
def start_runtime():
    with vehicle.command_lock:
        vehicle.start()  # Deliberately no upload, arm or mission command.
    return vehicle.snapshot()


@app.post('/runtime/stop')
def stop_runtime():
    with vehicle.command_lock:
        vehicle.stop()
    return vehicle.snapshot()


@app.post('/mission/upload')
def upload(body: FlightPlan):
    with vehicle.command_lock:
        if not vehicle.ready() or vehicle.snapshot()['armed']:
            raise HTTPException(409, 'Vehicle must be connected and disarmed')
        p = vehicle.snapshot()
        if any(abs(y-p['latitude'])>.004 or abs(x-p['longitude'])>.006 for x,y in body.waypoints):
            raise HTTPException(422, 'Plan is too far from simulator home')
        try:
            vehicle.upload(body)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
    return vehicle.snapshot()


@app.post('/mission/{command}')
def mission_command(command: str):
    with vehicle.command_lock:
        if not vehicle.ready():
            raise HTTPException(409, 'Vehicle is not ready')
        try:
            if command == 'start':
                if vehicle.total < 4 or vehicle.snapshot()['armed']:
                    raise HTTPException(409, 'A disarmed vehicle and uploaded mission are required')
                # A fresh position is not proof that PX4's startup checks passed.
                # Bound this wait below the backend HTTP timeout; never force-arm.
                try:
                    vehicle.wait(vehicle.armable, seconds=30)
                except RuntimeError as exc:
                    raise RuntimeError('PX4 pre-arm health checks did not pass: ' + '; '.join(vehicle.status_texts)) from exc
                vehicle.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
                vehicle.command(mavutil.mavlink.MAV_CMD_MISSION_START, 0, 0)
            elif command == 'pause':
                vehicle.command(mavutil.mavlink.MAV_CMD_DO_SET_MODE, *mavutil.px4_map['LOITER'])
            elif command == 'resume':
                vehicle.command(mavutil.mavlink.MAV_CMD_DO_SET_MODE, *mavutil.px4_map['MISSION'])
                vehicle.command(mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED, 1, vehicle.speed_m_s, -1)
            elif command == 'cancel':
                vehicle.command(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
            else:
                raise HTTPException(404, 'Unknown command')
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
    return vehicle.snapshot()
