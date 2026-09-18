"""验证: 统计各地区总销售额排名前3的产品 (修复后)"""
import json, requests, sys

resp = requests.post(
    'http://localhost:8000/api/query',
    json={'query': '统计各地区总销售额排名前3的产品'},
    stream=True, timeout=120,
)

agent_sql = None
agent_result = None
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data: "):
        continue
    try:
        data = json.loads(line[6:])
    except json.JSONDecodeError:
        continue
    tp = data.get("type", "")
    payload = data.get("data")

    if tp == "sql":
        agent_sql = payload.strip()
    elif tp == "result" and isinstance(payload, list):
        agent_result = payload
    elif tp == "progress":
        print(f"▶ {data.get('step','')} [{data.get('status','')}]")

print(f"\n🎯 Agent SQL:")
print(agent_sql)
print(f"\n📊 结果 ({len(agent_result or [])} 行)")
if agent_result:
    # 按 region_name 分组统计
    from collections import Counter
    region_counts = Counter(r.get('region_name', r.get('region_code', '?')) for r in agent_result)
    print(f"\n每个地区的行数 (期望: 每个地区恰好 3 行):")
    for region, cnt in region_counts.items():
        flag = "✅" if cnt == 3 else "❌"
        print(f"  {flag} {region}: {cnt} 行")
    print(f"\n总行数: {len(agent_result)} (期望 21 = 7地区 × 3)")
else:
    print("❌ 没拿到结果!")

# 核心验证: PARTITION BY 里有没有 region_name 而不是 region_id
if agent_sql:
    if "PARTITION BY r.region_name" in agent_sql or "PARTITION BY region_name" in agent_sql:
        print("\n✅ PARTITION BY 用了 region_name (大区) — 修复生效!")
    elif "PARTITION BY r.region_id" in agent_sql or "PARTITION BY region_id" in agent_sql:
        print("\n❌ PARTITION BY 还是用了 region_id — 修复没生效")
    else:
        print("\n🤔 没找到 PARTITION BY — Agent 可能没用到窗口函数")
