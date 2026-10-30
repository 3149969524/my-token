import json, base64, time, re, random, os

TOKEN = os.environ.get('GH_TOKEN', '')
REPO = '3149969524/my-token'
API = f'https://api.github.com/repos/{REPO}/contents/messages.json'
HEADERS = ['-H', f'Authorization: token {TOKEN}', '-H', 'Accept: application/vnd.github+json']

def api_get(url):
    r = subprocess_run(['curl', '-s', url] + HEADERS)
    return json.loads(r)

def api_put(url, payload):
    r = subprocess_run(['curl', '-s', '-X', 'PUT', url] + HEADERS + ['-d', payload])
    return json.loads(r)

def subprocess_run(cmd):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True).stdout

print('=== 留言板小机器人开始巡逻 ===')

# 1. 获取当前留言
meta = api_get(API)
sha = meta['sha']
content = base64.b64decode(meta['content']).decode('utf-8')
data = json.loads(content)
msgs = data['messages']
print(f'当前留言数: {len(msgs)}')

# 2. 广告/垃圾过滤规则
SPAM_PATTERNS = [
    r'https?://',           # 包含链接
    r'www\.',                # 网址
    r'[Vv][Xx](?:号)?[:：]?\s*\d{6,}',  # 微信号
    r'[Qq][Qq](?:号)?[:：]?\s*\d{5,}',  # QQ号
    r'加我', r'代理', r'批发', r'低价', r'出售', r'微信同号',
    r'赌[搏博]', r'彩[票]', r'刷单', r'兼职日赚', r'加微',
    r'(?:性|黄|裸)', r'约炮', r'一夜情',
]

def is_spam(msg):
    text = msg.get('content', '') + msg.get('name', '')
    for pat in SPAM_PATTERNS:
        if re.search(pat, text):
            return True, pat
    return False, None

# 3. 删除广告留言
deleted = 0
clean_msgs = []
for m in msgs:
    bad, pat = is_spam(m)
    if bad:
        print(f'  [删除] 疑似广告: "{m.get("content","")[:20]}..." (匹配: {pat})')
        deleted += 1
    else:
        clean_msgs.append(m)

# 4. 刷屏检测：同一人1分钟内发3条以上，保留最后一条
from collections import defaultdict
by_user = defaultdict(list)
for m in clean_msgs:
    by_user[m.get('name', '匿名')].append(m)
spam_users = []
for user, user_msgs in by_user.items():
    if len(user_msgs) >= 5:
        user_msgs.sort(key=lambda x: x.get('time', 0))
        # 保留最后2条，删除前面的
        to_remove = user_msgs[:-2]
        for rm in to_remove:
            clean_msgs.remove(rm)
            print(f'  [刷屏清理] {user}: "{rm.get("content","")[:20]}..."')
            deleted += 1

data['messages'] = clean_msgs

# 5. 机器人留言（每6小时发一次，用时间戳判断）
BOT_LAST_FILE = 'bot_state.json'
BOT_INTERVAL = 6 * 3600 * 1000  # 6小时

bot_state = {'last_msg_time': 0}
try:
    bot_meta = api_get(f'https://api.github.com/repos/{REPO}/contents/{BOT_LAST_FILE}')
    bot_sha = bot_meta['sha']
    bot_content = base64.b64decode(bot_meta['content']).decode('utf-8')
    bot_state = json.loads(bot_content)
except:
    bot_sha = None

now_ms = int(time.time() * 1000)
should_bot_speak = (now_ms - bot_state.get('last_msg_time', 0)) >= BOT_INTERVAL

if should_bot_speak and len(clean_msgs) > 0:
    last_msgs = clean_msgs[-3:]
    replies = [
        f'感谢"{last_msgs[-1].get("name","匿名")}"的留言！有你支持这个网站才精彩～',
        '欢迎大家常来逛逛，这里永远为你敞开～',
        '今天的留言板很热闹呢，感谢每一位留言的你！',
        '路过别忘了留言，你的每一句话都让这里更有温度～',
    ]
    reply = random.choice(replies)
    data['messages'].append({
        'name': '小助手Bot',
        'content': reply,
        'time': now_ms
    })
    bot_state['last_msg_time'] = now_ms
    print(f'  [机器人发言] {reply}')
    
    # 上传bot状态
    bot_json = json.dumps(bot_state, ensure_ascii=False)
    bot_b64 = base64.b64encode(bot_json.encode('utf-8')).decode('ascii')
    bot_payload = json.dumps({'message': 'update bot state', 'content': bot_b64})
    if bot_sha:
        bot_payload = json.dumps({'message': 'update bot state', 'content': bot_b64, 'sha': bot_sha})
    api_put(f'https://api.github.com/repos/{REPO}/contents/{BOT_LAST_FILE}', bot_payload)

# 6. 上传更新后的留言
new_json = json.dumps(data, ensure_ascii=False)
b64 = base64.b64encode(new_json.encode('utf-8')).decode('ascii')
payload = json.dumps({'message': f'bot patrol: deleted {deleted} spam', 'content': b64, 'sha': sha})
resp = api_put(API, payload)

if 'content' in resp:
    print(f'=== 巡逻完成！删除{deleted}条广告/刷屏，当前{len(data["messages"])}条留言 ===')
else:
    print(f'上传失败: {str(resp)[:200]}')