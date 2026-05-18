import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps

app = Flask(__name__, static_folder='public', static_url_path='')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
KIE_API_KEY = os.environ.get('KIE_API_KEY', '')
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'news2026')

KIE_CREATE_URL = 'https://api.kie.ai/api/v1/jobs/createTask'
KIE_STATUS_URL = 'https://api.kie.ai/api/v1/jobs/recordInfo'
JINA_URL = 'https://r.jina.ai/'

_GEMINI_MODEL = None

def get_gemini_model():
    global _GEMINI_MODEL
    if _GEMINI_MODEL:
        return _GEMINI_MODEL
    if os.environ.get('GEMINI_MODEL'):
        _GEMINI_MODEL = os.environ.get('GEMINI_MODEL')
        print(f'[Gemini] 使用環境變數指定模型：{_GEMINI_MODEL}')
        return _GEMINI_MODEL
    candidates = [
        'gemini-2.5-flash-preview',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]
    for model in candidates:
        try:
            r = requests.get(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}?key={GEMINI_API_KEY}',
                timeout=5
            )
            if r.status_code == 200:
                _GEMINI_MODEL = model
                print(f'[Gemini] 自動偵測到可用模型：{_GEMINI_MODEL}')
                return _GEMINI_MODEL
        except Exception:
            continue
    _GEMINI_MODEL = 'gemini-2.0-flash'
    print(f'[Gemini] 自動偵測失敗，使用 fallback：{_GEMINI_MODEL}')
    return _GEMINI_MODEL

def get_gemini_url():
    model = get_gemini_model()
    return f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}'

def require_password(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = request.headers.get('X-Access-Password', '')
        if pwd != SITE_PASSWORD:
            return jsonify({'error': '密碼錯誤'}), 401
        return f(*args, **kwargs)
    return decorated

def fetch_news(url):
    import re as _re
    # 方法一：直接爬蟲（模擬真實瀏覽器，針對 ETtoday 優化）
    try:
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8',
            'Referer': 'https://www.google.com/',
        }
        r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        r.encoding = 'utf-8'
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')

            # 抓標題
            title = ''
            og_t = soup.find('meta', property='og:title')
            if og_t and og_t.get('content'):
                title = og_t['content'].strip()
            elif soup.find('title'):
                title = _re.sub(r'\s*[-|]\s*(ETtoday|.*)\s*$', '', soup.title.text).strip()

            # 針對 ETtoday 的文章選擇器
            selectors = [
                '.story', '.news_article', 'article[itemprop="articleBody"]',
                '.news-content', 'article', '.article-content', '.post-content',
            ]
            article = None
            for sel in selectors:
                article = soup.select_one(sel)
                if article:
                    break

            if article:
                for unwanted in article.select(
                    '.related_news, .ad, script, style, .fb-comments, '
                    '.photo_pop, aside, .recommend, .tags, .share, '
                    '.news_keyword, .more_news'
                ):
                    unwanted.decompose()
                paras = article.find_all('p')
            else:
                paras = soup.find_all('p')

            noise = ['廣告', '訂閱', 'LINE', 'Copyright', 'JavaScript', 'Cookie',
                     '請繼續往下閱讀', '推薦閱讀', '延伸閱讀']
            lines = []
            for p in paras:
                t = _re.sub(r'<[^>]+>', '', str(p)).strip()
                t = _re.sub(r'\s+', ' ', t)
                if len(t) > 15 and not any(k in t for k in noise):
                    lines.append(t)

            body = chr(10).join(lines[:60])
            if len(body) > 100:
                return ('【標題】' + title + chr(10) + chr(10) + '【內文】' + body)[:8000]
    except Exception as e:
        print(f'[fetch_news] 直接爬蟲失敗：{e}')

    # 方法二：Jina AI 備援
    try:
        jina_url = 'https://r.jina.ai/' + url
        r = requests.get(jina_url, timeout=20, headers={
            'Accept': 'text/plain',
            'X-Return-Format': 'text',
            'User-Agent': 'Mozilla/5.0'
        })
        if r.status_code == 200 and len(r.text) > 200:
            return r.text[:8000]
    except Exception as e:
        print(f'[fetch_news] Jina 備援失敗：{e}')

    return None


def parse_gemini_json(raw):
    start = raw.find('{')
    if start == -1:
        raise ValueError('找不到 JSON 開頭')
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
    if end == -1:
        raise ValueError('JSON 解析失敗')
    return json.loads(raw[start:end])

