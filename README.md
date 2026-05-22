# Agent-Development
大作业“网络小说智能推荐与舆情分析系统”

## Safe-Search Architect 模块

### 目录结构
- src/safe_search: 语义检索 + 避雷过滤
- src/sentiment_critic: 舆情风险评分与证据摘要
- src/main.py: 最小可运行示例

### 依赖安装
```bash
pip install -r requirements.txt
```

### 环境变量
- DEEPSEEK_API_KEY: DeepSeek API key
- DEEPSEEK_BASE_URL: https://api.deepseek.com
- DEEPSEEK_CHAT_MODEL: deepseek-v4-pro
- DEEPSEEK_EMBEDDING_MODEL: text-embedding-3-large (如需更换请根据供应商支持调整)

### 快速运行
```bash
python src/main.py
```

### 数据字段约定
Book 最小字段:
- id
- title
- intro
- tags
- status (可选)
- sentiment_summary (可选)
