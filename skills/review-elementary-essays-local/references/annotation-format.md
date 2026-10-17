# 可核對批註資料

每頁獨立 project.json，使用 `prepare` 取得真正 source，不能編造 SHA256。頂層 version=1；reading 為 vertical-right-to-left 或 horizontal-left-to-right；coverage=partial／full；annotations 列出可定位項；unlocated 列出沒有可靠位置的疑義；score 可為 null。

## 一項已核對的修改建議

以下是橫排欄位示意，不是任何學生的批改結果；頁面 reading 應為 horizontal-left-to-right。原文與座標必須由當次照片核對後填入：

```json
{
  "id":"S1",
  "kind":"suggestion",
  "status":"confirmed",
  "source_layer":"student",
  "quote":"我覺得很開心。",
  "segments":[{"text":"我覺得很開心。","box":[40,60,180,30],"origin":"observed-crop"}],
  "note":"補充讓你開心的具體事件，讀者才知道原因。",
  "short_note":"補充開心的原因",
  "example":"我把作品送給媽媽，她笑著抱住我，我覺得很開心。",
  "mark_side":"below",
  "review":{"text":true,"position":true,"judgment":true,"reviewer":"Agent 看圖覆核；尚未教師人工確認"}
}
```

kind：typo、praise、suggestion、uncertain、existing。status：pending、confirmed、rejected。source_layer：student、teacher-existing、unclassified。原文 quote 必須等於按閱讀順序串接的 segments.text；每個 box=[x,y,width,height]，基準是原尺寸圖左上角。origin=observed-crop／manual；只有外部真實 PaddleOCR 資料才可使用 paddleocr。

訂正單字另加：
```json
{"quote":"我很高心。","segments":[{"text":"我很高心。","box":[40,60,150,30],"origin":"observed-crop"}],"target_box":[130,60,30,30],"target_anchor":{"segment":0,"start":3,"text":"心","origin":"observed-crop"},"replacement":"興","label_xy":[140,105]}
```
此例為另一個假設句子的錯字欄位，應放在 kind=typo 的完整項目內，不能套到上方佳句或建議項目。start 是 Python Unicode 字元索引，0起算；必須精確指向真實原字，不能使用 UTF-16碼元索引。圈選位置在相應句片段內，label_xy 是看圖量測留白。marker_xy 與 local_label 為可選短註；紅字不能遮字。單字框、原字裁切與替換字三者都需核對。

pending／uncertain／existing 不新增紅筆；不得用 confirmed uncertain 畫猜測。沒有框的疑字保存在頂層：
```json
{"unlocated":[{"id":"U1","quote":"可讀上下文〔疑字〕","note":"字形不足，尚不能定位或判錯。"}]}
```

各頁及 unlocated 的 ID 全案唯一。輸出程式檢查原圖雜湊、尺寸、框、引文、單字連結、三項覆核旗標與來源層；程式不能證明人工／模型的語意判斷正確。工作台修改文字、判斷或位置後重新覆核，不能沿用舊旗標。不要重畫原圖。

report 的 score（若需輸出評分）：
```json
{"content":4,"structure":3.5,"language":4,"reasons":{"content":"原文依據","structure":"原文依據","language":"原文依據"}}
```
有評分時另填 report.complete_work=true，且各頁 coverage=full，明記已取得足以理解的完整作文；此旗標不能代替真實完整性核對。總分由程式依權重計算，不另外手填。缺頁／大量疑字影響理解時不填 score，改寫 scope 與待確認項。給分前讀評分規準。
