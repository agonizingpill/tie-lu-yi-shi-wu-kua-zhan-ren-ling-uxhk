from datetime import date

from railway.db import connect
from railway.models.ledger import append_event
from railway.security import new_password, proof_hash

PASSWORD = "RailDemo26"
STATIONS = (("BAL", "北砾", 1), ("HQG", "河桥关", 2), ("YSH", "远沙河", 3))
STAFF = (
    ("beili@rail.test", "孟怡 · 北砾柜员", "clerk", "BAL"),
    ("heqiao@rail.test", "于澄 · 河桥关柜员", "clerk", "HQG"),
    ("dispatch@rail.test", "陈筝 · 区段调度", "dispatcher", None),
    ("audit@rail.test", "唐杉 · 票务稽核", "observer", None),
)
DEMO_DATE = date(2026, 11, 23)
BAGS = (
    ("BL-261123-014", "BAL", "G216", "包袋", "深蓝", "双肩包 黄色拉链 织布 背带", "内袋缝线是一枚白山刺绣"),
    ("BL-261123-017", "BAL", "G216", "包袋", "深蓝", "双肩包 黄色拉链 防水 硬壳", "侧袋有两枚空钥匙环"),
    ("HQ-261123-006", "HQG", "D801", "数码", "银灰", "耳机盒 磨砂 充电口", "盖内贴着编号二四"),
    ("YS-261123-002", "YSH", "G216", "衣物", "米白", "针织围巾 毛边 条纹", "有鹿脚印吊牌"),
    ("BL-261123-023", "BAL", "G218", "票证", "棕色", "卡夹 圆角 皮质 单扣", "内衬左侧墨点"),
)


def seed():
    with connect() as db:
        with db.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO stations (code, display_name, corridor_position) VALUES (%s, %s, %s)
                ON CONFLICT (code) DO NOTHING
            """, STATIONS)
            for email, name, role, station in STAFF:
                if not cursor.execute("SELECT 1 FROM staff WHERE email = %s", (email,)).fetchone():
                    salt, digest = new_password(PASSWORD)
                    cursor.execute("""
                        INSERT INTO staff VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (email) DO NOTHING
                    """, (email, name, role, station, salt, digest))
            for seal, station, train, category, color, description, mark in BAGS:
                added = cursor.execute("""
                    INSERT INTO sealed_bags (seal_id, origin_station, current_station, train_no, found_on,
                        category, color, description, proof_digest, recorded_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (seal_id) DO NOTHING RETURNING seal_id
                """, (seal, station, station, train, DEMO_DATE, category, color,
                      description, proof_hash(seal, mark), "beili@rail.test")).fetchone()
                if added:
                    append_event(db, seal, "beili@rail.test", "seal_created", f"{station} 站历史封袋交班导入")
            counts = {
                name: cursor.execute(f"SELECT COUNT(*) AS total FROM {name}").fetchone()["total"]
                for name in ("stations", "staff", "sealed_bags", "custody_events")
            }
    return counts


if __name__ == "__main__":
    print(seed())
