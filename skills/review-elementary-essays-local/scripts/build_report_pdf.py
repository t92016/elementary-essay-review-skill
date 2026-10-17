"""Portable PDF from the same reviewed data; no Word COM or network."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def build_pdf(pages, report, output, font_path):
    font_name = "EssayCJK"
    pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=0))
    normal = ParagraphStyle("EssayNormal", fontName=font_name, fontSize=11.5,
                            leading=18, spaceAfter=8, wordWrap="CJK")
    heading = ParagraphStyle("EssayHeading", parent=normal, fontSize=16,
                             leading=23, spaceBefore=10, spaceAfter=10, keepWithNext=True)
    title = ParagraphStyle("EssayTitle", parent=normal, fontSize=22, leading=30, spaceAfter=16)
    small = ParagraphStyle("EssaySmall", parent=normal, fontSize=9, leading=14, textColor=colors.HexColor("#555555"))
    flow = []
    def para(text, style=normal):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)
    flow += [para(report.get("title","作文批改講評"),title),
             para("國小作文批改小老師 本機公開版",small),
             para(report.get("summary","依本次原文核對。")),
             para(report.get("scope","只處理提供頁面，疑字不判確定錯字。"))]
    labels = {"typo":"錯字訂正","praise":"佳句賞析","suggestion":"修改建議",
              "uncertain":"字跡待確認","existing":"既有老師註記"}
    for page in pages:
        flow += [PageBreak(),para(page["label"]+" 原圖批註",heading)]
        image = Image(str(page["annotated"]))
        scale = min(468/image.imageWidth, 530/image.imageHeight)
        image.drawWidth=image.imageWidth*scale;image.drawHeight=image.imageHeight*scale
        flow += [image,Spacer(1,10),para("原圖SHA256："+page["data"]["source"]["sha256"],small)]
        flow += [PageBreak(),para(page["label"]+" 逐項講評",heading)]
        for item in page["data"]["annotations"]:
            if item["status"] == "rejected":
                continue
            pending = item["status"]=="pending" and item["kind"]!="existing"
            flow += [para(item["id"]+" "+("待覆核候選" if pending else labels[item["kind"]]),heading),
                     para("原文："+item["quote"]),
                     para(("好在哪裡：" if item["kind"]=="praise" else "理由：")+item.get("reason",item["note"]))]
            if item.get("replacement"):
                flow.append(para(("替換候選（尚未確認）：" if pending else "訂正：")+item["replacement"]))
            if item.get("example"):
                flow.append(para(("修改候選（尚未確認）：" if pending else "修改參考：")+item["example"]))
            flow.append(para("狀態："+item["status"]+"；覆核者："+item.get("review",{}).get("reviewer","尚未覆核"),small))
        for item in page["data"].get("unlocated",[]):
            flow += [para(item["id"]+" 尚未可靠定位",heading),
                     para("上下文："+item["quote"]),para("待確認："+item["note"])]
    def footer(canvas, doc):
        canvas.saveState();canvas.setFont(font_name,9)
        canvas.drawRightString(540,30,"批改參考 "+str(doc.page))
        canvas.restoreState()
    target=Path(output)
    SimpleDocTemplate(str(target),pagesize=letter,rightMargin=72,leftMargin=72,
                      topMargin=54,bottomMargin=54,title=report.get("title","作文批改講評"),
                      author="t92016 - Local essay review").build(flow,onFirstPage=footer,onLaterPages=footer)
