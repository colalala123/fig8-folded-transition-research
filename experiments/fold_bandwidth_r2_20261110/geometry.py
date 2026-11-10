"""Pure six-dimension -> slot Boolean operand boxes. No CAD launch."""
import chain
import math


def slot_boxes(g, topology='folded'):
    chain.dimensions(g, topology)
    w, l1, l2, l3 = (g[k] for k in ('Ws', 'Ls1', 'Ls2', 'Ls3'))
    xy = [('main', -l1/2, -w/2, l1, w)]
    if topology == 'folded':
        y = -l2+w/2
        xy += [('right_connector', l1/2-w, y, w, l2-w),
               ('right_leg', l1/2-l3, y, l3-w, w),
               ('left_connector', -l1/2, y, w, l2-w),
               ('left_leg', -l1/2+w, y, l3-w, w)]
    return [dict(name=f'StructureBSlot_{side}_{name}',
                 parameters_mm=dict(XPosition=x, YPosition=y, ZPosition=z,
                                    XSize=dx, YSize=dy, ZSize=.055))
            for side, z in [('top', -.01), ('bottom', -.045)]
            for name, x, y, dx, dy in xy]


def compare_boxes(expected, observed):
    """Numeric operands comparison, fixed 1e-8 mm AEDT text-rounding tolerance.

    Caller must supply native operands from the intended generated design, not
    this module's own table. This is not a final-solid/topology certification.
    """
    if len({b['name'] for b in observed}) != len(observed):
        return dict(passed=False, reason='duplicate_native_operand_names')
    e, o = ({b['name']:b['parameters_mm'] for b in rows} for rows in (expected,observed))
    if e.keys()!=o.keys():
        return dict(passed=False, reason='missing_or_extra_operands')
    errors=[]
    for name in e:
        if e[name].keys()!=o[name].keys():
            return dict(passed=False,reason='operand_fields_mismatch')
        for key in e[name]:
            v=float(o[name][key])
            if not math.isfinite(v) or abs(e[name][key]-v)>1e-8:
                errors.append(dict(name=name,field=key,expected=e[name][key],actual=v))
    return dict(passed=not errors,tolerance_mm=1e-8,errors=errors,
                final_solid_topology_certified=False)
