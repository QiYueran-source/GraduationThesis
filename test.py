from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import torch

# 模型路径
model_path = "~/llm/Qwen2.5-1.5B"
model_path = os.path.expanduser(model_path)

print("=" * 60)
print("Qwen2.5-1.5B 模型测试")
print("=" * 60)

# 1. 加载模型和分词器
print("\n[1] 正在加载模型和分词器...")
try:
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,  # 使用 bfloat16 以节省显存
        device_map="auto"  # 自动选择设备（GPU/CPU）
    )
    print("✅ 模型加载成功！")
    print(f"   设备: {next(model.parameters()).device}")
    print(f"   数据类型: {next(model.parameters()).dtype}")
except Exception as e:
    print(f"❌ 模型加载失败: {e}")
    exit(1)

# 2. 基本文本生成测试
print("\n[2] 基本文本生成测试")
print("-" * 60)

test_prompts = [
    "人工智能的发展历史可以追溯到",
    "The capital of France is",
    "请解释什么是机器学习：",
]

for i, prompt in enumerate(test_prompts, 1):
    print(f"\n测试 {i}: {prompt}")
    print("-" * 60)
    
    # 编码输入
    inputs = tokenizer(prompt, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    # 生成文本
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,  # 最多生成100个新token
            temperature=0.7,     # 控制随机性
            top_p=0.9,           # 核采样
            do_sample=True,      # 启用采样
            pad_token_id=tokenizer.eos_token_id
        )
    
    # 解码输出
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"生成结果: {generated_text}")

# 3. 对话格式测试（虽然这是base模型，但可以手动构建格式）
print("\n[3] 对话格式测试")
print("-" * 60)

# Qwen2.5 使用 ChatML 格式
conversation = [
    {"role": "user", "content": "什么是强化学习？"}
]

# 构建对话格式
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    *conversation
]

# 使用 apply_chat_template 格式化
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

print(f"格式化后的输入: {text[:200]}...")

inputs = tokenizer(text, return_tensors="pt")
if torch.cuda.is_available():
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=150,
        temperature=0.7,
        top_p=0.9,
        do_sample=True,
    )

response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
print(f"\n模型回复: {response}")

# 4. 模型信息展示
print("\n[4] 模型信息")
print("-" * 60)
print(f"模型类型: {model.config.model_type}")
print(f"参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")
print(f"最大上下文长度: {model.config.max_position_embeddings:,} tokens")
print(f"词汇表大小: {model.config.vocab_size:,}")

# 5. Token 统计测试
print("\n[5] Token 统计测试")
print("-" * 60)
test_text = "这是一个测试文本，用于统计token数量。This is a test text for token counting."
tokens = tokenizer.encode(test_text)
print(f"原文: {test_text}")
print(f"Token 数量: {len(tokens)}")
print(f"Token IDs: {tokens[:20]}...")  # 只显示前20个

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)