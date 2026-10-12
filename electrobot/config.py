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
    rack_layout: str = 'rectangular'
    rack_radius: float = 200.0
    rack_start_angle: float = -25.0
    rack_angle_step: float = 7.0
    rack_socket_clearance: float = 0.4
    rack_socket_depth: float = 60.0
    rack_post_height: float = 65.0
    rack_socket_wall: float = 3.0
    rack_base_thickness: float = 4.0
    rack_margin: float = 6.0
    rack_design: str = 'socket'
    holder_diameter: float = 18.0
    holder_height: float = 14.0
    holder_flange_diameter: float = 24.0
    holder_flange_thickness: float = 3.0
    holder_rod_depth: float = 13.0
    holder_rod_clearance: float = 0.3
    holder_pad_diameter: float = 8.0
    holder_pad_depth: float = 1.0
    holder_wire_diameter: float = 2.0
    holder_set_screw_diameter: float = 2.5
    rack_holder_clearance: float = 0.4
    rack_seat_depth: float = 1.5
    rack_deck_thickness: float = 6.0
    rack_seat_wall: float = 3.0
    rack_rib_width: float = 6.0
    rack_hanging_length: float = 87.0
    rack_tip_clearance: float = 10.0
    rack_gripper_gap: float = 8.0
    rack_module_slots: int = 4
    rack_peg_diameter: float = 4.0
    rack_peg_clearance: float = 0.3
    rack_peg_length: float = 2.0
    rack_foot_base: float = 3.0
    rack_foot_column_diameter: float = 6.0
    rack_foot_mount_hole: float = 3.4
    rack_printer_width: float = 220.0
    rack_printer_depth: float = 220.0
    rinse_beaker_diameter: float = 50.0
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
        if self.rack_design not in ('socket','lattice'): raise ValueError('Unknown rack design')
        if self.rack_layout not in ('rectangular','radial'): raise ValueError('Rack layout must be rectangular or radial')
        for key in ('rack_radius','rack_angle_step','rack_socket_clearance','rack_socket_depth','rack_post_height','rack_socket_wall','rack_base_thickness','rack_margin','rinse_beaker_diameter'):
            if not math.isfinite(getattr(self,key)) or getattr(self,key)<=0: raise ValueError(f'{key} must be finite and positive')
        if self.rack_design=='socket':
            if self.rack_socket_depth>=self.rack_post_height: raise ValueError('Socket depth must be below post height to leave a floor')
            if self.rack_socket_depth<=self.tip_below_shoulder: raise ValueError('Rack socket must be deeper than the tip below shoulder to keep the active tip off the floor')
        else: self.validate_lattice()
        if self.rack_socket_wall<2 or self.rack_base_thickness<2: raise ValueError('Rack wall and base must be at least 2 mm')
        if self.rack_layout=='radial' and (self.rack_columns-1)*self.rack_angle_step>=360:
            raise ValueError('Radial row must span less than 360 degrees')
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

    def lattice_dimensions(self):
        peg_offset=self.holder_diameter/2+1.0
        bore=(self.rod_diameter+self.we_clearance)/2
        seat=(self.holder_diameter+self.rack_holder_clearance)/2
        outer=max(seat+self.rack_seat_wall,peg_offset+(self.rack_peg_diameter+self.rack_peg_clearance)/2+self.rack_seat_wall,peg_offset+self.rack_foot_column_diameter/2+.5)
        foot_radius=max(6.0,self.rack_peg_diameter/2+3,self.rack_foot_column_diameter/2+3)
        separation=max(self.holder_flange_diameter+self.rack_gripper_gap,2*outer+1,2*(peg_offset+foot_radius)+1)
        seat_height=self.rack_hanging_length+self.rack_tip_clearance
        foot_height=seat_height-self.rack_deck_thickness+self.rack_seat_depth
        return {'bore':bore,'seat':seat,'outer':outer,'peg_offset':peg_offset,'foot_radius':foot_radius,
                'separation':separation,'seat_height':seat_height,'foot_height':foot_height}

    def validate_lattice(self):
        keys=('holder_diameter','holder_height','holder_flange_diameter','holder_flange_thickness','holder_rod_depth',
              'holder_rod_clearance','holder_pad_diameter','holder_pad_depth','holder_wire_diameter','holder_set_screw_diameter',
              'rack_holder_clearance','rack_seat_depth','rack_deck_thickness','rack_seat_wall','rack_rib_width',
              'rack_hanging_length','rack_tip_clearance','rack_gripper_gap','rack_peg_diameter','rack_peg_clearance',
              'rack_peg_length','rack_foot_base','rack_foot_column_diameter','rack_foot_mount_hole','rack_printer_width','rack_printer_depth')
        if any(not math.isfinite(getattr(self,k)) or getattr(self,k)<=0 for k in keys): raise ValueError('Holder and lattice dimensions must be finite and positive')
        if not 1<=self.rack_module_slots<=12: raise ValueError('Use 1–12 slots per top module')
        d=self.lattice_dimensions()
        if self.holder_flange_diameter<self.holder_diameter+2: raise ValueError('Holder flange needs at least 2 mm beyond the grip body')
        if self.holder_diameter<=self.rod_diameter+self.holder_rod_clearance+4: raise ValueError('Holder needs at least 2 mm of wall around the rod socket')
        if self.holder_rod_depth>self.holder_height-1: raise ValueError('Holder rod socket needs at least 1 mm roof below flange')
        if self.holder_rod_depth>=self.rod_length: raise ValueError('Holder socket depth must be less than the electrode rod length')
        if self.rack_hanging_length<self.rod_length-self.holder_rod_depth:
            raise ValueError('Hanging length must cover rod length minus holder socket depth; include any additional active-tip projection')
        if self.holder_pad_diameter+2>self.holder_flange_diameter or self.holder_pad_depth>self.holder_flange_thickness-1:
            raise ValueError('Contact recess must leave a 1 mm rim and floor in the flange')
        if self.holder_wire_diameter>=min(self.holder_pad_diameter,self.rod_diameter+self.holder_rod_clearance): raise ValueError('Wire passage must be smaller than pad and rod socket')
        if self.holder_set_screw_diameter>=self.holder_rod_depth-2: raise ValueError('Set-screw pilot is too large for the rod socket depth')
        if self.rack_seat_depth>=self.holder_height-5: raise ValueError('Leave at least 5 mm of holder body exposed for gripping')
        if d['bore']+2>=d['seat']: raise ValueError('Holder seat needs at least 2 mm bearing width around the rod opening')
        if self.rack_deck_thickness-self.rack_seat_depth-self.rack_peg_length-self.rack_peg_clearance<2:
            raise ValueError('Top support needs 2 mm floor between the holder recess and foot sockets')
        if self.rack_rib_width<4 or self.rack_seat_wall<2 or self.rack_foot_base<2: raise ValueError('Use ribs ≥4 mm, seat walls ≥2 mm and foot bases ≥2 mm')
        if d['foot_height']<=self.rack_foot_base+5: raise ValueError('Hanging length and clearance leave insufficient foot height')
        if self.rack_peg_diameter>self.rack_foot_column_diameter-2: raise ValueError('Foot column needs at least a 1 mm shoulder around its peg')
        if self.rack_foot_mount_hole>4: raise ValueError('Foot mounting tab supports holes up to 4 mm diameter')
        if d['peg_offset']-self.rack_foot_column_diameter/2<=d['bore']+1: raise ValueError('Foot columns need clearance around the rod passage')
        return self

    def rack_pose(self,index):
        if self.rack_layout=='radial':
            radius=self.rack_radius+((index-1)//self.rack_columns)*self.rack_pitch
            angle=math.radians(self.rack_start_angle+((index-1)%self.rack_columns)*self.rack_angle_step)
            return (radius*math.cos(angle),radius*math.sin(angle),self.rack_z)
        return (self.rack_x+((index-1)%self.rack_columns)*self.rack_pitch,
                self.rack_y+((index-1)//self.rack_columns)*self.rack_pitch,self.rack_z)

    def rack_export_positions(self):
        # Complete rows through the last selected slot; inactive slots remain
        # available for future batches and match the diagrams.
        last=self.first_electrode+self.electrodes-1
        count=min(100,((last+self.rack_columns-1)//self.rack_columns)*self.rack_columns)
        return [self.rack_pose(i) for i in range(1,count+1)]

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

    def calibration_issues(self):
        """All independent calibration problems, including in simulation."""
        issues=[]
        def add(keys,message): issues.append((keys,message))
        for axis in 'xyz':
            a,b=f'workspace_{axis}_min',f'workspace_{axis}_max'
            if getattr(self,a)>=getattr(self,b): add((a,b),f'{axis.upper()} minimum must be below maximum.')
        if self.workspace_radius_min>=self.workspace_radius_max:
            add(('workspace_radius_min','workspace_radius_max'),'Minimum radius must be below maximum radius.')
        for key,label in (('rack_z','Rack gripping'),('cell_z','Cell seating'),('rinse_z','Rinse dipping')):
            if self.safe_z<=getattr(self,key): add(('safe_z',key),f'Travel Z must be above {label.lower()} Z.')
        if self.rack_pitch<=self.shoulder_diameter+4:
            add(('rack_pitch','shoulder_diameter'),'Slot pitch must exceed shoulder diameter + 4 mm.')
        positions=self.rack_export_positions()
        separation=self.lattice_dimensions()['separation'] if self.rack_design=='lattice' else max(self.shoulder_diameter+4,self.rod_diameter+self.rack_socket_clearance+2*self.rack_socket_wall+1)
        for i,a in enumerate(positions):
            if any(math.dist(a[:2],b[:2])<separation for b in positions[i+1:]):
                add(('rack_layout','rack_columns','rack_pitch','rack_radius','rack_angle_step','rack_socket_wall','shoulder_diameter','holder_diameter','holder_flange_diameter','rack_gripper_gap'),f'Rack slots need at least {separation:g} mm separation for carriers and the selected rack design.')
                break
        slots=range(self.first_electrode,min(101,self.first_electrode+self.electrodes))
        rack_keys=('rack_radius','rack_start_angle','rack_angle_step') if self.rack_layout=='radial' else ('rack_x','rack_y')
        stations=[(f'Rack slot {i}',self.rack_pose(i),(*rack_keys,'rack_z','rack_pitch','rack_columns','first_electrode','electrodes')) for i in slots]
        stations.extend((('Cell',(self.cell_x,self.cell_y,self.cell_z),('cell_x','cell_y','cell_z')),('Rinse',(self.rinse_x,self.rinse_y,self.rinse_z),('rinse_x','rinse_y','rinse_z'))))
        for label,pose,keys in stations:
            for axis,value in zip('xyz',pose):
                a,b=f'workspace_{axis}_min',f'workspace_{axis}_max'
                if not getattr(self,a)<=value<=getattr(self,b): add((*keys,a,b),f'{label} {axis.upper()}={value:g} mm is outside workspace limits.')
            radius=math.hypot(*pose[:2])
            if not self.workspace_radius_min<=radius<=self.workspace_radius_max:
                add((*keys,'workspace_radius_min','workspace_radius_max'),f'{label} radius {radius:.1f} mm is outside the radial band.')
        if not self.workspace_z_min<=self.safe_z<=self.workspace_z_max:
            add(('safe_z','workspace_z_min','workspace_z_max'),'Travel Z is outside workspace Z limits.')
        return issues

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
