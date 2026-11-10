"""R2-3 pure per-attempt geometry gate; no launch API, budget or permission.

Only a failed tuning-generated geometry may reduce its arm. Fixed Lm/Ls1,
Wm/Ws/Ls2 are never changed here. Real dispatch MUST call this on each attempt
AND separately check explicit user authorization and native CAD/resources.
"""
import math
import chain


def presubmit(geometry, nominal_a, tuning_changed=False, topology='folded', board_half_x=15.):
    g={k:float(geometry[k]) for k in ('Wm','Ws','Lm','Ls1','Ls2','Ls3')}
    if not isinstance(tuning_changed,bool):raise ValueError('Explicit boolean tuning_changed required')
    if not math.isfinite(nominal_a) or nominal_a<0:raise ValueError('Invalid nominal a')
    result=dict(input_geometry_mm=g.copy(),geometry_mm=g.copy(),nominal_a_mm=nominal_a,
                input_a_mm=g['Ls3']-g['Ws'] if topology=='folded' else 0.,actual_a_mm=None,
                adjusted=False,adjustment_step_mm=.001,additional_attempts=0,
                can_submit=False,decision_scope='geometry_only_not_solver_authorization',
                solver_authorized=False,must_recheck_every_attempt=True)
    def check(v):
        try:return chain.geometry_screen(v,topology,board_half_x)
        except ValueError as e:return dict(screen_pass=False,reasons=[str(e)])
    before=check(g);result['screen_before']=before
    if before['screen_pass']:
        result.update(can_submit=True,actual_a_mm=before['a_mm'],screen_after=before,reason='already_passes')
        return result
    if not tuning_changed or topology!='folded':
        result.update(screen_after=before,reason='failed_without_eligible_tuning_adjustment')
        return result
    if set(before['reasons'])-{'tip_line_clearance_below_0.813mm','tip_tip_clearance_below_line_width_plus_1.626mm'}:
        result.update(screen_after=before,reason='arm_reduction_cannot_fix_other_geometry_failure')
        return result
    limit=(g['Ls1']-max(g['Wm'],1.82)-2*.813)/2-g['Ws']
    max_a=min(limit,result['input_a_mm'])
    # Enumerate downward from the analytic bound on the 0.001mm grid; the
    # original strict screen resolves floating-point boundary roundoff.
    millisteps=math.floor(max_a*1000+1e-10)
    while millisteps>=1:
        a=millisteps/1000
        candidate={**g,'Ls3':g['Ws']+a}
        after=check(candidate)
        if a<=result['input_a_mm'] and after['screen_pass']:
            result.update(geometry_mm=candidate,actual_a_mm=a,adjusted=True,can_submit=True,
                          screen_after=after,reason='tuning_clearance_failure_reduce_a_to_largest_passing_grid_value',
                          analytic_upper_bound_mm=limit,analysis_arm_field='actual_a_mm')
            # A machine-readable maximality witness; next grid value is either
            # above the requested arm or fails the exact same gate.
            next_g={**g,'Ls3':g['Ws']+(millisteps+1)/1000}
            result['next_grid_a_mm']=(millisteps+1)/1000
            result['next_grid_allowed']=result['next_grid_a_mm']<=result['input_a_mm'] and check(next_g)['screen_pass']
            return result
        millisteps-=1
    result.update(screen_after=before,reason='no_positive_arm_on_0.001mm_grid_can_pass')
    return result
