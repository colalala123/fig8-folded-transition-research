"""R6 审核的复核计算。离线，只读已提交的数据，不启动 HFSS，不发消息。"""
import collections, glob, importlib.util, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
R4 = ROOT / 'experiments/fold_bandwidth_r4_20261110'


def r5_module():
    p = ROOT / 'experiments/fold_bandwidth_review_r5_20261110/review_checks.py'
    spec = importlib.util.spec_from_file_location('review_r5', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def n04_redo():
    m = r5_module()
    m.NEW = R4 / 'r5_cache_results/S1_BASE_N04/full_modes.csv'
    out = m.first_run()
    out.pop('dB_equivalent_at_minus20p5')
    return out


def role(cmd):
    for key in ('-solve_broadband_adapt', '-port_adapt', '-port_solve', '-solve'):
        if re.search(re.escape(key) + r'(\s|$)', cmd):
            return key
    return 'unknown'


def archive_process_roles():
    """归档运行记录里观察到的 hf3d.exe 进程，按角色和核数统计。"""
    count = collections.Counter()
    for p in sorted(glob.glob(str(ROOT / 'data/raw/*/state.json'))):
        for seg in json.load(open(p, encoding='utf-8'))['segments']:
            for obs in seg.get('observations', []):
                for pr in obs:
                    cmd = ' '.join(pr.get('cmdline') or [])
                    cores = re.search(r'-max_processors (\d+)', cmd)
                    count[(role(cmd), cores.group(1) if cores else 'none')] += 1
    return [dict(role=r, max_processors=c, observations=n) for (r, c), n in sorted(count.items())]


def run(out_dir):
    out = dict(n04_redo_vs_archive=n04_redo(), archive_process_roles=archive_process_roles())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'REVIEW_CHECKS.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    return out


if __name__ == '__main__':
    here = pathlib.Path(__file__).resolve().parent
    print(json.dumps(run(here / (sys.argv[1] if len(sys.argv) > 1 else 'out_rerun'))['archive_process_roles'], indent=1))
