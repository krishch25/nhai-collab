import requests

api_key = "44905c3b4aa9458f891afabb22db7378.bT9UGfiqO49hCcPJaZE4iLfW"

# Try Ollama endpoint
url = "https://api.ollama.com/v1/models"
headers = {"Authorization": f"Bearer {api_key}"}
try:
    res = requests.get(url, headers=headers, timeout=10)
    print("Ollama Models API:", res.status_code, res.text[:200])
except Exception as e:
    print(e)
