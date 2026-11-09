"""Offline only; new output directory required. Never starts HFSS or sends notifications."""
import argparse,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--mode',choices=['train','inverse'],required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
for name in ['dataset.npz','DATASET.json']:
 shutil.copy2(r/'model'/name,out/name)
if a.mode=='inverse':
 for name in ['model_C.joblib','FOLDS_AND_TUNING.json']:
  shutil.copy2(r/'model'/name,out/name)
env={**os.environ,'FIG8_MODEL_DIR':str(out)}
steps=['train.py','ablate.py'] if a.mode=='train' else ['inverse_offline.py','law_and_stress.py']
for script in steps:subprocess.run([sys.executable,str(r/'analysis'/script)],check=True,env=env)
print('Offline replay finished:',out)
