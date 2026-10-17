# 安裝流程

版本 1.0.0。請完整閱讀本文件，再執行適合目前平台的命令。不要只安裝 SKILL.md；必須取得 scripts/、references/、assets/、依賴清單及授權檔。

## 1 確認平台與 Python

完整功能：Windows 原生 x64，Python 3.12 x64，具可用繁體中文字型。OCR 在 CPU 執行，開始前須有至少2500 MiB可用記憶體；完整 Python／OCR 依賴需預留數 GB磁碟空間。不能從 WSL 執行 Windows 記憶體保護程式。

檢查 `py -3.12 --version`。若沒有 Python，從 https://www.python.org/downloads/ 安裝官方 Python Install Manager，再以 `pymanager install 3.12` 取得 3.12。請使用完整CPython安裝，不使用裁切的應用程式內嵌Python建立環境。若目前是舊版 py launcher，不能把它當 Install Manager；可使用已存在的 Python 3.12 x64絕對路徑。官方說明：https://docs.python.org/3/using/windows.html

其他系統可選 core 模式：產生核對工作台、原圖批註與文件；OCR runner 尚未跨平台驗收。沒有看圖／檔案／程序工具的純聊天 Agent 無法完成本機安裝。

## 2 下載安裝器

Windows PowerShell：

```powershell
$essaySite = 'https://t92016.github.io/elementary-essay-review-skill'
Invoke-WebRequest "$essaySite/install.py" -OutFile "$env:TEMP/essay-skill-install.py"
py -3.12 "$env:TEMP/essay-skill-install.py" --help
```

如果Agent的網頁讀取工具暫時無法讀新Pages，但本機工具可連網，可先下載文件再讀；不是只憑網址猜安裝步驟：

~~~powershell
Invoke-WebRequest "$essaySite/INSTALL.md" -OutFile "$env:TEMP/essay-skill-INSTALL.md"
Get-Content "$env:TEMP/essay-skill-INSTALL.md" -Raw -Encoding UTF8
~~~

此安裝器只用 Python 標準函式庫啟動，沒有 pip 前置依賴。可以先檢視程式碼。完整模式會下載約數十MB模型及較大的 Python 套件，依網路速度而異；不下載學生範例或生成式繪圖模型。

## 3 選擇全域技能目錄

| Agent | 預設目標 |
|---|---|
| Codex | ~/.agents/skills/review-elementary-essays-local |
| OpenCode | ~/.config/opencode/skills/review-elementary-essays-local |
| shared | ~/.agents/skills/review-elementary-essays-local，供支援此路徑的 Agent 共用 |

Codex 已有舊 ~/.codex/skills 同名技能時也會停止，避免產生不同版本的重複定義。選 --agent opencode 只新增 OpenCode 目錄，不覆寫其他 Agent 的技能。既有目標不會覆寫；不提供強制覆寫選項。

## 4 安裝完整 Windows 版

選擇有寫入權限、非雲端同步磁碟、**全路徑為ASCII字元**的穩定 runtime 路徑，例如 C:/EssayReview。若C槽根目錄不可寫，可選自己的其他本機ASCII路徑；不要使用會被清除的 Temp 作長期環境。技能本身仍放各Agent的全域目錄。

```powershell
py -3.12 "$env:TEMP/essay-skill-install.py" --agent codex --runtime C:/EssayReview
# OpenCode 改用：
# py -3.12 "$env:TEMP/essay-skill-install.py" --agent opencode --runtime C:/EssayReview-OpenCode
```

安裝器依序：
1. 讀取 Pages 的 release.json、下載固定版本 ZIP，核對大小與SHA256，拒絕不安全的解壓路徑。
2. 在 runtime/venv 建立隔離環境，依requirements-ocr-windows-lock.txt安裝已驗證的完整Windows依賴版本，不修改系統Python；core模式使用requirements-core.txt。
3. 從 references/mobile-models.json 列出的 Paddle 官方HTTPS來源下載兩個mobile模型；逐檔核對SHA，不接受變更或不完整的既有模型。
4. 執行環境檢查與合成圖片自測，保存報告。這階段不自動跑真實照片OCR，不把套件載入當字跡辨識通過。
5. 成功後才放入目標技能目錄，產生 installation.json 與 runtime/installation-state.json，記錄實際Python、模型、字型與測試結果。

若中途失敗，保留 runtime 與錯誤報告；沒有成功便不建立全域目標。只有本安裝器建立、有相同版本標記的 runtime 可以重新使用；不要隨意刪除其他專案環境，也不要無限制重試模型推論。

## 5 非Windows或只需要疊圖與文件

```text
python3 install.py --agent opencode --mode core --runtime /your/local/essay-review --font /your/cjk-font.ttf
```

core 需要Python 3.10+、Pillow、python-docx、ReportLab及可用中文字型，不安裝Paddle或下載模型。PDF需可嵌入的TrueType中文字型；部分CFF／OTF／TTC字型可能不能由ReportLab匯出，必須按報告處理，不假稱PDF已完成。沒有字型時先依目標系統取得合法可用字型，再指定 --font。

## 6 安裝後驗收

讀取 runtime/installation-state.json 中的 environment 與 self_test：
- 配置通過，不代表真實OCR或語意判斷通過。
- 開啟合成PNG，核對圈選、紅字、波浪線、括線；Word與PDF逐頁看中文、引文與例句。
- 再讀 [USAGE.md](USAGE.md)，用使用者自己的原圖執行一次有上限的mobile OCR，核對裁切、原字、座標，再產生成品。
- 確認Agent能找到技能；Codex未出現可開新對話或重新啟動。OpenCode請檢查技能權限與目錄。
- 不把「這台配置通過」說成其他電腦、所有字跡或所有模型已驗證。

如果只是手動從GitHub下載技能資料夾，仍須自行完成依賴、模型、字型、自測與安裝記錄，不能省略。
