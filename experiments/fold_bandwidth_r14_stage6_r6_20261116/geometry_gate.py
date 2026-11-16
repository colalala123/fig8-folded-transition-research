"""R11 pure domain/board envelopes. Not a substitute for native Boolean validation."""
import math
import native_control as nc

def check_envelopes(objects,tol=1e-7):
    air=objects['air_box'];errors=[];contacts=[]
    for name,b in objects.items():
        if len(b)!=6 or not all(math.isfinite(v) for v in b):errors.append(name+': nonfinite bbox');continue
        if any(b[i]>b[i+3]+tol for i in range(3)):errors.append(name+': reversed bbox')
        if name=='air_box':continue
        for axis in range(3):
            if b[axis]<air[axis]-tol or b[axis+3]>air[axis+3]+tol:errors.append(name+': outside air axis '+str(axis))
            for end in (axis,axis+3):
                if abs(b[end]-air[end])<=tol:
                    permitted=(axis==0 and abs(abs(b[end])-15.)<=tol) or (axis==1 and abs(abs(b[end])-25.)<=tol)
                    contacts.append(dict(object=name,axis=axis,value=b[end],permitted=permitted))
                    if not permitted:errors.append(name+': unapproved air surface contact')
        if name in ('Substrate_3','Substrate_4','Substrate_5','Substrate_18','Substrate_7','Substrate_9'):
            if b[0]<-15.-tol or b[3]>15.+tol or b[1]<-25.-tol or b[4]>25.+tol:errors.append(name+': copper outside board')
    return dict(passed=not errors,errors=errors,contacts=contacts,scope='All frozen solid/sheet envelopes; native ValidateDesign required separately')

def check_ir(ir):
    proof=check_envelopes(nc.expected_objects(ir))
    if ir.get('board_policy')!='fixed_milled_outline':proof['errors'].append('legacy/nonfixed board policy forbidden for dispatch')
    if ir['rectangles']['ground']!=[[-15.,-25.,15.,25.]]:proof['errors'].append('ground board outline not fixed on both etch signs')
    for name,poly in ir['profiles'].items():
        if any(abs(p[0])>15.+1e-7 or abs(p[1])>25.+1e-7 for p in poly):proof['errors'].append(name+': profile exceeds board')
    proof['passed']=not proof['errors']
    if not proof['passed']:raise RuntimeError('R11 offline geometry gate: '+str(proof))
    return proof
