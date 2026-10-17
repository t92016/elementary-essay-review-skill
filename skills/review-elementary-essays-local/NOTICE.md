# 來源與第三方項目

此公開發行由t92016透過Codex桌面版製作。Python與HTML程式是在本機開發與驗證過程中撰寫；公開的Skill指令、安裝文件與評分描述另行整理，未把原始Gem指令檔整包公開。

最初工作流程參考來源是使用者持有的Gem「國小作文批改小老師」，當時來源註記為「阿玉老師分享」。此註記是來源說明，不宣稱已取得第三方原始Gem文字的再授權。本repo不附該原始Gem套件、學生照片或私人成品。

本repo自行撰寫的程式與文件依LICENSE提供；第三方軟體、模型、字型各自依其授權。本repo不把第三方內容改授權成MIT。

- PaddleOCR／PaddlePaddle／PaddleX：由PyPI與Paddle官方取得；PaddleOCR專案授權見 https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE
- 固定mobile模型來源與SHA：skills/review-elementary-essays-local/references/mobile-models.json；從官方HTTPS主機直接下載，不在repo重傳模型。
- Pillow、python-docx、ReportLab、NumPy、psutil、OpenCV及間接依賴由pip安裝，保留各原專案授權。
- 微軟正黑體不隨包散布；使用目標Windows合法提供的字型，或使用者指定的可用繁體中文字型。

Pages只提供靜態文件及技能ZIP，不接收或上傳作文照片。Agent執行安裝會連線Pages、PyPI與固定Paddle模型主機；安裝器不把照片傳送到這些主機。若Agent使用雲端AI分析照片，其資料處理依該Agent／供應商設定，與本靜態網站不同。
