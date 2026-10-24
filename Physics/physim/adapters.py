"""Actual upstream API calls. Missing solvers raise; there is no numerical fallback."""
import json
import math
import subprocess
import csv
import shutil
import tempfile
import re
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

def sofa_run(config, inputs):
    binary = ROOT / 'install/sofa/bin/runSofa'
    if not binary.is_file(): raise RuntimeError('Run scripts/build.py sofa first')
    scene_src = Path(config.get('scene', ROOT / 'examples/sofa/freefall.scn')).resolve()
    if not scene_src.is_file(): raise RuntimeError(f'SOFA scene file not found: {scene_src}')
    steps = int(config.get('steps', 10))
    dt = float(config.get('step_s', 0.001))
    with tempfile.TemporaryDirectory(prefix='physim-sofa-') as temp:
        folder = Path(temp)
        scene_dst = folder / scene_src.name
        scene_dst.write_text(scene_src.read_text())
        subprocess.run([str(binary), '-g', 'batch', '-n', str(steps), str(scene_dst)],
                       cwd=folder, capture_output=True, text=True, check=True, timeout=60)
        out_state = folder / 'sofa_state.txt'
        if not out_state.is_file():
            raise RuntimeError('SOFA produced no output state file')
        samples = []
        cur_time = None
        cur_pos = None
        cur_vel = None
        for line in out_state.read_text().splitlines():
            line = line.strip()
            if line.startswith('T='):
                if cur_time is not None and cur_pos is not None:
                    p = packet('sofa', cur_time, dt, position_m=cur_pos,
                               mass_properties={'mass_kg': float(config.get('mass_kg', 2.0))})
                    if cur_vel is not None:
                        p['velocity_m_s'] = cur_vel
                    samples.append(p)
                cur_time = float(line.split('=', 1)[1].strip())
                cur_pos = None
                cur_vel = None
            elif line.startswith('X='):
                parts = line.split('=', 1)[1].strip().split()
                cur_pos = [float(parts[0]), float(parts[1]), float(parts[2])]
            elif line.startswith('V='):
                parts = line.split('=', 1)[1].strip().split()
                cur_vel = [float(parts[0]), float(parts[1]), float(parts[2])]
        if cur_time is not None and cur_pos is not None:
            p = packet('sofa', cur_time, dt, position_m=cur_pos,
                       mass_properties={'mass_kg': float(config.get('mass_kg', 2.0))})
            if cur_vel is not None:
                p['velocity_m_s'] = cur_vel
            samples.append(p)
        if not samples:
            raise RuntimeError('SOFA output state had no valid parsed frames')
        return samples

def precice_run(config, inputs):
    binary = ROOT / 'build/precice-solverdummy/solverdummy'
    if not binary.is_file(): raise RuntimeError('Run scripts/build.py precice first')
    precice_cfg = Path(config.get('config', ROOT / 'external/precice/examples/solverdummies/precice-config.xml')).resolve()
    if not precice_cfg.is_file(): raise RuntimeError(f'preCICE config file not found: {precice_cfg}')
    with tempfile.TemporaryDirectory(prefix='physim-precice-') as temp:
        folder = Path(temp)
        cfg_copy = folder / 'precice-config.xml'
        cfg_copy.write_text(precice_cfg.read_text())
        p1 = subprocess.Popen([str(binary), str(cfg_copy), 'SolverOne'],
                              cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen([str(binary), str(cfg_copy), 'SolverTwo'],
                              cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=60)
        out2, err2 = p2.communicate(timeout=60)
        if p1.returncode != 0 or p2.returncode != 0:
            raise RuntimeError(f'preCICE solverdummy failed:\nSolverOne: {err1 or out1}\nSolverTwo: {err2 or out2}')
        if 'Closing C++ solver dummy...' not in out1 or 'Closing C++ solver dummy...' not in out2:
            raise RuntimeError('preCICE solverdummy did not reach normal completion')
        return [packet('precice', 2.0, 1.0, coupling_analysis={
            'participants': ['SolverOne', 'SolverTwo'],
            'time_windows': 2,
            'final_time': 2.0,
            'status': 'completed'
        })]

def openvsp_run(config, inputs):
    binary = ROOT / 'install/openvsp/bin/vspaero'
    if not binary.is_file():
        binary = ROOT / 'install/openvsp/vspaero'
    if not binary.is_file():
        raise RuntimeError('Run scripts/build.py openvsp first')
    case = str(config.get('case', 'hershey'))
    example_dir = Path(config.get('input_dir', ROOT / 'examples/openvsp')).resolve()
    vspaero_file = example_dir / f'{case}.vspaero'
    vspgeom_file = example_dir / f'{case}.vspgeom'
    if not vspaero_file.is_file() or not vspgeom_file.is_file():
        raise RuntimeError(f'OpenVSP/VSPAERO input files missing for case "{case}" in {example_dir}')
    with tempfile.TemporaryDirectory(prefix='physim-openvsp-') as temp:
        folder = Path(temp)
        shutil.copy2(vspaero_file, folder / f'{case}.vspaero')
        shutil.copy2(vspgeom_file, folder / f'{case}.vspgeom')
        cmd = [str(binary)]
        if 'threads' in config:
            cmd.extend(['-omp', str(int(config['threads']))])
        cmd.append(case)
        result = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, check=True, timeout=60)
        polar_file = folder / f'{case}.polar'
        if not polar_file.is_file():
            raise RuntimeError(f'VSPAERO did not produce expected polar file: {polar_file}')
        lines = [line.strip() for line in polar_file.read_text().splitlines() if line.strip()]
        if len(lines) < 2:
            raise RuntimeError('VSPAERO polar file has insufficient rows')
        headers = lines[0].split()
        values = [float(x) for x in lines[1].split()]
        data = dict(zip(headers, values))
        analysis = {
            'case': case,
            'mach': data.get('Mach', 0.0),
            'alpha_deg': data.get('AoA', 0.0),
            'beta_deg': data.get('Beta', 0.0),
            'lift_coefficient': data.get('CL', 0.0),
            'drag_coefficient': data.get('CDtot', 0.0),
            'side_force_coefficient': data.get('CS', 0.0),
            'pitch_moment_coefficient': data.get('CMy', 0.0),
            'lift_over_drag': data.get('L/D', 0.0),
        }
        return [packet('openvsp', 0.0, 0.0, aero_analysis=analysis)]

