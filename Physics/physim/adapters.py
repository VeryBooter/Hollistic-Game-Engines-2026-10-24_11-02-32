"""Actual upstream API calls. Missing solvers raise; there is no numerical fallback."""
import json
import math
import subprocess
import csv
import shutil
import tempfile
from pathlib import Path
from .contract import ROOT, packet, validate

def jsbsim_run(config, inputs):
    import jsbsim
    dt = float(config.get('step_s', 0.01))
    steps = int(config.get('steps', 100))
    if not 0 < dt <= 1 or not 1 <= steps <= 100000:
        raise ValueError('Invalid JSBSim step or step count')
    sim = jsbsim.FGFDMExec(None)
    sim.set_debug_level(0)
    sim.disable_output()
    if not sim.load_model(config.get('aircraft', 'c172p')):
        raise RuntimeError('JSBSim aircraft failed to load')
    sim.set_dt(dt)
    sim['ic/h-sl-ft'] = float(config.get('altitude_m', 1000.0)) / 0.3048
    sim['ic/vc-kts'] = float(config.get('airspeed_m_s', 50.0)) / 0.514444444444
    sim['ic/lat-gc-deg'] = 0
    sim['ic/long-gc-deg'] = 0
    if not sim.run_ic():
        raise RuntimeError('JSBSim initial conditions failed')
    samples = []
    for _ in range(steps):
        if not sim.run(): raise RuntimeError('JSBSim run stopped early')
        samples.append(packet('jsbsim', sim.get_sim_time(), dt,
            atmosphere={'temperature_K': sim['atmosphere/T-R'] * 5 / 9,
                        'pressure_Pa': sim['atmosphere/P-psf'] * 47.88025898033584},
            altitude_m=sim['position/h-sl-ft'] * 0.3048,
            velocity_m_s=[sim['velocities/v-north-fps'] * 0.3048,
                          sim['velocities/v-east-fps'] * 0.3048,
                          sim['velocities/v-down-fps'] * 0.3048],
            loads={'frame': 'BODY_FRD',
                   'force_N': [sim['forces/fbx-total-lbs'] * 4.4482216152605,
                               sim['forces/fby-total-lbs'] * 4.4482216152605,
                               sim['forces/fbz-total-lbs'] * 4.4482216152605],
                   'torque_N_m': [sim['moments/l-total-lbsft'] * 1.3558179483314,
                                  sim['moments/m-total-lbsft'] * 1.3558179483314,
                                  sim['moments/n-total-lbsft'] * 1.3558179483314]},
            mass_properties={'mass_kg': sim['inertia/mass-slugs'] * 14.5939029372}))
    return samples

def coolprop_run(config, inputs):
    from CoolProp.CoolProp import PropsSI
    source = inputs or [packet('input', 0.0, 0.0, atmosphere={
        'temperature_K': float(config.get('temperature_K', 288.15)),
        'pressure_Pa': float(config.get('pressure_Pa', 101325.0))})]
    output = []
    for state in source:
        validate(state)
        a = state['atmosphere']
        t, p = a['temperature_K'], a['pressure_Pa']
        output.append(packet('coolprop', state['time_s'], state['step_s'],
            atmosphere=dict(a, density_kg_m3=PropsSI('D', 'T', t, 'P', p, 'Air'),
                            sound_speed_m_s=PropsSI('A', 'T', t, 'P', p, 'Air'),
                            specific_heat_J_kg_K=PropsSI('C', 'T', t, 'P', p, 'Air')),
            provenance={'source_module': state['module'], 'source_time_s': state['time_s']}))
    return output

def cantera_run(config, inputs):
    import cantera as ct
    gas = ct.Solution('gri30.yaml')
    gas.TPX = float(config.get('temperature_K', 300)), float(config.get('pressure_Pa', 101325)), 'CH4:1,O2:2,N2:7.52'
    initial_h = gas.enthalpy_mass
    gas.equilibrate('HP')
    return [packet('cantera', 0.0, 0.0, temperature_K=gas.T,
        chemistry={'pressure_Pa': gas.P, 'initial_enthalpy_J_kg': initial_h,
                   'enthalpy_J_kg': gas.enthalpy_mass,
                   'species_mole_fractions': dict(zip(gas.species_names, map(float, gas.X)))})]

def chrono_run(config, inputs):
    binary = ROOT / 'build/bridge/chrono_smoke'
    if not binary.is_file(): raise RuntimeError('Run scripts/build.py chrono first')
    result = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=60)
    raw = json.loads(result.stdout)
    return [packet('chrono', raw['time_s'], raw['step_s'], position_m=raw['position_m'],
                   velocity_m_s=raw['velocity_m_s'], mass_properties={'mass_kg': raw['mass_kg']})]

def su2_run(config, inputs):
    binary = ROOT / 'install/su2/bin/SU2_CFD'
    if not binary.is_file(): raise RuntimeError('Run scripts/build.py su2 first')
    with tempfile.TemporaryDirectory(prefix='physim-su2-') as temp:
        folder = Path(temp)
        for name in ['uniform.cfg', 'uniform.su2']:
            shutil.copyfile(ROOT / 'examples/su2' / name, folder / name)
        result = subprocess.run([str(binary), 'uniform.cfg'], cwd=folder,
                                capture_output=True, text=True, check=True, timeout=60)
        with (folder / 'history.csv').open() as stream:
            rows = list(csv.DictReader(stream, skipinitialspace=True))
        if not rows: raise RuntimeError('SU2 produced no iteration history')
        last = {k.strip().strip('"'): float(v) for k,v in rows[-1].items()}
        residuals = {k:v for k,v in last.items() if k.startswith('rms[')}
        if not residuals: raise RuntimeError('SU2 history has no RMS residual columns')
        if not all(math.isfinite(v) and v < -8 for v in residuals.values()):
            raise RuntimeError('SU2 free-stream preservation failed: ' + str(residuals))
        return [packet('su2', 0.0, 0.0, flow_analysis={
            'case': 'uniform_2d_euler', 'iterations_recorded': len(rows),
            'residuals_log10': residuals})]

def external_run(name, config, inputs):
    """Explicit process integration for built upstream executables and real decks."""
    commands = config.get('command')
    if not isinstance(commands, list) or not commands or not all(isinstance(x, str) for x in commands):
        raise RuntimeError(f'{name}: no built executable configured; see docs/MODULES.md')
    cwd = Path(config.get('cwd', ROOT)).resolve()
    result = subprocess.run(commands, cwd=cwd, capture_output=True, text=True, check=True,
                            timeout=float(config.get('timeout_s', 300)))
    # Process success is evidence of invocation only; output physics needs a solver-specific parser.
    return {'invocation_only': True, 'module': name, 'stdout': result.stdout, 'stderr': result.stderr}

ADAPTERS = {'jsbsim': jsbsim_run, 'coolprop': coolprop_run,
            'cantera': cantera_run, 'chrono': chrono_run, 'su2': su2_run}
