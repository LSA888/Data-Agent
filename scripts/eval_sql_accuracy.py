"""
SQL 生成准确率评测脚本 (v2)
==========================

【输出 JSON 报告结构】
{
  "summary": {
    "total": 35,
    "sql_correct": 33,          // Agent SQL 语法正确 (能执行)
    "sql_error": 2,             // Agent SQL 语法错误 (执行报错)
    "result_correct": 32,       // 结果与 expected_result 一致
    "result_wrong": 3,          // 结果不一致
    "accuracy_pct": 91.4,
    "by_difficulty": { ... }
  },
  "details": [
    {
      "id": "L7",
      "status": "PASS",          // PASS / FAIL_SQL / FAIL_RESULT
      "difficulty": "简单",
      "category": "等值过滤+JOIN",
      "nl": "手机数码品类的销售额",
      "gold_sql": "SELECT ...",
      "agent_sql": "SELECT ...",  // 抓到的真实 SQL
      "sql_runnable": true,      // Agent SQL 能否执行
      "gold_result": [{...}],
      "agent_result": [{...}],   // 类型已统一
      "gold_rows": 1,
      "agent_rows": 1
    },
    ...
  ]
}
"""

import json
import os
import re
import sys
import time
import subprocess
from decimal import Decimal
from pathlib import Path

import requests

