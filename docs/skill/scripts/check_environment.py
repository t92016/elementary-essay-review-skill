"""Report local capabilities without importing Paddle or starting a model."""
import argparse, importlib.metadata as metadata, json, os, platform, shutil, sys
from pathlib import Path

CORE = ('Pillow', 'python-docx')
OCR = ('Pillow', 'numpy', 'psutil', 'paddleocr', 'paddlepaddle', 'paddlex', 'opencv-contrib-python')

def inspect_environment(font=None, models=None, require_ocr=False):
    versions={}
    for name in dict.fromkeys(CORE+OCR):
        try: versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError: versions[name]=None
    font=Path(font) if font else (Path('C:/Windows/Fonts/msjh.ttc') if os.name=='nt' else None)
    font_error=None
    if font and font.is_file() and versions['Pillow']:
        try:
            from PIL import ImageFont
            ImageFont.truetype(str(font),16)
        except (OSError,ValueError) as exc: font_error=str(exc)
    else: font_error='Provide an existing Traditional Chinese font via --font'
    word=False
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,r'Word.Application\CLSID'): word=True
        except OSError: pass
    model_dirs={}
    if models:
        for part in ('det','rec'):
            path=Path(models)/f'PP-OCRv5_mobile_{part}_infer'
            entry={'directory':str(path),'inference_files_present':all((path/f).is_file() for f in ['inference.json','inference.pdiparams','inference.yml']),'pinned_hashes_verified':False}
            try:
                from fetch_mobile_models import verify
                pinned=json.loads((Path(__file__).resolve().parents[1]/'references/mobile-models.json').read_text(encoding='utf-8'))
                verify(path,pinned['models'][path.name]['files']);entry['pinned_hashes_verified']=True
            except (OSError,ValueError,KeyError) as exc: entry['verification_error']=str(exc)
            model_dirs[part]=entry
    issues=[]
    if sys.version_info<(3,10): issues.append('Python 3.10+ required')
    for name in CORE:
        if versions[name] is None: issues.append('Missing core dependency: '+name)
    if font_error: issues.append(font_error)
    core_ready=not issues
    ocr_issues=[]
    if os.name!='nt': ocr_issues.append('Bundled guarded OCR runner currently supports Windows only')
    for name in OCR:
        if versions[name] is None: ocr_issues.append('Missing OCR dependency: '+name)
    if not model_dirs or not all(v['inference_files_present'] and v['pinned_hashes_verified'] for v in model_dirs.values()): ocr_issues.append('Provide both local mobile model directories with inference.json/inference.pdiparams')
    if require_ocr: issues+=ocr_issues
    return {'python':sys.executable,'python_version':platform.python_version(),'platform':platform.platform(),'versions':versions,'font':str(font) if font else None,'core_ready':core_ready,'ocr_configuration_ready':not ocr_issues,'ocr_configuration_issues':ocr_issues,'models':model_dirs,'pdf_export_tools':{'word_registered':word,'libreoffice':shutil.which('soffice')},'issues':issues,'pass':not issues,'scope':'Configuration check only; no OCR inference, font glyph coverage or PDF layout verification'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--font');parser.add_argument('--models');parser.add_argument('--require-ocr',action='store_true');parser.add_argument('--out');args=parser.parse_args()
    report=inspect_environment(args.font,args.models,args.require_ocr)
    if args.out:
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['pass'] else 2
if __name__=='__main__':sys.exit(main())
