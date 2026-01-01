"""
分词器：  
将内容切分为单词或者词组，然后将每个词或者词组转换为ID  
还需要辅助信息(hf自动判断)   
"""  
from transformers import AutoTokenizer

checkpoint = 'distilbert-base-uncased-finetuned-sst-2-english' # 加载这个模型  
tokenizer = AutoTokenizer.from_pretrained(checkpoint)  # 加载分词器  

text = ["I've been waiting for a Hugging Face course my whole life.",'Why do you like Transformers?']
tokens = tokenizer(
    text, # 要分词的文本
    padding = True, # 是否填充--将不同长度的文本填充到相同长度（按最长的填充0）  
    truncation = True, # 是否截断--将文本截断到指定长度（很多输入长度为512） 
    return_tensors = 'pt', # 返回的类型--pt:pytorch,tf:tensorflow,np:numpy  
)

# 补充  
# 如果要自己加占位符，需要将attention_mask设置为0  

# 不用的padding
# padding = True, 'max_length', 'longest'  
# True: 将所有文本填充到最长文本长度  
# 'max_length': 将所有文本填充到指定长度, 可以指定max_length参数  
# 'longest': 将所有文本填充到最长文本长度  

if __name__ == '__main__':
    print(tokens)
    """
    返回结果：  
    - input_ids: 词的ID  
    - attention_mask: 注意力掩码，用于忽略填充的token   
    tensor([[  101,  1045,  1005,  2310,  2042,  3403,  2005,  1037, 17662,  2227,
            2607,  2026,  2878,  2166,  1012,   102],
            [  101,  2339,  2079,  2017,  2066, 19081,  1029,   102,     0,     0,
                0,     0,     0,     0,     0,     0]]), 
    'attention_mask': tensor([[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    id为0：填充    
    attention_mask为0：填充    
    """

    # 解码查看ID
    decoded_string = tokenizer.decode(tokens['input_ids'][0]) # 解码，需要输入一个list, 将tensor转为list  
    print(decoded_string)  
    """
    解码输出如下：
    [CLS] i've been waiting for a hugging face course my whole life. [SEP]
    """


