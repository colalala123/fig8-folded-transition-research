"""Pure stage6 measurement accounting. Missing data never become zero effect.

Inputs must already have independent numerical review and real-view ACK; this
module does not manufacture them and cannot launch a solver or publish a gate.
"""
import math

RESPONSES=('center_GHz','low_peak_dB','high_peak_dB','BW20_GHz','S21_min_dB')
PAIRS={'Ws':('P1','P2'),'Lm':('P3','P4'),'Ls1':('P5','P6'),'Wm':('P7','P8'),
    'etch':('P9','P10'),'er':('P11','P12'),'h':('P13','P14')}

def highest(r):return max(r['low_peak_dB'],r['high_peak_dB'])
def valid(r):
    if not r.get('numerical_review_passed') or not r.get('actual_view_ack'):raise ValueError('unreviewed measurement')
    if any(r.get(k) is None or not math.isfinite(r[k]) for k in ('center_GHz','low_peak_dB','high_peak_dB')):raise ValueError('invalid/missing shape metrics')

def linearity(base,plus,minus):
    out={}
    for k in RESPONSES:
        if any(x.get(k) is None for x in (base,plus,minus)):
            out[k]=dict(assessable=False,reason='missing main-band/response metric');continue
        a=plus[k]-base[k];b=minus[k]-base[k]
        out[k]=dict(assessable=True,delta_plus=a,delta_minus=b,even_component_abs=abs(a+b),
            half_odd_component_abs=.5*abs(a-b),clearly_nonlinear=abs(a+b)>.5*abs(a-b),
            later_uncertainty_source='measured_sides_not_J')
    return out

def stage6a(base,measured):
    valid(base)
    required={n for p in PAIRS.values() for n in p}|{'N0'}
    missing=sorted(required-set(measured))
    if missing:return dict(complete=False,missing=missing,release_R10_2=False,reason='no invented zero tolerance effects')
    for r in measured.values():valid(r)
    b=highest(base);noise=abs(highest(measured['N0'])-b)
    dense_required=noise>.05
    if dense_required:
        absent={'P1dense','P2dense'}-set(measured)
        if absent:return dict(complete=False,missing=sorted(absent),release_R10_2=False,noise_dB=noise,conditional_dense_required=True)
    sides={};lines={};diff={}
    for source,(pos,neg) in PAIRS.items():
        # Deterministic tie chooses the first listed plan ID, disclosed below.
        worst=max((pos,neg),key=lambda n:highest(measured[n]))
        sides[source]=dict(worst_case=worst,highest_peak_rise_dB=max(0.,highest(measured[worst])-b),
            signed_raw_rise_dB=highest(measured[worst])-b,
            side_raw_rises_dB={n:highest(measured[n])-b for n in (pos,neg)},tie_policy='first listed plan ID')
        lines[source]=linearity(base,measured[pos],measured[neg])
    for n,r in measured.items():
        diff[n]={k:(r[k]-base[k] if r.get(k) is not None and base.get(k) is not None else None) for k in RESPONSES}
    realistic=('etch','er','h');rss=math.sqrt(sum(sides[k]['highest_peak_rise_dB']**2 for k in realistic))
    noise_add=noise if noise>.1 else 0.;M=rss+noise_add;req=-20.-M-.256-.1
    conservative=sum(sides[k]['highest_peak_rise_dB'] for k in ('Ws','Lm','Ls1','Wm','er','h'))
    if b<=req:decision='use_B1_skip_B1R'
    elif req<-21.8:decision='skip_B1R_ripple_only_not_cost_effective'
    else:decision='try_B1R_max_three'
    q11a=abs(measured['P1']['high_peak_dB']-measured['P2']['high_peak_dB'])/2
    q11b=abs(measured['P3']['center_GHz']-measured['P4']['center_GHz'])/2*1000
    er_delta={n:(measured[n]['center_GHz']-base['center_GHz'])*1000 for n in ('P11','P12')}
    q13=all(20.-1e-8<=abs(d)<=50.+1e-8 for d in er_delta.values()) and er_delta['P11']>0 and er_delta['P12']<0 and sides['er']['highest_peak_rise_dB']<=.25
    return dict(complete=True,release_R10_2=True,per_case_differences=diff,per_source=sides,linearity=lines,
        noise_dB=noise,conditional_dense_required=dense_required,noise_linear_addition_dB=noise_add,
        realistic_RSS_before_noise_dB=rss,M_dB=M,delta_mesh_dB=.256,P_req_dB=req,
        C1_worst_sides={k:sides[k]['worst_case'] for k in realistic},
        conservative_linear_margin_dB=conservative,conservative_is_design_target=False,
        conservative_including_mesh_and_noise_dB=conservative+.256+noise_add,
        stage6B_decision=decision,B1_highest_peak_dB=b,
        Q11=dict(passed=.45<=q11a<=.95 and 35<=q11b<=60,high_peak_half_difference_dB=q11a,Lm_center_half_difference_MHz=q11b),
        Q12=dict(passed=sides['etch']['highest_peak_rise_dB']>=sides['Ws']['highest_peak_rise_dB']),
        Q13=dict(passed=q13,er_center_deltas_MHz=er_delta),
        Q14=dict(passed=sides['h']['highest_peak_rise_dB']>=max(sides[k]['highest_peak_rise_dB'] for k in realistic)),
        caveats=['RSS is the plan-prescribed engineering margin, not a statistical yield guarantee.',
            'C1 is a joint measured corner, not the RSS sum; report its actual result independently.',
            'Nonlinear responses always use side measurements rather than tuning J.',
            'Conditional dense P1/P2 are compared separately against archived B1 dense; primary margins retain ordinary-grid measurement context.'])

def robust_nominal_pass(row,P_req):
    valid(row)
    return (P_req-.2<=row['low_peak_dB']<=P_req and P_req-.2<=row['high_peak_dB']<=P_req and
        abs(row['high_peak_dB']-row['low_peak_dB'])<=.2000000001 and abs(row['center_GHz']-6.72)<=.0300000001 and
        row.get('S21_min_dB') is not None and row['S21_min_dB']>=-2 and row.get('BW20_GHz') is not None)

def robust_confirmation(nominal,dense,corner,M):
    for r in (nominal,dense,corner):valid(r)
    # Upward bias only. A downward mesh change cannot manufacture margin.
    signed=[dense[k]-nominal[k] for k in ('low_peak_dB','high_peak_dB')]
    bias=max(0.,*signed)
    return dict(dense_peak_changes_dB=signed,own_upward_mesh_bias_dB=bias,
        dense_pass=highest(dense)<=-20.-M,corner_with_mesh_pass=highest(corner)+bias<=-20.,
        passed=highest(dense)<=-20.-M and highest(corner)+bias<=-20.,
        mesh_bias_policy='max(0, low-frequency dense-nominal peak change, high-frequency dense-nominal peak change)')
