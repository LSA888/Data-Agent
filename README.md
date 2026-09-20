# 掌柜问数 · Data Agent

基于大模型的电商领域 Text-to-SQL 数据智能问数助手。用自然语言查询数据仓库，自动完成 **语义检索 → SQL 生成 → 验证 → 校正 → 执行** 全流程，前端通过 **SSE 流式输出** 实时展示每一步推理节点状态。

## ✨ 项目特点

- **LangGraph 12 节点确定性工作流**：关键词抽取 → 扩展召回 → 字段/指标/取值召回 → 合并过滤 → SQL 生成 → 验证 → 校正 → 执行，固定执行路径 + 验证校正分支
- **Schema Linking 混合检索架构**：Qdrant 向量库负责字段/指标语义召回 + Elasticsearch 负责字段取值模糊匹配，解决全量 schema 超 token 问题
- **完整的星型 DW 数据仓库**：fact_order + dim_customer / dim_product / dim_region / dim_date，覆盖 4 季度 × 15 省份 × 7 品类 × 4 会员等级
- **自动化评测体系**：85 条分难度测试集（含真实执行的 gold_sql + expected_result），覆盖 JOIN / GROUP BY / 窗口函数（RANK / ROW_NUMBER / LAG / 累计 SUM）/ CASE WHEN / HAVING / Top N / 组内占比等场景

## 🏗️ 架构

```
Vue3 + Vite ──▶ Nginx ──▶ FastAPI (SSE 流式) ──▶ LangGraph Agent
                                                │
                                                ├── 关键词抽取 (LLM)
                                                ├── 扩展召回词 (LLM, 字段/指标/取值三路)
                                                ├── 字段/指标召回 ──▶ Qdrant 向量检索 (bge-large-zh-v1.5)
                                                ├── 取值召回     ──▶ Elasticsearch (IK 分词)
                                                ├── 合并 + 过滤 (LLM + RAG 上下文)
                                                ├── SQL 生成 (LLM, 带窗口函数 / 分组粒度规则)
                                                ├── SQL 验证 (EXPLAIN)
                                                ├── SQL 校正 (失败则循环修正)
                                                └── SQL 执行 ──▶ MySQL 数仓
```

**技术栈**：Python 3.12 · FastAPI · LangChain / LangGraph · MySQL 8.0 · Qdrant · Elasticsearch · sentence-transformers (bge-large-zh-v1.5) · Vue3 · Docker

## 📊 数据仓库模型（星型）

```
                 dim_date                    dim_region
                 ┌──────────┐                ┌──────────┐
                 │ date_id  │                │ region_id │
                 │ year     │                │ province  │
                 │ quarter  │                │ region_name│ ← 大区 (华东/华南/7个值)
                 │ month    │                └─────┬────┘
                 └─────┬────┘                      │
                       │                           │
fact_order             │                           │
┌──────────────────┐   │   ┌──────────────────┐   │
│ order_id (PK)    │   │   │ dim_product      │   │
│ date_id     (FK) │───┘   │ ┌──────────────┐ │   │
│ customer_id (FK) │       │ │ product_id   │ │   │
│ product_id  (FK) │───────▶│ │ product_name │ │   │
│ region_id   (FK) │────────▶│ │ category     │ │   │
│ order_amount     │       │ │ brand        │ │   │
│ order_quantity   │       │ └──────────────┘ │   │
└──────────────────┘       └──────────────────┘   │
       │                                           │
       ▼                                           │
┌──────────────────┐                               │
│ dim_customer     │                               │
│ ┌──────────────┐ │                               │
│ │ customer_id  │ │                               │
│ │ member_level │ │                               │
│ │ gender       │ │                               │
│ └──────────────┘ │                               │
└──────────────────┘                               │
                                                   │
region_id → 省份粒度 (15 个值, 一对一)
region_name → 大区粒度 (7 个值, 多对一)
```

