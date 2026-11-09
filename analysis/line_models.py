"""Independent nominal straight-line models; NOT HFSS effective extraction.

Slotline: Janaswamy/Schaubert, NASA 19860021419, Appendix A eqs (8),(9),
PDF p61; valid branch 2.22<=er<=3.8, .0015<=w/lambda0<=.075,
.006<=h/lambda0<=.06. Zero-thickness slot metal approximation.
Microstrip: Hammerstad/Jensen finite thickness with optional Kirschning/Jansen
dispersion; equations as documented by the Qucs project, node75.
All dimensional arguments below are in mm; frequency in GHz.
No response measurements or calibrated coefficients are used.
"""
from math import exp, log, sin, pi, sqrt, tanh, cosh

C_MM_GHZ = 299.792458
ETA0 = 376.730313668

def slotline(er, w, h=.813, f=6.72):
    wave = C_MM_GHZ/f
    if not (2.22<=er<=3.8 and .0015<=w/wave<=.075 and .006<=h/wave<=.06):
        raise ValueError('Outside the implemented Janaswamy/Schaubert branch')
    u=w/h
    z=(60+3.69*sin((er-2.22)*pi/2.36)+133.5*log(10*er)*sqrt(w/wave)
       +2.81*(1-.011*er*(4.48+log(er)))*u*log(100*h/wave)
       +131.1*(1.028-log(er))*sqrt(h/wave)
       +12.48*(1+.18*log(er))*u/sqrt(er-2.06+.85*u*u))
    k=(1.045-.365*log(er)+6.3*u*er**.945/(238.64+100*u)
       -(.148-8.81*(er+.95)/(100*er))*log(h/wave))
    return {'Z_ohm':z,'eeff':1/k**2,'w_over_lambda0':w/wave,'h_over_lambda0':h/wave}

def air_z(u):
    q=6+(2*pi-6)*exp(-(30.666/u)**.7528)
    return ETA0/(2*pi)*log(q/u+sqrt(1+4/u**2))

def kj_dispersion(u, er, e0, z0, fn):
    # fn is f[GHz]*h[mm]. Formula coefficients are dimensionless.
    p1=.27488+(.6315+.525/(1+.0157*fn)**20)*u-.065683*exp(-8.7513*u)
    p2=.33622*(1-exp(-.03442*er))
    p3=.0363*exp(-4.6*u)*(1-exp(-(fn/38.7)**4.97))
    p4=1+2.751*(1-exp(-(er/15.916)**8))
    ef=er-(er-e0)/(1+p1*p2*((.1844+p3*p4)*fn)**1.5763)
    r1=min(.03891*er**1.4,20);r2=min(.2671*u**7,20)
    r3=4.766*exp(-3.228*u**.641);r4=.016+(.0514*er)**4.524
    r5=(fn/28.843)**12;r6=min(22.20*u**1.92,20)
    r7=1.206-.3144*exp(-r1)*(1-exp(-r2))
    r8=1+1.275*(1-exp(-.004625*r3*er**1.674*(fn/18.365)**2.745))
    r9=5.086*r4*r5/(.3838+.386*r4)*exp(-r6)/(1+1.2992*r5)*(er-1)**6/(1+10*(er-1)**6)
    r10=.00044*er**2.136+.0184
    r11=(fn/19.47)**6/(1+.0962*(fn/19.47)**6)
    r12=1/(1+.00245*u*u)
    r13=.9408*ef**r8-.9603;r14=(.9408-r9)*e0**r8-.9603
    r15=.707*r10*(fn/12.3)**1.097
    r16=1+.0503*er**2*r11*(1-exp(-(u/15)**6))
    r17=r7*(1-1.1241*r12/r16*exp(-.026*fn**1.15656-r15))
    return z0*(r13/r14)**r17,ef

def microstrip(er,w,h=.813,t=.035,f=6.72,dispersion=True):
    if not (er>1 and w>0 and h>0 and 0<=t<min(h,w/2) and f>0):
        raise ValueError('Invalid microstrip geometry/material')
    u=w/h;tn=t/h
    du=tn/pi*log(1+4*exp(1)/tn*tanh(sqrt(6.517*u))**2) if t else 0
    u1=u+du;ur=u+du*(1+1/cosh(sqrt(er-1)))/2
    a=1+log((ur**4+(ur/52)**2)/(ur**4+.432))/49+log(1+(ur/18.1)**3)/18.7
    b=.564*((er-.9)/(er+3))**.053
    ee=(er+1)/2+(er-1)/2*(1+10/ur)**(-a*b)
    z=air_z(ur)/sqrt(ee)
    ee*= (air_z(u1)/air_z(ur))**2
    z_static=z
    if dispersion:
        # Use physical normalized width as in Qucs compatibility mode.
        z,ee=kj_dispersion(u,er,ee,z,f*h)
    return {'Z_ohm':z,'eeff':ee,'static_Z_ohm':z_static,'u_effective':ur}
