"""PaddleOCR baseline/refinement on raw photo pixels, preserving provenance."""
import argparse,hashlib,importlib.metadata,json,os,platform,time,shutil,tempfile,threading
from pathlib import Path
from PIL import Image
import numpy as np
from essay import source_info,write_json

def run(image,out,models,cache,resume=False,cpu_threads=1,rec_batch_size=1,refined_limit=1280,max_rss_mb=1200,variant="mobile",phase="refined",commit_mb=1800):
 from resource_guard import apply_windows_limit
 hard_limit=apply_windows_limit(commit_mb)
 image=Path(image).resolve();out=Path(out).resolve();models=Path(models).resolve();cache=Path(cache).resolve()
 if (out/'run-metadata.json').exists() and not resume:raise ValueError('Use a new directory or --resume for verified incomplete runs')
 out.mkdir(parents=True,exist_ok=True)
 for k in ['PADDLE_PDX_CACHE_HOME','HF_HOME','MODELSCOPE_CACHE']:os.environ[k]=str(cache/k.lower())
 os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
 info=source_info(image)
 if info['exif_orientation']!=1:raise ValueError('Normalize EXIF into a separate source before OCR')
 dirs={k:models/f'PP-OCRv5_{variant}_{k}_infer' for k in ['det','rec']}
 for path in dirs.values():
  if not path.is_dir():raise ValueError('Missing local official model: '+str(path))
 meta={'source':info,'python':platform.python_version(),'versions':{n:importlib.metadata.version(n) for n in ['paddleocr','paddlepaddle','paddlex','opencv-contrib-python','Pillow']},'model':f'PP-OCRv5_{variant}','hard_memory_limit':hard_limit,'status':'running','runs':[], 'model_files':{str(f.relative_to(models)):hashlib.sha256(f.read_bytes()).hexdigest() for p in dirs.values() for f in p.rglob('*') if f.is_file()}}
 if resume and (out/'run-metadata.json').exists():
  previous=json.loads((out/'run-metadata.json').read_text(encoding='utf-8-sig'))
  if previous['source']!=info or previous['model_files']!=meta['model_files'] or previous['versions']!=meta['versions']:raise ValueError('Resume requires identical source, model hashes and package versions')
  for completed in previous.get('runs',[]):
   folder=out/completed['name'];raw=json.loads((folder/'raw-1.json').read_text(encoding='utf-8-sig'));summary=json.loads((folder/'summary.json').read_text(encoding='utf-8-sig'))
   if len(summary['rec_texts'])!=completed['regions']:raise ValueError('Incomplete saved OCR run')
  meta['runs']=previous.get('runs',[]);meta['resumed_from_status']=previous.get('status');meta['resumed_after_restart']=True
 save_lock=threading.RLock()
 def save():
  with save_lock:
   temporary=out/'run-metadata.json.tmp';write_json(temporary,meta);temporary.replace(out/'run-metadata.json')
 save()
 if os.name=='nt' and any(not str(path).isascii() for path in dirs.values()):
  # Paddle native file streams on Windows can fail on Unicode model paths.
  # Use a task-owned temporary copy; metadata hashes still identify originals.
  stage=Path(tempfile.mkdtemp(prefix='codex-essay-models-'))
  if not str(stage).isascii():raise ValueError('Paddle needs an ASCII model directory; specify --models explicitly')
  staged={}
  for key,path in dirs.items():
   staged[key]=stage/path.name;shutil.copytree(path,staged[key])
  dirs=staged;meta['model_staging']={'reason':'Windows native Unicode model-path compatibility','directory':str(stage)};save()
 import psutil
 process=psutil.Process();stop=threading.Event()
 if hasattr(process,'cpu_affinity'):
  allowed=process.cpu_affinity();process.cpu_affinity(allowed[:cpu_threads])
 resource={'peak_rss_mb':0,'minimum_available_mb':999999,'cpu_affinity':process.cpu_affinity() if hasattr(process,'cpu_affinity') else [],'max_rss_mb':max_rss_mb,'minimum_available_limit_mb':2048}
 meta['low_load_settings']={'cpu_threads':cpu_threads,'rec_batch_size':rec_batch_size,'refined_limit':refined_limit};meta['resources']=resource;save()
 def monitor():
  while not stop.wait(1):
   rss=process.memory_info().rss/1048576;available=psutil.virtual_memory().available/1048576
   resource['peak_rss_mb']=round(max(resource['peak_rss_mb'],rss),1);resource['minimum_available_mb']=round(min(resource['minimum_available_mb'],available),1)
   if rss>max_rss_mb or available<2048:
    meta['status']='stopped_resources';meta['error']='Memory guard stopped this OCR process';save();print(meta['error'],flush=True);os._exit(75)
 watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
 try:
  from paddleocr import PaddleOCR
  ocr=PaddleOCR(text_detection_model_name=f'PP-OCRv5_{variant}_det',text_recognition_model_name=f'PP-OCRv5_{variant}_rec',text_detection_model_dir=str(dirs['det']),text_recognition_model_dir=str(dirs['rec']),use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,device='cpu',enable_mkldnn=False,cpu_threads=cpu_threads,text_recognition_batch_size=rec_batch_size)
  array=np.asarray(Image.open(image).convert('RGB'))
  for name,limit,threshold in [('baseline',1280,.6),('refined',refined_limit,.4)]:
   if phase!='both' and name!=phase:continue
   if any(r['name']==name for r in meta['runs']):print('Preserved completed run:',name,flush=True);continue
   folder=out/name
   if folder.exists() and any(folder.iterdir()):raise ValueError('Partial OCR files exist; preserve them and use a new output directory')
   folder.mkdir(exist_ok=True);t=time.perf_counter()
   results=list(ocr.predict(array,text_det_limit_type='max',text_det_limit_side_len=limit,text_det_box_thresh=threshold,text_rec_score_thresh=0.0,return_word_box=True))
   for i,r in enumerate(results):
    r.save_to_json(str(folder/f'raw-{i+1}.json'));r.save_to_img(str(folder))
    data=r.json;data=data.get('res',data)
    write_json(folder/'summary.json',{'rec_texts':data.get('rec_texts',[]),'rec_scores':data.get('rec_scores',[]),'rec_polys':data.get('rec_polys',[]),'word_keys':[k for k in data if 'word' in k]})
   meta['runs'].append({'name':name,'det_limit':limit,'box_threshold':threshold,'seconds':round(time.perf_counter()-t,2),'regions':len(data.get('rec_texts',[])),'cpu_threads':cpu_threads,'rec_batch_size':rec_batch_size});save();print(meta['runs'][-1],flush=True)
  stop.set();watcher.join(timeout=2);meta['status']='completed';save()
 except Exception as e:
  stop.set();meta['status']='failed';meta['error']=repr(e);save();raise
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--image',required=True);ap.add_argument('--out',required=True);ap.add_argument('--models',required=True);ap.add_argument('--cache',required=True);ap.add_argument('--resume',action='store_true');ap.add_argument('--cpu-threads',type=int,default=1);ap.add_argument('--rec-batch-size',type=int,default=1);ap.add_argument('--refined-limit',type=int,default=1280);ap.add_argument('--max-rss-mb',type=int,default=1200);ap.add_argument('--variant',choices=['mobile','server'],default='mobile');ap.add_argument('--phase',choices=['baseline','refined','both'],default='refined');ap.add_argument('--commit-mb',type=int,default=1800);a=ap.parse_args();run(a.image,a.out,a.models,a.cache,a.resume,a.cpu_threads,a.rec_batch_size,a.refined_limit,a.max_rss_mb,a.variant,a.phase,a.commit_mb)