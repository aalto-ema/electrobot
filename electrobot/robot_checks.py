"""Non-moving reachability samples and DobotLink alarm response decoding."""
import math


def segment_samples(start,target,step):
    n=max(1,math.ceil(math.dist(start[:3],target[:3])/step),math.ceil(abs(target[3]-start[3])/5))
    times={i/n for i in range(n+1)}
    # Include the exact closest approach to the base, which regular samples
    # could miss when crossing the inner radial exclusion.
    dx,dy=target[0]-start[0],target[1]-start[1]
    if dx*dx+dy*dy:
        t=-(start[0]*dx+start[1]*dy)/(dx*dx+dy*dy)
        if 0<t<1: times.add(t)
    return [tuple(a+(b-a)*t for a,b in zip(start,target)) for t in sorted(times)]


def response_params(raw):
    if isinstance(raw,dict):
        for key in ('result','params'):
            if key in raw: return response_params(raw[key])
    return raw


def alarm_codes(raw):
    data=response_params(raw)
    if isinstance(data,dict):
        if 'state' in data: data=data['state']
        elif 'alarmsState' in data: data=data['alarmsState']
        else: raise ValueError('Unrecognized alarm response (expected state byte array)')
    if not isinstance(data,(list,tuple)) or any(type(b) is not int or not 0<=b<=255 for b in data):
        raise ValueError('Invalid alarm byte array')
    return [i*8+bit for i,byte in enumerate(data) for bit in range(8) if byte&(1<<bit)]


def alarm_description(code):
    known={0:'controller reset',16:'planning singularity',17:'planning inverse-kinematics failure',18:'planning joint limit',
           32:'movement singularity',33:'movement inverse-kinematics failure',34:'movement joint limit',
           72:'coupled J2/J3 positive limit',73:'coupled J2/J3 negative limit'}
    if code in known: return known[code]
    if 64<=code<=71: return f'J{(code-64)//2+1} '+('positive' if code%2==0 else 'negative')+' limit'
    if 48<=code<=51: return f'J{code-47} overspeed'
    if 80<=code<=83: return f'J{code-79} lost-step indication'
    return 'unmapped controller alarm'
