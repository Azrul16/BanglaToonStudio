"""Deterministic travel/stride clock shared with Godot and sound planning."""
import math
PROFILES={
 'nabil':{'stride':64.,'arm_swing':.27,'bounce':3.0,'tempo':1.06,'reaction':1.06},
 'rayan':{'stride':60.,'arm_swing':.22,'bounce':2.2,'tempo':.94,'reaction':.94},
 'fahim':{'stride':66.,'arm_swing':.29,'bounce':3.2,'tempo':1.05,'reaction':1.05},
 'anika':{'stride':63.,'arm_swing':.25,'bounce':2.7,'tempo':1.0,'reaction':1.02},
 'maliha':{'stride':58.,'arm_swing':.20,'bounce':2.0,'tempo':.92,'reaction':.92}}
DEFAULT={'stride':65.,'arm_swing':.25,'bounce':2.5,'tempo':1.,'reaction':1.}
MOVING={'walk','run','step_back','move_closer','move_away'}


def smooth(value):
    x=max(0.,min(1.,value));return x*x*(3.-2.*x)


def inverse_smooth(value):
    target=max(0.,min(1.,value));low=0.;high=1.
    for _ in range(24):
        middle=(low+high)/2
        if smooth(middle)<target:low=middle
        else:high=middle
    return (low+high)/2


def contacts(cue,scale=.8):
    if cue['action'] not in MOVING:return []
    span=cue['end']-cue['start'];distance=abs(cue.get('to_x',0)-cue.get('from_x',0))
    stride=cue.get('motion',DEFAULT)['stride']*(1.4 if cue['action']=='run' else 1.)*scale
    if distance>.1:
        count=distance/stride
        return [{'time':cue['start']+inverse_smooth(n*.5/count)*span,'foot':'left' if n%2==0 else 'right','cycle':n*.5}
                for n in range(1,math.ceil(count*2)) if .12<inverse_smooth(n*.5/count)*span<span-.16]
    frequency=max(.15,abs(cue.get('speed',65))/max(1,stride))*cue.get('motion',DEFAULT)['tempo']
    return [{'time':cue['start']+n*.5/frequency,'foot':'left' if n%2==0 else 'right','cycle':n*.5}
            for n in range(1,math.ceil(span*frequency*2)) if n*.5/frequency<span-.16]
