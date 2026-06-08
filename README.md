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
