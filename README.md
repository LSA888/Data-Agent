# 掌柜问数 · Data Agent

基于大模型的 Text-to-SQL 数据智能问数助手：用自然语言查询数据仓库，自动完成 **语义检索 → SQL 生成 → 验证 → 执行** 全流程，前端实时展示每一步进度。

## 架构

```
Vue3 + Vite ──▶ Nginx ──▶ FastAPI (SSE 流式) ──▶ LangGraph Agent
                                                ├─ 关键词抽取 (LLM)
                                                ├─ 字段召回  ──▶ Qdrant 向量检索
                                                ├─ 指标召回  ──▶ Qdrant 向量检索
                                                ├─ 取值召回  ──▶ Elasticsearch (IK 分词)
                                                ├─ 信息合并 / 过滤 (LLM + RAG 上下文)
                                                └─ SQL 生成 / 验证 / 修正 / 执行 ──▶ MySQL 数仓
```

**技术栈**：Python 3.12 · FastAPI · LangChain/LangGraph · MySQL · Qdrant · Elasticsearch · sentence-transformers (bge-large-zh-v1.5) · Vue3 · Docker

## 快速开始（本地开发）

### 1. 基础设施

```bash
docker compose -f docker/docker-compose.yaml up -d   # MySQL/ES/Qdrant 等
```

### 2. 下载本地 Embedding 模型（约 1.3GB）

模型目录不入库，clone 后需手动下载到 `docker/embedding/bge-large-zh-v1.5`：

- HuggingFace: https://huggingface.co/BAAI/bge-large-zh-v1.5
- 国内镜像: https://hf-mirror.com/BAAI/bge-large-zh-v1.5

```bash
# 方式一：huggingface-cli
huggingface-cli download BAAI/bge-large-zh-v1.5 --local-dir docker/embedding/bge-large-zh-v1.5

# 方式二：git clone（国内替换域名为 hf-mirror.com）
git clone https://hf-mirror.com/BAAI/bge-large-zh-v1.5 docker/embedding/bge-large-zh-v1.5
```

### 3. 配置

```bash
cp conf/app_config.example.yaml conf/app_config.yaml   # 填入你的 LLM api_key / base_url
```

### 4. 初始化知识库（首次必跑）

```bash
uv sync
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

### 5. 启动

```bash
uv run python main.py                          # 后端 http://localhost:8000
cd data-agent-fronted && npm install && npm run dev   # 前端 http://localhost:5173
```

## 示例问题

- 统计 2025 年各地区的销售总额
- 哪个地区的销售额最高
- 黄金会员的消费金额占比
