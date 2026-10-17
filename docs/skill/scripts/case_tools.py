"""Local case preparation, guarded mobile OCR and evidence-linked export."""
import argparse, hashlib, importlib.util, json, math, platform, sys
from pathlib import Path

FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "C:/Windows/Fonts/msjh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)

def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def find_font(requested=None):
    from PIL import ImageFont
    paths = (requested,) if requested else FONT_CANDIDATES
    for name in paths:
        if not name or not Path(name).is_file():
            continue
        try:
            font = ImageFont.truetype(str(name), 24)
            family = font.getname()[0]
            return str(Path(name).resolve()), family
        except (OSError, ValueError):
            if requested:
                raise ValueError("Cannot load the supplied font")
    raise ValueError("No loadable CJK font found; supply --font. Glyphs need visual review.")

def probe(requested=None):
    modules = {name: bool(importlib.util.find_spec(name)) for name in ("PIL", "docx", "reportlab")}
    result = {"python": platform.python_version(), "modules": modules,
              "ocr_performed": False, "network_used": False,
              "font": None,
              "cjk_glyphs_visually_verified": False}
    if modules["PIL"]:
        try:
            path, family = find_font(requested)
            result["font"] = {"path": path, "family": family, "loaded": True}
        except Exception as exc:
            result["font_error"] = str(exc)
    result["png_possible"] = bool(modules["PIL"] and result["font"])
    result["docx_package_present"] = modules["docx"]
    result["pdf_package_present"] = modules["reportlab"]
    result["note"] = "Presence is not proof of successful export, CJK glyph coverage or annotation accuracy."
    return result

