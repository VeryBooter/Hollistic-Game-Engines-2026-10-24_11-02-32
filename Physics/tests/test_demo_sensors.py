import math
import unittest
from physim.demo_sensors import BANDS_HZ, C, SensorSuite, optical, radar_budget

def aircraft(x=0,y=1800,z=0,yaw=0):
    return dict(position=[x,y,z],yaw=yaw,pitch=0,roll=0,velocity_m_s=[0,0,0])

class SensorPhysicsTests(unittest.TestCase):
    def test_inverse_fourth_power_and_si_wavelength(self):
        for frequency in BANDS_HZ:
            a=radar_budget(1000,frequency);b=radar_budget(2000,frequency)
            self.assertAlmostEqual(a['received_power_W']/b['received_power_W'],16)
            self.assertAlmostEqual(a['wavelength_m']*frequency,C)
            self.assertGreater(a['noise_power_W'],0)
            self.assertAlmostEqual(a['range_resolution_m'],C/(2*a['bandwidth_Hz']))

    def test_aperture_frequency_and_scan_tradeoffs(self):
        a,b=radar_budget(1000,1e9),radar_budget(1000,1e10)
        self.assertAlmostEqual(b['gain_linear']/a['gain_linear'],100)
        self.assertAlmostEqual(a['beamwidth_rad']/b['beamwidth_rad'],10)
        on=radar_budget(1000,1e10)
        off=radar_budget(1000,1e10,az=math.pi/3)
        self.assertAlmostEqual(off['received_power_W']/on['received_power_W'],.25)
        displaced=radar_budget(1000,1e10,pointing_error_rad=on['beamwidth_rad']/2)
        self.assertAlmostEqual(displaced['received_power_W']/on['received_power_W'],.25)

    def test_optical_cue_and_track_timeout(self):
        source,target=aircraft(),aircraft(z=2000)
        suite=SensorSuite();r,eo=suite.observe(source,target,0)
        self.assertTrue(eo['detected']);self.assertTrue(r['detected'])
        self.assertEqual(r['mode'],'EO CUE')
        coast,_=suite.observe(source,aircraft(z=-1000),.1)
        self.assertTrue(coast['detected']);self.assertFalse(coast['illuminated'])
        self.assertEqual(coast['track_position_m'],target['position'])
        behind=aircraft(z=-2000)
        r,eo=suite.observe(source,behind,3)
        self.assertFalse(r['detected']);self.assertFalse(eo['detected'])
        self.assertEqual(r['range_m'],0)
        self.assertEqual(r['mode'],'RASTER SEARCH')

    def test_frequency_switch_does_not_reuse_old_track(self):
        suite=SensorSuite();r,_=suite.observe(aircraft(),aircraft(z=10000),0,94e9)
        self.assertTrue(r['detected'])
        r,_=suite.observe(aircraft(),aircraft(z=10000),.01,1e9)
        self.assertFalse(r['detected'])

    def test_reject_invalid_frequency_and_range(self):
        for frequency in [0,2e9,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):radar_budget(1000,frequency)
        with self.assertRaises(ValueError):radar_budget(0,1e10)

if __name__=='__main__':unittest.main()
