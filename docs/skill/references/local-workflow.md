# 安裝與本機執行

完整安裝文件：https://t92016.github.io/elementary-essay-review-skill/INSTALL.md
批改命令：https://t92016.github.io/elementary-essay-review-skill/USAGE.md

以installation.json記錄的python、models及font為準。Python套件與模型在runtime，案件資料在使用者指定的技能目錄之外，不把照片存進全域技能。需要穩定、本機、ASCII路徑；勿依賴暫存或雲端同步環境。

完整OCR為Windows原生x64／Python3.12 CPU。case_tools.py ocr 呼叫獨立resource_guard.py與run_paddle.py：CPU1、batch1、mobile、RSS1200MiB、commit1800MiB、最低可用2500MiB、180秒。不得自動切server、無限制重試或把配置通過當推論成功。

先執行 scripts/check_environment.py --require-ocr --models 實際模型路徑。Core模式不加require-ocr，需Pillow／python-docx／ReportLab及可用字型；PDF另需可嵌入TrueType字型。check_environment只檢查配置，不證明中文字齊全、語意正確或文件版面通過。

常用介面（python都換成真正隔離Python）：
- python scripts/case_tools.py probe
- python scripts/case_tools.py prepare --image 原圖.png --out 新工作目錄
- python scripts/case_tools.py ocr --image 原圖.png --out 新OCR目錄 --models 模型路徑 --cache 快取路徑
- python scripts/case_tools.py export --case case.json --out 新成品目錄 --font 繁體中文字型
- python scripts/self_test.py --out 新合成測試目錄

批改前先看原圖；OCR產生的candidates.json只是pending候選。定位、原字、判斷核對後才能confirmed。工作台匯出修正JSON後再重新看圖，不沿用修改前核對旗標。
