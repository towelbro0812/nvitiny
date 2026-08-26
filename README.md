# nvitiny

窄終端機優先的 NVIDIA GPU 監看工具。`nvitop` 在寬度不足 79 欄時會拒絕渲染，
`nvitiny` 一路縮到 24 欄仍有完整的長條圖與歷史曲線。

適合手機透過 SSH 看遠端 GPU，或塞在被切窄的 tmux pane 裡。

```
drv 580.142  cuda 13.0
GPU0  NVIDIA GB10
M ▕██░░░░░░░░░░░░░░░░░░░░░░░░▏  8%  46°C
U ▕███░░░░░░░░░░░░░░░░░░░░░░░▏ 13%   13W
  10.1G/122G  unified
M ⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣤⣤⣤⣤⣤⣤⣤⣤⣤⣤⣤⣴⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶
U ⣶⣶⣶⣶⣶⣶⣶⣶⣤⣤⣤⣤⣶⣶⣦⣤⣤⣤⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣠⣤⣀
────────────────────────────────────────
  3661 alice   2.6G  kit
236404 gdm    43.9M  Xorg
236611 gdm    16.6M  gnome-shell
```

`M` 是記憶體、`U` 是使用率，曲線是各自的歷史走勢。

## 安裝

尚未發佈到 PyPI，直接從 git 倉庫裝。

```bash
uv tool install git+https://github.com/towelbro0812/nvitiny.git          # 裝成常駐指令
uvx --from git+https://github.com/towelbro0812/nvitiny.git nvitiny       # 不安裝，直接跑
```

公開倉庫走 HTTPS 不需要任何認證。可以在網址後面加 `@v0.1.0` 或 `@main`
指定 tag 或分支；私有倉庫則改用 `git+ssh://git@github.com/...`。

本機開發時用路徑：

```bash
uv tool install /path/to/nvitiny
uv tool uninstall nvitiny
```

## 用法

```bash
nvitiny            # 即時監看（預設），按 q 離開
nvitiny -i 0.5     # 取樣間隔 0.5 秒
nvitiny --once     # 單次輸出，導進管線時也會自動走這條
nvitiny --demo     # 無須GPU，用內建 fixture 把各種寬度都畫一遍
```

## 專案結構

```
src/nvitiny/
  cli.py            參數解析與模式分派
  app/              執行模式：live / once / demo / keys
  view/             呈現
    plan.py         純函式：尺寸 → LayoutPlan（決定顯示什麼）
    compose.py      照計畫組裝畫面（決定怎麼排）
    widgets.py  sparkline.py  units.py  theme.py
  core/             資料：model / sample / history
  fixtures/         匿名的 GPU 狀態樣本，供 --demo 與測試使用
tests/
```

相依方向永遠是 `app → view → core`。

## 測試

```bash
uv run pytest
```

不需要 NVIDIA GPU，全部走 fixture。即時模式的測試會開一個真的 pty。

## 授權注意事項

依賴的 `nvitop` 是雙授權：`nvitop/api/**` 是 Apache-2.0，本專案只用這層；
`nvitop/tui/**` 是 GPL-3.0-only，**不可匯入**，否則整包會被傳染。
`view/sparkline.py` 因此是自行實作，沒有重用 `nvitop.tui.library`。