## 🚀 快速开始（本地开发）

### 1. 启动基础设施

```bash
docker compose -f docker/docker-compose.yaml up -d
```

### 2. 下载本地 Embedding 模型（~1.3GB）

模型目录不入库，clone 后手动下载到 `docker/embedding/bge-large-zh-v1.5`：

```bash
huggingface-cli download BAAI/bge-large-zh-v1.5 --local-dir docker/embedding/bge-large-zh-v1.5

# 国内镜像 (推荐)
git clone https://hf-mirror.com/BAAI/bge-large-zh-v1.5 docker/embedding/bge-large-zh-v1.5
```

### 3. 配置

```bash
cp conf/app_config.example.yaml conf/app_config.yaml
# 填入 LLM 的 api_key / base_url
```

### 4. 初始化数据（首次必跑）

```bash
# 4.1 创建表结构 (meta.sql + dw.sql)
# PowerShell 环境需过滤 CREATE DATABASE:
Get-Content docker/mysql/meta.sql | Where-Object { $_ -notmatch 'CREATE DATABASE' } | mysql -h localhost -P 3307 -u root -proot meta
Get-Content docker/mysql/dw.sql   | mysql -h localhost -P 3307 -u root -proot dw

# 4.2 导入 DW 测试数据 (约 1500 条订单)
uv run python scripts/generate_dw_sql.py
mysql -h localhost -P 3307 -u root -proot dw < scripts/dw_extend_data.sql

# 4.3 构建 Meta Knowledge (字段/指标 → Qdrant 向量; 字段取值 → ES 全文)
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

### 5. 启动服务

```bash
# 后端 http://localhost:8000
uv run python main.py

# 前端 http://localhost:5173
cd data-agent-fronted && npm install && npm run dev
```

### 6. API 文档

后端启动后访问 Swagger UI：`http://localhost:8000/docs`

## 🧪 评测

内置 **85 条分难度测试集**，覆盖 Text-to-SQL 核心场景：

| 难度 | 数量 | 覆盖场景 |
|------|------|----------|
| 简单 | 20 | 单表聚合 SUM/AVG/MAX/MIN / COUNT DISTINCT / 基础 JOIN + 过滤 |
| 中等 | 28 | GROUP BY + 排序 / 双维度聚合 / Top N LIMIT / 指标别名 GMV·AOV / 时间序列 / HAVING |
| 困难 | 37 | CASE WHEN 占比 / 窗口函数 RANK·ROW_NUMBER·LAG·累计 SUM / 子查询 / 多表 JOIN / 组内占比 / 条件聚合增长率 / BETWEEN / 多条件 AND/OR |

每条测试用例在真实 MySQL 上执行过，`expected_result` 是数据库实际返回值。

### 运行评测

```bash
# 确保后端已启动
uv run python scripts/eval_sql_accuracy.py

# 输出:
#   - 控制台: 逐条 ✅/❌ + 按难度分层准确率
#   - tests/eval_report.json: 完整报告 (gold_sql vs agent_sql vs 对比结果)
```

### 报告字段说明

```json
{
  "summary": {
    "total": 85,
    "sql_correct": 85,        // Agent SQL 语法正确 (能执行)
    "sql_error": 0,           // Agent SQL 报错
    "result_correct": 28,     // 结果与 gold 一致
    "result_wrong": 7,
    "result_accuracy_pct": 80.0,
    "by_difficulty": { ... }  // 简单 / 中等 / 困难 分层
  },
  "details": [
    {
      "id": "L17",
      "status": "PASS",            // PASS / FAIL_SQL / FAIL_RESULT
      "gold_sql": "SELECT ...",
      "agent_sql": "SELECT ...",   // Agent 实际生成的 SQL
      "gold_result": [{...}],
      "agent_result": [{...}],
      "agent_error": null
    }
  ]
}
```

### 比对策略

