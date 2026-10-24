import json
import math
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from physim.contract import ROOT, packet, validate, ned_to_unity, ned_axial_to_unity
from physim.host import Host

class ContractTests(unittest.TestCase):
    def test_reject_bad_units_negative_kelvin_and_nan(self):
        good = packet('test', 0, 0, atmosphere={'temperature_K': 300, 'pressure_Pa': 101325})
        validate(good)
        for key, val in [('units', 'imperial'), ('frame', 'Unity')]:
            bad = dict(good, **{key: val})
            with self.assertRaises(Exception): validate(bad)
        for val in [-1, float('nan'), float('inf')]:
            bad = deepcopy(good); bad['atmosphere']['temperature_K'] = val
            with self.assertRaises(Exception): validate(bad)

    def test_handedness_for_force_and_torque(self):
        def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        arm, force = [2,3,4], [5,7,11]
        self.assertEqual(ned_to_unity([1,2,3]), [2,-3,1])
        self.assertEqual(cross(ned_to_unity(arm),ned_to_unity(force)),ned_axial_to_unity(cross(arm,force)))

    def test_geometry_and_inertia(self):
        state=packet('test',0,0,geometry={'revision':1,'frame':'BODY_FRD',
            'vertex_ids':[1,2],'displacements_m':[[0,0,0],[0,0,1]]})
        validate(state)
        state['geometry']['vertex_ids']=[1,1]
        with self.assertRaises(ValueError): validate(state)
        bad=packet('test',0,0,mass_properties={'mass_kg':1,'inertia_body_kg_m2':[[1,2,0],[0,1,0],[0,0,1]]})
        with self.assertRaises(ValueError): validate(bad)

    def test_disabled_and_bad_dependency(self):
        with self.assertRaises(RuntimeError): Host().run('radarsim')
        with self.assertRaises(ValueError): Host().pipeline([{'id':'a','module':'coolprop','input_from':'future'}])

    def test_timeout_stops_worker(self):
        h = Host()
        with self.assertRaises(subprocess.TimeoutExpired): h.run('jsbsim', timeout=0.001)
        self.assertIsNotNone(h.process.poll())

