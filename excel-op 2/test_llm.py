import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(
    model="google/gemma-3-27b-it:free",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

try:
    res = llm.invoke("Say 'Hello World'")
    print("SUCCESS")
    print(res.content)
except Exception as e:
    print("FAILED")
    print(e)
