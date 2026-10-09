from dataclasses import dataclass, asdict
import math

@dataclass
class Settings:
    mode: str = 'simulation'
    run_name: str = 'Electrode screening'
    first_electrode: int = 1
    robot_host: str = 'localhost'
    robot_ws_port: int = 9090
    robot_velocity: float = 20.0
    robot_acceleration: float = 20.0
    robot_timeout: float = 5.0
    motion_timeout: float = 30.0
    home_timeout: float = 60.0
    position_tolerance: float = 1.0
    rotation_tolerance: float = 1.0
    tool_r: float = 0.0
    grip_dwell: float = 0.7
    workspace_x_min: float = -300.0
    workspace_x_max: float = 300.0
    workspace_y_min: float = -300.0
    workspace_y_max: float = 300.0
    workspace_z_min: float = -50.0
    workspace_z_max: float = 150.0
    workspace_radius_min: float = 120.0
    workspace_radius_max: float = 300.0
    calibrated: bool = False
    fixture_verified: bool = False
    potentiostat_id: str = ''
    sdk_timeout: float = 20.0
    power_frequency: int = 50
    electrodes: int = 3
    rack_columns: int = 5
    rack_pitch: float = 22.0
    rod_diameter: float = 6.0
    rod_length: float = 100.0
    shoulder_diameter: float = 12.0
    tip_below_shoulder: float = 50.0
    immersion: float = 15.0
    beaker_diameter: float = 50.0
    beaker_height: float = 70.0
    rim_diameter: float = 53.0
    cap_clearance: float = 0.8
    cap_wall: float = 3.0
    cap_thickness: float = 4.0
    skirt_depth: float = 6.0
    we_clearance: float = 0.6
    funnel_diameter: float = 10.0
    re_hole: float = 8.0
    ce_hole: float = 6.0
    port_offset: float = 14.0
    rinse_dips: int = 3
    rinse_dwell: float = 1.0
    settle: float = 2.0
    safe_z: float = 80.0
    rack_x: float = 190.0
    rack_y: float = -65.0
    rack_z: float = 15.0
    cell_x: float = 220.0
    cell_y: float = 15.0
    cell_z: float = 15.0
    rinse_x: float = 190.0
    rinse_y: float = 70.0
    rinse_z: float = 15.0
    start_v: float = 0.0
    vertex1_v: float = 0.5
    vertex2_v: float = -0.5
    end_v: float = 0.0
    scan_rate: float = 0.1
    step_v: float = 0.005
    cycles: int = 2
    current_range_ua: float = 100.0
    simulation_speed: float = 10.0
    camera_index: int = -1
    robot_port: str = 'auto'
    reference_label: str = 'Ag/AgCl (confirm electrolyte)'

    def validate(self):
        if self.mode not in ('simulation','hardware'):
            raise ValueError('Mode must be simulation or hardware')
        if not 1 <= self.first_electrode <= 100 or self.first_electrode+self.electrodes-1 > 100:
            raise ValueError('Rack slot range must be within 1–100')
        if not 1 <= self.robot_ws_port <= 65535 or self.power_frequency not in (50,60):
            raise ValueError('Invalid DobotLink port or mains frequency')
        for key in ('robot_velocity','robot_acceleration'):
            if not 0 < getattr(self,key) <= 100:
                raise ValueError(f'{key} must be between 0 and 100')
        for key in ('robot_timeout','motion_timeout','home_timeout','position_tolerance',
                    'rotation_tolerance','grip_dwell','sdk_timeout'):
            if getattr(self,key) <= 0:
                raise ValueError(f'{key} must be positive')
        for axis in 'xyz':
            if getattr(self,f'workspace_{axis}_min') >= getattr(self,f'workspace_{axis}_max'):
                raise ValueError(f'Invalid workspace {axis.upper()} bounds')
        if not 0 <= self.workspace_radius_min < self.workspace_radius_max or not -90 <= self.tool_r <= 90:
            raise ValueError('Invalid radial bounds or tool rotation')
        if self.mode=='hardware' and not math.isclose(self.end_v,self.start_v,abs_tol=1e-9):
            raise ValueError('PalmSens CV ends at its start potential; end must equal start')
        for key, value in asdict(self).items():
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError(f'{key} must be finite')
        for key in ('electrodes','rack_columns','rinse_dips','cycles'):
            if getattr(self,key) < 1 or getattr(self,key) > 100:
                raise ValueError(f'{key} must be between 1 and 100')
        for key in ('rod_diameter','rod_length','shoulder_diameter','tip_below_shoulder',
                    'immersion','beaker_diameter','beaker_height','rim_diameter','cap_clearance',
                    'cap_wall','cap_thickness','skirt_depth','we_clearance','funnel_diameter',
                    're_hole','ce_hole','port_offset','rack_pitch','scan_rate','step_v',
                    'current_range_ua','simulation_speed'):
            if getattr(self,key) <= 0:
                raise ValueError(f'{key} must be positive')
        if self.rinse_dwell < 0 or self.settle < 0:
            raise ValueError('Dwell times cannot be negative')
        if any(abs(getattr(self,k)) > 3 for k in ('start_v','vertex1_v','vertex2_v','end_v')):
            raise ValueError('EmStat4S LR potentials must lie within ±3 V')
        if not self.vertex2_v < self.vertex1_v:
            raise ValueError('Upper vertex must be above lower vertex')
        if not all(self.vertex2_v <= getattr(self,k) <= self.vertex1_v for k in ('start_v','end_v')):
            raise ValueError('Start/end potentials must lie between the vertices')
        if self.step_v > self.vertex1_v-self.vertex2_v:
            raise ValueError('Potential step exceeds scan window')
        if self.current_range_ua not in (0.001,0.01,0.1,1,10,100,1000,10000):
            raise ValueError('Select one of the EmStat4S LR current ranges')
        if self.safe_z <= max(self.rack_z,self.cell_z,self.rinse_z):
            raise ValueError('Travel Z must be above all approach positions')
        if self.rack_pitch <= self.shoulder_diameter + 4:
            raise ValueError('Rack pitch needs at least 4 mm beyond shoulder diameter')
        if self.tip_below_shoulder >= self.rod_length:
            raise ValueError('Carrier needs a gripping section above its shoulder')
        if self.tip_below_shoulder-self.cap_thickness >= self.beaker_height-5:
            raise ValueError('Electrode tip would approach the beaker bottom')
        if self.immersion >= self.tip_below_shoulder-self.cap_thickness:
            raise ValueError('Immersion exceeds available length below cap')
        if self.rim_diameter < self.beaker_diameter:
            raise ValueError('Rim diameter cannot be smaller than beaker body')
        bore = self.rod_diameter+self.we_clearance
        if not bore < self.funnel_diameter < self.shoulder_diameter:
            raise ValueError('Require WE bore < funnel mouth < carrier shoulder')
        if self.cap_thickness < 3:
            raise ValueError('Cap must be at least 3 mm thick for the 2 mm lead-in')
        for hole in (self.re_hole,self.ce_hole):
            if self.port_offset-hole/2-self.funnel_diameter/2 < 2:
                raise ValueError('Electrode ports need at least 2 mm separation')
            if self.port_offset+hole/2 > self.beaker_diameter/2-3:
                raise ValueError('RE/CE opening is too close to the beaker wall')
        if self.camera_index < -1 or self.camera_index > 20:
            raise ValueError('Camera index must be -1 (auto) or 0–20')
        if len(self.potential_points()) > 200000:
            raise ValueError('Protocol exceeds 200,000 points')
        return self

    def rack_pose(self,index):
        return (self.rack_x+((index-1)%self.rack_columns)*self.rack_pitch,
                self.rack_y+((index-1)//self.rack_columns)*self.rack_pitch,self.rack_z)

    def validate_pose(self,pose):
        if len(pose) not in (3,4) or not all(math.isfinite(v) for v in pose):
            raise ValueError('Pose must have finite XYZ and optional R values')
        for axis,value in zip('xyz',pose):
            if not getattr(self,f'workspace_{axis}_min') <= value <= getattr(self,f'workspace_{axis}_max'):
                raise ValueError(f'{axis.upper()} target {value:g} lies outside configured workspace')
        radius=math.hypot(pose[0],pose[1])
        if not self.workspace_radius_min <= radius <= self.workspace_radius_max:
            raise ValueError(f'Target radius {radius:.1f} mm lies outside configured workspace')
        if len(pose)==4 and not -90 <= pose[3] <= 90:
            raise ValueError('Tool rotation must be within ±90 degrees')
        return pose

    def validate_batch(self):
        self.validate()
        if self.mode=='hardware':
            if not self.calibrated or not self.fixture_verified:
                raise ValueError('Mark calibration and gripper/contact fixture as verified in Settings before a hardware batch')
            poses=[self.rack_pose(i) for i in range(self.first_electrode,self.first_electrode+self.electrodes)]
            poses.extend(((self.cell_x,self.cell_y,self.cell_z),(self.rinse_x,self.rinse_y,self.rinse_z)))
            for pose in poses:
                self.validate_pose(pose); self.validate_pose((pose[0],pose[1],self.safe_z,self.tool_r))
        return self

    def potential_points(self):
        points = [(0.0,self.start_v,1)]
        t=0.0; previous=self.start_v
        targets=[]
        for _ in range(self.cycles):
            targets.extend((self.vertex1_v,self.vertex2_v))
        targets.append(self.end_v)
        for target in targets:
            distance=abs(target-previous)
            n=max(1,math.ceil(distance/self.step_v))
            if n+len(points)>200000:
                raise ValueError('Protocol exceeds 200,000 points')
            direction=1 if target>=previous else -1
            if distance:
                for i in range(1,n+1):
                    points.append((t+distance*i/n/self.scan_rate,
                                   previous+(target-previous)*i/n,direction))
            t+=distance/self.scan_rate; previous=target
        return points
