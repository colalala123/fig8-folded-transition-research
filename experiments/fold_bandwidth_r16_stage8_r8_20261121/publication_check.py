"""Verify the same git blobs and worktree hashes as R7, in one read-only cat-file batch."""
import hashlib,subprocess
from common_stage2 import REPO,sha
def verify_blobs(commit,files):
    if not files:raise RuntimeError('empty proof')
    keys=list(files)
    for k in keys:
        if sha(REPO/k)!=files[k]:raise RuntimeError('workspace publication mismatch '+k)
    cp=subprocess.run(['git','cat-file','--batch'],cwd=REPO,input=''.join(commit+':'+k+'\n' for k in keys).encode(),capture_output=True,check=True)
    i=0;b=cp.stdout
    for k in keys:
        end=b.index(b'\n',i);fields=b[i:end].split()
        if len(fields)!=3 or fields[1]!=b'blob':raise RuntimeError('missing git blob '+k)
        n=int(fields[2]);i=end+1
        if hashlib.sha256(b[i:i+n]).hexdigest()!=files[k] or b[i+n:i+n+1]!=b'\n':raise RuntimeError('published blob mismatch '+k)
        i+=n+1
    if i!=len(b):raise RuntimeError('trailing publication bytes')