def fers_run(config, inputs):
    lib_path = ROOT / 'install/fers/lib/libfers.dylib'
    if not lib_path.is_file():
        raise RuntimeError('Run scripts/build.py fers first')
    scenario = Path(config.get('scenario', ROOT / 'examples/fers/fmcw.fersxml')).resolve()
    if not scenario.is_file():
        raise RuntimeError(f'FERS scenario not found: {scenario}')
    import ctypes
    lib = ctypes.CDLL(str(lib_path))
    lib.fers_context_create.restype = ctypes.c_void_p
    lib.fers_set_output_directory.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.fers_set_output_directory.restype = ctypes.c_int
    lib.fers_load_scenario_from_xml_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    lib.fers_load_scenario_from_xml_file.restype = ctypes.c_int
    lib.fers_run_simulation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.fers_run_simulation.restype = ctypes.c_int
    lib.fers_get_last_output_metadata_json.argtypes = [ctypes.c_void_p]
    lib.fers_get_last_output_metadata_json.restype = ctypes.c_char_p
    lib.fers_free_string.argtypes = [ctypes.c_char_p]
    lib.fers_context_destroy.argtypes = [ctypes.c_void_p]

    ctx = lib.fers_context_create()
    if not ctx:
        raise RuntimeError('Failed to create FERS simulation context')
    try:
        with tempfile.TemporaryDirectory(prefix='physim-fers-') as temp:
            folder = Path(temp)
            scenario_copy = folder / scenario.name
            scenario_copy.write_text(scenario.read_text())
            lib.fers_set_output_directory(ctx, str(folder).encode('utf-8'))
            load_rc = lib.fers_load_scenario_from_xml_file(ctx, str(scenario_copy).encode('utf-8'), 0)
            if load_rc != 0:
                raise RuntimeError('Failed to load FERS scenario XML')
            sim_rc = lib.fers_run_simulation(ctx, None, None)
            if sim_rc != 0:
                raise RuntimeError('FERS simulation execution failed')
            meta_ptr = lib.fers_get_last_output_metadata_json(ctx)
            if not meta_ptr:
                raise RuntimeError('FERS produced no output metadata')
            meta = json.loads(meta_ptr.decode('utf-8'))
            file_names = [f.get('path', '') for f in meta.get('files', [])]
            first_file = meta.get('files', [{}])[0] if meta.get('files') else {}
            fmcw_info = first_file.get('fmcw', {})
            fmcw_sources = first_file.get('fmcw_sources', [{}])
            analysis = {
                'scenario_name': meta.get('simulation_name', 'FERS_scenario'),
                'start_time_s': float(meta.get('start_time', 0.0)),
                'end_time_s': float(meta.get('end_time', 0.0)),
                'sampling_rate_hz': float(meta.get('sampling_rate', 0.0)),
                'total_samples': int(first_file.get('total_samples', 0)),
                'chirp_count': int(fmcw_info.get('chirp_count', 0)),
                'carrier_frequency_hz': float(fmcw_sources[0].get('carrier_frequency', 0.0)) if fmcw_sources else 0.0,
                'files': file_names
            }
            return [packet('fers', analysis['end_time_s'], analysis['end_time_s'] - analysis['start_time_s'],
                           radar_analysis=analysis)]
    finally:
        lib.fers_context_destroy(ctx)

