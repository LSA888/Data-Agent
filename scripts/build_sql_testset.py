"""
构造 SQL 生成准确率测试集

每条样本 = {
  "id": "L1",
  "difficulty": "简单",
  "nl": "用户自然语言问题",
  "target_schema": "涉及的库表和字段",
  "gold_sql": "参考 SQL (正确答案)",
  "expected_result": [{"col1": val1, "col2": val2}, ...]  -- 真实执行结果
}

覆盖场景:
  - 简单: 单表聚合、DISTINCT、基础 JOIN + 等值过滤
  - 中等: GROUP BY + 排序、多指标聚合、Top N、时间序列、指标别名 (GMV/AOV)
  - 困难: 多表 JOIN、CASE WHEN 占比、子查询、窗口函数、复杂筛选条件组合
"""
import json
import subprocess
import re
from decimal import Decimal

# ============================================================
# 1. 表 Schema 描述 (给 Agent 看的简化版)
# ============================================================
SCHEMA_DOC = """
数据库: dw (数据仓库)
───────────────────────────────────────────────────────────────
表 fact_order (订单事实表):
  order_id          VARCHAR(30) PK   -- 订单ID
  customer_id       VARCHAR(20)      -- 客户ID (FK→dim_customer)
  product_id        VARCHAR(20)      -- 商品ID (FK→dim_product)
  date_id           INT              -- 日期ID (FK→dim_date, 格式yyyyMMdd)
  region_id         VARCHAR(20)      -- 地区ID (FK→dim_region)
  order_quantity    INT              -- 购买数量
  order_amount      FLOAT            -- 订单金额

表 dim_customer (客户维度):
  customer_id       VARCHAR(20) PK
  customer_name     VARCHAR(50)
  gender            VARCHAR(10)      -- 男 / 女
  member_level      VARCHAR(20)      -- 青铜 / 白银 / 黄金 / 铂金

表 dim_product (商品维度):
  product_id        VARCHAR(20) PK
  product_name      VARCHAR(200)
  category          VARCHAR(50)      -- 手机数码/家用电器/鞋靴/服饰/食品饮料/休闲零食/图书文娱
  brand             VARCHAR(50)

表 dim_region (地区维度):
  region_id         VARCHAR(20) PK
  province          VARCHAR(50)      -- 省份
  region_name       VARCHAR(50)      -- 大区: 华北/华东/华南/华中/西南/东北/西北

表 dim_date (时间维度):
  date_id           INT PK           -- yyyyMMdd
  year              INT              -- 2025
  quarter           VARCHAR(2)       -- Q1/Q2/Q3/Q4
  month             INT              -- 1-12
  day               INT              -- 1-31

指标别名:
  GMV  = SUM(fact_order.order_amount)  -- 成交总额
  AOV  = SUM(order_amount) / COUNT(order_id)  -- 平均订单金额
───────────────────────────────────────────────────────────────
"""

