"""Phase-0 offline hypothesis chain. NOT a solver or a verified design generator.

Appendix-A rounded coefficients are intentionally not silently refitted. They
describe an historical parameter-sum length, NOT the CAD centreline length.
Unsupported a/g require explicit exploratory=True; gap effects are UNKNOWN.
"""
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import brentq, root

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'analysis'))
from line_models import microstrip, slotline
from lib import intervals

C, ER, F0 = 299.792458, 3.55, 6.72
COEFFICIENTS = {
    'N1': [1.0343, .0029, .0206, -.0328],
    'N2': [.2655, -.0216, .1506, -.0239],
    'deltaLm': [.1561, -.1249, .3751, .0607],
    'deltaLs_parameter_sum': [1.9644, -.4017, -5.2118, -.5389],
}


def circuit(f, zm, zs, fm, fs):
    f = np.asarray(f, float)
    if not all(np.isfinite(v) and v > 0 for v in (zm, zs, fm, fs)):
        raise ValueError('Four finite positive circuit parameters required')
    z = -1j * zm / np.tan(np.pi * f / (2 * fm))
    y = -2j / (zs * np.tan(np.pi * f / (2 * fs)))
    a, b = 1 + z*y, z*(2 + z*y)
    den = 2*a + b + y
    return (b-y)/den, 2/den


def threshold(db):
    if not np.isfinite(db) or db >= 0:
        raise ValueError('Negative finite dB threshold required')
    r = 10**(db/10)
    return np.sqrt(r/(1-r))


def ripple_db(p):
    if not np.isfinite(p) or p <= 1:
        raise ValueError('Three-valley equal-frequency ripple requires p>1')
    v = 2/p * ((p-1)/3)**1.5
    return float(10*np.log10(v*v/(1+v*v)))


def closed_band(p, zm, f0, db):
    """Exact centre band for fm=fs=f0; outer span separately labelled.

    When the inner peak fails the threshold, the SMALL positive root bounds
    the centre component. The largest root is only an outer-envelope span.
    Supports p<=1 too; that case is not a three-valley filter.
    """
    if not all(np.isfinite(v) and v > 0 for v in (p, zm, f0)):
        raise ValueError('Positive finite p, zm, f0 required')
    t = threshold(db)
    poly = lambda u: (u**3-(p-1)*u)/p
    hi = max(2., np.sqrt(max(p-1, 0))+1)
    while poly(hi) < t:
        hi *= 2
    outer = brentq(lambda u: poly(u)-t, np.sqrt(max(p-1, 0)), hi)
    split = p > 1 and 2/p*((p-1)/3)**1.5 > t*(1+1e-12)
    centre = brentq(lambda u: poly(u)+t, 0, np.sqrt((p-1)/3)) if split else outer
    width = lambda u: float(2*f0*(1-2*np.arctan2(zm, u)/np.pi))
    bw, span = width(centre), width(outer)
    return dict(low_GHz=f0-bw/2, high_GHz=f0+bw/2, BW_GHz=bw,
                outer_span_GHz=span, components=3 if split else 1,
                equal_frequency_only=True)


def bands(f, s11, s21, centre=F0):
    """Exact piecewise-linear dB intersections, not nearest-sample lookup."""
    f = np.asarray(f, float)
    if len(f) < 2 or not np.all(np.isfinite(f)) or not np.all(np.diff(f)>0):
        raise ValueError('Increasing finite frequency grid required')
    r, t = [20*np.log10(np.maximum(np.abs(s), 1e-15)) for s in (s11, s21)]
    if r.shape != f.shape or t.shape != f.shape or not np.isfinite(r).all() or not np.isfinite(t).all():
        raise ValueError('Finite matching response vectors required')
    def extract(r0, t0, reflection=-20, transmission=-2):
        seg = intervals(f, r0, t0, reflection, transmission)
        c = next((b for b in seg if b[0] <= centre <= b[1]), None)
        return dict(low_GHz=c[0] if c else None, high_GHz=c[1] if c else None,
                    BW_GHz=c[1]-c[0] if c else None, components=len(seg),
                    intervals_GHz=seg, edge_censored=bool(c and (c[0]==f[0] or c[1]==f[-1])))
    return dict(BW15=extract(r, np.zeros_like(t), -15),
                BW20=extract(r, np.zeros_like(t)),
                BW_S21=extract(np.full_like(r,-100), t), BW_joint=extract(r,t))


