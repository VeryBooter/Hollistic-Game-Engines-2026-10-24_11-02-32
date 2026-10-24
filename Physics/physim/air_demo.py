"""Two real JSBSim aircraft, SI telemetry, radar budget and visible EO observations.

Unity launches this module as a persistent JSON-lines worker. Native solver logs
go to stderr; stdout contains protocol messages only. No network port is opened.
"""
import argparse
import json
import math
import os
import sys
import threading
import time
from .demo_sensors import SensorSuite

DT = 1 / 120
FT = 0.3048

def clamp(x, lo, hi): return max(lo, min(hi, x))
def wrap(x): return (x + math.pi) % (2 * math.pi) - math.pi

def detect(observer, target):
    return SensorSuite().observe(observer,target,0)[0]

class Flight:
    def __init__(self, north_m, east_m, heading_rad):
        import jsbsim
        self.f = f = jsbsim.FGFDMExec(None)
        f.set_debug_level(0); f.disable_output()
        if not f.load_model('f16'): raise RuntimeError('JSBSim F16 model unavailable')
        f.set_dt(DT)
        self.north, self.east = north_m, east_m
        # All public configuration is SI. JSBSim's native properties convert here only.
        for k,v in {'ic/h-sl-ft':1828.8/FT, 'ic/vc-kts':154.333333333/.514444444444,
                    'ic/psi-true-deg':math.degrees(heading_rad),
                    'ic/lat-gc-deg':0, 'ic/long-gc-deg':0, 'propulsion/set-running':-1}.items(): f[k]=v
        if not f.run_ic(): raise RuntimeError('JSBSim initialization failed')
        f['propulsion/set-running']=-1
        f.do_trim(0)
        self.throttle = f['fcs/throttle-cmd-norm']
        self.target_altitude = 1828.8
        self.initial_fuel_kg = f['propulsion/total-fuel-lbs']*.45359237

    def state(self):
        f=self.f
        return {'position':[self.east, f['position/h-sl-ft']*FT, self.north],
                'yaw':f['attitude/psi-rad'], 'pitch':f['attitude/theta-rad'],
                'roll':f['attitude/phi-rad'], 'speed_m_s':f['velocities/vtrue-fps']*FT,
                'throttle':self.throttle,'mach':f['velocities/mach'],
                'velocity_m_s':[f['velocities/v-east-fps']*FT,-f['velocities/v-down-fps']*FT,f['velocities/v-north-fps']*FT],
                'fuel_kg':f['propulsion/total-fuel-lbs']*.45359237,
                'initial_fuel_kg':self.initial_fuel_kg,
                'fuel_flow_kg_s':f['propulsion/engine/fuel-flow-rate-pps']*.45359237}

    def advance(self, bank, pitch, throttle=None, rudder=0):
        f=self.f
        if throttle is not None: self.throttle=clamp(throttle,0,1)
        f['fcs/throttle-cmd-norm']=self.throttle
        f['fcs/aileron-cmd-norm']=clamp(1.4*wrap(bank-f['attitude/phi-rad'])-.35*f['velocities/p-rad_sec'],-1,1)
        f['fcs/elevator-cmd-norm']=clamp(-1.6*(pitch-f['attitude/theta-rad'])+.5*f['velocities/q-rad_sec'],-.6,.6)
        f['fcs/rudder-cmd-norm']=clamp(rudder,-.3,.3)
        if not f.run(): raise RuntimeError('JSBSim stopped')
        self.north += f['velocities/v-north-fps']*FT*DT
        self.east += f['velocities/v-east-fps']*FT*DT
        state=self.state()
        if not all(math.isfinite(x) for x in state['position']+[state['speed_m_s']]):
            raise RuntimeError('Non-finite flight state')
        return state

