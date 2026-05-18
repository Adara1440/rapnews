import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps

app = Flask(__name__, static_folder='public', static_url_path='')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
KIE_API_KEY = os.environ.get('KIE_API_KEY', '')
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'news2026')

GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'
KIE_CREATE_URL = 'https://api.kie.ai/api/v1/jobs/createTask'
KIE_STATUS_URL = 'https://api.kie.ai/api/v1/jobs/recordInfo'
JINA_URL = 'https://r.jina.ai/'

def require_password(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = request.headers.get('X-Access-Password', '')
        if pwd != SITE_PASSWORD:
            return jsonify({'error': '密碼錯誤'}), 401
        return f(*args, **kwargs)
    return decorated

def fetch_news(url):
    # 先試 Jina AI
    try:
        r = requests.get(JINA_URL + url, timeout=15, headers={'Accept': 'text/plain'})
        if r.status_code == 200 and len(r.text) > 200:
            return r.text[:8000]
    except Exception:
        pass

    # 備用：讓 Gemini 直接讀 URL
    try:
        payload = {
            'contents': [{
                'parts': [
                    {'text': '請抓取並回傳這個網址的完整新聞內文，只要純文字，不要任何格式：' + url}
                ]
            }],
            'generationConfig': {'temperature': 0}
        }
        r = requests.post(GEMINI_URL, json=payload, timeout=30)
        data = r.json()
        if 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text'][:8000]
    except Exception:
        pass

    return None

def parse_gemini_json(raw):
    start = raw.find('{')
    depth = 0
    end = -1
    for i, ch in enumerate(raw[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(raw[start:end])

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/analyze', methods=['POST'])
@require_password
def analyze():
    data = request.json
    news_input = data.get('news_input', '').strip()

    if not news_input:
        return jsonify({'error': '請輸入新聞網址或內文'}), 400

    news_content = news_input
    if news_input.startswith('http'):
        fetched = fetch_news(news_input)
        if fetched:
            news_content = fetched
        else:
            return jsonify({'error': '無法抓取網址內容，請直接貼上新聞內文'}), 400

    prompt = f"""你是台灣新聞說唱腳本專家。任務：把新聞轉成洗腦 rap 歌詞，讓讀者用聽歌方式理解新聞。

【新聞內容】
{news_content[:6000]}

【核心原則】
- 倒金字塔：最重要的資訊第一句就說
- 快嘴 rap 節奏：每句控制在 10-14 字，讀起來要有節奏感
- 洗腦設計：副歌重複核心訊息，讓人聽完記住一件最重要的事
- 口語化：像在跟朋友說，不是在唸稿

【歌詞結構】
- Verse 1（4句）：最重要的資訊 + 法條/數字，第一句就是結論
- Hook（4句）：洗腦重複，只有核心訊息，要押韻
- Verse 2（4句）：事件背景 + 為什麼發生
- Verse 3（4句）：來龍去脈 + 延伸影響
- Outro（2句）：行動呼籲或收尾

【畫面場景】
同時生成 3 個關鍵畫面 prompt，用於 grok-imagine text-to-video：
- 每個 prompt 必須是扁平小人動畫風格
- 固定尾綴：flat 2D animation, stick figure style, white background, simple black outline, smooth motion, 9:16, no text
- 對應歌詞中最需要視覺化的 3 個時間點

【Suno Style Prompt】
生成適合這首 rap 的 Suno 音樂風格指令（英文，30字內）

只輸出合法 JSON，不要任何說明文字：
{{
  "title": "影片標題（10字內，吸睛）",
  "lyrics": {{
    "verse1": ["第1句", "第2句", "第3句", "第4句"],
    "hook": ["第1句", "第2句", "第3句", "第4句"],
    "verse2": ["第1句", "第2句", "第3句", "第4句"],
    "verse3": ["第1句", "第2句", "第3句", "第4句"],
    "outro": ["第1句", "第2句"]
  }},
  "suno_prompt": "Mandarin rap, 115 BPM, ...",
  "scenes": [
    {{
      "id": 1,
      "time": "verse1",
      "description": "場景描述（10字內中文）",
      "prompt": "英文 grok prompt..."
    }},
    {{
      "id": 2,
      "time": "verse2",
      "description": "場景描述",
      "prompt": "英文 grok prompt..."
    }},
    {{
      "id": 3,
      "time": "outro",
      "description": "場景描述",
      "prompt": "英文 grok prompt..."
    }}
  ]
}}"""

    try:
        r = requests.post(GEMINI_URL, json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'response_mime_type': 'application/json',
                'temperature': 0.85
            }
        }, timeout=60)

        resp = r.json()

        # 詳細錯誤：API key 問題或配額
        if 'error' in resp:
            err_msg = resp['error'].get('message', str(resp['error']))
            return jsonify({'error': f'Gemini API 錯誤：{err_msg}'}), 500

        if 'candidates' not in resp:
            return jsonify({'error': f'Gemini 回傳異常：{str(resp)[:300]}'}), 500

        candidate = resp['candidates'][0]

        # 安全過濾被擋
        if candidate.get('finishReason') == 'SAFETY':
            return jsonify({'error': 'Gemini 安全過濾擋掉了，請換一篇新聞或直接貼內文'}), 400

        raw = candidate['content']['parts'][0]['text']
        result = parse_gemini_json(raw)
        result['original_content'] = news_content[:2000]
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI 回傳格式解析失敗，請重試：{str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'AI 分析失敗：{str(e)}'}), 500