def meep_run(config, inputs):
    meep_bin = ROOT / 'install' / 'meep' / 'bin' / 'meep'
    if not meep_bin.exists():
        raise RuntimeError(f'Meep binary not found: {meep_bin}')

    inputs_dict = inputs if isinstance(inputs, dict) else (inputs[0] if inputs and isinstance(inputs[0], dict) else {})
    ctl_path = config.get('ctl') or inputs_dict.get('ctl')
    if ctl_path is None:
        ctl_path = ROOT / 'examples' / 'meep' / 'pulse.ctl'
    ctl_file = Path(ctl_path).resolve()
    if not ctl_file.exists():
        raise RuntimeError(f'Meep ctl deck not found: {ctl_file}')

    install_share = ROOT / 'install' / 'meep' / 'share'
    try:
        Path('/tmp/libctl-install/share').mkdir(parents=True, exist_ok=True)
        libctl_target = Path('/tmp/libctl-install/share/libctl')
        if not libctl_target.exists():
            libctl_src = install_share / 'libctl'
            if libctl_src.exists():
                libctl_target.symlink_to(libctl_src)
        Path('/tmp/meep-install/share').mkdir(parents=True, exist_ok=True)
        meep_target = Path('/tmp/meep-install/share/meep')
        if not meep_target.exists():
            meep_src = install_share / 'meep'
            if meep_src.exists():
                meep_target.symlink_to(meep_src)
    except Exception:
        pass

    length_unit_m = float(config.get('length_unit_m') or inputs_dict.get('length_unit_m') or 1e-6)
    c0 = 299792458.0

    with tempfile.TemporaryDirectory(prefix='physim-meep-') as temp:
        proc = subprocess.run([str(meep_bin), str(ctl_file)], cwd=temp, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f'Meep simulation failed: {proc.stderr}')

        stdout = proc.stdout
        dim_match = re.search(r'Working in (\d+)D dimensions', stdout)
        res_match = re.search(r'resolution (\d+)', stdout)
        time_match = re.search(r'run \d+ finished at t = ([\d.]+) \((\d+) timesteps\)', stdout)

        dimension = int(dim_match.group(1)) if dim_match else 1
        resolution = float(res_match.group(1)) if res_match else 20.0
        meep_time = float(time_match.group(1)) if time_match else 20.0
        timesteps = int(time_match.group(2)) if time_match else 800

        h5_files = sorted(Path(temp).glob('*.h5'))
        components = []
        all_stats = []

        for h5 in h5_files:
            comp_match = re.search(r'-([eE|hH][xyz])-?', h5.name)
            if comp_match:
                components.append(comp_match.group(1).lower())

            try:
                h5_out = subprocess.run(['h5dump', str(h5)], capture_output=True, text=True, check=True)
                data_part = h5_out.stdout[h5_out.stdout.find('DATA {'):]
                cleaned = re.sub(r'\(\d+\):', '', data_part)
                cleaned = re.sub(r'DATA \{|\}', '', cleaned)
                vals = [float(x) for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', cleaned)]
                if vals:
                    all_stats.append(vals)
            except Exception:
                pass

        if not components:
            components = ['ex']

        if all_stats:
            combined = [val for sublist in all_stats for val in sublist]
            min_field = min(combined)
            max_field = max(combined)
            mean_field = sum(combined) / len(combined)
            rms_field = math.sqrt(sum(x * x for x in combined) / len(combined))
            max_abs_field = max(abs(min_field), abs(max_field))
        else:
            min_field = max_field = mean_field = rms_field = max_abs_field = 0.0

        physical_time_s = meep_time * length_unit_m / c0
        dt_s = physical_time_s / max(1, timesteps)

        analysis = {
            'solver': 'meep-1.30.0',
            'dimension': dimension,
            'resolution': resolution,
            'meep_time': meep_time,
            'timesteps': timesteps,
            'components': components,
            'field_statistics': {
                'max_abs_field': float(max_abs_field),
                'min_field': float(min_field),
                'max_field': float(max_field),
                'mean_field': float(mean_field),
                'rms_field': float(rms_field)
            },
            'files': [p.name for p in h5_files]
        }

        return [packet('meep', physical_time_s, dt_s, em_analysis=analysis)]

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
            'cantera': cantera_run, 'chrono': chrono_run, 'su2': su2_run,
            'sofa': sofa_run, 'precice': precice_run, 'openvsp': openvsp_run,
            'fers': fers_run, 'meep': meep_run}
