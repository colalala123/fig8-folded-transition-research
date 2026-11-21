"""Actual oDesign.ValidateDesign with preserved native report; never Analyze."""
import re
from common_stage2 import read,write,sha,now
from geometry_gate import check_ir
from native_control import plain_value

def assess(return_code,text,messages):
    errors=[x for x in text.splitlines()+list(messages) if re.search(r'\[error\]|\berror\b',x,re.I) and not re.search(r'\b(?:0|no)\s+errors?\b|errors?\s*[:=]\s*0\b',x,re.I)]
    return dict(passed=type(return_code) is int and return_code==1 and not errors and bool(text.strip()),return_code=return_code,error_lines=errors)

def boundary_inventory(app):
    from ansys.aedt.core.internal.load_aedt_file import load_keyword_in_aedt_file
    saved=load_keyword_in_aedt_file(app.project_file,'BoundarySetup',design_name=app.design_name)
    native=list(app.oboundary.GetBoundaries())
    entries={b.name:dict(type=b.type,props=plain_value(b.props)) for b in app.boundaries}
    air=app.modeler['air_box'];faces=[];explicit_faces=set()
    for b in entries.values():explicit_faces.update(map(int,b['props'].get('Faces',[])))
    for f in air.faces:faces.append(dict(id=int(f.id),center=list(map(float,f.center)),explicit_face_assignment=int(f.id) in explicit_faces))
    if set(entries)!={'Rad1','1','2'}:raise RuntimeError('native boundary names differ from original saved design')
    if entries['Rad1']['type']!='Radiation' or entries['Rad1']['props'].get('Objects') not in ([air.id],['air_box']):raise RuntimeError('Rad1 is not assigned to original air_box')
    if any(entries[n]['type']!='Wave Port' for n in ('1','2')):raise RuntimeError('port boundary type changed')
    return dict(saved_BoundarySetup=plain_value(saved),native_GetBoundaries=native,explicit_boundaries=entries,air_object_id=air.id,air_faces=faces,
        exterior_boundary='Rad1 Radiation assigned to air_box; wave ports on Rectangle1/2 override their apertures',
        evidence_basis='native GetBoundaries + actual object-ID mapping + independently parsed saved BoundarySetup; not inferred from a wave-port-only filter',
        official_help='https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/HFSS/PerfectEBoundaries.htm',boundary_policy_unchanged=True)

def validate_native(app,pred,out,freeze_path=None):
    out.mkdir(parents=True,exist_ok=False)
    offline=check_ir(pred['cad_ir']);write(out/'OFFLINE_GATE.json',offline)
    before=list(app.odesktop.GetMessages(app.project_name,app.design_name,0))
    report=out/'ValidateDesign.log';rc=app.odesign.ValidateDesign(str(report))
    text=report.read_text(encoding='utf-8-sig',errors='replace') if report.exists() else ''
    after=list(app.odesktop.GetMessages(app.project_name,app.design_name,0));verdict=assess(rc,text,after)
    write(out/'MESSAGES.json',dict(before=before,after=after))
    proof=dict(at=now(),**verdict,new_Analyze=0,offline_passed=offline['passed'],native_report_sha256=sha(report) if report.exists() else None,
        input_sha256=sha(freeze_path) if freeze_path else None,project_sha256=sha(app.project_file))
    write(out/'VERDICT.json',proof)
    if not verdict['passed']:raise RuntimeError('R11 native design validation failed: '+str(verdict))
    write(out/'BOUNDARIES.json',boundary_inventory(app))
    return proof