def derived(g):
    wm, ws, lm, l1, l2, l3 = (float(g[k]) for k in ('Wm','Ws','Lm','Ls1','Ls2','Ls3'))
    if not all(np.isfinite(v) and v>0 for v in (wm,ws,lm,l1,l2,l3)):
        raise ValueError('Positive finite six dimensions required')
    path = l1+2*l2+2*l3
    return dict(a_mm=l3-ws, g_mm=l2-2*ws, L_parameter_sum_mm=path,
                L_polyline_center_mm=path-4*ws,
                rho_parameter_sum=2*(l2+l3)/path, eta=l2/(l2+l3),
                arm_tip_to_microstrip_x_mm=(l1-2*l3-wm)/2,
                arm_tip_to_arm_tip_x_mm=l1-2*l3)


def geometry_screen(g, min_clearance=.813):
    """Conservative projected CAD screen; NOT full CAD collision validation."""
    d = derived(g)
    reasons = []
    if d['a_mm'] <= 0 or d['g_mm'] <= 0:
        reasons.append('nonpositive_arm_or_gap; straight topology must be separate')
    if d['rho_parameter_sum'] >= .5:
        reasons.append('rho_ge_0p5')
    if d['arm_tip_to_microstrip_x_mm'] < min_clearance:
        reasons.append('tip_microstrip_x_clearance_below_provisional_0p813mm')
    if d['arm_tip_to_arm_tip_x_mm'] <= 0:
        reasons.append('opposed_arms_overlap')
    return dict(**d, screen_pass=not reasons, reasons=reasons,
                full_CAD_verified=False, manufacturing_limits_confirmed=False)


def nominal(wm, ws):
    zm, zs = microstrip(ER,wm)['Z_ohm'], slotline(ER,ws)['Z_ohm']
    return dict(Zm_ohm=zm,Zs_ohm=zs,P=zm*zs/2500,R=zm/zs)


def scope(wm, ws, a, gap):
    n=nominal(wm,ws)
    reasons=[]
    if not any(abs(a-v)<1e-8 for v in (1.4,1.8)):
        reasons.append('arm_not_observed')
    if abs(gap-.55)>1e-8:
        reasons.append('gap_effect_unidentified')
    if not (47 <= n['Zm_ohm'] <= 52 and 106 <= n['Zs_ohm'] <= 114):
        reasons.append('nominal_impedance_outside_plan_calibration_box')
    return reasons


def ratios(zm, zs, a):
    x=np.array([1,a,np.log(zs),np.log(zm)])
    n1,n2=(float(x@COEFFICIENTS[k]) for k in ('N1','N2'))
    if n1<=0 or n2<=0:
        raise ValueError('Invalid extrapolated transformer ratio')
    return n1,n2


def corrections(wm, ws, a):
    x=np.array([1,wm,ws,a])
    return tuple(float(x@COEFFICIENTS[k]) for k in ('deltaLm','deltaLs_parameter_sum'))


def wave_length(w, freq, micro=True):
    model=microstrip if micro else slotline
    return C/((4 if micro else 2)*freq*np.sqrt(model(ER,w,f=freq)['eeff']))


