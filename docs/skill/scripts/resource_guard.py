"""Windows commit limit plus independent supervision of task-owned OCR only."""
import argparse, ctypes, json, os, subprocess, sys, time
from pathlib import Path
_job = None

def apply_windows_limit(megabytes):
    global _job
    if os.name != 'nt': raise RuntimeError('Hard memory limit requires Windows')
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(n,ctypes.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',IO),('process_limit',ctypes.c_size_t),('job_limit',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];k.CreateJobObjectW.restype=w.HANDLE
    k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];k.SetInformationJobObject.restype=w.BOOL
    k.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p];k.QueryInformationJobObject.restype=w.BOOL
    k.GetCurrentProcess.restype=w.HANDLE
    k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];k.AssignProcessToJobObject.restype=w.BOOL
    job=k.CreateJobObjectW(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    limit=Extended();limit.basic.flags=0x100;limit.process_limit=int(megabytes)*1048576
    if not k.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)):raise ctypes.WinError(ctypes.get_last_error())
    if not k.AssignProcessToJobObject(job,k.GetCurrentProcess()):raise ctypes.WinError(ctypes.get_last_error())
    actual=Extended()
    if not k.QueryInformationJobObject(job,9,ctypes.byref(actual),ctypes.sizeof(actual),None):raise ctypes.WinError(ctypes.get_last_error())
    if actual.process_limit!=limit.process_limit:raise RuntimeError('Memory limit verification failed')
    _job=job
    return {'type':'Windows Job Object committed-memory limit','verified_limit_bytes':actual.process_limit,'structure_size':ctypes.sizeof(actual)}

def supervise(command,report,rss_mb=1200,minimum_available_mb=2500,timeout=300):
    import psutil
    report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
    record={'command':command,'rss_limit_mb':rss_mb,'minimum_available_limit_mb':minimum_available_mb,'timeout_seconds':timeout,'peak_rss_mb':0,'minimum_available_mb':999999,'status':'starting'}
    def save():report.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    free=psutil.virtual_memory().available/1048576
    if free<minimum_available_mb:
        record.update(status='not_started_low_memory',available_mb=round(free,1));save();return 75
    env=os.environ.copy()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='1'
    env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    with report.with_suffix('.stdout.log').open('w',encoding='utf-8') as stdout,report.with_suffix('.stderr.log').open('w',encoding='utf-8') as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env)
        proc=psutil.Process(child.pid);start=time.monotonic();record.update(status='running',pid=child.pid);save()
        while child.poll() is None:
            try:
                owned=[proc]+proc.children(recursive=True)
                rss=sum(p.memory_info().rss for p in owned if p.is_running())/1048576
                record['observed_pids']=[p.pid for p in owned]
            except psutil.NoSuchProcess:
                continue
            available=psutil.virtual_memory().available/1048576
            record['peak_rss_mb']=round(max(record['peak_rss_mb'],rss),1);record['minimum_available_mb']=round(min(record['minimum_available_mb'],available),1)
            reason='rss_limit' if rss>rss_mb else 'system_available_memory' if available<minimum_available_mb else 'timeout' if time.monotonic()-start>timeout else None
            if reason:
                for descendant in reversed(owned[1:]):
                    try:descendant.kill()
                    except psutil.NoSuchProcess:pass
                child.kill();record.update(status='stopped_external_guard',reason=reason);break
            save();time.sleep(.25)
        code=child.wait();record.update(exit_code=code,seconds=round(time.monotonic()-start,2))
        if record['status']=='running':record['status']='completed' if code==0 else 'child_failed'
        save();return code

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--rss-mb',type=int,default=1200);p.add_argument('--minimum-available-mb',type=int,default=2500);p.add_argument('--timeout',type=int,default=300);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    command=a.command[1:] if a.command[:1]==['--'] else a.command
    if not command:p.error('Provide child command after --')
    sys.exit(supervise(command,a.report,a.rss_mb,a.minimum_available_mb,a.timeout))