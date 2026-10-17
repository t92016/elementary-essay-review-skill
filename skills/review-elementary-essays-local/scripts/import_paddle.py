"""Import PaddleOCR 3.x ORIGINAL-IMAGE results; never split line boxes into characters."""
import argparse
import json
import math
from pathlib import Path
from essay import source_info, validate, write_json

def convert(raw, image, reading="vertical-right-to-left"):
    if reading not in ["vertical-right-to-left","horizontal-left-to-right"]:raise ValueError("Unsupported reading direction")
    r = raw.get('res', raw)
    settings = r.get('model_settings', {})
    pre = r.get('doc_preprocessor_res', {}).get('model_settings', {})
    if settings.get('use_doc_preprocessor') is not False:
        if pre.get('use_doc_orientation_classify') is not False or pre.get('use_doc_unwarping') is not False:
            raise ValueError('Need evidence that document rotation/unwarping was disabled')
    if settings.get('use_textline_orientation') is not False:
        raise ValueError('Need evidence that textline orientation was disabled')
    texts, scores, polys = [r[k] for k in ['rec_texts', 'rec_scores', 'rec_polys']]
    if not len(texts)==len(scores)==len(polys):raise ValueError('unaligned OCR lists')
    result={'version':1,'source':source_info(image),'coverage':'partial','reading':reading,'score':None,'annotations':[]}
    # Preserve model output order. It is not assumed to be vertical reading order.
    for i,(text,score,poly) in enumerate(zip(texts,scores,polys)):
        if not text.strip():continue
        if len(poly)<4 or any(len(p)!=2 or any(type(v) not in [float,int] or not math.isfinite(v) for v in p) for p in poly):raise ValueError('invalid OCR polygon')
        xs,ys=zip(*poly); box=[min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]
        result['annotations'].append({'id':f'OCR{i+1}','kind':'uncertain','status':'pending',
            'segments':[{'text':text,'box':box,'polygon':poly,'origin':'paddleocr'}],
            'quote':text,'replacement':'','note':'OCR 行框候選，請核對原文、欄序及位置；不是錯字判定。',
            'source_layer':'unclassified','ocr_score':score,'review':{'text':False,'position':False,'judgment':False,'reviewer':''}})
    validate(result,image)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--image',required=True);p.add_argument('--out',required=True);p.add_argument('--reading',choices=['vertical-right-to-left','horizontal-left-to-right'],default='vertical-right-to-left');a=p.parse_args()
    if Path(a.out).exists():raise ValueError('output exists')
    write_json(a.out,convert(json.loads(Path(a.input).read_text(encoding='utf-8-sig')),a.image,a.reading))
if __name__=='__main__':main()