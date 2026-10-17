# 國小作文批改小老師 本機版

由 Codex 桌面版開發的 Agent Skill，供 Codex、OpenCode 等具本機讀檔、看圖與 Python 執行能力的 Agent 使用。公開版將已測的原圖批註程式獨立封裝，不會修改開發者的本機定稿。

- **分享與安裝入口**：https://t92016.github.io/elementary-essay-review-skill/
- **Agent 請先讀完整安裝流程**：[INSTALL.md](INSTALL.md)
- **批改操作與輸出**：[USAGE.md](USAGE.md)
- **測試與限制**：[VALIDATION.md](VALIDATION.md)
- **套件來源與授權**：[NOTICE.md](NOTICE.md)
- **技能位置**：[skills/review-elementary-essays-local/SKILL.md](skills/review-elementary-essays-local/SKILL.md)

## 可以做什麼

| 功能 | 實際處理方式 |
|---|---|
| 錯字訂正 | 核對原字與單字框，圈選原字，在量測留白處寫紅色正字 |
| 佳句 | 依直排／橫排畫波浪線，引用原句說明好在哪裡 |
| 修改建議 | 用括線標示原句，提供原因、如何修改與參考例句 |
| 長講評 | 原圖外側短評，以及同份資料的 Markdown、可編輯 Word、PDF |
| 人工修正 | 內嵌原圖的離線 HTML 工作台、JSON、原字裁切與透明批註層 |
| OCR | 固定 PP-OCRv5 mobile 偵測／辨識模型，保留原始候選與原圖座標 |

這不是無需覆核的自動改字系統。OCR 不等於學生錯字；不確定字不扣分、不新增紅圈，不生成或重畫學生筆跡。原圖既有老師紅筆保留並另列來源。

## 相容環境

完整 OCR 流程先支援 **Windows 原生 x64、Python 3.12**。PaddleOCR 使用 CPU 一執行緒、batch 1、外部 RSS／逾時監控及 Windows 記憶體硬上限。macOS／Linux／WSL 僅提供 core 流程；目前不宣稱 Windows OCR 保護程式可直接跨系統運作。

技能格式可由 Codex／OpenCode 讀取；Agent 必須具備看圖或查看裁切的能力與必要本機執行權限。格式相容不等於每個模型的語意批改品質相同。安裝後仍需原圖及成品覆核。

## 給對方 Agent 的提示

> 請讀取 https://t92016.github.io/elementary-essay-review-skill/INSTALL.md ，將「國小作文批改小老師」安裝到我的全域技能目錄。先確認作業系統、Python 3.12 x64與目標路徑；保留已存在的技能，使用獨立環境、固定官方 mobile 模型及雜湊核對。安裝後執行環境檢查和合成自測，再按 USAGE.md 用我的照片核對原文、座標和批改結果。不要把模型候選當確定錯字，不要重畫學生文字，也不要宣稱未做的測試已通過。

GitHub Pages 是靜態文件與套件下載入口，**不會在瀏覽器內執行 OCR，也不接收作文照片**。模型經本入口指引，直接從 Paddle 官方 HTTPS 主機下載；不放入 Git。Python 套件由 PyPI 安裝到本機隔離環境。安裝不是瀏覽網址就自動完成，而由有權限的 Agent／使用者依文件執行。
