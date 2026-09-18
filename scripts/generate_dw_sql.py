"""生成 DW 扩展数据 SQL 文件 - 用于管道喂给 mysql CLI"""
import random
from datetime import datetime, timedelta

random.seed(42)

# ========== 新增维度数据 ==========

NEW_REGIONS = [
    ("R007", "辽宁省", "东北", "中国"),
    ("R008", "吉林省", "东北", "中国"),
    ("R009", "黑龙江省", "东北", "中国"),
    ("R010", "陕西省", "西北", "中国"),
    ("R011", "甘肃省", "西北", "中国"),
    ("R012", "云南省", "西南", "中国"),
    ("R013", "贵州省", "西南", "中国"),
    ("R014", "福建省", "华东", "中国"),
    ("R015", "江苏省", "华东", "中国"),
]

NEW_CUSTOMERS = [
    ("C021", "陈明", "男", "黄金"),
    ("C022", "赵丽", "女", "黄金"),
    ("C023", "孙强", "男", "白银"),
    ("C024", "周洁", "女", "白银"),
    ("C025", "吴彦", "男", "青铜"),
    ("C026", "郑红", "女", "青铜"),
    ("C027", "冯雷", "男", "铂金"),
    ("C028", "蔡琳", "女", "铂金"),
    ("C029", "韩磊", "男", "黄金"),
    ("C030", "杨雪", "女", "黄金"),
    ("C031", "林永", "男", "白银"),
    ("C032", "何静", "女", "铂金"),
    ("C033", "高翔", "男", "青铜"),
    ("C034", "梁爽", "女", "白银"),
    ("C035", "宋佳", "女", "黄金"),
    ("C036", "唐杰", "男", "铂金"),
    ("C037", "许晴", "女", "青铜"),
    ("C038", "邓超", "男", "白银"),
    ("C039", "曹颖", "女", "黄金"),
    ("C040", "彭涛", "男", "铂金"),
]

NEW_PRODUCTS = [
    ("P016", "华为 MateBook X Pro", "手机数码", "华为"),
    ("P017", "小米 14 Ultra", "手机数码", "小米"),
    ("P018", "OPPO Find X7", "手机数码", "OPPO"),
    ("P019", "vivo X100 Pro", "手机数码", "vivo"),
    ("P020", "MacBook Pro 14寸", "手机数码", "苹果"),
    ("P021", "戴森 Airwrap 卷发棒", "家用电器", "戴森"),
    ("P022", "格力空调 KFR-72LW", "家用电器", "格力"),
    ("P023", "海尔冰箱 BCD-510", "家用电器", "海尔"),
    ("P024", "飞利浦空气炸锅", "家用电器", "飞利浦"),
    ("P025", "耐克 Jordan 1 Retro", "鞋靴", "耐克"),
    ("P026", "阿迪达斯 Yeezy Boost", "鞋靴", "阿迪达斯"),
    ("P027", "New Balance 990v5", "鞋靴", "New Balance"),
    ("P028", "优衣库羽绒服", "服饰", "优衣库"),
    ("P029", "ZARA 西装外套", "服饰", "ZARA"),
    ("P030", "H&M 连衣裙", "服饰", "H&M"),
    ("P031", "星巴克美式咖啡豆", "食品饮料", "星巴克"),
    ("P032", "伊利纯牛奶 1L*6", "食品饮料", "伊利"),
    ("P033", "农夫山泉 550ml*24", "食品饮料", "农夫山泉"),
    ("P034", "三只松鼠坚果礼盒", "休闲零食", "三只松鼠"),
    ("P035", "良品铺子每日坚果", "休闲零食", "良品铺子"),
    ("P036", "《三体》全集", "图书文娱", "重庆出版社"),
    ("P037", "乐高城市系列积木", "图书文娱", "乐高"),
    ("P038", "Sony WH-1000XM5 耳机", "手机数码", "索尼"),
    ("P039", "Bose QuietComfort 耳机", "手机数码", "Bose"),
    ("P040", "Switch OLED 游戏机", "手机数码", "任天堂"),
]


