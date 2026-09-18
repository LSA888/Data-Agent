"""扩展 DW 数据仓库测试数据 - 使用 SQLAlchemy + asyncmy"""
import random
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

random.seed(42)

engine = create_engine(
    "mysql+asyncmy://root:root@localhost:3307/dw?charset=utf8mb4",
    echo=False,
)

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


def generate_date_rows(year, start_month, end_month):
    rows = []
    for month in range(start_month, end_month + 1):
        if month == 12:
            days_in_month = 31
        else:
            days_in_month = (datetime(year, month + 1, 1) - timedelta(days=1)).day
        quarter = f"Q{(month - 1) // 3 + 1}"
        for day in range(1, days_in_month + 1):
            date_id = year * 10000 + month * 100 + day
            rows.append({"date_id": date_id, "year": year, "quarter": quarter, "month": month, "day": day})
    return rows


def main():
    with engine.begin() as conn:
        print("=" * 50)
        print("开始扩展 DW 测试数据")
        print("=" * 50)

        # 1. dim_date
        print("\n[1/5] 扩展 dim_date (Q2/Q3/Q4)...")
        new_dates = generate_date_rows(2025, 4, 12)
        conn.execute(
            text("INSERT IGNORE INTO dim_date (date_id, year, quarter, month, day) VALUES (:date_id, :year, :quarter, :month, :day)"),
            new_dates,
        )
        cnt = conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar()
        print(f"  dim_date 总数: {cnt}")

        # 2. dim_region
        print("\n[2/5] 扩展 dim_region...")
        conn.execute(
            text("INSERT IGNORE INTO dim_region (region_id, province, region_name, country) VALUES (:rid, :prov, :rname, :country)"),
            [{"rid": r[0], "prov": r[1], "rname": r[2], "country": r[3]} for r in NEW_REGIONS],
        )
        cnt = conn.execute(text("SELECT COUNT(*) FROM dim_region")).scalar()
        print(f"  dim_region 总数: {cnt}")

        # 3. dim_customer
        print("\n[3/5] 扩展 dim_customer...")
        conn.execute(
            text("INSERT IGNORE INTO dim_customer (customer_id, customer_name, gender, member_level) VALUES (:cid, :cname, :gender, :ml)"),
            [{"cid": r[0], "cname": r[1], "gender": r[2], "ml": r[3]} for r in NEW_CUSTOMERS],
        )
        cnt = conn.execute(text("SELECT COUNT(*) FROM dim_customer")).scalar()
        print(f"  dim_customer 总数: {cnt}")

        # 4. dim_product
        print("\n[4/5] 扩展 dim_product...")
        conn.execute(
            text("INSERT IGNORE INTO dim_product (product_id, product_name, category, brand) VALUES (:pid, :pname, :cat, :brand)"),
            [{"pid": r[0], "pname": r[1], "cat": r[2], "brand": r[3]} for r in NEW_PRODUCTS],
        )
        cnt = conn.execute(text("SELECT COUNT(*) FROM dim_product")).scalar()
        print(f"  dim_product 总数: {cnt}")

        # 5. fact_order
        print("\n[5/5] 生成 fact_order...")
        region_ids = [r[0] for r in conn.execute(text("SELECT region_id FROM dim_region"))]
        customer_ids = [r[0] for r in conn.execute(text("SELECT customer_id FROM dim_customer"))]
        product_ids = [r[0] for r in conn.execute(text("SELECT product_id FROM dim_product"))]
        date_ids = [r[0] for r in conn.execute(text("SELECT date_id FROM dim_date ORDER BY date_id"))]

        # 估算商品单价
        price_rows = conn.execute(text("""
            SELECT p.product_id, 
                   AVG(NULLIF(f.order_amount, 0) / NULLIF(f.order_quantity, 0)) as avg_price
            FROM fact_order f RIGHT JOIN dim_product p ON f.product_id = p.product_id
            GROUP BY p.product_id
        """)).fetchall()
        price_map = {}
        category_base = {
            "手机数码": 5000, "家用电器": 1500, "鞋靴": 500,
            "服饰": 300, "食品饮料": 80, "休闲零食": 50, "图书文娱": 200,
        }
        for pid, avg_price in price_rows:
            if avg_price:
                price_map[pid] = float(avg_price)

        cat_rows = conn.execute(text("SELECT product_id, category FROM dim_product")).fetchall()
        for pid, cat in cat_rows:
            if pid not in price_map:
                base = category_base.get(cat, 100)
                price_map[pid] = round(random.uniform(base * 0.5, base * 1.5), 2)

        # 生成订单数据
        rows = []
        used_ids = set()

        for date_id in date_ids:
            daily_cnt = random.randint(2, 5)
            for _ in range(daily_cnt):
                for _attempt in range(10):
                    suffix = random.randint(1, 999)
                    oid = f"ORD{date_id}{suffix:03d}"
                    if oid not in used_ids:
                        used_ids.add(oid)
                        break
                cid = random.choice(customer_ids)
                pid = random.choice(product_ids)
                rid = random.choice(region_ids)
                qty = random.choice([1, 1, 1, 2, 2, 3, 5])
                price = price_map.get(pid, 100.0)
                amt = round(price * qty * random.uniform(0.9, 1.1), 2)
                rows.append({"oid": oid, "cid": cid, "pid": pid, "did": date_id, "rid": rid, "qty": qty, "amt": amt})

        # 大额订单 (阈值查询用)
        for date_id in random.sample(date_ids, min(30, len(date_ids))):
            for _ in range(2):
                for _attempt in range(10):
                    suffix = random.randint(1000, 9999)
                    oid = f"ORD{date_id}{suffix:03d}"
                    if oid not in used_ids:
                        used_ids.add(oid)
                        break
                pid = random.choice(product_ids)
                qty = random.randint(10, 30)
                price = price_map.get(pid, 100.0)
                amt = round(price * qty, 2)
                rows.append({"oid": oid, "cid": random.choice(customer_ids), "pid": pid,
                             "did": date_id, "rid": random.choice(region_ids), "qty": qty, "amt": amt})

        print(f"  待插入订单数: {len(rows)}")
        conn.execute(
            text("INSERT INTO fact_order (order_id, customer_id, product_id, date_id, region_id, order_quantity, order_amount) VALUES (:oid, :cid, :pid, :did, :rid, :qty, :amt)"),
            rows,
        )
        cnt = conn.execute(text("SELECT COUNT(*) FROM fact_order")).scalar()
        print(f"  fact_order 总数: {cnt}")

        # 覆盖度验证
        print("\n" + "=" * 50)
        print("数据覆盖度验证")
        print("=" * 50)

        print("\n  [季度覆盖]", conn.execute(text("SELECT DISTINCT quarter FROM dim_date ORDER BY quarter")).fetchall())
        print("  [省份数]", conn.execute(text("SELECT COUNT(DISTINCT province) FROM dim_region")).scalar())
        print("  [会员等级]", conn.execute(text("SELECT DISTINCT member_level FROM dim_customer")).fetchall())
        print("  [品类]", conn.execute(text("SELECT DISTINCT category FROM dim_product")).fetchall())
        print("  [品牌数]", conn.execute(text("SELECT COUNT(DISTINCT brand) FROM dim_product")).scalar())
        print("  [有订单的日期数]", conn.execute(text("SELECT COUNT(DISTINCT date_id) FROM fact_order")).scalar())
        print("  [有订单的客户数]", conn.execute(text("SELECT COUNT(DISTINCT customer_id) FROM fact_order")).scalar())
        print("  [有订单的商品数]", conn.execute(text("SELECT COUNT(DISTINCT product_id) FROM fact_order")).scalar())
        print("  [有订单的地区数]", conn.execute(text("SELECT COUNT(DISTINCT region_id) FROM fact_order")).scalar())

        print("\n  [各季度订单分布]")
        for row in conn.execute(text("""
            SELECT d.quarter, COUNT(f.order_id), ROUND(SUM(f.order_amount), 2)
            FROM fact_order f JOIN dim_date d ON f.date_id = d.date_id
            GROUP BY d.quarter ORDER BY d.quarter
        """)).fetchall():
            print(f"    {row}")

        print("\n  [各品类订单分布]")
        for row in conn.execute(text("""
            SELECT p.category, COUNT(f.order_id), ROUND(SUM(f.order_amount), 2)
            FROM fact_order f JOIN dim_product p ON f.product_id = p.product_id
            GROUP BY p.category ORDER BY SUM(f.order_amount) DESC
        """)).fetchall():
            print(f"    {row}")

        print("\n" + "=" * 50)
        print("✅ 数据扩展完成!")
        print("=" * 50)


if __name__ == "__main__":
    main()
