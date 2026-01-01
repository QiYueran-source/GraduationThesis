import os

# 加载分词结果, 如果分词器不在当前目录，需要添加路径
from 分词器 import tokens

# 加载模型
from transformers import AutoModel

checkpoint = 'distilbert-base-uncased-finetuned-sst-2-english'
print(f"正在加载模型: {checkpoint}")
print(f"使用镜像源: {os.environ.get('HF_ENDPOINT')}")
model = AutoModel.from_pretrained(checkpoint)
# print(model) # 得到类似pytorch自定义模型的输出

# 将tokens输入模型
outputs = model(**tokens) # 使用**直接解包  
print(outputs.last_hidden_state.shape) # 输出形状 
"""
torch.Size([2, 16, 768])
表示是2个文本，每个文本16个词（填充到，每个词768个特征  

outputs记录模型的输出，包括  
- last_hidden_state: 每个词的特征  
- attention: 注意力权重  
- hidden_states: 每个层的特征    
"""
# ====================================================================
# ===================================================================
"""
NLP模型，最终需要做分类
"""
# 二分类模型，原模型输出特征，该模型输出分类结果
from transformers import AutoModelForSequenceClassification

checkpoint = 'distilbert-base-uncased-finetuned-sst-2-english'
model_for_classification = AutoModelForSequenceClassification.from_pretrained(checkpoint) # 模型后面加了一个分类头 

outputs = model_for_classification(**tokens)
print(outputs.logits.shape)
print(outputs.logits)
"""
torch.Size([2, 2])，2个文本，每个文本2个分类

分类模型的output    
- logits: 分类分数  
- loss: 损失值  
- hidden_states: 每个层的特征    
- attentions: 注意力权重  
- 其他可能的输出  
"""

# 使用torch的softmax函数进行激活
import torch
softmax = torch.nn.Softmax(dim=1)
probs = softmax(outputs.logits)
print(probs)
"""
tensor([[0.9999, 0.0001],
        [0.0000, 1.0000]])
"""

# 然后指定标签，如情感,这里用模型提供的 
label = model_for_classification.config.id2label
print(label)

# 将模型输出转为标签
preds = torch.argmax(probs, dim=-1) # 取最大值的索引
labels = [model_for_classification.config.id2label[pred.item()] for pred in preds]  
confidences = [probs[i][pred.item()] for i, pred in enumerate(preds)]
print(labels,confidences)




