import os
from openai import OpenAI
client = OpenAI(base_url="http://10.201.91.204:1234", api_key="lm-studio")
response = client.chat.completions.create(
    model="local-model",
    messages=[{"role": "user", "content": "Hi"}],
)
print(response)