# ============================================================
# 2. 测试用例定义
# ============================================================
TEST_CASES = [
    # ========================================================
    # L1-L8: 简单 —— 单表聚合 / 基础 JOIN + 等值过滤
    # ========================================================
    {
        "id": "L1", "difficulty": "简单", "category": "单表聚合",
        "nl": "所有订单的总销售额是多少",
        "target_schema": "fact_order(order_amount)",
        "gold_sql": "SELECT ROUND(SUM(order_amount), 2) AS gmv FROM fact_order"
    },
    {
        "id": "L2", "difficulty": "简单", "category": "单表聚合",
        "nl": "总共有多少个不同的客户下过单",
        "target_schema": "fact_order(customer_id)",
        "gold_sql": "SELECT COUNT(DISTINCT customer_id) AS customer_count FROM fact_order"
    },
    {
        "id": "L3", "difficulty": "简单", "category": "单表聚合",
        "nl": "总共有多少个订单",
        "target_schema": "fact_order(order_id)",
        "gold_sql": "SELECT COUNT(order_id) AS order_count FROM fact_order"
    },
    {
        "id": "L4", "difficulty": "简单", "category": "单表聚合",
        "nl": "商品的总销量是多少件",
        "target_schema": "fact_order(order_quantity)",
        "gold_sql": "SELECT SUM(order_quantity) AS total_quantity FROM fact_order"
    },
    {
        "id": "L5", "difficulty": "简单", "category": "等值过滤+JOIN",
        "nl": "广东省的订单总金额是多少",
        "target_schema": "fact_order, dim_region",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id WHERE r.province = '广东省'"
    },
    {
        "id": "L6", "difficulty": "简单", "category": "等值过滤+JOIN",
        "nl": "黄金会员的订单金额总和",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id WHERE c.member_level = '黄金'"
    },
    {
        "id": "L7", "difficulty": "简单", "category": "等值过滤+JOIN",
        "nl": "手机数码品类的销售额",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id WHERE p.category = '手机数码'"
    },
    {
        "id": "L8", "difficulty": "简单", "category": "时间过滤+JOIN",
        "nl": "2025年1月的订单金额是多少",
        "target_schema": "fact_order, dim_date",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_date d ON f.date_id = d.date_id WHERE d.year = 2025 AND d.month = 1"
    },

    # ========================================================
    # L9-L16, L26-L27: 中等 —— GROUP BY / Top N / 时间序列 / 指标别名
    # ========================================================
    {
        "id": "L9", "difficulty": "中等", "category": "GROUP BY+排序",
        "nl": "各省份的销售金额排名",
        "target_schema": "fact_order, dim_region",
        "gold_sql": "SELECT r.province, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id GROUP BY r.province ORDER BY gmv DESC"
    },
    {
        "id": "L10", "difficulty": "中等", "category": "GROUP BY+多指标",
        "nl": "各会员等级的消费金额和订单数",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT c.member_level, ROUND(SUM(f.order_amount), 2) AS gmv, COUNT(f.order_id) AS order_count FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id GROUP BY c.member_level"
    },
    {
        "id": "L11", "difficulty": "中等", "category": "GROUP BY+双指标",
        "nl": "各商品品类的销量和销售额",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT p.category, SUM(f.order_quantity) AS quantity, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id GROUP BY p.category"
    },
    {
        "id": "L12", "difficulty": "中等", "category": "时间序列+排序",
        "nl": "2025年每个月的销售额趋势",
        "target_schema": "fact_order, dim_date",
        "gold_sql": "SELECT d.month, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_date d ON f.date_id = d.date_id WHERE d.year = 2025 GROUP BY d.month ORDER BY d.month"
    },
    {
        "id": "L13", "difficulty": "中等", "category": "GROUP BY+排序",
        "nl": "各品牌的销售额排名",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT p.brand, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id GROUP BY p.brand ORDER BY gmv DESC"
    },
    {
        "id": "L14", "difficulty": "中等", "category": "GROUP BY+双COUNT",
        "nl": "各地区的订单数量和客户数",
        "target_schema": "fact_order, dim_region",
        "gold_sql": "SELECT r.region_name, COUNT(DISTINCT f.order_id) AS order_count, COUNT(DISTINCT f.customer_id) AS customer_count FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id GROUP BY r.region_name"
    },
    {
        "id": "L15", "difficulty": "中等", "category": "Top N LIMIT",
        "nl": "销售额最高的前5个商品",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT p.product_name, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id GROUP BY p.product_name ORDER BY gmv DESC LIMIT 5"
    },
    {
        "id": "L16", "difficulty": "中等", "category": "Top N LIMIT",
        "nl": "下单最多的3位客户",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT c.customer_name, COUNT(f.order_id) AS order_count FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id GROUP BY c.customer_name ORDER BY order_count DESC LIMIT 3"
    },
    {
        "id": "L26", "difficulty": "中等", "category": "指标别名 GMV",
        "nl": "今年的GMV是多少",
        "target_schema": "fact_order, dim_date",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS GMV FROM fact_order f JOIN dim_date d ON f.date_id = d.date_id WHERE d.year = 2025"
    },
    {
        "id": "L27", "difficulty": "中等", "category": "指标别名 AOV",
        "nl": "各地区的平均订单金额AOV",
        "target_schema": "fact_order, dim_region",
        "gold_sql": "SELECT r.region_name, ROUND(SUM(f.order_amount) / COUNT(f.order_id), 2) AS AOV FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id GROUP BY r.region_name"
    },

    # ========================================================
    # L17-L25, L28-L32: 困难 —— CASE WHEN占比 / 子查询 / 多表JOIN / 窗口函数
    # ========================================================
    {
        "id": "L17", "difficulty": "困难", "category": "CASE WHEN占比",
        "nl": "黄金会员的消费金额占比是多少",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT ROUND(SUM(CASE WHEN c.member_level = '黄金' THEN f.order_amount ELSE 0 END) / SUM(f.order_amount), 4) AS gold_ratio FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id"
    },
    {
        "id": "L18", "difficulty": "困难", "category": "CASE WHEN占比",
        "nl": "男性客户的订单占比",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT ROUND(SUM(CASE WHEN c.gender = '男' THEN 1 ELSE 0 END) / COUNT(f.order_id), 4) AS male_order_ratio FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id"
    },
    {
        "id": "L19", "difficulty": "困难", "category": "子查询+GROUP BY",
        "nl": "各会员等级的消费金额占总消费的比例",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT c.member_level, ROUND(SUM(f.order_amount) / (SELECT SUM(order_amount) FROM fact_order), 4) AS ratio FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id GROUP BY c.member_level"
    },
    {
        "id": "L20", "difficulty": "困难", "category": "派生指标 AOV",
        "nl": "平均客单价是多少",
        "target_schema": "fact_order",
        "gold_sql": "SELECT ROUND(SUM(order_amount) / COUNT(order_id), 2) AS aov FROM fact_order"
    },
    {
        "id": "L21", "difficulty": "困难", "category": "三表JOIN",
        "nl": "华东地区各品类的销售额",
        "target_schema": "fact_order, dim_product, dim_region",
        "gold_sql": "SELECT p.category, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id JOIN dim_region r ON f.region_id = r.region_id WHERE r.region_name = '华东' GROUP BY p.category"
    },
    {
        "id": "L22", "difficulty": "困难", "category": "三表JOIN+时间过滤",
        "nl": "2025年Q1各省份的销售额和订单数",
        "target_schema": "fact_order, dim_region, dim_date",
        "gold_sql": "SELECT r.province, ROUND(SUM(f.order_amount), 2) AS gmv, COUNT(f.order_id) AS order_count FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id WHERE d.year = 2025 AND d.quarter = 'Q1' GROUP BY r.province"
    },
    {
        "id": "L23", "difficulty": "困难", "category": "IN条件+多表JOIN",
        "nl": "白银及以上会员在手机数码品类的消费金额",
        "target_schema": "fact_order, dim_customer, dim_product",
        "gold_sql": "SELECT c.member_level, p.category, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id JOIN dim_product p ON f.product_id = p.product_id WHERE c.member_level IN ('白银', '黄金', '铂金') AND p.category = '手机数码' GROUP BY c.member_level"
    },
    {
        "id": "L24", "difficulty": "困难", "category": "多维度GROUP BY",
        "nl": "每个会员等级的平均订单金额和订单数",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT c.member_level, COUNT(f.order_id) AS order_count, ROUND(SUM(f.order_amount) / COUNT(f.order_id), 2) AS aov FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id GROUP BY c.member_level"
    },
    {
        "id": "L25", "difficulty": "困难", "category": "窗口函数 RANK",
        "nl": "每个季度内部销售额排名前3的省份",
        "target_schema": "fact_order, dim_region, dim_date",
        "gold_sql": "SELECT t.quarter, t.province, t.gmv FROM (SELECT d.quarter, r.province, ROUND(SUM(f.order_amount), 2) AS gmv, RANK() OVER(PARTITION BY d.quarter ORDER BY SUM(f.order_amount) DESC) AS rn FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id GROUP BY d.quarter, r.province) t WHERE t.rn <= 3 ORDER BY t.quarter, t.gmv DESC"
    },
    {
        "id": "L28", "difficulty": "困难", "category": "阈值过滤",
        "nl": "单笔订单金额超过1万元的订单有多少个",
        "target_schema": "fact_order",
        "gold_sql": "SELECT COUNT(order_id) AS big_order_count FROM fact_order WHERE order_amount > 10000"
    },
    {
        "id": "L29", "difficulty": "困难", "category": "CASE WHEN+百分比",
        "nl": "黄金会员的消费金额在总消费中的占比(百分比形式)",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT ROUND(SUM(CASE WHEN c.member_level = '黄金' THEN f.order_amount ELSE 0 END) / SUM(f.order_amount) * 100, 2) AS gold_ratio_pct FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id"
    },
    {
        "id": "L30", "difficulty": "困难", "category": "多占比计算",
        "nl": "苹果品牌的GMV占比和销量占比分别是多少",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT ROUND(SUM(CASE WHEN p.brand = '苹果' THEN f.order_amount ELSE 0 END) / SUM(f.order_amount), 4) AS apple_gmv_ratio, ROUND(SUM(CASE WHEN p.brand = '苹果' THEN f.order_quantity ELSE 0 END) / SUM(f.order_quantity), 4) AS apple_qty_ratio FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id"
    },
    {
        "id": "L31", "difficulty": "困难", "category": "窗口函数 LAG 环比",
        "nl": "各季度GMV及环比增长率",
        "target_schema": "fact_order, dim_date",
        "gold_sql": "SELECT t.quarter, t.gmv, ROUND((t.gmv - t.prev_gmv) / t.prev_gmv * 100, 2) AS growth_pct FROM (SELECT d.quarter, SUM(f.order_amount) AS gmv, LAG(SUM(f.order_amount)) OVER(ORDER BY MIN(d.date_id)) AS prev_gmv FROM fact_order f JOIN dim_date d ON f.date_id = d.date_id GROUP BY d.quarter) t ORDER BY t.quarter"
    },
    {
        "id": "L32", "difficulty": "困难", "category": "BETWEEN时间范围",
        "nl": "2025年上半年华南地区的销售额",
        "target_schema": "fact_order, dim_region, dim_date",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id WHERE d.date_id BETWEEN 20250101 AND 20250630 AND r.region_name = '华南'"
    },
    {
        "id": "L33", "difficulty": "困难", "category": "多条件组合 AND/OR",
        "nl": "2025年Q1或Q3期间, 华南地区的铂金会员消费金额",
        "target_schema": "fact_order, dim_region, dim_customer, dim_date",
        "gold_sql": "SELECT ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_region r ON f.region_id = r.region_id JOIN dim_customer c ON f.customer_id = c.customer_id JOIN dim_date d ON f.date_id = d.date_id WHERE (d.quarter = 'Q1' OR d.quarter = 'Q3') AND r.region_name = '华南' AND c.member_level = '铂金'"
    },
    {
        "id": "L34", "difficulty": "困难", "category": "HAVING分组后过滤",
        "nl": "订单金额超过50万的品牌有哪些",
        "target_schema": "fact_order, dim_product",
        "gold_sql": "SELECT p.brand, ROUND(SUM(f.order_amount), 2) AS gmv FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id GROUP BY p.brand HAVING SUM(f.order_amount) > 500000 ORDER BY gmv DESC"
    },
    {
        "id": "L35", "difficulty": "困难", "category": "CASE WHEN多分支",
        "nl": "各会员等级下单金额的分段统计 (低<500/中500-2000/高>2000)",
        "target_schema": "fact_order, dim_customer",
        "gold_sql": "SELECT c.member_level, SUM(CASE WHEN f.order_amount < 500 THEN 1 ELSE 0 END) AS low_orders, SUM(CASE WHEN f.order_amount BETWEEN 500 AND 2000 THEN 1 ELSE 0 END) AS mid_orders, SUM(CASE WHEN f.order_amount > 2000 THEN 1 ELSE 0 END) AS high_orders FROM fact_order f JOIN dim_customer c ON f.customer_id = c.customer_id GROUP BY c.member_level"
    },
]

