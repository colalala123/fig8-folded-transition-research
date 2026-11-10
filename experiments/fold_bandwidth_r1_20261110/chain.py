"""R1 chain: equivalent centreline/parameter-sum forms, explicit straight prior.

No refit, no learned g effect, no solver permission. R0 remains byte-identical.
"""
import numpy as np
from scipy.optimize import brentq
from common import OLD, load

base = load('phase0_chain_readonly', OLD / 'chain.py')
C, ER, F0 = base.C, base.ER, base.F0
circuit, nominal, ratios = base.circuit, base.nominal, base.ratios
wave_length, ripple_db, closed_band = base.wave_length, base.ripple_db, base.closed_band
COEFFICIENTS = {**base.COEFFICIENTS,
                'deltaLs_centerline': [1.9644, -.4017, -1.2118, -.5389]}


def corrections(wm, ws, a, form='centerline'):
    if form not in ('centerline', 'parameter_sum'):
        raise ValueError('Unknown length convention')
    dm, ds = base.corrections(wm, ws, a)
    return dm, ds + (4 * ws if form == 'centerline' else 0)


def dimensions(g, topology='folded'):
    v = {k: float(g[k]) for k in ('Wm', 'Ws', 'Lm', 'Ls1', 'Ls2', 'Ls3')}
    if not all(np.isfinite(x) for x in v.values()):
        raise ValueError('Nonfinite geometry')
    if min(v[k] for k in ('Wm', 'Ws', 'Lm', 'Ls1')) <= 0:
        raise ValueError('Nonpositive main dimensions')
    if topology == 'straight_control':
        if v['Ls2'] != 0 or v['Ls3'] != 0:
            raise ValueError('Straight topology has zero Ls2/Ls3')
        return dict(a_mm=0., g_mm=None, L_parameter_sum_mm=v['Ls1'],
                    L_centerline_mm=v['Ls1'], rho=0.)
    if topology != 'folded' or v['Ls3'] <= v['Ws'] or v['Ls2'] <= 2*v['Ws']:
        raise ValueError('Folded topology requires a>0 and g>0')
    p = v['Ls1'] + 2*v['Ls2'] + 2*v['Ls3']
    return dict(a_mm=v['Ls3']-v['Ws'], g_mm=v['Ls2']-2*v['Ws'],
                L_parameter_sum_mm=p, L_centerline_mm=p-4*v['Ws'],
                rho=2*(v['Ls2']+v['Ls3'])/p)


def geometry_screen(g, topology='folded', board_half_x=15.):
    d = dimensions(g, topology)
    if not np.isfinite(board_half_x) or board_half_x <= 0:
        raise ValueError('Invalid board half width')
    width = max(g['Wm'], 1.82)
    tips = g['Ls1']-2*g['Ls3'] if topology == 'folded' else None
    clearance = (tips-width)/2 if tips is not None else None
    edge = board_half_x-g['Ls1']/2
    reasons = []
    if clearance is not None and clearance < .813:
        reasons.append('tip_line_clearance_below_0.813mm')
    if tips is not None and tips < width+2*.813:
        reasons.append('tip_tip_clearance_below_line_width_plus_1.626mm')
    if edge < 5.:
        reasons.append('slot_board_margin_below_5mm')
    return dict(**d, central_line_width_mm=width, tip_to_line_x_mm=clearance,
                tip_to_tip_x_mm=tips, min_tip_to_tip_x_mm=width+1.626 if tips is not None else None,
                slot_to_board_edge_x_mm=edge, board_half_x_mm=board_half_x,
                screen_pass=not reasons, reasons=reasons, rho_is_gate=False,
                long_arm_direct_coupling_flag=d['a_mm'] >= 2.6-1e-12,
                full_CAD_verified=False)


def forward(g, topology='folded', length_form='centerline'):
    d = dimensions(g, topology)
    wm, ws, a = g['Wm'], g['Ws'], d['a_mm']
    dm, ds = corrections(wm, ws, a, length_form)
    if topology == 'straight_control':
        # A straight main slot has no 4Ws corner convention. Both forms MUST
        # use the extrapolated centreline correction, not folded sum+zero arms.
        ds = corrections(wm, ws, a, 'centerline')[1]
        length = g['Ls1']
    else:
        length = d['L_centerline_mm' if length_form == 'centerline' else 'L_parameter_sum_mm']
    fm = brentq(lambda f: wave_length(wm, f)-g['Lm']-dm, 4, 10)
    fs = brentq(lambda f: wave_length(ws, f, False)-length-ds, 4, 10)
    n = nominal(wm, ws)
    n1, n2 = ratios(n['Zm_ohm'], n['Zs_ohm'], a)
    zm, zs = n1*n1*n['Zm_ohm']/50, n2*n2*n['Zs_ohm']/50
    return dict(**n, N1=n1, N2=n2, zm_eff=zm, zs_eff=zs, P_eff=zm*zs, R_eff=zm/zs,
                fm_GHz=fm, fs_GHz=fs, length_form=length_form,
                gap_effect='unidentified; zero extra effect prior only',
                evidence='extrapolated_straight_prior' if topology == 'straight_control' else 'rounded_law_prior',
                validated_prediction=False)


def straight(wm, ws, fm=6.622, fs=6.588):
    dm, ds = corrections(wm, ws, 0, 'centerline')
    return dict(Wm=wm, Ws=ws, Lm=round(wave_length(wm, fm)-dm, 3),
                Ls1=round(wave_length(ws, fs, False)-ds, 3), Ls2=0., Ls3=0.)


def bands(f, s11, s21, centre=F0):
    b = base.bands(f, s11, s21, centre)
    for key, q in b.items():
        seg = q['intervals_GHz']
        q['outer_envelope_GHz'] = [seg[0][0], seg[-1][1]] if seg else None
        q['outer_span_GHz'] = seg[-1][1]-seg[0][0] if seg else None
        q['center_component_BW_GHz'] = q['BW_GHz']
        q['fit_eligible'] = q['BW_GHz'] is not None and not q['edge_censored']
        if key == 'BW20':
            q['hard_constraint_valid'] = q['components'] == 1 and q['BW_GHz'] is not None
            if q['components'] > 1:
                q['BW_GHz'] = q['low_GHz'] = q['high_GHz'] = None
                q['fit_eligible'] = False
                q['exclusion_reason'] = 'R1_multiple_components'
    return b
