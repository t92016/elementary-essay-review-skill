"""Deterministic teacher-style marks from verified original-photo coordinates."""
from pathlib import Path
import math,json,argparse
from PIL import Image,ImageDraw,ImageFont
from essay import validate,write_json,wrap

LABELS={'typo':'錯字訂正','praise':'佳句賞析','suggestion':'修改建議','uncertain':'待確認','existing':'原有註記'}

def render_teacher(image,project,out,font_path=None,title_text=None,footer_text=None):
    validate(project,image)
    reading=project.get('reading','vertical-right-to-left')
    if reading not in ['vertical-right-to-left','horizontal-left-to-right']:raise ValueError('Unsupported reading direction')
    horizontal=reading=='horizontal-left-to-right'
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    source=Image.open(image).convert('RGBA')
    overlay=Image.new('RGBA',source.size,(0,0,0,0));d=ImageDraw.Draw(overlay)
    label_size=max(12,round(23*min(1,source.width/1703)))
    label_font=ImageFont.truetype(font_path,label_size)
    font=ImageFont.truetype(font_path,27);small=ImageFont.truetype(font_path,23);title=ImageFont.truetype(font_path,36)
    confirmed=[a for a in project['annotations'] if a['status']=='confirmed' and a['kind']!='existing']
    prefix=Path(project['source']['file']).stem
    for a in confirmed:
        if a['kind']=='typo' and not a.get('label_xy'):
            raise ValueError('confirmed typo needs visually reviewed nearby replacement label: '+a['id'])
        if a.get('label_xy'):
            xy=a['label_xy'];label=a.get('local_label',a.get('replacement') or a['id'])
            if len(xy)!=2 or any(type(v) not in [int,float] or not math.isfinite(v) for v in xy):raise ValueError('invalid label coordinates')
            if a['kind']=='typo' and label!=a['replacement']:raise ValueError('typo label must equal replacement')
            bounds=label_font.getbbox(label)
            if xy[0]+bounds[0]<0 or xy[1]+bounds[1]<0 or xy[0]+bounds[2]>source.width or xy[1]+bounds[3]>source.height:raise ValueError('replacement label out of bounds')
    cards=[]
    for a in confirmed:
        lines=wrap(a['id']+' '+LABELS[a['kind']]+'\n原文：'+a['quote']+'\n'+a.get('short_note',a['note']),small,615)
        if a['kind']=='typo':lines+=wrap('訂正：'+a['replacement'],font,615)
        cards.append((a,lines,max(130,len(lines)*34+32)))
    h=max(source.height+190,sum(c[2]+16 for c in cards)+190)
    canvas=Image.new('RGBA',(source.width+750,h),'white');cd=ImageDraw.Draw(canvas)
    cd.text((40,25),title_text or prefix+' 紅筆批改參考',font=title,fill='black')
    cd.text((40,78),'紅色：已核對佳句、訂正與建議　待確認項不新增紅筆',font=small,fill='#555555')
    ycard=140
    for a,lines,height in cards:
        color='#c41624' if a['kind']!='uncertain' else '#bd6900'
        for seg in a['segments']:
            x,y,w,hbox=seg['box']
            if a['kind']=='typo' and not a.get('target_box'):d.ellipse((x-3,y-3,x+w+3,y+hbox+3),outline=color,width=3)
            elif a['kind']=='uncertain':d.rectangle((x-2,y-2,x+w+2,y+hbox+2),outline=color,width=2)
            elif a['kind']=='praise':
                side=seg.get('mark_side',a.get('mark_side','below' if horizontal else 'right'))
                if side not in (['above','below'] if horizontal else ['left','right']):raise ValueError('Invalid wave side for reading direction')
                if horizontal:
                    edge=y-4 if side=='above' else y+hbox+4
                    pts=[(x+v,edge+2*math.sin(v/7)) for v in range(0,round(w)+1,2)]
                else:
                    edge=x-5 if side=='left' else x+w+5
                    pts=[(edge+3*math.sin(v/7),y+v) for v in range(0,round(hbox)+1,2)]
                if any(px<1 or py<1 or px>source.width-2 or py>source.height-2 for px,py in pts):raise ValueError('Wave outside source; choose another side')
                d.line(pts,fill=color,width=2 if horizontal else 3)
            elif a['kind']=='suggestion':
                if horizontal:
                    side=seg.get('mark_side',a.get('mark_side','below'))
                    if side not in ['above','below']:raise ValueError('Invalid bracket side for reading direction')
                    yy=y-4 if side=='above' else y+hbox+4;cap=4 if side=='above' else -4
                    pts=[(x,yy+cap),(x,yy),(x+w,yy),(x+w,yy+cap)]
                    if any(px<1 or py<1 or px>source.width-2 or py>source.height-2 for px,py in pts):raise ValueError('Horizontal bracket outside source; choose another side')
                    d.line(pts,fill=color,width=2)
                else:
                    side=seg.get('mark_side',a.get('mark_side','left'))
                    if side not in ['left','right']:raise ValueError('Invalid bracket side for reading direction')
                    xx=x-5 if side=='left' else x+w+5;cap=10 if side=='left' else -10
                    pts=[(xx+cap,y),(xx,y),(xx,y+hbox),(xx+cap,y+hbox)]
                    if any(px<2 or py<2 or px>source.width-3 or py>source.height-3 for px,py in pts):raise ValueError('Vertical bracket outside source; choose another side')
                    d.line(pts,fill=color,width=3)
        if a.get('target_box'):
            tx,ty,tw,th=a['target_box']
            if min(tx,ty)<0 or min(tw,th)<=0 or tx+tw>source.width or ty+th>source.height:
                raise ValueError('invalid correction target')
            d.ellipse((tx-2,ty-2,tx+tw+2,ty+th+2),outline=color,width=3)
        # Explicitly measured empty positions may be supplied for nearby labels.
        if a.get('label_xy'):
            d.text(tuple(a['label_xy']),a.get('local_label',a.get('replacement') or a['id']),font=label_font,fill=color)
        if a.get('marker_xy'):
            mx,my=a['marker_xy'];bounds=label_font.getbbox(a['id'])
            if min(mx,my)<0 or mx+bounds[2]>source.width or my+bounds[3]>source.height:raise ValueError('Marker outside source')
            d.text((mx,my),a['id'],font=label_font,fill=color)
        yy=ycard
        for line in lines:
            cd.text((source.width+80,yy),line,font=small,fill=color);yy+=34
        ycard+=height+16
    canvas.alpha_composite(source,(35,130));canvas.alpha_composite(overlay,(35,130))
    cd=ImageDraw.Draw(canvas)
    cd.text((40,source.height+145),footer_text or '詳解見隨附講評；請依原文與座標覆核批註。',font=small,fill='#555555')
    Image.alpha_composite(source,overlay).convert('RGB').save(out/(prefix+'_原圖批註.png'))
    canvas.convert('RGB').save(out/(prefix+'_紅筆講評.png'))
    overlay.save(out/(prefix+'_透明批註層.png'))
    # Each page keeps its own evidence; the legacy alias only describes the last render.
    import hashlib
    record={'source':project['source'],'reading':reading,'offset':[35,130],'rendered':[a['id'] for a in confirmed],'original_size':list(source.size),'canvas_size':list(canvas.size),'nearby_label_font_size':label_size,'known_new_typos':sum(a['kind']=='typo' for a in confirmed),'skipped':[a['id'] for a in project['annotations'] if a not in confirmed]}
    record['annotation_sha256']=hashlib.sha256(json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    record['outputs']={suffix:hashlib.sha256((out/(prefix+suffix)).read_bytes()).hexdigest() for suffix in ['_原圖批註.png','_紅筆講評.png','_透明批註層.png']}
    write_json(out/(prefix+'_render-manifest.json'),record)
    write_json(out/'render-manifest.json',record)
    return canvas
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--project',required=True);p.add_argument('--out',required=True);p.add_argument('--font',required=True);p.add_argument('--title');p.add_argument('--footer');a=p.parse_args()
    render_teacher(a.image,json.loads(Path(a.project).read_text(encoding='utf-8-sig')),a.out,a.font,a.title,a.footer)