# ============================================================
# 3. 执行参考 SQL 获取真实结果
# ============================================================
def run_mysql_query(sql: str) -> list[dict]:
    """执行一条 SQL, 返回行列表 (list[dict])"""
    result = subprocess.run(
        [
            "mysql", "-h", "localhost", "-P", "3307",
            "-u", "root", "-proot",
            "-N", "-B",  # 无表头、tab分隔
            "dw", "-e", sql
        ],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        err = result.stderr.strip()
        raise RuntimeError(f"SQL执行失败: {err}\nSQL: {sql}")

    raw = result.stdout.strip()
    if not raw:
        return []

    # 解析 tab-separated 输出 + 获取列名
    col_result = subprocess.run(
        ["mysql", "-h", "localhost", "-P", "3307", "-u", "root", "-proot", "dw", "-e", sql],
        capture_output=True, text=True, encoding="utf-8"
    )
    lines = col_result.stdout.strip().split("\n")
    if len(lines) < 2:
        return []

    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        row = {}
        for i, col in enumerate(header):
            val = values[i] if i < len(values) else None
            # 类型转换
            if val is None or val == "NULL":
                row[col] = None
            else:
                try:
                    row[col] = int(val)
                except ValueError:
                    try:
                        row[col] = round(float(val), 4)
                    except ValueError:
                        row[col] = val
        rows.append(row)
    return rows


def main():
    print("=" * 60)
    print("构建 SQL 生成测试集")
    print("=" * 60)

    dataset = {
        "schema": SCHEMA_DOC,
        "test_cases": []
    }

    success = 0
    failed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {tc['id']} ({tc['difficulty']}): {tc['nl'][:40]}...")
        try:
            expected = run_mysql_query(tc["gold_sql"])
            item = {
                "id": tc["id"],
                "difficulty": tc["difficulty"],
                "category": tc["category"],
                "nl": tc["nl"],
                "target_schema": tc["target_schema"],
                "gold_sql": tc["gold_sql"],
                "expected_result": expected,
                "result_row_count": len(expected),
            }
            dataset["test_cases"].append(item)
            sample = expected[0] if expected else "(empty)"
            print(f"  ✅ {len(expected)} rows | sample: {sample}")
            success += 1
        except Exception as e:
            print(f"  ❌ 执行失败: {e}")
            failed += 1

    # 按难度统计
    stats = {}
    for tc in dataset["test_cases"]:
        d = tc["difficulty"]
        stats.setdefault(d, 0)
        stats[d] += 1
    dataset["stats"] = stats
    dataset["total"] = success

    # 输出 JSON
    output_path = "tests/sql_gen_testset.json"
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 60)
    print(f"✅ 测试集构建完成!")
    print(f"   成功: {success}/{len(TEST_CASES)}, 失败: {failed}")
    print(f"   按难度分布: {stats}")
    print(f"   输出文件: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