def call_gemini(prompt):
    r = requests.post(get_gemini_url(), json={
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'response_mime_type': 'application/json',
            'temperature': 0.9
        }
    }, timeout=90)
    resp = r.json()
    if 'error' in resp:
        err_msg = resp['error'].get('message', str(resp['error']))
        if 'not found' in err_msg.lower() or 'not supported' in err_msg.lower():
            global _GEMINI_MODEL
            _GEMINI_MODEL = None
        raise Exception('Gemini API 錯誤：' + err_msg)
    if 'candidates' not in resp:
        raise Exception('Gemini 回傳異常：' + str(resp)[:300])
    candidate = resp['candidates'][0]
    if candidate.get('finishReason') == 'SAFETY':
        raise Exception('Gemini 安全過濾擋掉了，請換一篇新聞或直接貼內文')
    return candidate['content']['parts'][0]['text']

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/model', methods=['GET'])
@require_password
def current_model():
    return jsonify({'model': get_gemini_model()})

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

    prompt = f"""你是台灣最強的解釋性新聞 Rap 寫手。
任務：把新聞寫成讓人停下來、聽完、記住、還想分享的洗腦 Rap 歌詞。

【新聞內容】
{news_content[:6000]}

════════════════════════════════════
第一步：先從新聞裡挖出這些東西（寫歌前必做）
════════════════════════════════════

1. 最衝擊的一句話是什麼？（這就是你的第一句）
2. 新聞裡有哪些具體數字、日期、金額、比例？（全部列出來）
3. 有哪些具體的人名、機構、地點、事件名稱？
4. 這件事的「來龍去脈」三行版：起因→過程→結果
5. 如果你要跟朋友說這個新聞，你會怎麼說？（用那個語氣寫）

════════════════════════════════════
第二步：寫歌詞（這才是你要輸出的東西）
════════════════════════════════════

【歌詞結構】
- Verse 1（4句）：倒金字塔，最重要的結論+數字+影響，第一句就要讓人「哇」
- Hook（4句）：只有核心訊息，重複洗腦，要押韻，聽完就記住這則新聞在說什麼
- Verse 2（4句）：說清楚「為什麼」，背景故事，讓人理解來龍去脈
- Verse 3（4句）：延伸影響、細節補充、跟聽眾的關係
- Outro（2句）：收尾，行動感，不說教

【歌詞品質硬規定——違反就重寫】

✅ 必須做到：
- 第一句就是最衝擊的結論，讓人停下來
- 每個段落至少一個具體數字、日期或金額
- Hook 要讓人聽完就能複述這則新聞的核心
- 句子要有節奏感，讀出來要順，有押韻更好
- 口語化，像在跟朋友說，不是在唸稿

❌ 絕對禁止（出現就重寫）：
- 通用句：「了解這些事」「保護你健康」「工作更有力」「值得深思」
  → 這種句子換個新聞主題也能用，代表你沒有真正理解這則新聞
- 說教句：「我們應該」「大家要注意」「希望大家」
- 空洞句：沒有具體資訊的廢話
- 書面語：「此乃」「因此」「然而」「據悉」
- 沒有鉤子的開場：不能用「今天要講的是」「讓我告訴你」

【風格參考——這是你要達到的感覺】
第一句範例：「今年開始台灣修法了你知道嗎 / 請病假十天以內老闆不能罰」
Hook 範例：「請病假！合法的！/ 請病假！不用怕！/ 請病假！老闆罰你！/ 兩萬到一百萬！」
→ 注意：具體、有數字、有衝擊、有節奏、聽一次就記住

════════════════════════════════════
第三步：生成畫面和音樂指令
════════════════════════════════════

【畫面場景】3 個 grok-imagine text-to-video prompt：
- 對應歌詞中最有畫面感的 3 個時間點
- 固定風格：flat 2D animation, stick figure style, white background, simple black outline, smooth motion, 9:16, no text

【Suno 音樂風格】英文，控制在 40 字內，針對這則新聞的情緒和節奏設計

════════════════════════════════════
輸出格式（純 JSON，不要任何說明文字）
════════════════════════════════════

{{
  "title": "影片標題（10字內，衝擊感，讓人想點進來）",
  "lyrics": {{
    "verse1": ["第1句（最衝擊的結論）", "第2句（具體數字）", "第3句", "第4句"],
    "hook": ["第1句（洗腦重複）", "第2句", "第3句", "第4句（記憶點）"],
    "verse2": ["第1句（為什麼）", "第2句（故事）", "第3句", "第4句"],
    "verse3": ["第1句（影響）", "第2句（細節）", "第3句", "第4句"],
    "outro": ["第1句（行動感）", "第2句（收尾）"]
  }},
  "suno_prompt": "針對這則新聞設計的 Suno 風格指令（英文）",
  "scenes": [
    {{"id": 1, "time": "verse1", "description": "場景描述（10字內中文）", "prompt": "具體場景描述... flat 2D animation, stick figure style, white background, simple black outline, smooth motion, 9:16, no text"}},
    {{"id": 2, "time": "verse2", "description": "場景描述", "prompt": "具體場景描述... flat 2D animation, stick figure style, white background, simple black outline, smooth motion, 9:16, no text"}},
    {{"id": 3, "time": "outro", "description": "場景描述", "prompt": "具體場景描述... flat 2D animation, stick figure style, white background, simple black outline, smooth motion, 9:16, no text"}}
  ]
}}"""

    try:
        raw = call_gemini(prompt)
        result = parse_gemini_json(raw)
        result['original_content'] = news_content[:2000]
        result['model_used'] = get_gemini_model()
        return jsonify(result)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'AI 回傳格式解析失敗，請重試：{str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_music', methods=['POST'])
