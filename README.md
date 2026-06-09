# RAP 新聞每日選題與製作包系統

這是一個既有 Flask 專案，提供 RAP 新聞內容分析、音樂生成、影片生成，以及每日選題與製作包 API。

## 環境變數

| 變數 | 說明 |
| --- | --- |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | 可選，指定 Gemini 模型 |
| `KIE_API_KEY` | kie.ai API key，用於音樂與影片任務 |
| `SITE_PASSWORD` | API 密碼，預設 `news2026` |
| `PORT` | 啟動 port，部署平台通常會自動提供 |

## 本機啟動

```bash
pip install -r requirements.txt
python app.py
```

所有受保護 API 都需要 header：

```http
X-Access-Password: your_password
Content-Type: application/json
```

## 網頁操作方式

開啟首頁後，先在上方密碼欄輸入 `SITE_PASSWORD`。所有按鈕都沿用同一個密碼欄，前端會透過 `X-Access-Password` header 呼叫 API。

### 每天建議流程

1. 先用「1｜自動掃描 ETtoday」找候選題。
2. 到「2｜候選題清單」審核 AI 推薦，判斷可做、觀望或不建議。
3. 對可做的題目按「產製作包」，取得歌詞、Suno prompt、影像 prompt、YouTube 標題與風險提醒。
4. 若 ETtoday 沒掃到好題，再用「3｜手動補充選題池」貼多則新聞補評分。
5. 若已經確定只做一則新聞，直接用「4｜單篇 RAP 製作」走原本單篇產製流程。

### 1｜自動掃描 ETtoday

此區用在還沒有題目時。預設掃描來源是 `https://www.ettoday.net/news/news-list.htm`。

可調整欄位：

- `interval_minutes`：掃描間隔，預設 30。開著網頁時，每幾分鐘自動掃一次。
- `scan_limit`：掃描列表數，預設 100，最大 300。先看新聞列表標題與分類，不讀全文。
- `deep_read_limit`：AI 深讀數，預設 25，最大 50。從初篩後的新聞中抓全文給 AI 判斷。
- `topic_count`：最終候選數，預設 5，最大 10。最後顯示幾則候選題給你審核。

掃描邏輯：先看 `scan_limit` 則新聞標題與分類，初步排除高風險與不適合題，再抓 `deep_read_limit` 則全文，最後推薦最多 `topic_count` 則 RAP 題目。建議值：平常用 100 / 25 / 5；怕漏題用 200 / 35 / 8；快速測試用 30 / 10 / 3。

按「立即掃 ETtoday」會立刻掃描最新新聞。按「啟動定時通知」後，只要網頁開著，系統就會定時掃描；「只顯示新新聞」預設開啟，瀏覽器通知也只通知新新聞。

掃描完成後會顯示摘要：實際掃描列表數、粗篩保留數、AI 深讀數、最終候選數、高風險排除數、掃描時間。

### 2｜候選題清單

自動掃描與手動補充選題的結果都會集中顯示在這裡。每張候選卡片會顯示：

- 左側：排名、標題、新聞摘要、新聞價值、為什麼適合 RAP、可唱 Hook、可唱素材、風險提醒、內文預覽。
- 右側：建議動作、RAP 分數、初步可唱分、建議曲風、風險等級、安全分類、安全門檻、已抓內文字數、抓取狀態、新新聞 / 已看過、原文連結、產製作包按鈕。

### 選題安全標準

系統會先把新聞分成三類：

- `preferred`：優先做。生活、消費、科技、3C、AI、防詐、交通、政策新制、健康科普、財經白話、職場、教育、旅遊、食安、商品召回等。
- `cautious`：觀望。政治政策、企業醜聞、醫療個案、名人事件、司法相關但未涉及受害者痛苦等，需要人工先看原文。
- `blocked`：不建議。死亡、災難傷亡、車禍、火災、氣爆、性犯罪、兒少、自殺、命案、家屬悲痛、桃色羞辱、剛過世名人、純政治攻防等。

`blocked` 題材不會進入 ETtoday 深讀名單，也不應出現在最終候選題。如果仍因外部資料進入前端，候選卡會顯示「此題不建議 RAP 化」，並停用產製作包按鈕。

建議動作規則：

