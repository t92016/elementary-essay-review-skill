"""Synthetic overlay and document test; no OCR or student photos."""
import argparse,copy,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from essay import source_info
from case_tools import export_case

def test(out,font):
    out=Path(out)
    if out.exists():raise ValueError("Use a new self-test output directory")
    out.mkdir(parents=True)
    original=Image.new("RGB",(640,600),"white")
    draw=ImageDraw.Draw(original);f=ImageFont.truetype(font,28)
    for y,text in [(55,"我很高心。"),(170,"陽光像金色絲帶。"),(290,"今天很好。")]:
        draw.text((50,y),text,font=f,fill="#222222")
    draw.text((50,460),"原有老師紅筆",font=f,fill="#bb0000")
    def box(text,y):
        left,top,right,bottom=draw.textbbox((50,y),text,font=f)
        return [left,top,right-left,bottom-top]
    tx,ty,tr,tb=draw.textbbox((50+f.getlength("我很高"),55),"心",font=f)
    target=[tx,ty,tr-tx,tb-ty]
    source=out/"synthetic.png";original.save(source)
    review={"text":True,"position":True,"judgment":True,"reviewer":"Synthetic test fixture, not teacher approval"}
    def item(ident,kind,quote,box,note,**kw):
        return dict(id=ident,kind=kind,status="confirmed",source_layer="student",quote=quote,
                    segments=[dict(text=quote,box=box,origin="observed-crop")],note=note,
                    review=copy.deepcopy(review),**kw)
    p={"version":1,"source":source_info(source),"reading":"horizontal-left-to-right",
       "coverage":"partial","score":None,"annotations":[
        item("T1","typo","我很高心。",box("我很高心。",55),"合成測試：核對字框與近旁訂正。",
             target_box=target,target_anchor=dict(segment=0,start=3,text="心",origin="observed-crop"),
             replacement="興",label_xy=[225,58]),
        item("P1","praise","陽光像金色絲帶。",box("陽光像金色絲帶。",170),"以具體形象描寫陽光。",mark_side="below"),
        item("S1","suggestion","今天很好。",box("今天很好。",290),"補充讓你覺得好的事件。",mark_side="below",
             example="今天完成了作品，我很有成就感。"),
        item("U1","uncertain","〔疑字〕",[50,370,100,36],"字形不足，不新增紅筆。")] ,
       "unlocated":[{"id":"U2","quote":"〔尚未定位〕","note":"不猜位置。"}]}
    p["annotations"][-1].update(status="pending",review={"text":False,"position":False,"judgment":False,"reviewer":""})
    (out/"project.json").write_text(json.dumps(p,ensure_ascii=False),encoding="utf-8")
    case={"pages":[{"label":"合成測試頁","source":"synthetic.png","project":"project.json"}],
          "report":{"title":"作文批改合成自測","summary":"測試輸出與資料一致性，不能當手寫辨識或批改準確率。"}}
    (out/"case.json").write_text(json.dumps(case,ensure_ascii=False),encoding="utf-8")
    result=export_case(out/"case.json",out/"results",font)
    native=Image.open(out/"results/page-1/synthetic_原圖批註.png").convert("RGB")
    alpha=Image.open(out/"results/page-1/synthetic_透明批註層.png").getchannel("A")
    assert native.size==original.size
    for y in range(original.height):
        for x in range(original.width):
            if alpha.getpixel((x,y))==0:assert native.getpixel((x,y))==original.getpixel((x,y))
    assert result["pages"][0]["rendered"]==["T1","P1","S1"]
    assert "U1" in result["pages"][0]["skipped"]
    assert alpha.crop((225,58,260,95)).getbbox()
    assert result["reports"]["docx"]["status"]=="generated"
    # PDF may be unavailable with an unsupported user-supplied CJK font; report it explicitly.
    checks={"pass":True,"checks":["original pixels outside overlay","pending skipped",
            "single-character anchor and replacement","praise and suggestion lines","DOCX generated"],
            "pdf_status":result["reports"]["pdf"]["status"],"visual_review_completed":False,
            "ocr_inference_performed":False,"scope":"Synthetic engineering checks, not handwriting accuracy"}
    (out/"self-test.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")
    return checks
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--font",required=True)
    a=p.parse_args();print(json.dumps(test(a.out,a.font),indent=2))