def strict_project(project, source):
    from essay import validate
    info = validate(project, source)
    if project["source"].get("file") != Path(source).name:
        raise ValueError("Source filename mismatch")
    if project.get("coverage") not in ("partial", "full"):
        raise ValueError("Specify coverage=partial or full")
    if project.get("score") is not None:
        raise ValueError("Keep per-page score null; use the case report score")
    ids = set()
    for item in project["annotations"]:
        ids.add(item["id"])
        if item["kind"] == "uncertain" and item["status"] == "confirmed":
            raise ValueError("Uncertain glyphs cannot be confirmed: " + item["id"])
        if item["status"] == "confirmed" and item["kind"] != "existing":
            if item.get("source_layer") != "student":
                raise ValueError("Verified student source layer is required")
            if item["kind"] == "typo":
                if not item.get("target_box") or not item.get("target_anchor") or not item.get("label_xy"):
                    raise ValueError("Typo requires target box, original character anchor and nearby label")
                x,y,w,h = item["target_box"]
                if x < 3 or y < 3 or x+w > info["width"]-3 or y+h > info["height"]-3:
                    raise ValueError("Circle would be clipped at source edge")
    if not isinstance(project.get("unlocated", []), list):
        raise ValueError("unlocated must be a list")
    for item in project.get("unlocated", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in ids:
            raise ValueError("Duplicate or invalid unlocated ID")
        if not isinstance(item.get("quote"), str) or not isinstance(item.get("note"), str) or not item["note"].strip():
            raise ValueError("Unlocated item requires verbatim context and uncertainty note")
        if any(k in item for k in ("box", "target_box", "segments", "replacement")):
            raise ValueError("unlocated is a text uncertainty record, not an unverified correction")
        ids.add(item["id"])
    return ids

def score_summary(report, projects):
    score = report.get("score")
    if score is None:
        return "未提供總分；請依題目、年級、完整性與疑字範圍判斷是否適合評分。"
    if report.get("complete_work") is not True or any(p["coverage"] != "full" for p in projects):
        raise ValueError("Score requires complete_work=true and full coverage of every supplied page")
    values = {}
    for key in ("content", "structure", "language"):
        value = score.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 5 or value*2 != round(value*2):
            raise ValueError("Score must be 0..5 in half-point increments")
        reason = score.get("reasons", {}).get(key)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Each score needs evidence-linked reasons")
        values[key] = value
    total = values["content"]*10 + values["structure"]*5 + values["language"]*5
    return ("依本技能規準的建議分數：" + str(total) + "/100。\n"
            + "內容：" + str(values["content"]) + "/5；" + score["reasons"]["content"] + "\n"
            + "結構：" + str(values["structure"]) + "/5；" + score["reasons"]["structure"] + "\n"
            + "用字：" + str(values["language"]) + "/5；" + score["reasons"]["language"])

def report_markdown(pages, report):
    lines = ["# " + report.get("title", "作文批改講評"), "",
             "國小作文批改小老師 本機公開版；本次資料由執行者核對。", "",
             report.get("summary", "依原文核對；請連同原圖與待確認項閱讀。"), "",
             report.get("scope", "只處理本次提供頁面，不將疑字當確定錯字。"), ""]
    names = {"typo":"錯字訂正", "praise":"佳句", "suggestion":"修改建議", "uncertain":"字跡待確認", "existing":"既有老師註記"}
    for page in pages:
        p = page["data"]
        lines.extend(["## " + page["label"], "", "來源SHA256：" + p["source"]["sha256"], ""])
        for a in p["annotations"]:
            if a["status"] == "rejected":
                continue
            pending = a["status"] == "pending" and a["kind"] != "existing"
            lines.extend(["### " + a["id"] + " " + ("待覆核候選" if pending else names[a["kind"]]), "",
                          "原文：" + a["quote"], "理由：" + a.get("reason", a["note"]),
                          "位置：" + json.dumps([s["box"] for s in a["segments"]], ensure_ascii=False),
                          "狀態：" + a["status"] + "；覆核者：" + a.get("review", {}).get("reviewer", "尚未覆核")])
            if a.get("replacement"):
                lines.append(("替換候選（未確認）：" if pending else "訂正：") + a["replacement"])
            if a.get("example"):
                lines.append(("修改候選（未確認）：" if pending else "修改參考：") + a["example"])
            lines.append("")
        for a in p.get("unlocated", []):
            lines.extend(["### " + a["id"] + " 尚未可靠定位", "", "上下文：" + a["quote"], "待確認：" + a["note"], ""])
    return "\n".join(lines)

def export_case(case_path, out, requested_font=None, font_family=None):
    from essay import editor, evidence
    from render_teacher import render_teacher
    file = Path(case_path).resolve()
    case = read(file)
    if not isinstance(case.get("pages"), list) or not case["pages"]:
        raise ValueError("Case needs a non-empty pages list")
    pages, all_ids = [], set()
    for number, page in enumerate(case["pages"], 1):
        source = (file.parent / page["source"]).resolve()
        project_path = (file.parent / page["project"]).resolve()
        project = read(project_path)
        ids = strict_project(project, source)
        if ids & all_ids:
            raise ValueError("IDs must be unique across all pages and unlocated records")
        all_ids.update(ids)
        pages.append({"label": str(page.get("label", "第"+str(number)+"頁")),
                      "source": source, "data": project})
    report = dict(case.get("report", {}))
    grade = score_summary(report, [p["data"] for p in pages])
    report["summary"] = report.get("summary", "依原文與座標核對的批改參考。") + "\n\n" + grade
    font, detected_family = find_font(requested_font)
    report["font_family"] = font_family or detected_family
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Output directory already exists; use a new directory")
    out.mkdir(parents=True)
    products = {}
    manifest = {"skill": "review-elementary-essays-local", "version": "1.0.0",
                "pages": [], "reports": products, "font": {"path": font, "family": report["font_family"]},
                "ocr_performed": False, "network_used": False,
                "visual_review_completed": False,
                "note": "Generated files require visual review; code does not certify judgment correctness."}
    case_export = {"pages": []}
    unlocated = []
    for number, page in enumerate(pages, 1):
        directory = out / ("page-"+str(number))
        directory.mkdir()
        dump(directory/"project.json", page["data"])
        evidence(page["source"], page["data"], directory/"evidence")
        editor(page["source"], page["data"], directory/"editor.html")
        render_teacher(page["source"], page["data"], directory, font,
                       page["label"]+" 紅筆批改參考",
                       "詳解見隨附講評；待確認與既有老師註記不新增紅筆。")
        prefix = Path(page["data"]["source"]["file"]).stem
        page["annotated"] = directory/(prefix+"_原圖批註.png")
        native_manifest = read(directory/(prefix+"_render-manifest.json"))
        manifest["pages"].append({"label": page["label"], "source": page["data"]["source"],
                                  "project": str((directory/"project.json").relative_to(out)),
                                  "rendered": native_manifest["rendered"],
                                  "skipped": native_manifest["skipped"],
                                  "outputs": native_manifest["outputs"]})
        case_export["pages"].append({"label": page["label"], "source": str(page["source"]),
            "project": str(directory/"project.json"), "image": str(page["annotated"]),
            "evidence_dir": str(directory/"evidence")})
        unlocated.extend(dict(item, page=page["label"]) for item in page["data"].get("unlocated", []))
    report["unlocated"] = unlocated
    case_export["report"] = report
    dump(out/"case-export.json", case_export)
    (out/"講評.md").write_text(report_markdown(pages, report), encoding="utf-8")
    products["markdown"] = {"status": "generated", "file": "講評.md"}
    for key, module, filename in (("docx","docx","講評.docx"), ("pdf","reportlab","講評.pdf")):
        if importlib.util.find_spec(module) is None:
            products[key] = {"status": "unavailable", "reason": module+" is not installed; no installation attempted"}
            continue
        try:
            if key == "docx":
                from build_teacher_docx import build_case
                build_case(out/"case-export.json", out/filename, report)
            else:
                from build_report_pdf import build_pdf
                build_pdf(pages, report, out/filename, font)
            products[key] = {"status": "generated", "file": filename, "visual_review_completed": False}
        except Exception as exc:
            products[key] = {"status": "failed", "reason": str(exc)}
            # A failed export never becomes a valid downloadable report.
            if (out/filename).exists():
                (out/filename).unlink()
    manifest["files"] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(out.rglob("*")) if p.is_file()}
    dump(out/"output-manifest.json", manifest)
    return manifest

