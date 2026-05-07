from zhipuai import ZhipuAI
client = ZhipuAI(api_key="44905c3b4aa9458f891afabb22db7378.bT9UGfiqO49hCcPJaZE4iLfW")
response = client.chat.completions.create(
    model="glm-4",
    messages=[{"role": "user", "content": "hi"}],
)
print(response)
