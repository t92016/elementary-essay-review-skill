"""Fetch the pinned official mobile models, with no Paddle import or inference."""
import argparse,hashlib,json,os,shutil,tarfile,tempfile,urllib.request
from pathlib import Path,PurePosixPath

def verify(directory,files):
    for name,expected in files.items():
        path=Path(directory)/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Missing or changed pinned model file: '+str(path))

def unpack(archive,stage,name):
    total=0
    with tarfile.open(archive,'r:*') as tar:
        for member in tar:
            path=PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name or not path.parts or path.parts[0]!=name:raise ValueError('Invalid model archive path')
            if not member.isdir() and not member.isfile():raise ValueError('Links and special files are not allowed')
            total+=member.size
            if total>150*1048576:raise ValueError('Model archive exceeds extraction limit')
            target=stage.joinpath(*path.parts)
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest,1024*1024)

def fetch(out,manifest=None):
    out=Path(out).resolve()
    if os.name=='nt' and not str(out).isascii():raise ValueError('Use an ASCII model path for Windows native inference')
    data=json.loads(Path(manifest or Path(__file__).resolve().parents[1]/'references/mobile-models.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True,exist_ok=True);records={}
    for name,entry in data['models'].items():
        if name not in ['PP-OCRv5_mobile_det_infer','PP-OCRv5_mobile_rec_infer']:raise ValueError('Only tested mobile models allowed')
        target=out/name
        if target.exists():verify(target,entry['files']);records[name]={'status':'verified_existing','url':entry['url'],'files':entry['files']};continue
        if not entry['url'].startswith('https://paddle-model-ecology.bj.bcebos.com/'):raise ValueError('Official HTTPS source required')
        with tempfile.TemporaryDirectory(prefix='essay-model-',dir=out) as temp:
            stage=Path(temp);archive=stage/'model.tar';size=0
            with urllib.request.urlopen(entry['url'],timeout=30) as response,archive.open('wb') as dest:
                if not response.url.startswith('https://paddle-model-ecology.bj.bcebos.com/'):raise ValueError('Unexpected download redirect')
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    size+=len(block)
                    if size>100*1048576:raise ValueError('Download exceeds model size limit')
                    dest.write(block)
            unpack(archive,stage,name);verify(stage/name,entry['files']);(stage/name).rename(target)
            records[name]={'status':'downloaded_verified','url':entry['url'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'download_bytes':size,'files':entry['files']}
    record={'models':records,'scope':'Pinned download integrity only; no inference or OCR accuracy test'}
    (out/'models-download.json').write_text(json.dumps(record,indent=2),encoding='utf-8');return record
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(fetch(a.out),indent=2))