@app.route('/api/generate_music', methods=['POST'])
@require_password
def generate_music():
    data = request.json
    lyrics = data.get('lyrics', '')
    suno_prompt = data.get('suno_prompt', '')
    title = data.get('title', '新聞神曲')

    if not lyrics or not suno_prompt:
        return jsonify({'error': '缺少歌詞或風格指令'}), 400

    payload = {
        'model': 'V4_5PLUS',
        'customMode': True,
        'instrumental': False,
        'title': title,
        'style': suno_prompt,
        'prompt': lyrics,
        'vocalGender': 'm',
        'audioWeight': 0.85,
        'callBackUrl': 'none'
    }

    try:
        r = requests.post(KIE_CREATE_URL, json=payload, headers={
            'Authorization': f'Bearer {KIE_API_KEY}',
            'Content-Type': 'application/json'
        }, timeout=30)
        result = r.json()
        task_id = result.get('data', {}).get('taskId') or result.get('taskId')
        if not task_id:
            return jsonify({'error': f'Suno 任務建立失敗：{result}'}), 500
        return jsonify({'task_id': task_id, 'status': 'pending'})
    except Exception as e:
        return jsonify({'error': f'音樂生成失敗：{str(e)}'}), 500

@app.route('/api/generate_video', methods=['POST'])
@require_password
def generate_video():
    data = request.json
    prompt = data.get('prompt', '')
    scene_id = data.get('scene_id', 1)

    if not prompt:
        return jsonify({'error': '缺少畫面描述'}), 400

    payload = {
        'model': 'grok-imagine/text-to-video',
        'input': {
            'prompt': prompt,
            'aspect_ratio': '9:16',
            'duration': 6,
            'resolution': '480p',
            'mode': 'normal',
            'sound': False
        }
    }

    try:
        r = requests.post(KIE_CREATE_URL, json=payload, headers={
            'Authorization': f'Bearer {KIE_API_KEY}',
            'Content-Type': 'application/json'
        }, timeout=30)
        result = r.json()
        task_id = result.get('data', {}).get('taskId') or result.get('taskId')
        if not task_id:
            return jsonify({'error': f'影片任務建立失敗：{result}'}), 500
        return jsonify({'task_id': task_id, 'scene_id': scene_id, 'status': 'pending'})
    except Exception as e:
        return jsonify({'error': f'影片生成失敗：{str(e)}'}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
@require_password
def check_status(task_id):
    try:
        r = requests.get(KIE_STATUS_URL, params={'taskId': task_id}, headers={
            'Authorization': f'Bearer {KIE_API_KEY}'
        }, timeout=15)
        data = r.json().get('data', {})
        state = data.get('state', data.get('status', 'unknown'))

        if state in ('success', 'completed'):
            result_json = data.get('resultJson', '{}')
            if isinstance(result_json, str):
                result_json = json.loads(result_json) if result_json else {}
            url = (result_json.get('audio_url') or
                   result_json.get('video_url') or
                   data.get('audioUrl') or
                   data.get('videoUrl') or '')
            return jsonify({'status': 'completed', 'url': url, 'raw': data})
        elif state in ('failed', 'error'):
            return jsonify({'status': 'failed', 'error': data.get('errorMessage', '生成失敗')})
        else:
            return jsonify({'status': 'processing'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