# ==================== 配置 ====================
BACKEND_URL = "http://localhost:8000/api/query"
TESTSET_PATH = Path(__file__).parent.parent / "tests" / "sql_gen_testset.json"
REPORT_PATH = Path(__file__).parent.parent / "tests" / "eval_report.json"
# SSE 流式读取: timeout 是“两个数据块之间”的最大等待, 不是整请求耗时
# 困难题(窗口函数)LLM 长尾延迟较高, read timeout 给 300s; 可用环境变量覆盖
CONNECT_TIMEOUT = float(os.getenv("EVAL_CONNECT_TIMEOUT", "10"))
READ_TIMEOUT = float(os.getenv("EVAL_READ_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("EVAL_MAX_RETRIES", "2"))  # 超时/连接错误时的最大重试次数(不含首次)
# =============================================


def call_agent(nl_query: str) -> tuple[str | None, list[dict] | None, str | None]:
    """
    调用后端 API, 解析 SSE 流

    返回: (agent_sql, agent_result, agent_error)
    超时/连接异常时自动重试 MAX_RETRIES 次; 最终失败返回 error 而非抛出,
    保证单条用例异常不会中断整批评测。
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        sql_text = None
        result_rows = None
        error_msg = None

        try:
            resp = requests.post(
                BACKEND_URL,
                json={"query": nl_query},
                stream=True,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            resp.raise_for_status()

            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                try:
                    data = json.loads(raw_line[6:])
                except json.JSONDecodeError:
                    continue

                tp = data.get("type", "")
                payload = data.get("data")

                if tp == "sql" and isinstance(payload, str):
                    sql_text = payload.strip()

                elif tp == "result" and isinstance(payload, list):
                    result_rows = payload

                elif tp == "error":
                    error_msg = str(payload)

            return sql_text, result_rows, error_msg

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            # 读超时/连接断开: 等 3s 后重试 (SSE 中途超时会丢流, 只能整请求重发)
            last_error = f"请求超时/连接中断(第{attempt + 1}次): {e}"
            if attempt < MAX_RETRIES:
                print(f"  ⏳ {last_error} → 3秒后重试...", flush=True)
                time.sleep(3)
                continue
            return None, None, last_error
        except Exception as e:
            return None, None, f"请求异常: {e}"

    return None, None, last_error


def normalize_value(val):
    """
    把各种类型的值统一成 JSON 友好的可比较类型:
    - str 中看起来像数字的 → float
    - Decimal → float
    - float → round(4)
    - 其他原样
    """
    if val is None or val == "NULL":
        return None
    if isinstance(val, Decimal):
        return round(float(val), 4)
    if isinstance(val, str):
        s = val.strip()
        try:
            return round(float(s), 4)
        except ValueError:
            return s
    if isinstance(val, float):
        return round(val, 4)
    if isinstance(val, bool):
        return val
    return val


def normalize_rows(rows: list[dict] | None) -> list[dict]:
    """把结果集里每个 value 做类型归一化"""
    if not rows:
        return []
    return [
        {k: normalize_value(v) for k, v in row.items()}
        for row in rows
    ]


def sort_key(x):
    if x is None:
        return (0, "")
    if isinstance(x, (int, float)):
        return (1, f"{x:.6f}")
    return (2, str(x))


def row_values(row: dict) -> set:
    """把一行的所有值 (normalize 后) 放到 set 里"""
    return {normalize_value(v) for v in row.values()}


def compare_results(gold: list[dict] | None, agent: list[dict] | None) -> bool:
    """
    宽松比对结果集:
    - 行数必须相同
    - gold 每一行的值集合 是 agent 某一行值集合的子集 (agent 允许多输出额外列)
    - 但 gold 不能缺失任何自己的值 (agent 不能少)

    举例:
      gold_row:  {"province": "四川", "gmv": 843801.22}         → values = {"四川", 843801.22}
      agent_row: {"province": "四川", "gmv": 843801.22, "rank": 1} → values = {"四川", 843801.22, 1}
      → gold.values ⊆ agent.values ✅ 匹配

      gold_row:  {"gmv": 100}       → values = {100}
      agent_row: {"gmv": None}      → values = {None}
      → gold.values ⊈ agent.values ❌ 不匹配 (agent 值错误)
    """
    gold = normalize_rows(gold)
    agent = normalize_rows(agent)

    if len(gold) != len(agent):
        return False

    # 贪心匹配: 对每个 gold_row, 找一个 agent_row 使得 gold.values ⊆ agent.values
    used_agent_rows = set()
    for g_row in gold:
        g_vals = row_values(g_row)
        matched = False
        for i, a_row in enumerate(agent):
            if i in used_agent_rows:
                continue
            a_vals = row_values(a_row)
            if g_vals.issubset(a_vals):
                used_agent_rows.add(i)
                matched = True
                break
        if not matched:
            return False

    return True


def build_report(records: list[dict], elapsed: float) -> dict:
    """根据已完成的记录构建报告 (统计口径与最终汇总一致)"""
    total = len(records)
    pass_count = sum(1 for r in records if r["status"] == "PASS")
    fail_sql = sum(1 for r in records if r["status"] == "FAIL_SQL")
    fail_result = sum(1 for r in records if r["status"] == "FAIL_RESULT")
    sql_ok = total - fail_sql
    result_ok = pass_count

    by_diff = {}
    for r in records:
        d = r["difficulty"]
        by_diff.setdefault(d, {"total": 0, "pass": 0, "fail_sql": 0, "fail_result": 0})
        by_diff[d]["total"] += 1
        by_diff[d][r["status"].lower()] += 1

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "backend_url": BACKEND_URL,
        "elapsed_seconds": round(elapsed, 1),
        "per_case_seconds": round(elapsed / total, 1) if total else 0,
        "summary": {
            "total": total,
            "sql_correct": sql_ok,
            "sql_error": fail_sql,
            "result_correct": result_ok,
            "result_wrong": fail_result + fail_sql,
            "sql_accuracy_pct": round(sql_ok / total * 100, 1) if total else 0,
            "result_accuracy_pct": round(result_ok / total * 100, 1) if total else 0,
            "by_difficulty": {
                d: {
                    "total": s["total"],
                    "pass": s["pass"],
                    "fail_sql": s["fail_sql"],
                    "fail_result": s["fail_result"],
                    "result_accuracy_pct": round(s["pass"] / s["total"] * 100, 1) if s["total"] else 0,
                }
                for d, s in sorted(by_diff.items())
            },
        },
        "details": records,
    }


def save_report(records: list[dict], elapsed: float):
    """实时落盘, 保证中途超时/崩溃时已跑完的结果不丢"""
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(build_report(records, elapsed), f, ensure_ascii=False, indent=2, default=str)


def main():
    # ---- 检查后端 ----
    try:
        r = requests.get(BACKEND_URL.replace("/api/query", "/docs"), timeout=3)
        if r.status_code != 200:
            print(f"❌ 后端异常, 状态码: {r.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        print("❌ 后端没启动! 先跑: .\\.venv\\Scripts\\python.exe main.py")
        sys.exit(1)

    # ---- 加载测试集 ----
    with open(TESTSET_PATH, encoding="utf-8") as f:
        testset = json.load(f)
    cases = testset["test_cases"]

    print("=" * 70)
    print("Agent SQL 生成准确率评测")
    print(f"测试集: {len(cases)} 条 | 后端: {BACKEND_URL}")
    print("=" * 70)

    records = []
    t0 = time.time()

    for i, tc in enumerate(cases, 1):
        nl = tc["nl"]
        print(f"\n[{i:2d}/{len(cases)}] {tc['id']} [{tc['difficulty']}] {nl}", flush=True)

        agent_sql, agent_result, agent_error = call_agent(nl)
        gold = normalize_rows(tc["expected_result"])
        agent_norm = normalize_rows(agent_result)

        # 判定
        sql_runnable = agent_error is None and agent_result is not None
        result_match = compare_results(agent_norm, gold)

        if not sql_runnable:
            status = "FAIL_SQL"
        elif not result_match:
            status = "FAIL_RESULT"
        else:
            status = "PASS"

        icon = {"PASS": "✅", "FAIL_SQL": "🟠", "FAIL_RESULT": "❌"}[status]
        print(f"  {icon} {status}", flush=True)
        print(f"     Gold SQL:  {tc['gold_sql'][:100]}", flush=True)
        print(f"     Agent SQL: {(agent_sql or '(未抓到)')[:100]}", flush=True)
        print(f"     Gold rows={len(gold)}  Agent rows={len(agent_norm)}", flush=True)
        if not sql_runnable and agent_error:
            print(f"     SQL Error: {agent_error[:120]}", flush=True)
        if not result_match and sql_runnable:
            diff_agent = agent_norm[:2] if agent_norm else []
            diff_gold = gold[:2]
            print(f"     Agent[:2]: {diff_agent}", flush=True)
            print(f"     Gold[:2]:  {diff_gold}", flush=True)

        records.append({
            "id": tc["id"],
            "status": status,
            "difficulty": tc["difficulty"],
            "category": tc["category"],
            "nl": nl,
            "gold_sql": tc["gold_sql"],
            "agent_sql": agent_sql,
            "sql_runnable": sql_runnable,
            "result_match": result_match,
            "gold_rows": len(gold),
            "agent_rows": len(agent_norm),
            "gold_result": gold,
            "agent_result": agent_norm,
            "agent_error": agent_error,
        })

        # 每条用例后实时落盘, 中途异常也能保留已完成结果
        save_report(records, time.time() - t0)

    elapsed = time.time() - t0

    # ---- 统计 ----
    final_report = build_report(records, elapsed)
    summary = final_report["summary"]
    total = summary["total"]
    sql_ok = summary["sql_correct"]
    fail_sql = summary["sql_error"]
    result_ok = summary["result_correct"]
    fail_result = sum(1 for r in records if r["status"] == "FAIL_RESULT")
    by_diff = {
        d: s for d, s in summary["by_difficulty"].items()
    }

    print("\n" + "=" * 70)
    print("📊 评测结果汇总")
    print("=" * 70)
    print(f"\n  总耗时: {elapsed:.0f} 秒 ({elapsed/total:.0f}秒/条)")
    print(f"\n  SQL 语法层面:")
    print(f"    ✅ 可执行: {sql_ok}/{total}  ({sql_ok/total*100:.1f}%)")
    print(f"    🟠 报错:   {fail_sql}/{total}")
    print(f"\n  查询结果层面:")
    print(f"    ✅ 正确:   {result_ok}/{total}  ({result_ok/total*100:.1f}%)")
    print(f"    ❌ 错误:   {fail_result + fail_sql}/{total}")

    print(f"\n  按难度分层 (结果正确率):")
    for diff, s in sorted(by_diff.items()):
        acc = s["pass"] / s["total"] * 100 if s["total"] else 0
        bar = "█" * int(acc / 5) + "░" * (20 - int(acc / 5))
        print(f"    {diff:>4s}: {s['pass']:2d}/{s['total']:2d} {bar} {acc:5.1f}%")
        if s["fail_sql"] or s["fail_result"]:
            print(f"         (SQL报错 {s['fail_sql']}, 结果错误 {s['fail_result']})")

    # 失败题目清单
    fails = [r for r in records if r["status"] != "PASS"]
    if fails:
        print(f"\n  ❌ 失败明细 ({len(fails)} 条):")
        for r in fails:
            reason = "SQL报错" if r["status"] == "FAIL_SQL" else "结果不一致"
            print(f"    {r['id']} [{r['difficulty']}] {reason} — {r['nl'][:50]}")

    # ---- 保存最终报告 ----
    save_report(records, elapsed)

    print(f"\n  📄 完整报告: {REPORT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
