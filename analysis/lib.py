"""Portable offline-only math. No solver, notification, process, or desktop imports."""
import json,hashlib,math,os
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
from line_models import microstrip,slotline
ROOT=Path(os.environ.get('FIG8_MODEL_DIR',str(Path(__file__).resolve().parents[1]/'model')))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,d):
 with (ROOT/n).open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)

TARGET={'f_low_GHz': 3.92, 'f_high_GHz': 9.52, 'BW_GHz': 5.6, 'S11_max_dB': -20, 'S21_min_dB': -2}

def intervals(f, s11, s21, reflection=-20, transmission=-2):
    """Exact intersection of both piecewise-linear dB constraints per segment.

    Important: do not interpolate min(margin11,margin21) across a segment;
    that loses a valid interior when opposite endpoints fail different tests.
    """
    ans = []
    for i in range(len(f) - 1):
        lo, hi = (0.0, 1.0)
        for v0, v1 in [(reflection - s11[i], reflection - s11[i + 1]), (s21[i] - transmission, s21[i + 1] - transmission)]:
            if v0 < 0 and v1 < 0:
                hi = -1
                break
            if v0 < 0:
                lo = max(lo, -v0 / (v1 - v0))
            if v1 < 0:
                hi = min(hi, -v0 / (v1 - v0))
        if hi <= lo:
            continue
        a = float(f[i] + lo * (f[i + 1] - f[i]))
        b = float(f[i] + hi * (f[i + 1] - f[i]))
        if ans and abs(a - ans[-1][1]) < 1e-09:
            ans[-1][1] = b
        else:
            ans.append([a, b])
    return ans

def band_score(f, s11, s21, lo, hi):
    if not f[0] <= lo < hi <= f[-1]:
        raise ValueError('Requested band outside sampled frequencies')
    ff = np.r_[lo, f[(f > lo) & (f < hi)], hi]
    return dict(worst_S11_dB=float(np.max(np.interp(ff, f, s11))), min_S21_dB=float(np.min(np.interp(ff, f, s21))))

def load_curve(path):
    d = np.atleast_1d(np.genfromtxt(path, delimiter=',', names=True))
    needed = ['Freq_GHz', 'S11_real', 'S11_imag', 'S21_real', 'S21_imag']
    if not all((k in d.dtype.names for k in needed)):
        raise ValueError('Native complex S11/S21 required')
    f = d['Freq_GHz']
    s = np.column_stack([d[k + '_real'] + 1j * d[k + '_imag'] for k in ['S11', 'S21']])
    if not np.isfinite(f).all() or not np.isfinite(s).all() or (not np.all(np.diff(f) > 0)):
        raise ValueError('Invalid native curve')
    return (f, s)

def assess(f, s, target, optimization_margin=False):
    db = 20 * np.log10(np.maximum(abs(s), 1e-15))
    r, t = db.T
    lo, hi = (target['f_low_GHz'], target['f_high_GHz'])
    score = band_score(f, r, t, lo, hi)
    seg = intervals(f, np.full_like(f, -100), t)
    bands = sorted(seg, key=lambda p: p[1] - p[0], reverse=True)
    if not bands:
        return dict(passed=False, shape_valid=False, objective=1000000.0, **score)
    left, right = bands[0]
    mins = find_peaks(-r, prominence=0.5)[0]
    vv = [i for i in mins if left < f[i] < right and r[i] < -10]
    if len(vv) != 3:
        return dict(passed=False, shape_valid=False, objective=1000000.0 + abs(len(vv) - 3), **score)
    peaks = [a + 1 + int(np.argmax(r[a + 1:b])) for a, b in zip(vv, vv[1:])]
    center = float(f[vv[1]])
    gap = float(abs(r[peaks[0]] - r[peaks[1]]))
    rlimit = target.get('S11_max_dB', -20)
    tlimit = target.get('S21_min_dB', -2)
    passed = bool(score['worst_S11_dB'] <= rlimit and score['min_S21_dB'] >= tlimit and (abs(center - 6.72) <= 0.03000000001) and (gap <= 0.5))
    rm = 0.4 if optimization_margin else 0
    tm = 0.05 if optimization_margin else 0
    gaplimit = 0.25 if optimization_margin else 0.5
    centerlimit = 0.02 if optimization_margin else 0.03
    v = np.array([max(0, score['worst_S11_dB'] - rlimit + rm) / 0.1, max(0, tlimit + tm - score['min_S21_dB']) / 0.05, max(0, abs(center - 6.72) - centerlimit) / 0.01, max(0, gap - gaplimit) / 0.1])
    return dict(**score, shape_valid=True, passed=passed, central_valley_GHz=center, peak_difference_dB=gap, inner_peaks=[dict(GHz=float(f[i]), S11_dB=float(r[i])) for i in peaks], objective=float(v @ v), nominal_buffer_satisfied=bool(np.all(v <= 1e-10)))

def features(g):
 a=g['Ls3']-g['Ws'];gap=g['Ls2']-2*g['Ws'];assert abs(gap-.55)<1e-8
 m=microstrip(3.55,g['Wm']);s=slotline(3.55,g['Ws']);P=m['Z_ohm']*s['Z_ohm']/2500;R=m['Z_ohm']/s['Z_ohm']
 lm=299.792458/(4*6.72*math.sqrt(m['eeff']));ls=299.792458/(2*6.72*math.sqrt(s['eeff']))-2*g['Ls2']-2*g['Ls3']
 return [math.log(P),math.log(R),a,g['Lm']-lm,g['Ls1']-ls],{'P':P,'R':R,'a':a,'Lm_nominal':lm,'Ls1_nominal':ls}
LABELS=['worst_S11_dB','min_S21_dB','central_valley_GHz','peak_difference_dB','S21_BW_GHz']
def label(f,z):
 q=assess(f,z,TARGET);d=20*np.log10(np.maximum(abs(z),1e-15));b=intervals(f,np.full_like(f,-100),d[:,1]);q['S21_BW_GHz']=max((v-u for u,v in b),default=0)
 j=intervals(f,d[:,0],d[:,1]);q['joint_intervals']=j;q['joint_components']=len(j);q['joint_center_band']=next(([u,v,v-u] for u,v in j if u<=6.72<=v),None)
 return q
