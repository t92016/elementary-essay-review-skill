# 批改操作與成品

使用 installation.json 中記錄的 python 路徑，勿假定系統 python 是安裝環境。以下以Windows完整模式及Codex預設目錄為例；OpenCode改成自己的技能路徑。

```powershell
$essayPython = 'C:/EssayReview/venv/Scripts/python.exe'
$essaySkill = "$HOME/.agents/skills/review-elementary-essays-local"
```

安裝後可在Codex新對話呼叫 $review-elementary-essays-local，或請OpenCode「載入review-elementary-essays-local技能批改附件作文」。OpenCode需允許skill與必要的讀檔／Python工具。使用支援看圖的模型；只支援文字的模型不能核對手寫原字。

## 1 準備原圖

保留學生原檔。先看頁數、直排／橫排與既有老師註記。EXIF方向不是1時另存已旋正副本，對此新來源建立座標，不能覆寫原照。學生素材與案件輸出放技能目錄之外，例如使用者指定的案件資料夾。

```powershell
& $essayPython "$essaySkill/scripts/case_tools.py" prepare --image 'C:/Essays/page1.png' --out 'C:/Essays/case1/page-work'
```

這只建立來源SHA、空白project.json及內嵌原圖的工作台，不會自動判錯。沒有可靠座標的意見保留文字清單，不猜框。

## 2 選擇先執行OCR候選

完整Windows模式，模型由安裝器取得，輸出須為新目錄：

```powershell
& $essayPython "$essaySkill/scripts/case_tools.py" ocr --image 'C:/Essays/page1.png' --out 'C:/Essays/case1/ocr1' --models 'C:/EssayReview/models' --cache 'C:/EssayReview/cache'
```

橫排另加 --reading horizontal-left-to-right。外部監控RSS1200 MiB、系統可用2500 MiB與180秒逾時；Paddle程序commit上限1800 MiB、CPU1、batch1。失敗保留ocr-supervisor.json及stdout/stderr，不自動切server或無限重試。

成功產生原始結果、模型／來源記錄、candidates.json及候選工作台。所有候選都是pending、unclassified；辨識分數不是錯字機率。OCR行框不能按字數等分為字框。

## 3 核對與批改

Agent須看原圖與原字裁切：核對文字、位置、批改判斷三項，明記實際覆核者。Gemini／Codex／OpenCode自行看圖不等於教師已確認。詳見技能references/annotation-format.md。

- 錯字：完整原句＋原字單字框＋原字連結＋正字＋量測留白的紅字位置。
- 佳句：引用實際原句，波浪線標片段，說明細節或修辭如何發揮作用。
- 修改句：括線標片段，附原因與保留原意的參考例句。
- 疑字：pending，不新增紅圈、不扣分；無座標列unlocated。既有老師紅筆用existing另記。
- 圖像製作只用原圖疊透明層，不生成或重畫學生文字。

工作台可下載／開啟editor.html調整框與紅字、匯出JSON；修改後重設及重做覆核。通常由Agent完成主要批改，老師覆核疑義與位置，不要求老師每篇從零手動畫框。

## 4 建立單頁或多頁案件

新建 case.json（相對路徑以本清單目錄為基準）：

```json
{
 "pages":[{"label":"第一頁","source":"page1.png","project":"page1-reviewed.json"}],
 "report":{"title":"作文批改講評","summary":"總評，需依實際原文撰寫。","scope":"寫明頁數、原文核對與疑字範圍。"}
}
```

多頁就逐項加入pages，不能漏續頁。各頁批註與unlocated的ID全案唯一；每頁只使用自己的原圖與座標。

## 5 輸出紅筆圖片與文件

```powershell
& $essayPython "$essaySkill/scripts/case_tools.py" export --case 'C:/Essays/case1/case.json' --out 'C:/Essays/case1/results' --font 'C:/Windows/Fonts/msjh.ttc'
```

產生各頁原尺寸批註PNG、帶圖外短評PNG、透明層、裁切證據、JSON、工作台，以及Markdown、Word和可用時的PDF。PDF直接由相同資料排版，不依賴Word COM。output-manifest.json分別記錄generated／unavailable／failed；檔案產生不代表已看完版面。字型或PDF匯出失敗時保留文字與Word，明列原因。

每項校對編號與原句、理由、例句一致。原圖在批註外的像素不改變，不能把增加旁欄後的完整圖片說成原尺寸。先看每頁原字裁切與圈線，再看所有文件頁面。給使用者真實可下載檔案，不把重新命名副檔名當轉檔。

## 評分

依題目與已知年級判斷；不知道年級不猜。預設內容50%、結構25%、用字25%，各0–5分、0.5增量：總分=內容×10+結構×5+用字×5。report.score填content／structure／language與各項reasons；有完整原文才填complete_work=true、各頁coverage=full。不能因照片模糊扣分，缺頁或疑字嚴重影響理解就暫緩總分。詳細範例見技能references/rubric.md。