def escape_sql(s):
    """简单 SQL 字符串转义"""
    return str(s).replace("'", "\\'")


def generate_date_values(year, start_month, end_month):
    values = []
    for month in range(start_month, end_month + 1):
        if month == 12:
            days = 31
        else:
            days = (datetime(year, month + 1, 1) - timedelta(days=1)).day
        q = f"Q{(month - 1) // 3 + 1}"
        for d in range(1, days + 1):
            did = year * 10000 + month * 100 + d
            values.append(f"({did}, {year}, '{q}', {month}, {d})")
    return ",\n".join(values)


def main():
    lines = ["USE dw;", ""]

    # 1. dim_date
    print("生成 dim_date Q2-Q4...")
    lines.append("-- dim_date: 补全 Q2/Q3/Q4 2025")
    lines.append("INSERT IGNORE INTO dim_date (date_id, year, quarter, month, day) VALUES")
    lines.append(generate_date_values(2025, 4, 12) + ";")
    lines.append("")

    # 2. dim_region
    print("生成 dim_region...")
    lines.append("-- dim_region: 新增东北/西北等省份")
    region_vals = ",\n".join(
        f"('{escape_sql(r[0])}', '{escape_sql(r[1])}', '{escape_sql(r[2])}', '{escape_sql(r[3])}')"
        for r in NEW_REGIONS
    )
    lines.append("INSERT IGNORE INTO dim_region (region_id, province, region_name, country) VALUES")
    lines.append(region_vals + ";")
    lines.append("")

    # 3. dim_customer
    print("生成 dim_customer...")
    lines.append("-- dim_customer: 新增 20 客户")
    cust_vals = ",\n".join(
        f"('{escape_sql(r[0])}', '{escape_sql(r[1])}', '{escape_sql(r[2])}', '{escape_sql(r[3])}')"
        for r in NEW_CUSTOMERS
    )
    lines.append("INSERT IGNORE INTO dim_customer (customer_id, customer_name, gender, member_level) VALUES")
    lines.append(cust_vals + ";")
    lines.append("")

    # 4. dim_product
    print("生成 dim_product...")
    lines.append("-- dim_product: 新增 25 商品")
    prod_vals = ",\n".join(
        f"('{escape_sql(r[0])}', '{escape_sql(r[1])}', '{escape_sql(r[2])}', '{escape_sql(r[3])}')"
        for r in NEW_PRODUCTS
    )
    lines.append("INSERT IGNORE INTO dim_product (product_id, product_name, category, brand) VALUES")
    lines.append(prod_vals + ";")
    lines.append("")

    # 5. fact_order - 用 Python 动态生成, 写入单独文件
    print("生成 fact_order (动态部分)...")
    # 读取现有维度
    # 这里我们直接硬编码所有可能的 ID (从已有 SQL 得知)
    all_region_ids = [f"R{i:03d}" for i in range(1, 16)]
    all_customer_ids = [f"C{i:03d}" for i in range(1, 41)]
    all_product_ids = [f"P{i:03d}" for i in range(1, 41)]

    # 日期: 从 20250101 到 20251231, 跳过不存在的日期
    date_ids = []
    for m in range(1, 13):
        if m == 12:
            days = 31
        else:
            days = (datetime(2025, m + 1, 1) - timedelta(days=1)).day
        for d in range(1, days + 1):
            date_ids.append(20250000 + m * 100 + d)

    # 商品单价 (基于品类基准 + 随机)
    category_base = {
        "手机数码": 5000, "家用电器": 1500, "鞋靴": 500,
        "服饰": 300, "食品饮料": 80, "休闲零食": 50, "图书文娱": 200,
    }
    # 已有商品的价格参考 (从 dw.sql 估算)
    known_prices = {
        "P001": 8999, "P002": 9499, "P003": 6999, "P004": 5499, "P005": 3200,
        "P006": 899, "P007": 1299, "P008": 199, "P009": 599, "P010": 25,
        "P011": 5, "P012": 5, "P013": 3.5, "P014": 1399, "P015": 899,
    }
    # 已知品类映射
    known_categories = {
        "P001": "手机数码", "P002": "手机数码", "P003": "手机数码", "P014": "手机数码",
        "P004": "家用电器", "P005": "家用电器", "P015": "家用电器",
        "P006": "鞋靴", "P007": "鞋靴",
        "P008": "服饰", "P009": "服饰",
        "P010": "食品饮料", "P011": "食品饮料",
        "P012": "休闲零食", "P013": "休闲零食",
    }

    # 新品品类映射
    new_product_cats = {
        "P016": "手机数码", "P017": "手机数码", "P018": "手机数码", "P019": "手机数码",
        "P020": "手机数码", "P038": "手机数码", "P039": "手机数码", "P040": "手机数码",
        "P021": "家用电器", "P022": "家用电器", "P023": "家用电器", "P024": "家用电器",
        "P025": "鞋靴", "P026": "鞋靴", "P027": "鞋靴",
        "P028": "服饰", "P029": "服饰", "P030": "服饰",
        "P031": "食品饮料", "P032": "食品饮料", "P033": "食品饮料",
        "P034": "休闲零食", "P035": "休闲零食",
        "P036": "图书文娱", "P037": "图书文娱",
    }

    price_map = {}
    for pid in all_product_ids:
        if pid in known_prices:
            price_map[pid] = known_prices[pid]
        else:
            cat = new_product_cats.get(pid, "手机数码")
            base = category_base.get(cat, 200)
            price_map[pid] = round(random.uniform(base * 0.5, base * 1.5), 2)

    # 生成订单
    order_rows = []
    used_ids = set()

    # 普通订单: 每天 2-5 单
    for date_id in date_ids:
        n = random.randint(2, 5)
        for _ in range(n):
            for _attempt in range(10):
                suffix = random.randint(1, 999)
                oid = f"ORD{date_id}{suffix:03d}"
                if oid not in used_ids:
                    used_ids.add(oid)
                    break
            cid = random.choice(all_customer_ids)
            pid = random.choice(all_product_ids)
            rid = random.choice(all_region_ids)
            qty = random.choice([1, 1, 1, 2, 2, 3, 5])
            price = price_map[pid]
            amt = round(price * qty * random.uniform(0.9, 1.1), 2)
            order_rows.append(f"('{oid}', '{cid}', '{pid}', {date_id}, '{rid}', {qty}, {amt})")

    # 大额订单 (用于阈值查询): 30 天 x 2 单
    for date_id in random.sample(date_ids, min(30, len(date_ids))):
        for _ in range(2):
            for _attempt in range(10):
                suffix = random.randint(1000, 9999)
                oid = f"ORD{date_id}{suffix:03d}"
                if oid not in used_ids:
                    used_ids.add(oid)
                    break
            pid = random.choice(all_product_ids)
            qty = random.randint(10, 30)
            price = price_map[pid]
            amt = round(price * qty, 2)
            order_rows.append(f"('{oid}', '{random.choice(all_customer_ids)}', '{pid}', {date_id}, '{random.choice(all_region_ids)}', {qty}, {amt})")

    print(f"  生成 {len(order_rows)} 条订单 (将分块写入)")

    # 写入 fact_order 分块 INSERT
    lines.append(f"-- fact_order: {len(order_rows)} 条订单")
    batch_size = 500
    for i in range(0, len(order_rows), batch_size):
        batch = order_rows[i : i + batch_size]
        lines.append("INSERT INTO fact_order (order_id, customer_id, product_id, date_id, region_id, order_quantity, order_amount) VALUES")
        lines.append(",\n".join(batch) + ";")

    # 写文件
    output = "scripts/dw_extend_data.sql"
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ SQL 文件已生成: {output}")
    print(f"   总行数: {sum(1 for _ in open(output, encoding='utf-8'))}")
    print(f"   fact_order 待插入: {len(order_rows)} 条")


if __name__ == "__main__":
    main()