采用宽松比对：
- Agent SQL 可以比 gold **多输出列**（如 Agent 多了 RANK() 列不影响主结果比对）
- 但不能少输出 gold 里的值
- 浮点数值做 `round(4)` 归一化，忽略精度差异

## 📁 项目结构

```
Data-Agent/
├── app/
│   ├── agent/
│   │   ├── graph.py                  # LangGraph 工作流定义 (12 节点 + 条件边)
│   │   ├── state.py                  # DataAgentState 状态字典
│   │   ├── nodes/                    # 12 个节点实现
│   │   │   ├── extract_keywords.py
│   │   │   ├── recall_column.py
│   │   │   ├── recall_metric.py
│   │   │   ├── recall_value.py
│   │   │   ├── merge_retrieved_info.py
│   │   │   ├── filter_table.py
│   │   │   ├── filter_metric.py
│   │   │   ├── add_extra_context.py
│   │   │   ├── generate_sql.py
│   │   │   ├── validate_sql.py
│   │   │   ├── correct_sql.py
│   │   │   └── execute_sql.py
│   │   └── prompts/                  # 各节点的 prompt 模板
│   ├── api/                          # FastAPI 路由
│   ├── clients/                      # Qdrant / ES / MySQL / LLM 客户端
│   ├── repositories/                 # 数据访问层
│   ├── services/                     # 业务服务 (QueryService / MetaKnowledgeService)
│   └── scripts/                      # 初始化脚本
├── conf/
│   ├── app_config.yaml               # LLM / DB / Embedding 等运行时配置
│   └── meta_config.yaml              # 表结构 / 字段 alias / 指标定义
├── docker/
│   ├── docker-compose.yaml           # MySQL / ES / Qdrant 一键启动
│   ├── mysql/                        # meta.sql / dw.sql 建表脚本
│   └── embedding/                    # 本地 embedding 模型 (需手动下载)
├── scripts/                          # 辅助脚本
│   ├── generate_dw_sql.py            # 生成 DW 测试数据 INSERT SQL
│   └── eval_sql_accuracy.py          # SQL 生成准确率评测
├── tests/
│   ├── sql_gen_testset.json          # 35 条测试集 (gold_sql + expected_result)
│   └── eval_report.json              # 评测输出报告
├── data-agent-fronted/               # Vue3 前端 (推理过程可视化)
└── pyproject.toml
```

## 📝 已实现的工程要点

| 模块 | 要点 |
|------|------|
| **LangGraph 编排** | 12 节点固定工作流 + validate→correct 条件校正循环，每节点发 progress SSE 事件 |
| **Schema Linking** | Qdrant 向量召回字段/指标 + ES 全文召回取值，5 步检索后再注入 prompt |
| **分组粒度规则** | meta_config.yaml 区分 region_id (省份) / region_name (大区)，prompt 约束 PARTITION BY 粒度 |
| **窗口函数模板** | prompt 内置 Top-N 窗口函数模板（ROW_NUMBER + WHERE rn <= N） |
| **浮点格式化** | dw_mysql_repository 对执行结果统一 round(2) 处理 |
| **评测体系** | 35 条测试集 × eval_sql_accuracy.py，宽松比对 + 按难度分层统计 |

## 🧩 示例问题

- 统计 2025 年各地区的销售总额
- 各省份的销售额排名前 3 的产品
- 黄金会员的消费金额占比是多少
- 各季度 GMV 及环比增长率
- 订单金额超过 50 万的品牌有哪些
- 各会员等级下单金额的分段统计 (低<500/中500-2000/高>2000)

## ⚠️ 已知限制

- **无记忆管理**：当前是单轮无状态 Agent，不支持多轮上下文追问
- **不使用 Tool Calling**：工作流固定编排，Agent 不动态决定调用哪个工具
- **非 RAG 标准用法**：检索的是表结构元数据而非文本知识，属于 Schema Linking 变体