- `blocked`：不建議。
- `cautious`：觀望。
- `preferred` 且 `rap_score >= 4.3`、`risk_level = low`、`article_text_length >= 800`：可做。
- 其他：觀望。

若內文少於 300 字，候選卡會醒目顯示「內文不足，需人工確認」，AI 分數會保守處理，風險至少為 `medium`。

### 3｜手動補充選題池

此區用在還沒決定要做哪一則，但想把多則新聞交給 AI 一起評分排序時。每行一則，可貼：

```text
https://example.com/news-a
新聞標題｜https://example.com/news-b｜新聞內文摘要
另一則只有文字的新聞摘要
```

按「掃描這批新聞」後，AI 會幫這批新聞一起評分排序，結果會出現在「2｜候選題清單」。

### 4｜單篇 RAP 製作

此區只負責原本單篇新聞產製。已經決定要做某一則時，貼上一則新聞網址或完整新聞內文，按「生成這則 RAP」後，後續仍可編輯歌詞、生成音樂、生成影片與下載素材。

## 既有 API

### `GET /`

回傳 `public/index.html`。

### `GET /api/model`

回傳目前使用的 Gemini 模型。

### `POST /api/analyze`

單篇新聞 RAP 內容分析。保留既有功能。

```json
{
  "news_input": "新聞網址或新聞內文"
}
```

### `POST /api/generate_music`

送出 Suno 音樂生成任務。保留既有功能。

```json
{
  "title": "歌曲標題",
  "lyrics": "完整歌詞",
  "suno_prompt": "音樂風格提示"
}
```

### `POST /api/generate_video`

送出影片生成任務。保留既有功能。

```json
{
  "scene_id": 1,
  "prompt": "video generation prompt"
}
```

### `GET /api/status/<task_id>`

查詢音樂或影片任務狀態。保留既有功能。

## 新增 API

### `POST /api/ettoday_scan`

自動讀取 ETtoday 新聞列表，抓取候選新聞內文，再產生每日 RAP 選題。

請求範例：

```json
{
  "list_url": "https://www.ettoday.net/news/news-list.htm",
  "scan_limit": 100,
  "deep_read_limit": 25,
  "topic_count": 5
}
```

流程：

1. 從 ETtoday 列表抓 `scan_limit` 則新聞的 `title`、`url`、`category`、`time`。
2. 用 `pre_filter_news_item()` 做快速粗篩，不抓全文。
3. 依標題畫面感、反差、數字、政策/科技/生活/消費/健康/國際/財經等可解釋題材加分。
4. 命中災難、死亡、性犯罪、兒少、自殺、重大刑案、家屬悲痛等高風險關鍵字時排除。
5. 取粗篩分數最高的 `deep_read_limit` 則抓全文。
6. AI 只針對深讀後的全文做最終 RAP 選題，最多回 `topic_count` 則，也可以少於 `topic_count`。

回傳格式與 `/api/daily_topics` 類似，另外包含：

```json
{
  "scanned_from": "https://www.ettoday.net/news/news-list.htm",
  "scanned_at": "2026-06-08T10:00:00",
  "candidate_count": 25,
  "scan_summary": {
    "scan_limit": 100,
    "pre_filter_kept": 72,
    "deep_read_limit": 25,
    "ai_deep_read_count": 25,
    "final_topic_count": 5,
    "excluded_high_risk_count": 8
  }
}
```

每則來源會包含：

```json
{
  "id": 1,
  "title": "新聞標題",
  "source_url": "https://www.ettoday.net/news/example.htm",
  "category": "財經",
  "time": "2026/06/08 12:00",
  "preliminary_score": 82,
  "filter_reason": "標題含數字，適合做資訊節奏；屬於可解釋題材",
  "risk_flags": [],
  "article_text_length": 1200,
  "content_preview": "新聞內文前 120 字...",
  "fetch_status": "success",
  "is_new": true
}
```

`fetch_status` 可能是：

- `success`：成功抓到完整或足夠內文。
- `partial`：有抓到內容，但少於 300 字。
- `failed`：列表有抓到新聞，但內文讀取失敗。

系統會用 `data/seen_urls.json` 記錄已掃過的新聞 URL。第一次看到的 URL 會回傳 `is_new: true`，之後同一 URL 會回傳 `is_new: false`。

若 `article_text_length` 少於 300，後端會強制保守處理：

