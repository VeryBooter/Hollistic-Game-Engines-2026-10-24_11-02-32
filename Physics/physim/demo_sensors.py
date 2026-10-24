"""SI-only, deterministic radar-equation and visible EO models for the demo.

Not a waveform or Maxwell solver. Constant RCS, ideal aperture, Gaussian beam,
thermal receiver noise, no clutter/weather/terrain. EO is angular geometry plus
an ideal diffraction limit, not radiometry or an infrared temperature image.
"""
import math

C = 299792458.0
K = 1.380649e-23
BANDS_HZ = (1e9, 1e10, 94e9)

def geometry(observer, target):
    delta = [b-a for a,b in zip(observer['position'], target['position'])]
    distance = math.sqrt(sum(x*x for x in delta))
    yaw,pitch,roll = observer['yaw'],observer['pitch'],observer.get('roll',0)
    forward = [math.cos(pitch)*math.sin(yaw),math.sin(pitch),math.cos(pitch)*math.cos(yaw)]
    right = [math.cos(yaw),0,-math.sin(yaw)]
    up = [-math.sin(pitch)*math.sin(yaw),math.cos(pitch),-math.sin(pitch)*math.cos(yaw)]
    r = [a*math.cos(roll)-b*math.sin(roll) for a,b in zip(right,up)]
    u = [a*math.sin(roll)+b*math.cos(roll) for a,b in zip(right,up)]
    dot = lambda v: sum(a*b for a,b in zip(delta,v))
    f,x,y = dot(forward),dot(r),dot(u)
    radial = sum((b-a)*d for a,b,d in zip(observer.get('velocity_m_s',[0,0,0]),
                 target.get('velocity_m_s',[0,0,0]),delta))/max(distance,1e-9)
    return distance, math.atan2(x,f), math.atan2(y,math.hypot(f,x)),radial

def optical(observer, target):
    distance,az,el,_ = geometry(observer,target)
    wavelength,aperture = 550e-9,.08
    angular_size = 10/max(distance,1)
    resolution = 1.22*wavelength/aperture
    seen = distance>0 and abs(az)<.18 and abs(el)<.18 and angular_size>=3*resolution
    return {'detected':seen,'range_m':distance if seen else 0,'bearing_rad':az if seen else 0,
            'wavelength_m':wavelength,'aperture_m':aperture,'angular_resolution_rad':resolution,
            'field_of_view_rad':.36}

def radar_budget(distance, frequency_Hz, az=0, el=0, pointing_error_rad=0):
    if not math.isfinite(frequency_Hz) or frequency_Hz not in BANDS_HZ:
        raise ValueError('Radar frequency must be one of the declared SI presets')
    if not math.isfinite(distance) or distance<=0: raise ValueError('Positive finite range required')
    wavelength = C/frequency_Hz
    aperture,efficiency,power,bandwidth,temperature,noise_factor,loss,rcs = .5,.6,3000.,20e6,290.,3.,4.,3.
    diameter = math.sqrt(4*aperture/math.pi)
    beamwidth = .886*wavelength/diameter
    scan_cosine = max(0,math.cos(az)*math.cos(el))
    gain = 4*math.pi*aperture*efficiency/wavelength**2*scan_cosine
    pattern = math.exp(-4*math.log(2)*(pointing_error_rad/max(beamwidth,1e-9))**2)
    received = power*gain**2*wavelength**2*rcs*pattern**2/((4*math.pi)**3*distance**4*loss)
    noise = K*temperature*bandwidth*noise_factor
    threshold=20.
    return {'frequency_Hz':frequency_Hz,'wavelength_m':wavelength,'beamwidth_rad':beamwidth,
            'transmit_power_W':power,'received_power_W':received,'noise_power_W':noise,
            'snr_linear':received/noise,'snr_threshold':threshold,'gain_linear':gain,
            'aperture_m2':aperture,'rcs_m2':rcs,'bandwidth_Hz':bandwidth,
            'range_resolution_m':C/(2*bandwidth),'noise_temperature_K':temperature,
            'noise_factor':noise_factor,'loss_factor':loss,
            'ideal_range_m':distance*(received/noise/threshold)**.25}

class SensorSuite:
    def __init__(self): self.last_hit=None;self.frequency=None
    def observe(self,observer,target,time_s,frequency_Hz=1e10):
        if frequency_Hz!=self.frequency: self.last_hit=None;self.frequency=frequency_Hz
        distance,az,el,radial=geometry(observer,target)
        eo=optical(observer,target)
        base=radar_budget(max(distance,1),frequency_Hz)
        width=base['beamwidth_rad'];sector=math.pi/3;elevation=.26;dwell=.01
        nx=max(1,math.ceil(2*sector/(.7*width)));ny=max(1,math.ceil(2*elevation/(.7*width)))
        index=int(time_s/dwell)%(nx*ny)
        beam_az=-sector+(index%nx+.5)*2*sector/nx
        beam_el=-elevation+(index//nx+.5)*2*elevation/ny
        # A valid visible-light observation may cue the electronically steered beam.
        # Search never uses hidden target coordinates to choose its pointing direction.
        cue=eo['detected'] and abs(az)<=sector and abs(el)<=elevation
        if cue: beam_az,beam_el=az,el
        error=math.hypot((az-beam_az)*math.cos(el),el-beam_el)
        budget=radar_budget(max(distance,1),frequency_Hz,beam_az,beam_el,error)
        hit=distance>1 and abs(az)<=sector and abs(el)<=elevation and budget['snr_linear']>=budget['snr_threshold']
        if hit:self.last_hit=(time_s,distance,az,el,radial,list(target['position']))
        age=time_s-self.last_hit[0] if self.last_hit else 1e6
        tracked=age<=2
        measured=self.last_hit if tracked else (0,0,0,0,0,[0,0,0])
        radar=dict(budget,detected=tracked,illuminated=hit,range_m=measured[1],bearing_rad=measured[2],
                   elevation_rad=measured[3],radial_velocity_m_s=measured[4],track_age_s=age,
                   track_position_m=measured[5],doppler_Hz=-2*measured[4]/budget['wavelength_m'],beam_azimuth_rad=beam_az,
                   beam_elevation_rad=beam_el,sector_half_angle_rad=sector,
                   scan_revisit_s=nx*ny*dwell,mode='EO CUE' if cue else 'RASTER SEARCH')
        return radar,eo