def forward(g, exploratory=False):
    d=derived(g); wm,ws=g['Wm'],g['Ws'];a,gap=d['a_mm'],d['g_mm']
    reasons=scope(wm,ws,a,gap)
    if reasons and not exploratory:
        raise ValueError('; '.join(reasons))
    n=nominal(wm,ws); n1,n2=ratios(n['Zm_ohm'],n['Zs_ohm'],a)
    dm,ds=corrections(wm,ws,a)
    fm=brentq(lambda f: wave_length(wm,f)-g['Lm']-dm,4,10)
    fs=brentq(lambda f: wave_length(ws,f,False)-d['L_parameter_sum_mm']-ds,4,10)
    zm,zs=n1*n1*n['Zm_ohm']/50,n2*n2*n['Zs_ohm']/50
    return dict(**n,N1=n1,N2=n2,zm_eff=zm,zs_eff=zs,P_eff=zm*zs,R_eff=zm/zs,
                fm_GHz=fm,fs_GHz=fs,deltaLm_mm=dm,deltaLs_parameter_sum_mm=ds,
                supported_calibration_box=not reasons, warnings=reasons,
                gap_model='constant at g=0.55; off-gap is a null-effect hypothesis only',
                validated_prediction=False)


def lengths(wm, ws, a, gap, fm=6.622, fs=6.588):
    if not np.isfinite(a+gap) or a<=0 or gap<=0:
        raise ValueError('Fold chain requires positive a,g; a=0 needs separate topology')
    dm,ds=corrections(wm,ws,a);l2=gap+2*ws;l3=a+ws
    return dict(Wm=float(wm),Ws=float(ws),Lm=wave_length(wm,fm)-dm,
                Ls1=wave_length(ws,fs,False)-ds-2*l2-2*l3,Ls2=l2,Ls3=l3)


def inverse(bandwidth, ripple=-21, a=1.4, gap=.55, edge_level=-20,
            exploratory=False):
    """Ideal equal-frequency initial guess, then unequal-frequency lengths.

    B targets the edge_level threshold, ripple sets inner peaks. These are
    different levels. Recomputed unequal-frequency responses are NOT promised
    to have the requested bandwidth. No loss/certification guarantee.
    """
    if not np.isfinite(bandwidth) or not 0<bandwidth<2*F0 or ripple>edge_level:
        raise ValueError('Invalid B or ripple above band-edge threshold')
    if a<=0 or gap<=0:
        raise ValueError('Straight topology not supported')
    p=brentq(lambda p:ripple_db(p)-ripple,1+1e-8,100)
    t=threshold(edge_level)
    u=brentq(lambda v:v**3-(p-1)*v-p*t,np.sqrt(p-1),50)
    zm=u*np.tan(np.pi/2*(1-bandwidth/(2*F0))); zs=p/zm
    def residual(logz):
        m,s=np.exp(logz);n1,n2=ratios(m,s,a)
        return [np.log(n1*n1*m/50/zm),np.log(n2*n2*s/50/zs)]
    sol=root(residual,np.log([50*zm,50*zs/.84**2]))
    if not sol.success or max(abs(np.asarray(residual(sol.x))))>1e-8:
        raise ValueError('Nominal impedance inversion did not converge')
    m,s=np.exp(sol.x)
    wm=brentq(lambda w:microstrip(ER,w)['Z_ohm']-m,.071,10)
    # slotline reference-frequency validity branch, not arbitrary zero width
    # Stay just inside the documented branch: endpoint division can round
    # w/lambda below .0015 or above .075 even for an algebraically exact bound.
    ws=brentq(lambda w:slotline(ER,w)['Z_ohm']-s,
              (.0015+1e-12)*C/F0,(.075-1e-12)*C/F0)
    reasons=scope(wm,ws,a,gap)
    if reasons and not exploratory:
        raise ValueError('; '.join(reasons))
    g=lengths(wm,ws,a,gap)
    return dict(geometry_mm=g,ideal_target=dict(B_GHz=bandwidth,ripple_dB=ripple,
                edge_level_dB=edge_level,P_eff=p,R_eff=zm/zs,zm_eff=zm,zs_eff=zs),
                forward=forward(g,exploratory=True),geometry_check=geometry_screen(g),
                warnings=reasons,solver_authorized=False)
