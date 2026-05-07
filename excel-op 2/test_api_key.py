import requests

api_key = "44905c3b4aa9458f891afabb22db7378.bT9UGfiqO49hCcPJaZE4iLfW"

# Try ZhipuAI
try:
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": "glm-4", "messages": [{"role": "user", "content": "hello"}]}
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print("ZhipuAI:", res.status_code, res.text[:200])
except Exception as e:
    print("ZhipuAI Error:", e)

# Try DeepSeek
try:
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hello"}]}
    res = requests.post(url, headers=headers, json=payload, timeout=10)
    print("DeepSeek:", res.status_code, res.text[:200])
except Exception as e:
    print("DeepSeek Error:", e)