- RAP / 熱度 / 視覺分數不會維持高分。
- `risk_level` 至少為 `medium`。
- `risk_notes` 會包含「內文不足，需人工確認」。

### Railway 與 ETtoday SSL 憑證問題

Railway 執行環境若讀取 ETtoday 時遇到 SSL 憑證驗證錯誤，系統會先用正常憑證驗證抓取；只有發生 `SSLError` 時，才會關閉該次請求的憑證驗證並重試一次。這個 fallback 只用在 ETtoday 掃描路徑，不會把 `verify=False` 設成全站預設。

如果備援抓取仍失敗，API 會回傳可讀錯誤訊息：

```json
{
  "error": "讀取 ETtoday 時發生 SSL 憑證驗證問題，系統已嘗試備援抓取但仍失敗。請稍後再試。"
}
```

### `POST /api/daily_topics`

根據多篇新聞來源產生每日 RAP 新聞選題清單。

請求範例：

```json
{
  "date": "2026-06-08",
  "topic_count": 5,
  "audience": "台灣社群短影音觀眾",
  "tone": "犀利、好懂、有節奏感",
  "focus": "優先挑能做成 60 秒 RAP 新聞的題目",
  "sources": [
    {
      "title": "新聞 A",
      "url": "https://example.com/news-a"
    },
    {
      "title": "新聞 B",
      "content": "新聞內文..."
    }
  ]
}
```

`sources`、`news_items`、`news_inputs`、`news_input` 都可使用。每筆來源可以是網址、純文字，或包含 `title`、`url`、`content` 的物件。

回傳重點：

```json
{
  "date": "2026-06-08",
  "editorial_summary": "今日選題方向",
  "topics": [
    {
      "rank": 1,
      "title": "選題標題",
      "news_angle": "切角",
      "why_it_matters": "值得做的原因",
      "rap_potential": 5,
      "public_interest": 5,
      "visual_potential": 4,
      "risk_level": "low",
      "risk_notes": "風險提醒",
      "source_ids": [1],
      "suggested_hook": "Hook 句",
      "production_brief": "製作 brief"
    }
  ],
  "not_recommended": [],
  "source_count": 2,
  "sources": [],
  "model_used": "gemini-2.0-flash"
}
```

### `POST /api/production_package`

針對單一選題產生 RAP 新聞製作包。

請求範例：

```json
{
  "date": "2026-06-08",
  "platform": "Shorts / Reels / TikTok",
  "duration": "45-60 秒",
  "topic": {
    "title": "選題標題",
    "news_angle": "本集觀點",
    "production_brief": "製作方向"
  },
  "sources": [
    {
      "title": "新聞來源",
      "content": "新聞內文..."
    }
  ]
}
```

回傳重點：

```json
{
  "date": "2026-06-08",
  "topic_title": "選題標題",
  "editorial_brief": {
    "one_sentence": "一句話說明這集",
    "key_facts": [],
    "angle": "本集觀點",
    "must_verify": [],
    "avoid": []
  },
  "rap_script": {
    "cold_open": [],
    "verse1": [],
    "hook": [],
    "verse2": [],
    "outro": []
  },
  "lyrics_text": "完整歌詞",
  "suno_prompt": "音樂風格提示",
  "video_scenes": [],
  "thumbnail": {},
  "social_copy": {},
  "production_checklist": [],
  "source_count": 1,
  "sources": [],
  "model_used": "gemini-2.0-flash"
}
```

### `POST /api/daily_package`

一站式流程：先產生每日選題，再用指定排名的題目產出製作包。

請求範例：

```json
{
  "date": "2026-06-08",
  "topic_count": 5,
  "selected_rank": 1,
  "sources": [
    "https://example.com/news-a",
    {
      "title": "新聞 B",
      "content": "新聞內文..."
    }
  ]
}
```

回傳重點：

```json
{
  "date": "2026-06-08",
  "selected_topic": {},
  "topics": {},
  "production_package": {},
  "model_used": "gemini-2.0-flash"
}
```

## 錯誤格式

所有新增 API 都回傳 JSON。常見錯誤：

```json
{
  "error": "請提供 sources、news_items、news_inputs 或 news_input，內容可以是新聞文字、網址或新聞物件。"
}
```

## 部署

Procfile 已設定：

```Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2 --worker-class gevent
```
