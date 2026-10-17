"""Offline, evidence-linked essay annotations. Python 3.10+, Pillow."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

KINDS = {'typo', 'uncertain', 'suggestion', 'praise', 'existing'}

def write_json(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def source_info(p):
    raw = Path(p).read_bytes()
    with Image.open(p) as im:
        return {'file': Path(p).name, 'sha256': hashlib.sha256(raw).hexdigest(),
                'width': im.width, 'height': im.height, 'frame': 'raw-pixels-top-left',
                'exif_orientation': im.getexif().get(274, 1)}

def validate_target(a, info):
    box=a.get('target_box')
    if box is not None:
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in [int,float] or not math.isfinite(v) for v in box):raise ValueError('invalid target box: '+a['id'])
        x,y,w,h=box
        if min(x,y)<0 or min(w,h)<=0 or x+w>info['width'] or y+h>info['height']:raise ValueError('target outside source: '+a['id'])
        if a['status']=='confirmed':
            anchor=a.get('target_anchor',{})
            index=anchor.get('segment');start=anchor.get('start');text=anchor.get('text')
            if type(index)!=int or index<0 or index>=len(a['segments']) or type(start)!=int or start<0 or not isinstance(text,str) or len(text)!=1 or anchor.get('origin') not in ['manual','paddleocr','observed-crop']:raise ValueError('confirmed target needs one original character and segment index: '+a['id'])
            segment=a['segments'][index]
            if segment['text'][start:start+1]!=text:raise ValueError('target character does not match original text: '+a['id'])
            sx,sy,sw,sh=segment['box']
            # This rejects unrelated circles; human review still checks all glyph edges.
            if not (sx<=x+w/2<=sx+sw and sy<=y+h/2<=sy+sh):raise ValueError('target center outside linked segment: '+a['id'])
    if a['status']=='confirmed' and a['kind']=='typo' and box is None:
        if len(a['segments'])!=1 or len(a['quote'])!=1:raise ValueError('a sentence typo needs an anchored single-character target: '+a['id'])

def validate(project, image):
    info = source_info(image)
    if info['exif_orientation'] != 1:
        raise ValueError('EXIF orientation must be normalized in a new source copy before annotation')
    for k in ['sha256', 'width', 'height', 'frame', 'exif_orientation']:
        if project['source'].get(k) != info[k]:
            raise ValueError('source mismatch: ' + k)
    if project.get('version') != 1:
        raise ValueError('unsupported project version')
    reading=project.get('reading','vertical-right-to-left')
    if reading not in ['vertical-right-to-left','horizontal-left-to-right']:raise ValueError('Unsupported reading direction')
    sides=['above','below'] if reading=='horizontal-left-to-right' else ['left','right']
    ids = set()
    for a in project['annotations']:
        if not isinstance(a.get('id'), str) or not a['id'] or a['id'] in ids:
            raise ValueError('empty/duplicate ID')
        ids.add(a['id'])
        if a.get('kind') not in KINDS or a.get('status') not in ['pending', 'confirmed', 'rejected']:
            raise ValueError('invalid kind/status: ' + a['id'])
        layer=a.get('source_layer')
        if layer is not None and layer not in ['student','teacher-existing','unclassified']:raise ValueError('Invalid source layer')
        if a['status']=='confirmed' and a['kind'] in ['typo','praise','suggestion'] and layer is not None and layer!='student':raise ValueError('Student feedback requires verified student text layer')
        if not isinstance(a.get('segments'), list) or not a['segments']:
            raise ValueError('missing source segments: ' + a['id'])
        for seg in a['segments']:
            b = seg.get('box')
            if not isinstance(b, list) or len(b) != 4 or any(type(v) not in [int, float] or not math.isfinite(v) for v in b):
                raise ValueError('invalid box: ' + a['id'])
            x, y, w, h = b
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > info['width'] or y+h > info['height']:
                raise ValueError('out of bounds: ' + a['id'])
            if not isinstance(seg.get('text'), str) or not seg['text'].strip():
                raise ValueError('missing verbatim text: ' + a['id'])
            if seg.get('origin') not in ['manual', 'paddleocr', 'observed-crop']:
                raise ValueError('unknown coordinate origin')
        if a.get('quote') != ''.join(s['text'] for s in a['segments']):
            raise ValueError('quote does not match linked segments: ' + a['id'])
        if not isinstance(a.get('note'), str) or not a['note'].strip():
            raise ValueError('missing note')
        if a['status'] == 'confirmed':
            rev = a.get('review', {})
            if not all(rev.get(k) is True for k in ['text', 'position', 'judgment']):
                raise ValueError('confirmation requires text, position and judgment review: ' + a['id'])
            if not isinstance(rev.get('reviewer'), str) or not rev['reviewer'].strip():
                raise ValueError('confirmation requires reviewer')
            if a['kind'] == 'typo' and ('〔' in a['quote'] or not a.get('replacement','').strip()):
                raise ValueError('uncertain transcription cannot be a confirmed typo')
        if a['kind'] in ['praise','suggestion']:
            if a.get('mark_side') is not None and a['mark_side'] not in sides:raise ValueError('Line side does not match reading direction')
            for segment in a['segments']:
                if segment.get('mark_side') is not None and segment['mark_side'] not in sides:raise ValueError('Segment line side does not match reading direction')
        validate_target(a,info)
    return info

def prepare(image, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out/'project.json').exists() or (out/'editor.html').exists():
        raise ValueError('output already exists; use a new directory')
    info = source_info(image)
    if info['exif_orientation'] != 1:
        raise ValueError('EXIF orientation must be normalized in a new source copy before annotation')
    project = {'version': 1, 'source': info, 'reading': 'vertical-right-to-left',
               'coverage': 'partial', 'annotations': [], 'score': None}
    write_json(out/'project.json', project)
    editor(image, project, out/'editor.html')

def editor(image, project, output):
    validate(project, image)
    mime = Image.open(image).get_format_mimetype()
    payload = {'project': project, 'image': 'data:'+mime+';base64,'+base64.b64encode(Path(image).read_bytes()).decode('ascii')}
    template = (Path(__file__).resolve().parents[1]/'assets'/'editor.html').read_text(encoding='utf-8')
    Path(output).write_text(template.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')), encoding='utf-8')

def wrap(text, font, width):
    lines = []; line = ''
    for ch in text:
        if ch == '\n' or (line and font.getlength(line+ch) > width):
            lines.append(line); line = ''
        if ch != '\n': line += ch
    if line: lines.append(line)
    return lines

def render(image, project, out, font_path):
    validate(project, image)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ['annotated.png', 'overlay.png', 'render-manifest.json']:
        if (out/name).exists(): raise ValueError('output already exists: '+name)
    source = Image.open(image).convert('RGBA')
    layer = Image.new('RGBA', source.size, (0,0,0,0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.truetype(font_path, 28)
    small = ImageFont.truetype(font_path, 24)
    accepted = [a for a in project['annotations'] if a['status'] == 'confirmed' and a['kind'] != 'existing']
    cards = []
    labels = {'typo':'錯字','uncertain':'待確認','suggestion':'修改建議','praise':'佳句賞析','existing':'原有註記'}
    for a in accepted:
        lines = wrap(a['id']+'【'+labels[a['kind']]+'】'+a['quote']+'\n'+a['note']+'\n座標：'+str([s['box'] for s in a['segments']]), small, 650)
        cards.append((a, lines, max(150, 50+len(lines)*36)))
    total = sum(c[2]+22 for c in cards)+90
    canvas = Image.new('RGBA', (source.width+740, max(source.height,total)), 'white')
    side = ImageDraw.Draw(canvas)
    side.text((source.width+32,20), '人工核對批註（測試預覽）', font=font, fill='#b91c1c')
    ycard = 82
    for a, lines, height in cards:
        color = '#d97706' if a['kind']=='uncertain' else '#c51624'
        side.rectangle((source.width+20,ycard,canvas.width-20,ycard+height), outline=color, width=2)
        yy = ycard+15
        for line in lines:
            side.text((source.width+34,yy),line,font=small,fill=color); yy += 36
        for seg in a['segments']:
            x,y,w,h = seg['box']; box=(round(x),round(y),round(x+w),round(y+h))
            if a['kind']=='typo' and not a.get('target_box'): draw.ellipse(box, outline=color, width=2)
            elif a['kind']=='typo': pass
            else: draw.rectangle(box, outline=color, width=2)
        if a.get('target_box'):
            x,y,w,h=a['target_box'];draw.ellipse((x,y,x+w,y+h),outline=color,width=2)
        # One leader per annotation; leaders outside the photo do not cover student ink.
        x,y,w,h = a['segments'][0]['box']
        # Do not draw long leaders through other student words. Only side-panel leaders.
        side.line([(source.width,y+h/2),(source.width+20,ycard+height/2)],fill=color,width=1)
        ycard += height+22
    canvas.alpha_composite(source,(0,0)); canvas.alpha_composite(layer,(0,0))
    layer.save(out/'overlay.png'); canvas.convert('RGB').save(out/'annotated.png')
    manifest = {'source': project['source'], 'rendered': [a['id'] for a in accepted],
                'skipped': [a['id'] for a in project['annotations'] if a not in accepted],
                'source_unchanged_outside_overlay': True, 'score': None,
                'note': 'Preview only; every rendered annotation has three review flags. No automated correctness guarantee.'}
    write_json(out/'render-manifest.json',manifest)
    return manifest

def evidence(image, project, out):
    validate(project,image)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    im=Image.open(image);index=[]
    for a in project['annotations']:
        safe=hashlib.sha256(a['id'].encode()).hexdigest()[:12];row={'id':a['id'],'files':[]}
        for i,segment in enumerate(a['segments']):
            x,y,w,h=segment['box'];box=(max(0,math.floor(x)-16),max(0,math.floor(y)-16),min(im.width,math.ceil(x+w)+16),min(im.height,math.ceil(y+h)+16))
            name=safe+'-'+str(i)+'.png';file=out/name
            if file.exists():raise ValueError('crop output exists')
            im.crop(box).save(file);row['files'].append(name)
        if a.get('target_box'):
            x,y,w,h=a['target_box'];box=(max(0,math.floor(x)-4),max(0,math.floor(y)-4),min(im.width,math.ceil(x+w)+4),min(im.height,math.ceil(y+h)+4))
            name=safe+'-target.png';file=out/name
            if file.exists():raise ValueError('crop output exists')
            im.crop(box).save(file);row.update(target_file=name,target_anchor=a.get('target_anchor'),target_source_box=list(box))
        index.append(row)
    write_json(out/'evidence-index.json',index)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','editor','validate','render','evidence']);p.add_argument('--image',required=True);p.add_argument('--project');p.add_argument('--out');p.add_argument('--font',default='C:/Windows/Fonts/msjh.ttc');a=p.parse_args()
    if a.command=='prepare':
        if not a.out:p.error('--out required')
        prepare(a.image,a.out);return
    if not a.project:p.error('--project required')
    data=json.loads(Path(a.project).read_text(encoding='utf-8-sig'))
    if a.command=='validate':print(json.dumps(validate(data,a.image),ensure_ascii=False));return
    if not a.out:p.error('--out required')
    if a.command=='editor':
        if Path(a.out).exists():raise ValueError('output exists')
        editor(a.image,data,a.out)
    if a.command=='render':print(json.dumps(render(a.image,data,a.out,a.font),ensure_ascii=False))
    if a.command=='evidence':evidence(a.image,data,a.out)

if __name__=='__main__':main()