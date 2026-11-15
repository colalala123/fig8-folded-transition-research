"""Read-only R13 post-STOP audit/report. Does not import or dispatch AEDT.

One-shot new evidence writer; no frozen runtime file is edited.
"""
import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
H=REPO/'experiments/fold_bandwidth_r13_stage6_r5_20261116'
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r13_stage6_r5_20261116')
sys.path.insert(0,str(H))
import r13
from common_stage2 import read,sha,write,now,case_dir,history

def build():
    out=H/'stop_review';out.mkdir(exist_ok=False)
    cfg=read(ROOT/'authorization.json');w=case_dir(ROOT,r13.CACHE_CASE,cfg)
    rec=read(w/'RUN_RECORD.json');stop=read(ROOT/'STOP.json')
    if rec['new_Analyze_requested']!=0 or rec['Analyze_requested']!=12 or list((ROOT/'ledger').glob('*.json')):
        raise RuntimeError('Not the expected zero-request observer failure')
    unchanged={}
    for rel,h in {**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('Frozen content changed '+rel)
        unchanged[rel]=h
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('Historical content changed '+p)
    r13.audit_cache_files(r13.SOURCE,cfg)
    frozen=read(H/'freeze/R13_R5.json')
    for name in ('reopened_convergence.txt','reopened_convergence_repeat.txt','pre_final_sweep.txt'):
        r13.verify_history(history((w/'native'/name).read_text(encoding='utf-8-sig')),cfg)
    # Fresh child reproduces the actual entrypoint import context, no capture/main.
    cmd=[sys.executable,'-c','import observer_r13']
    p=subprocess.run(cmd,cwd=H,capture_output=True,text=True,encoding='utf-8',env=os.environ.copy())
    reproduced=p.returncode!=0 and "No module named 'common_r6'" in p.stderr
    if not reproduced:raise RuntimeError('Root-cause import probe did not reproduce')
    write(out/'OBSERVER_IMPORT_PROBE.json',dict(at=now(),command=cmd[1:],cwd='R5 module directory',returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,
        expected_failure_reproduced=True,no_AEDT=True,no_capture_main=True))
    for n in ('failure.txt','RUN_RECORD.json','cleanup.json'):(out/n).write_bytes((w/n).read_bytes())
    (out/'observer_import_failure.txt').write_bytes((w/'evidence/final_sweep_observer.log').read_bytes())
    write(out/'STOP.json',stop)
    write(out/'CACHE_AUDIT.json',dict(at=now(),original_R4_cache_byte_identical=True,original_manifest_sha256=sha(H/'freeze/CACHE_MANIFEST.json'),
        clone_initially_identical=read(w/'evidence/CACHE_CLONED.json'),read_only_geometry=read(w/'evidence/geometry_build.json')['native_acceptance'],
        native_validation=read(w/'evidence/design_validation/VERDICT.json'),all_27_rows_exact_before_Analyze=True,
        final=[27,247756,.0023507],new_Analyze=0,geometry_unchanged=True,sweep_only_setting_prepared_but_not_solved=True,
        full_Sweep1_matches_T3=r13.sweep_section(w/'model.aedt')==frozen['nominal_T3_full_sweep_section']))
    import psutil
    active=[dict(pid=p.pid,name=p.info['name'],create_time=p.create_time()) for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
    worker=read(w/'worker_started.json');alive=False
    try:alive=abs(psutil.Process(worker['pid']).create_time()-worker['create_time'])<.001
    except psutil.NoSuchProcess:pass
    if active or alive:raise RuntimeError('Owned or foreign process still active; do not report stopped cleanly')
    claims=sorted(x.relative_to(w).as_posix() for x in w.rglob('*') if x.is_file() and ('claim' in x.name or 'spawn' in x.name or 'started' in x.name))
    result=dict(at=now(),strict_stop=True,R13_complete=False,R5_freeze_pushed_commit='0ecf9e5dda08693ddaf40e007141105eb96dc498',
        new_Analyze=0,new_geometry=0,cumulative_geometry=193,cumulative_Analyze=1846,stage6_geometry=20,stage6_Analyze=213,
        dense_physical_Analyze=12,dense_cap=20,not_charged_as_thirteenth=True,claims_preserved=claims,
        original_R4_STOP_and_all_historical_hashes_unchanged=True,frozen_files_checked=len(unchanged),historical_files_checked=len(cfg['historical_hashes']),
        original_cache_files_checked=len(read(H/'freeze/CACHE_MANIFEST.json')),worker_alive=False,active_HFSS=[],
        root_cause='New copied observer imports common_r6 without adding R6 directory to independent child sys.path. Main-worker common_stage2 initialization is not inherited by a fresh process.',
        responsible_component='R5 tool packaging/import, not HFSS solve or design physics',
        test_gap='55 in-process offline tests passed but none imported actual observer CLI module in a fresh interpreter.',
        C1R='not_prepared_or_started',W3_T4='not_prepared_or_started',W4='not_prepared_or_started',
        dense_S_parameters_valid=False,robustness='unverified',Q25=None,Q26=None,Q23=None,Q24=None,Q16=None,
        no_direct_points=True,no_hook=True,no_new_revision_or_stage7=True)
    write(out/'FINAL_VERIFICATION.json',result)
    table=read(r13.PRIOR_H/'stop_review/REVIEW.json')
    # Preserve inherited report as a reference, without asserting any new results.
    write(out/'INHERITED_R12_SCIENTIFIC_REVIEW.json',table)
    jst=datetime.datetime.fromisoformat(rec['finished_at']).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    report=f'''# R13 阶段6：R5 严格停止报告

## 总结

**本轮没有做完。** R5 冻结已于求解前推送（`0ecf9e5`），55项回归、默认11项及8765归档文件校验通过。缓存副本的原生CAD、材料、端口、Rad1、27行历史均通过核对；但独立观察器在提交求解前导入失败，按R13第3.5节严格停止。

终态：日本时间 **{jst:%Y-%m-%d %H:%M:%S}**。新增 **0个几何、0次Analyze**；累计仍为 **193/200个几何、1846次Analyze**。C1R和6C未启动。没有密网格S参数新结果，不能给出统计/最坏角点稳健结论。

## 1. 完成了什么

1. 合并计划分支`0c55fdc`，新建独立R5目录；R1–R4代码、冻结、STOP、claim、账本不改。
2. 求解前冻结：只扫频阶段仅允许从本次R12 STOP进入、旧历史27轮247756单元ΔS0.0023507逐行不变、同一物理几何12→13请求且不增加几何；Q25–Q26原文冻结。
3. 完整Sweep1保存段与名义T3比对一致（只切换IsEnabled）；最大轮数27，自适应设置不改。R4密网格规则仍拒绝继续加密。
4. 原R4缓存597个文件（工程+596个结果文件）保留字节一致；新副本原生几何/材料/边界、槽坐标、两次27行历史导出一致。原生ValidateDesign通过，0 Analyze。
5. 本次AEDT已正常释放，scratch已还原；核查无HFSS/hf3d、无存活本worker。所有工程、缓存和故障记录保留。

## 2. 故障及责任

原始独立观察器日志：`ModuleNotFoundError: No module named 'common_r6'`。

这是**本次R5工具打包/导入路径错误**，不是HFSS崩溃、网格不收敛或设计失败。观察器从R6目录复制到R5后，仍直接导入`common_r6`，却没有给独立子进程建立R6模块路径；主worker已经初始化的`sys.path`不会自动传到新Python进程。我漏测了这个真实独立入口。

55项测试验证了纯逻辑，但没有从全新解释器导入实际观察器入口，因此不能覆盖此故障。停止后已用全新子进程只导入模块（不运行capture，不连AEDT）复现，证据在`stop_review/OBSERVER_IMPORT_PROBE.json`。

观察器在ready之前退出；`charge()`尚未执行，所以第13次请求**没有计费、更没有提交**。运行记录中的12次全部是R4继承，不是新增12次。没有伪造实际14核启动或扫频完成证明。

## 3. 为什么没有继续C1R/6C

R13第3.4节的互不阻断只针对**数值失败**。本次是监护进程无法启动，属于第3.5节进程/工具完整性问题，必须立即停。因此没有把它伪标为数值缺失来绕过停止，也没有重置marker、编辑冻结代码或自动建立R6。

|步骤|状态|新增几何|新增Analyze|
|---|---|---:|---:|
|R5离线冻结并推送|完成|0|0|
|B1R密网格只读核对|完成|0|0|
|B1R密网格只扫频|观察器启动失败，未提交|0|0|
|C1R|未准备/未启动|0|0|
|6C W3 T4 / W4|未准备/未启动|0|0|

阶段6累计20/27几何、213次Analyze。原密网格12/20请求。R13剩余最多4个新几何和1次缓存扫频请求仍未使用；它们不是绕过本次STOP的授权。

## 4. B1R交付表（沿用R12，不冒充本轮成果）

名义尺寸mm：Wm2.350、Ws0.459、Lm6.599、Ls1 12.545、Ls2 1.468、Ls3 2.259；a1.8、g0.55。名义材料εr3.55、h0.813mm、tanδ0.0027、铜厚0.035mm。

|指标|名义T3（已审核）|密网格|C1R|
|---|---:|---|---|
|中央谷GHz|6.70|无有效扫频，未知|未测|
|低/高内峰dB|−22.507618 / −22.605617|未知|未测|
|BW20 GHz|6.131644|未知|未测|
|BW20内最差S21 dB|−1.011653|未知|未测|

S21口径明确为BW20内离散样本，不将BW15或其他窗口的最差值混称。名义插值达标不等于收敛/直接频点/制造证书。

## 5. 待评判据和预测

- 统计稳健（含网格残差）：Γ_dense+0.0023507≤0.079240120043；最高内峰约≤−22.283dB。**未知**。
- 统计稳健（不含网格残差，边缘）：Γ_dense≤0.079240120043，但不满足上一行。**未知**。
- 最坏角点稳健：Γ_C1R+max(0,Γ_dense−Γ_T3,max)≤0.1且密网格扫频有效。**未知**。
- 密网格无效时允许报告借用B1偏差0.00276的未经本设计确认标注；现在C1R也未测，仍不能给出这个标注。
- Q25、Q26、Q23、Q24、Q16：**均未新增可评分证据**，不能记为预测不通过或通过。
- R12已评分结论保持：Q21、Q22通过，Q15不通过；不事后改预测。

## 6. 规律汇总与实物含义

两参数P_eff/失谐规律在公差尺度的小扰动上有良好局部拟合，适合公差估计和微调，**不能一步外推出深纹波的大幅改动设计**。B1R T1–T3已有均值残差+0.18/+0.13/+0.12dB，倾斜残差−0.34/−0.28/−0.50dB，T2/T3符号也不符。大幅调整应依靠实测J外推和有限Broyden修正；本轮没有新数据改变此结论。

仿真不含SMA接头；实物会叠加接头与转接反射。已有公差数据中板厚是主导误差。拿到实测h0和公差后，可用P13/P14局部灵敏度重新估算余量，无需为这次**离线估算**新增仿真，但不把线性估算说成新的制造保证。

## 7. 后续审核入口（不是恢复授权）

只需有限工具修复，原则上应由新版本明确建立观察器的依赖路径，并增加真实独立入口的导入回归和虚拟进程监护测试；不能只再跑原55项测试。应重新冻结、推送、核验新旧预算与缓存来源后才能恢复。本报告没有修改R5冻结，也没有建立/启动R6。

下一步仍是：唯一原缓存只扫频→C1R→6C，数值缺失互不阻断，进程/完整性问题立即停；但须先获得对本次停止后的有限恢复授权。原R4和本R5 STOP、claim及失败记录继续保留，不清锁，不重复派发，不进入阶段7。

## 证据

- `freeze/R13_R5.json`：Q25–Q26原文、完整扫频对照、27行缓存历史。
- `freeze/OFFLINE_TESTS.json`：55+11测试及8765归档校验真实输出。
- `results/S6R10_B1Rdense__T1/`：原生只读核验、ValidateDesign、清理证据。
- `stop_review/CACHE_AUDIT.json`、`FINAL_VERIFICATION.json`：源缓存及冻结/历史哈希、预算与进程复核。
- `stop_review/observer_import_failure.txt`、`OBSERVER_IMPORT_PROBE.json`：原始故障和独立复现。
'''
    (H/'STOP_REPORT.md').write_text(report,encoding='utf-8')
    (H/'RECOVERY_REQUIREMENTS.md').write_text('# R13严格停止：审核入口，不是恢复授权\n\n见 STOP_REPORT.md 第7节。新观察器独立入口缺少common_r6路径；0新增Analyze，源缓存完整。不得改R5冻结/STOP、重置marker或自动R6。\n',encoding='utf-8')
    # Manifest is the last new file; excludes itself and interpreter caches.
    files={p.relative_to(H).as_posix():sha(p) for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='STOP_MANIFEST.json'}
    write(H/'STOP_MANIFEST.json',files)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':build()
