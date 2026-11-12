"""功率合理性审查。原生Power S设置成功不等于物理功率认证。"""
import numpy as np

def power_s_sanity(data):
    S=np.asarray(data['S'])
    col=np.sum(abs(S)**2,axis=1)
    return dict(passive_column_sums_all_frequencies=bool(np.all(col<=1.0001)),
        maximum_column_sum=float(col.max()),frequencies_violating=int(np.sum(np.any(col>1.0001,axis=1))),
        physical_power_certified=False,
        note='仅必要条件；失败禁止把1-sum(abs(S)^2)当辐射；通过也不单独构成功率认证。')

def lossless_modal_balance(data,lossless_materials_verified=False):
    f,S,Z,G=(np.asarray(data[k]) for k in ('f_GHz','S','Zo','Gamma'))
    # For PEC/tan-delta-zero ports only: positive, almost-real Zo AND almost-
    # imaginary propagation constant are a conservative propagating-mode test.
    zratio=abs(Z.imag)/np.maximum(abs(Z.real),1e-20)
    gratio=abs(G.real)/np.maximum(abs(G.imag),1e-20)
    propagating=(Z.real>0)&(zratio<1e-5)&(gratio<1e-5)&(abs(G.imag)>1.)
    evanescent=(abs(Z.imag)>100*abs(Z.real))&(abs(G.real)>100*abs(G.imag))&(abs(G.real)>1.)
    known=propagating|evanescent
    usable=np.all(known,axis=1)&propagating[:,0]&bool(lossless_materials_verified)
    # HFSS generalized *propagating* modes are 1W normalized. Evanescent
    # coefficients are not counted as outgoing real power.
    outgoing=np.sum(np.where(propagating,abs(S[:,:,0])**2,0.),axis=1)
    valid=usable&(outgoing<=1.0001)&(outgoing>=0)
    residual=np.where(valid,1-outgoing,np.nan)
    return dict(f_GHz=f,propagating=propagating,evanescent=evanescent,
        valid=valid,outgoing_fraction=outgoing,residual_fraction=residual,
        physical_power_certified=False,
        statement='仅无耗且传播分类明确频点的已声明端口模功率余量；端口模截断、边界与数值误差尚可能贡献，不直接等同纯辐射。',
        full_modal_completeness_proven=False)