class SolverTests(unittest.TestCase):
    def test_real_atmosphere_exchange_and_perturbation(self):
        from CoolProp.CoolProp import PropsSI
        h = Host()
        density = []
        for altitude in [0, 3000]:
            result = h.pipeline([
                {'id':'flight','module':'jsbsim','config':{'altitude_m':altitude,'steps':5}},
                {'id':'air','module':'coolprop','input_from':'flight'}])
            self.assertEqual(len(result['flight']),5)
            for src, dst in zip(result['flight'],result['air']):
                self.assertEqual(src['time_s'],dst['time_s'])
                self.assertEqual(dst['provenance']['source_module'],'jsbsim')
                a=src['atmosphere']; b=dst['atmosphere']
                self.assertEqual(a['temperature_K'],b['temperature_K'])
                self.assertEqual(a['pressure_Pa'],b['pressure_Pa'])
                self.assertAlmostEqual(b['density_kg_m3'],PropsSI('D','T',a['temperature_K'],'P',a['pressure_Pa'],'Air'),places=10)
                self.assertGreater(src['mass_properties']['mass_kg'],500)
            self.assertAlmostEqual(result['flight'][-1]['time_s'],0.05)
            density.append(result['air'][0]['atmosphere']['density_kg_m3'])
        self.assertGreater(density[0],density[1]*1.2)

    def test_cantera_energy_conservation(self):
        r=Host().run('cantera')[0]
        self.assertTrue(2100 < r['temperature_K'] < 2300)
        chem=r['chemistry']
        self.assertAlmostEqual(chem['initial_enthalpy_J_kg'],chem['enthalpy_J_kg'],delta=0.01)
        self.assertAlmostEqual(sum(chem['species_mole_fractions'].values()),1,places=8)

    def test_chrono_freefall(self):
        self.assertTrue((ROOT/'build/bridge/chrono_smoke').exists(), 'Build the required Chrono bridge first')
        r=Host().run('chrono')[0]
        self.assertAlmostEqual(r['position_m'][2],4.903325,delta=0.02)
        self.assertAlmostEqual(r['velocity_m_s'][2],9.80665,delta=1e-6)

    def test_su2_uniform_flow(self):
        self.assertTrue((ROOT/'install/su2/bin/SU2_CFD').exists(), 'Build the required SU2 executable first')
        r=Host().run('su2')[0]['flow_analysis']
        self.assertGreater(r['iterations_recorded'],0)
        self.assertTrue(all(v < -8 for v in r['residuals_log10'].values()))

    def test_sofa_freefall(self):
        self.assertTrue((ROOT/'install/sofa/bin/runSofa').exists(), 'Build the required SOFA executable first')
        samples = Host().run('sofa', {'steps': 10})
        self.assertEqual(len(samples), 10)
        final = samples[-1]
        self.assertAlmostEqual(final['time_s'], 0.009, places=6)
        self.assertAlmostEqual(final['velocity_m_s'][2], 0.0882599, places=5)
        self.assertAlmostEqual(final['position_m'][2], 0.000441299, places=6)

    def test_precice_coupling(self):
        self.assertTrue((ROOT/'build/precice-solverdummy/solverdummy').exists(), 'Build the required preCICE solverdummy first')
        r = Host().run('precice')[0]
        self.assertEqual(r['module'], 'precice')
        self.assertEqual(r['coupling_analysis']['status'], 'completed')
        self.assertEqual(r['coupling_analysis']['time_windows'], 2)
        self.assertEqual(r['coupling_analysis']['participants'], ['SolverOne', 'SolverTwo'])

    def test_openvsp_vspaero(self):
        self.assertTrue((ROOT/'install/openvsp/bin/vspaero').exists(), 'Build the required OpenVSP/VSPAERO executable first')
        r = Host().run('openvsp', {'case': 'hershey'})[0]
        self.assertEqual(r['module'], 'openvsp')
        aero = r['aero_analysis']
        self.assertEqual(aero['case'], 'hershey')
        self.assertAlmostEqual(aero['mach'], 0.11, places=3)
        self.assertAlmostEqual(aero['alpha_deg'], 5.0, places=3)
        self.assertGreater(aero['lift_coefficient'], 0.4)
        self.assertLess(aero['lift_coefficient'], 0.5)
        self.assertGreater(aero['drag_coefficient'], 0.01)
        self.assertLess(aero['drag_coefficient'], 0.03)
        self.assertGreater(aero['lift_over_drag'], 20.0)

    def test_fers_simulation(self):
        self.assertTrue((ROOT/'install/fers/lib/libfers.dylib').exists(), 'Build the required FERS library first')
        r = Host().run('fers')[0]
        self.assertEqual(r['module'], 'fers')
        radar = r['radar_analysis']
        self.assertEqual(radar['scenario_name'], 'FmcwMonostaticPhysicalDechirpScenario')
        self.assertAlmostEqual(radar['start_time_s'], 0.0)
        self.assertAlmostEqual(radar['end_time_s'], 0.064, places=4)
        self.assertAlmostEqual(radar['sampling_rate_hz'], 2.0e6)
        self.assertEqual(radar['chirp_count'], 64)
        self.assertAlmostEqual(radar['carrier_frequency_hz'], 10.0e9)
        self.assertGreater(radar['total_samples'], 100000)

    def test_meep_pulse(self):
        self.assertTrue((ROOT/'install/meep/bin/meep').exists(), 'Build the required Meep binary first')
        r = Host().run('meep')[0]
        self.assertEqual(r['module'], 'meep')
        em = r['em_analysis']
        self.assertEqual(em['solver'], 'meep-1.30.0')
        self.assertEqual(em['dimension'], 3)
        self.assertEqual(em['timesteps'], 800)
        self.assertIn('ex', em['components'])
        stats = em['field_statistics']
        self.assertGreater(stats['max_abs_field'], 0.001)
        self.assertLess(stats['max_abs_field'], 0.1)
        self.assertAlmostEqual(stats['max_field'], 0.004268, places=4)
        self.assertAlmostEqual(stats['min_field'], -0.006421, places=4)

if __name__ == '__main__': unittest.main()
