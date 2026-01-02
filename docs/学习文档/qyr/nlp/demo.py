"""
这是一个简单的情感分析  

transformers库的pipeline工具，需要设置HF_HOME和HF_HUB_CACHE环境变量  
会自动下载模型到本地，并使用本地模型进行推理  
"""
from transformers import pipeline

classifier = pipeline('sentiment-analysis')
results = classifier(
    [
        "I've been waiting for a Hugging Face course my whole life.",
        "I hate this so much!",
    ]
)
print(results)