class Demo:
    def __init__(self): self.reset()
    def reset(self):
        self.player=Flight(0,0,0)
        self.opponent=Flight(4200,300,math.pi)
        self.time=0; self.crashed=False
        self.frequency_Hz=1e10
        self.player_suite,self.opponent_suite=SensorSuite(),SensorSuite()
        self.update_sensors()

    def update_sensors(self):
        a,b=self.player.state(),self.opponent.state()
        self.player_sensor,self.player_eo=self.player_suite.observe(a,b,self.time,self.frequency_Hz)
        self.opponent_sensor,self.opponent_eo=self.opponent_suite.observe(b,a,self.time,1e10)

    def step(self, control):
        frequency=float(control.get('frequency_Hz',self.frequency_Hz))
        if frequency!=self.frequency_Hz:
            self.frequency_Hz=frequency;self.update_sensors()
        if self.crashed or control.get('paused',False): return
        pitch_input=clamp(float(control.get('pitch',0)),-1,1)
        self.player.target_altitude=clamp(self.player.target_altitude+pitch_input*100*DT,300,6000)
        altitude=self.player.state()['position'][1]
        pitch=clamp((self.player.target_altitude-altitude)*.002,-.23,.23)
        self.player.advance(clamp(float(control.get('roll',0)),-1,1)*.8,pitch,
                            control.get('throttle',.4),float(control.get('yaw',0))*.2)
        a,b=self.opponent.state(),self.player.state()
        heading=math.atan2(b['position'][0]-a['position'][0],b['position'][2]-a['position'][2])
        desired_bank=clamp(wrap(heading-a['yaw'])*1.2,-.65,.65)
        desired_pitch=clamp((b['position'][1]-a['position'][1])*.001,-.18,.18)
        self.opponent.advance(desired_bank,desired_pitch,.4)
        self.time+=DT
        self.update_sensors()
        self.crashed=min(self.player.state()['position'][1],self.opponent.state()['position'][1])<20

    def snapshot(self):
        a,b=self.player.state(),self.opponent.state()
        f=self.player.f
        return {'type':'state','time_s':self.time,'player':a,'opponent':b,
                'player_sensor':self.player_sensor,'opponent_sensor':self.opponent_sensor,
                'player_eo':self.player_eo,'opponent_eo':self.opponent_eo,
                'crashed':self.crashed,'range_limit_m':20000.,
                'temperature_K':f['atmosphere/T-R']*5/9,
                'pressure_Pa':f['atmosphere/P-psf']*47.88025898033584}

def serve(output):
    latest={'pitch':0,'roll':0,'yaw':0,'throttle':.4,'paused':False}
    lock=threading.Lock(); quit_event=threading.Event()
    def read():
        try:
            for line in sys.stdin:
                command=json.loads(line)
                with lock: latest.update(command)
        finally: quit_event.set()
    threading.Thread(target=read,daemon=True).start()
    demo=Demo(); tick=time.monotonic(); n=0
    while not quit_event.is_set():
        with lock:
            command=dict(latest); latest.pop('reset',None)
        if command.get('quit'): break
        if command.get('reset'): demo.reset(); tick=time.monotonic()
        demo.step(command); n+=1
        if n%4==0:
            output.write(json.dumps(demo.snapshot(),allow_nan=False)+'\n'); output.flush()
        tick+=DT
        remaining=tick-time.monotonic()
        if remaining>0: time.sleep(remaining)
        elif remaining<-.25: tick=time.monotonic()

def smoke(output):
    demo=Demo()
    assert demo.snapshot()['player_sensor']['detected']
    assert demo.snapshot()['opponent_sensor']['detected']
    for i in range(120*45):
        demo.step({'roll':.5 if 120*4<i<120*12 else 0,'pitch':.3 if i<120*5 else 0,'throttle':.4})
    final=demo.snapshot()
    assert not final['crashed'],final
    assert final['player']['position'][0]>100,final
    outside=dict(final['opponent'],position=[0,1800,200000])
    assert not detect(final['player'],outside)['detected']
    behind={'position':[0,1800,-100],'yaw':0,'pitch':0}
    assert not detect({'position':[0,1800,0],'yaw':0,'pitch':0},behind)['detected']
    before=demo.time; demo.step({'paused':True}); assert demo.time==before
    demo.reset(); assert demo.time==0
    output.write(json.dumps({'smoke_passed':True,'after_45s':final},allow_nan=False)+'\n')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--smoke',action='store_true'); args=parser.parse_args()
    output=os.fdopen(os.dup(sys.stdout.fileno()),'w',buffering=1)
    os.dup2(sys.stderr.fileno(),sys.stdout.fileno())
    try:
        if args.smoke: smoke(output)
        else: serve(output)
    except Exception as exc:
        output.write(json.dumps({'type':'error','message':str(exc)})+'\n');output.flush();raise

if __name__=='__main__':main()
