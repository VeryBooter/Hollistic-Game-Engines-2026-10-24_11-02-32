#!/usr/bin/env python3
"""Independent native builds; failures are recorded per module and never emulated."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'dependencies.lock.json').read_text())['modules']

def build(name, configure_only=False, jobs=4):
    src = ROOT / 'external' / name
    out = ROOT / 'build' / name
    prefix = ROOT / 'install' / name
    log = ROOT / 'artifacts/logs' / (name + '-build.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    state = {'configured': False, 'built_from_source': False, 'log': str(log.relative_to(ROOT))}
    env = dict(os.environ, CC='/usr/bin/clang', CXX='/usr/bin/clang++',
               CCACHE_DIR=str(ROOT / 'build/ccache'), CMAKE_BUILD_PARALLEL_LEVEL=str(jobs),
               CMAKE_POLICY_VERSION_MINIMUM='3.5', PYTHONUNBUFFERED='1')
    with log.open('w') as stream:
        def run(args, cwd=ROOT):
            args = list(map(str, args))
            stream.write('$ ' + shlex.join(args) + '\n'); stream.flush()
            subprocess.run(args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=1800, check=True)
        def cmake(extra=(), source=src, binary=out):
            run(['cmake', '-S', source, '-B', binary, '-DCMAKE_BUILD_TYPE=Release',
                 '-DCMAKE_C_COMPILER=/usr/bin/clang', '-DCMAKE_CXX_COMPILER=/usr/bin/clang++',
                 '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
                 '-DCMAKE_INSTALL_PREFIX=' + str(prefix), *extra])
        try:
            if not (src / '.git').is_dir(): raise RuntimeError('Fetch pinned source first')
            actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=src, text=True).strip()
            if actual != LOCK[name]['commit']: raise RuntimeError('Source commit differs from lock')
            if name in ['coolprop', 'cantera']:
                raise RuntimeError('Validated path uses hash-pinned native wheel; source rebuild is not configured')
            if name == 'eigen':
                cmake(['-DBUILD_TESTING=OFF'])
            elif name == 'jsbsim':
                cmake(['-DBUILD_TESTING=OFF', '-DINSTALL_PYTHON_MODULE=OFF'])
            elif name == 'chrono':
                eigen = ROOT / 'external/eigen'
                if not (eigen / 'Eigen/Core').exists(): raise RuntimeError('Fetch eigen 3.4.0 first; Homebrew Eigen 5 is incompatible with Chrono 9 finder')
                cmake(['-DBUILD_DEMOS=OFF', '-DBUILD_TESTING=OFF', '-DBUILD_BENCHMARKING=OFF',
                       '-DENABLE_OPENMP=OFF', '-DEIGEN3_INCLUDE_DIR=' + str(eigen),
                       '-DCMAKE_INSTALL_NAME_DIR=' + str(prefix / 'lib')])
            elif name == 'sofa':
                cmake(['-DSOFA_BUILD_TESTS=OFF', '-DSOFA_BUILD_TUTORIALS=OFF',
                       '-DSOFA_ALLOW_FETCH_DEPENDENCIES=OFF', '-DSOFA_WITH_OPENGL=OFF',
                       '-DPLUGIN_SOFA_GUI_QT=OFF', '-DPLUGIN_SOFAMATRIX=OFF',
                       '-DCMAKE_PREFIX_PATH=' + str(ROOT / 'install/eigen')])
            elif name == 'precice':
                if 'patches' in LOCK[name]:
                    for patch_lock in LOCK[name]['patches']:
                        patch = ROOT / patch_lock['file']
                        if hashlib.sha256(patch.read_bytes()).hexdigest() != patch_lock['sha256']:
                            raise RuntimeError(f'{name} patch differs from dependency lock: {patch}')
                        check = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)],
                                               cwd=src, stdout=stream, stderr=stream)
                        if check.returncode:
                            run(['git', 'apply', '--check', patch], cwd=src)
                            run(['git', 'apply', patch], cwd=src)
                    state['patches'] = [p['file'] for p in LOCK[name]['patches']]
                cmake(['-DPRECICE_FEATURE_MPI_COMMUNICATION=OFF', '-DPRECICE_FEATURE_PETSC_MAPPING=OFF',
                       '-DPRECICE_FEATURE_PYTHON_ACTIONS=OFF', '-DBUILD_TESTING=OFF',
                       '-DCMAKE_INSTALL_RPATH=' + str(prefix / 'lib'),
                       '-DCMAKE_INSTALL_NAME_DIR=' + str(prefix / 'lib'),
                       '-DCMAKE_PREFIX_PATH=' + str(ROOT / 'install/eigen')])
            elif name == 'openvsp':
                libs = ROOT / 'build/vspaero-libraries'
                cmake(['-DCMAKE_POLICY_VERSION_MINIMUM=3.5'], source=src / 'src/vsp_aero/StandAlone/Libraries', binary=libs)
                if configure_only:
                    state['configured'] = True
                    state['scope'] = 'VSPAERO StandAlone libraries configured'
                    return state
                run(['cmake', '--build', libs, '--parallel', jobs])
                cmake(['-DVSPAERO_LIBRARY_PATH=' + str(libs), '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
                       '-DCMAKE_INSTALL_PREFIX=' + str(prefix)],
                      source=src / 'src/vsp_aero/StandAlone', binary=out)
                state['configured'] = True
                run(['cmake', '--build', out, '--parallel', jobs])
                run(['cmake', '--install', out, '--prefix', str(prefix)])
                bin_dir = prefix / 'bin'
                bin_dir.mkdir(parents=True, exist_ok=True)
                for exe in ['vspaero', 'vspaero_complex', 'vspaero_adjoint', 'vspaero_opt', 'vsploads']:
                    if (prefix / exe).is_file():
                        shutil.copy2(prefix / exe, bin_dir / exe)
                state['built_from_source'] = True
                return state
            elif name == 'fers':
                vcpkg_candidates = [
                    ROOT / 'build/vcpkg',
                    Path(os.environ.get('VCPKG_ROOT', '')) if os.environ.get('VCPKG_ROOT') else None,
                    Path.home() / 'vcpkg'
                ]
                vcpkg_toolchain = None
                for cand in vcpkg_candidates:
                    if cand and (cand / 'scripts/buildsystems/vcpkg.cmake').is_file():
                        vcpkg_toolchain = cand / 'scripts/buildsystems/vcpkg.cmake'
                        break
                if not vcpkg_toolchain:
                    raise RuntimeError('vcpkg toolchain not found; clone and bootstrap vcpkg at build/vcpkg')
                cmake(['-DFERS_BUILD_TESTS=OFF',
                       '-DCMAKE_TOOLCHAIN_FILE=' + str(vcpkg_toolchain),
                       '-DVCPKG_TARGET_TRIPLET=arm64-osx'])
            elif name == 'su2':
                if not (src / 'externals/meson/mesonbuild').is_dir():
                    raise RuntimeError('Missing pinned gitlinks: run scripts/deps.py submodules su2')
                patch_lock = LOCK[name]['patches'][0]
                patch = ROOT / patch_lock['file']
                if hashlib.sha256(patch.read_bytes()).hexdigest() != patch_lock['sha256']:
                    raise RuntimeError('SU2 integration patch differs from dependency lock')
                check = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)],
                                       cwd=src, stdout=stream, stderr=stream)
                if check.returncode:
                    run(['git', 'apply', '--check', patch], cwd=src)
                    run(['git', 'apply', patch], cwd=src)
                state['patches'] = ['patches/su2-8.1.0-include.patch']
                run([sys.executable, 'meson.py', 'setup', out, '--prefix=' + str(prefix),
                     '-Dwith-mpi=disabled', '-Dwith-omp=false', '-Denable-cgns=false',
                     '-Denable-tecio=false'], cwd=src)
                state['configured'] = True
                if not configure_only:
                    run([src / 'ninja', '-C', out, '-j', jobs])
                    run([src / 'ninja', '-C', out, 'install'])
                    state['built_from_source'] = True
                return state
            elif name == 'moose':
                if not shutil.which('mpicxx'):
                    raise RuntimeError('mpicxx missing; install MOOSE-compatible MPI/PETSc/libMesh environment; see docs/MODULES.md')
                if not (src / 'libmesh/installed/bin/libmesh-config').is_file():
                    raise RuntimeError('Pinned libMesh not built; run scripts/update_and_rebuild_libmesh.sh in external/moose after PETSc setup')
                state['configured'] = True
                if not configure_only:
                    run(['make', '-j', jobs], cwd=src / 'test')
                    state['built_from_source'] = True
                return state
            elif name == 'meep':
                if not shutil.which('autoreconf'):
                    raise RuntimeError('autoreconf missing; install Autotools, FFTW, HDF5, Guile, libctl, Harminv; see scripts/install-native.sh')
                env.update({
                    'PATH': f"/tmp/libctl-install/bin:{env.get('PATH', '')}",
                    'CPPFLAGS': "-I/tmp/libctl-install/include -I/tmp/harminv-install/include -I/opt/homebrew/include",
                    'LDFLAGS': "-L/tmp/libctl-install/lib -L/tmp/harminv-install/lib -L/opt/homebrew/lib",
                    'PKG_CONFIG_PATH': f"/tmp/harminv-install/lib/pkgconfig:/opt/homebrew/lib/pkgconfig:{env.get('PKG_CONFIG_PATH', '')}"
                })
                cfg_cmd = ['./configure', '--enable-maintainer-mode', f'--prefix={prefix}',
                           '--without-mpi', '--without-python']
                if Path('/tmp/libctl-install/share/libctl').exists():
                    cfg_cmd.append('--with-libctl=/tmp/libctl-install/share/libctl')
                elif (ROOT / 'install/meep/share/libctl').exists():
                    cfg_cmd.append(f"--with-libctl={ROOT / 'install/meep/share/libctl'}")
                if not (src / 'configure').is_file():
                    run(['sh', 'autogen.sh'], cwd=src)
                run(cfg_cmd, cwd=src)
                state['configured'] = True
                if not configure_only:
                    run(['make', '-j', jobs], cwd=src)
                    run(['make', 'install'], cwd=src)
                    state['built_from_source'] = True
                return state
            elif name == 'radarsim':
                raise RuntimeError('Pinned v14.0.0 requires non-public git@github.com:rookiepeng/radarsimcpp.git; wrapper alone cannot simulate. Supply an authorized compatible backend distribution.')
            else: raise RuntimeError('No native recipe')
            state['configured'] = True
            if not configure_only:
                run(['cmake', '--build', out, '--parallel', jobs])
                run(['cmake', '--install', out])
                state['built_from_source'] = True
                if name == 'chrono':
                    bridge = ROOT / 'build/bridge'
                    cmake(['-DChrono_DIR=' + str(prefix / 'lib/cmake/Chrono')], source=ROOT / 'native', binary=bridge)
                    run(['cmake', '--build', bridge, '--parallel', jobs])
                    run(['ctest', '--test-dir', bridge, '--output-on-failure'])
                    state['bridge_test_passed'] = True
                if name == 'precice':
                    dummy_dir = ROOT / 'build/precice-solverdummy'
                    cmake(['-Dprecice_DIR=' + str(prefix / 'lib/cmake/precice')],
                          source=src / 'examples/solverdummies/cpp', binary=dummy_dir)
                    run(['cmake', '--build', dummy_dir, '--parallel', jobs])
                    state['solverdummy_built'] = True
        except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
            state['error'] = str(exc)
            stream.write('\nBLOCKED: ' + str(exc) + '\n')
    return state

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('modules', nargs='+', choices=[*LOCK, 'all'])
    p.add_argument('--configure-only', action='store_true')
    p.add_argument('--jobs', type=int, default=4)
    args = p.parse_args()
    if args.jobs < 1: p.error('--jobs must be positive')
    names = list(LOCK) if 'all' in args.modules else args.modules
    report = ROOT / 'artifacts/build.json'
    failed = False
    for name in names:
        state = build(name, args.configure_only, args.jobs)
        # Re-read between jobs so concurrently built independent modules are preserved.
        states = json.loads(report.read_text()) if report.exists() else {}
        states[name] = state
        failed |= 'error' in state
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(states, indent=2) + '\n')
        print(name, json.dumps(state), flush=True)
    sys.exit(1 if failed else 0)

if __name__ == '__main__': main()