def run_ocr(image,out,models,cache,reading):
    from resource_guard import supervise
    from check_environment import inspect_environment
    if platform.system()!='Windows':raise ValueError('Guarded OCR requires native Windows')
    report=inspect_environment(models=models,require_ocr=True)
    if not report['pass']:raise ValueError('OCR configuration not ready: '+str(report['issues']))
    output=Path(out).resolve()
    if output.exists():raise ValueError('OCR output exists; use a new directory')
    scripts=Path(__file__).resolve().parent
    command=[sys.executable,'-X','utf8',str(scripts/'run_paddle.py'),'--image',str(Path(image).resolve()),
             '--out',str(output/'runs'),'--models',str(Path(models).resolve()),
             '--cache',str(Path(cache).resolve()),'--variant','mobile','--phase','refined']
    code=supervise(command,output/'ocr-supervisor.json',rss_mb=1200,minimum_available_mb=2500,timeout=180)
    if code!=0:raise RuntimeError('OCR stopped; read ocr-supervisor.json and logs. No automatic retry.')
    from import_paddle import convert
    from essay import editor
    project=convert(read(output/'runs/refined/raw-1.json'),image,reading)
    dump(output/'candidates.json',project);editor(image,project,output/'candidate-editor.html')
    return {'status':'candidates_only','project':str(output/'candidates.json'),'annotations_pending':len(project['annotations']),
            'ocr_performed':True,'student_errors_confirmed':0}

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("probe"); check.add_argument("--font")
    prep = sub.add_parser("prepare"); prep.add_argument("--image", required=True); prep.add_argument("--out", required=True)
    exp = sub.add_parser("export"); exp.add_argument("--case", required=True); exp.add_argument("--out", required=True)
    exp.add_argument("--font"); exp.add_argument("--font-family")
    ocr = sub.add_parser("ocr")
    for key in ("image","out","models","cache"):ocr.add_argument("--"+key,required=True)
    ocr.add_argument("--reading",choices=("vertical-right-to-left","horizontal-left-to-right"),default="vertical-right-to-left")
    args = parser.parse_args()
    if args.command == "probe":
        result = probe(args.font)
    elif args.command == "prepare":
        from essay import prepare
        prepare(args.image, args.out)
        result = {"status": "prepared", "ocr_performed": False, "out": args.out}
    elif args.command == "ocr":
        result = run_ocr(args.image,args.out,args.models,args.cache,args.reading)
    else:
        result = export_case(args.case, args.out, args.font, args.font_family)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