@require_password
def generate_music():
    data = request.json
    lyrics = data.get('lyrics', '')
    suno_prompt = data.get('suno_prompt', '')
    title = data.get('title', 'Rap說新聞')
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
        if not r.content:
            return jsonify({'error': 'Suno API 無回應，請重試'}), 500
        result = r.json()
        if not isinstance(result, dict):
            return jsonify({'error': f'Suno API 回傳格式異常：{result}'}), 500
        data_field = result.get('data') or {}
        task_id = (data_field.get('taskId') if isinstance(data_field, dict) else None) or result.get('taskId')
        if not task_id:
            return jsonify({'error': f'Suno 任務建立失敗，完整回傳：{result}'}), 500
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
        if not r.content:
            return jsonify({'error': 'KIE API 無回應，請重試'}), 500
        result = r.json()
        if not isinstance(result, dict):
            return jsonify({'error': f'KIE API 回傳格式異常：{result}'}), 500
        data_field = result.get('data') or {}
        task_id = (data_field.get('taskId') if isinstance(data_field, dict) else None) or result.get('taskId')
        if not task_id:
            return jsonify({'error': f'影片任務建立失敗，完整回傳：{result}'}), 500
        return jsonify({'task_id': task_id, 'scene_id': scene_id, 'status': 'pending'})
    except Exception as e:
        return jsonify({'error': f'影片生成失敗：{str(e)}'}), 500

def _deep_find_url(obj, depth=0):
    """遞迴尋找 JSON 裡第一個 http URL"""
    if depth > 5:
        return ''
    if isinstance(obj, str) and obj.startswith('http'):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _deep_find_url(v, depth + 1)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _deep_find_url(item, depth + 1)
            if found:
                return found
    return ''

def _extract_url(task_data):
    """從 KIE 回傳的各種格式中找出媒體 URL"""
    # 先從 resultJson 找
    rj = task_data.get('resultJson', '')
    if rj:
        try:
            parsed = json.loads(rj) if isinstance(rj, str) else rj
            if isinstance(parsed, dict):
                for k in ['audio_url', 'video_url', 'url', 'imageUrl', 'videoUrl', 'audioUrl']:
                    if parsed.get(k) and str(parsed[k]).startswith('http'):
                        return parsed[k]
                # resultUrls 陣列
                urls = parsed.get('resultUrls', [])
                if urls:
                    return urls[0]
            if isinstance(parsed, list) and parsed:
                for item in parsed:
                    if isinstance(item, str) and item.startswith('http'):
                        return item
        except Exception:
            pass

    # 直接從 task_data 找常見欄位
    for k in ['audioUrl', 'videoUrl', 'audio_url', 'video_url', 'url', 'resultUrl']:
        v = task_data.get(k, '')
        if v and isinstance(v, str) and v.startswith('http'):
            return v

    # 最後遞迴深找
    return _deep_find_url(task_data)

def _is_done(task_data):
    """判斷任務是否完成，回傳 (success, failed)"""
    state = str(task_data.get('state', '')).lower()
    if state == 'success':
        return True, False
    if state in ('fail', 'failed', 'error'):
        return False, True
    if task_data.get('successFlag') == 1:
        return True, False
    if task_data.get('successFlag') in (2, 3):
        return False, True
    status = str(task_data.get('status', '')).upper()
    if status in ('SUCCESS', 'SUCCEEDED', 'FINISHED', 'COMPLETED'):
        return True, False
    if status in ('FAILED', 'ERROR', 'FAIL'):
        return False, True
    return False, False

@app.route('/api/status/<task_id>', methods=['GET'])
@require_password
def check_status(task_id):
    try:
        r = requests.get(KIE_STATUS_URL, params={'taskId': task_id}, headers={
            'Authorization': f'Bearer {KIE_API_KEY}'
        }, timeout=15)
        result = r.json()

        # KIE 回傳可能在 data 欄位，也可能直接在根
        task_data = result.get('data', {}) or {}
        if isinstance(task_data, list) and task_data:
            task_data = task_data[0]
        if not task_data.get('state') and not task_data.get('status'):
            task_data = result  # 直接用根層

        done, failed = _is_done(task_data)
        if not done and not failed:
            done, failed = _is_done(result)
            if done or failed:
                task_data = result

        if done:
            url = _extract_url(task_data) or _extract_url(result)
            print(f'[status] {task_id} done, url={bool(url)}, raw={str(task_data)[:200]}')
            return jsonify({'status': 'completed', 'url': url})
        elif failed:
            err = task_data.get('errorMessage') or task_data.get('error') or '生成失敗'
            return jsonify({'status': 'failed', 'error': err})
        else:
            return jsonify({'status': 'processing'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
