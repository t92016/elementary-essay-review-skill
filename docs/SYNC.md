# 公開主版本與私人備份同步

主要維護來源是本 repo。私人 Codex-Skills 的同名技能是發行鏡像，不從任何一台電腦已安裝的舊技能反向覆蓋。

## 對應位置

- 私人 `skills/review-elementary-essays-local/`：與本 repo 同版本的 24 個技能檔案逐位元組相同。
- 私人 `packages/elementary-essay-review-skill/`：完整已提交公開專案，包含安裝器、文件、測試、ZIP、模型雜湊及此同步工具。
- 私人 `manifest/essay-release.json`：公開來源 commit、發行版本、ZIP SHA256 與每個鏡像檔案 SHA256。
- 私人一般備份／安裝腳本略過本技能，避免舊全域定稿降版新版，或只複製技能而漏裝環境。

## 從私人 repo 安裝

先登入有權讀取私人 repo 的 GitHub 帳號，在新電腦的本機 NTFS 路徑 clone Codex-Skills。不要先用一般技能安裝腳本複製本技能到全域目錄。請先閱讀鏡像內 INSTALL.md，再從 Codex-Skills 根目錄執行：

~~~powershell
py -3.12 packages/elementary-essay-review-skill/tools/install_from_checkout.py --agent codex --runtime C:/EssayReview
# OpenCode 改成 --agent opencode，並使用自己的新 runtime 目錄。
~~~

這個入口用本機 loopback HTTP 供既有安裝器讀取私人 checkout 內的同版 ZIP 與清單；技能包不需從公開 Pages 下載。套件仍從 PyPI、模型仍從 Paddle 官方下載並核對。服務只綁 127.0.0.1，安裝結束會關閉；不啟動公開伺服器或上傳照片。檢查、隔離環境、拒絕覆寫與合成自測皆沿用原安裝器。已有同名技能時停止，不能直接套用 --dest 製造重複全域定義。

## 發行時的同步

1. 在公開 repo 修改並完成測試；技能內容有變更時發行新版本，不改寫既有版本 ZIP。
2. 執行 tools/build_site.py，確認 ZIP、清單與技能一致；提交公開版本。
3. 在另一個私人 checkout 執行下列檢查；需要套用時加 --write。
4. 檢查私人 diff、跑測試、提交及推送；重新下載核對遠端檔案，才回報同步完成。

~~~powershell
python tools/sync_private.py --target C:/Repos/Codex-Skills
python tools/sync_private.py --target C:/Repos/Codex-Skills --write
~~~

工具只同步已提交且乾淨的公開來源，更新指定鏡像、同名技能及清單，不自行提交／推送，不碰已安裝全域技能、其他技能、學生資料或模型。SHA 不符、來源未提交或多出未管理檔案時停止。

私人 repo 的 GitHub Actions 提供每六小時檢查及手動執行；有差異時先測試再提交同步。這是補查機制，排程可能延遲，並非公開 push 後立即完成。每次人工發行仍應依上面步驟同步確認。

GitHub Actions 使用私人 repo 自己的 GITHUB_TOKEN 寫入私人 repo，公開來源只讀，不新增跨 repo 個人憑證。機制依據：[GitHub GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token)。
