"""Verified page crops and exact translation of OCR candidates to the raw photo."""
import argparse,copy,json,hashlib
from pathlib import Path
from PIL import Image
from essay import source_info,validate,write_json
from import_paddle import convert

def prepare(image,regions,out):
    info=source_info(image)
    if info['exif_orientation']!=1:raise ValueError('EXIF must be normalized into a separate source first')
    if regions.get('source_sha256')!=info['sha256']:raise ValueError('Wrong region source hash')
    out=Path(out)
    if out.exists():raise ValueError('Use a new crop output directory')
    pages=regions['pages'];ids=set();orders=set()
    for page in pages:
        if page['id'] in ids or page['order'] in orders:raise ValueError('Duplicate page ID/order')
        ids.add(page['id']);orders.add(page['order'])
        if type(page['order'])!=int or page['order']<1:raise ValueError('Invalid page order')
        if page.get('position_reviewed') is not True or not page.get('reviewer'):raise ValueError('Page positions/order require visual review')
        box=page['box']
        if len(box)!=4 or any(type(v)!=int for v in box):raise ValueError('Integer pixel crop required')
        x,y,w,h=box
        if min(x,y)<0 or min(w,h)<=0 or x+w>info['width'] or y+h>info['height']:raise ValueError('Crop out of source bounds')
    for i,a in enumerate(pages):
        ax,ay,aw,ah=a['box']
        for b in pages[i+1:]:
            bx,by,bw,bh=b['box']
            if min(ax+aw,bx+bw)>max(ax,bx) and min(ay+ah,by+bh)>max(ay,by):raise ValueError('Page crops overlap')
    out.mkdir(parents=True)
    manifest={'version':1,'source':info,'transform':'integer crop translation only; no resize/rotation','pages':[]}
    with Image.open(image) as original:
        for i,page in enumerate(sorted(pages,key=lambda p:p['order']),1):
            x,y,w,h=page['box'];file=out/f'page-{i:02d}.png';crop=original.crop((x,y,x+w,y+h));crop.save(file)
            with Image.open(file) as saved:
                if saved.tobytes()!=crop.tobytes():raise ValueError('Crop pixels changed')
            manifest['pages'].append({**page,'file':str(file.resolve()),'crop_source':source_info(file),'to_source':[[1,0,x],[0,1,y],[0,0,1]]})
    write_json(out/'page-manifest.json',manifest);return manifest

def map_raw(image,manifest,inputs):
    info=source_info(image)
    if info!=manifest['source'] or manifest.get('transform')!='integer crop translation only; no resize/rotation':raise ValueError('Invalid mapping source or transform')
    if set(inputs)!=set(p['id'] for p in manifest['pages']):raise ValueError('Each verified page needs one raw OCR result')
    combined={'version':1,'source':info,'reading':'vertical-right-to-left','coverage':'partial','score':None,'annotations':[],'page_order':[p['id'] for p in manifest['pages']]}
    for page in manifest['pages']:
        crop=Path(page['file'])
        if source_info(crop)!=page['crop_source']:raise ValueError('Crop hash or dimensions changed')
        x,y,w,h=page['box']
        if any(type(v)!=int for v in page['box']) or min(x,y)<0 or min(w,h)<=0 or x+w>info['width'] or y+h>info['height']:raise ValueError('Invalid saved crop box')
        if page.get('position_reviewed') is not True or not page.get('reviewer'):raise ValueError('Saved page requires review')
        with Image.open(image) as original,Image.open(crop) as saved:
            if saved.size!=(w,h) or saved.tobytes()!=original.crop((x,y,x+w,y+h)).tobytes():raise ValueError('Crop pixels do not match their source region')
        if page['to_source']!=[[1,0,x],[0,1,y],[0,0,1]]:raise ValueError('Unsupported/tampered coordinate transform')
        data=convert(json.loads(Path(inputs[page['id']]).read_text(encoding='utf-8-sig')),crop)
        for item in data['annotations']:
            a=copy.deepcopy(item);a['id']=str(page['id'])+'-'+a['id'];a['page_id']=page['id'];a['crop_source_sha256']=page['crop_source']['sha256']
            for segment in a['segments']:
                sx,sy,sw,sh=segment['box'];segment['box']=[sx+x,sy+y,sw,sh];segment['polygon']=[[px+x,py+y] for px,py in segment['polygon']]
                segment['coordinate_mapping']={'type':'translation','offset':[x,y],'page_id':page['id'],'crop_source_sha256':page['crop_source']['sha256']}
            combined['annotations'].append(a)
    validate(combined,image);return combined

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','map']);p.add_argument('--image',required=True);p.add_argument('--regions');p.add_argument('--manifest');p.add_argument('--inputs');p.add_argument('--out',required=True);a=p.parse_args()
    if a.command=='prepare':prepare(a.image,json.loads(Path(a.regions).read_text(encoding='utf-8-sig')),a.out)
    else:
        if Path(a.out).exists():raise ValueError('Output exists')
        write_json(a.out,map_raw(a.image,json.loads(Path(a.manifest).read_text(encoding='utf-8-sig')),json.loads(Path(a.inputs).read_text(encoding='utf-8-sig'))))