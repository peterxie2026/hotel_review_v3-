"""种子数据：创建默认用户和两家酒店的知识库"""
import sys
sys.path.insert(0, ".")

from app.database import SessionLocal, engine, Base
from app.models import *
from app.services.auth_service import hash_password
from app.services.crypto_service import encrypt_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# === 创建订阅套餐 ===
plans = [
    {
        "code": "free_trial", "name": "免费基础版", "sort_order": 1,
        "description": "适合体验系统功能，管理一家酒店的基础点评需求",
        "features": ["1家酒店", "30条点评/月", "AI基础回复", "携程平台"],
        "hotel_limit": 1, "review_limit_monthly": 30,
        "ai_provider_limit": "basic", "ota_platforms": ["ctrip"],
        "price_monthly": 0, "price_yearly": 0,
    },
    {
        "code": "basic", "name": "标准版", "sort_order": 2,
        "description": "适合小型酒店，满足日常点评管理需求",
        "features": ["2家酒店", "150条点评/月", "AI智能回复", "携程+美团", "数据报告"],
        "hotel_limit": 2, "review_limit_monthly": 150,
        "ai_provider_limit": "deepseek", "ota_platforms": ["ctrip", "meituan"],
        "price_monthly": 5900, "price_yearly": 59000,
    },
    {
        "code": "pro", "name": "专业版", "sort_order": 3,
        "description": "适合中大型酒店或连锁，全面覆盖OTA平台，不限点评量",
        "features": ["5家酒店", "不限点评量", "AI高级回复", "全OTA平台（携程/美团/飞猪）", "自定义知识库", "数据报告"],
        "hotel_limit": 5, "review_limit_monthly": 99999,
        "ai_provider_limit": "advanced", "ota_platforms": ["ctrip", "meituan", "fliggy"],
        "price_monthly": 19900, "price_yearly": 199000,
    },
    {
        "code": "enterprise", "name": "企业版", "sort_order": 4,
        "description": "适合大型酒店集团，不限酒店数量和点评量",
        "features": ["不限酒店", "不限点评量", "AI高级回复+自定义模型", "全OTA平台", "专属知识库", "优先技术支持"],
        "hotel_limit": 9999, "review_limit_monthly": 99999,
        "ai_provider_limit": "advanced", "ota_platforms": ["ctrip", "meituan", "fliggy"],
        "price_monthly": 99900, "price_yearly": 999000,
    },
]
for p in plans:
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == p["code"]).first()
    if existing:
        # 更新已有套餐
        for key, val in p.items():
            setattr(existing, key, val)
        print(f"更新订阅套餐: {p['name']}")
    else:
        db.add(SubscriptionPlan(**p))
        print(f"创建订阅套餐: {p['name']}")
db.flush()

# === 创建默认用户 ===
user = db.query(User).filter(User.username == "peter").first()
if not user:
    user = User(
        username="peter",
        email="peter@xinghuiyuntu.com",
        company_name="星辉云途",
        hashed_password=hash_password("admin123"),
        role=UserRole.admin,
    )
    db.add(user)
    db.flush()
    print(f"创建用户: peter (密码: admin123)")
else:
    print(f"用户 peter 已存在")

# === 阆中尚雅酒店 ===
langzhong = db.query(Hotel).filter(Hotel.name.contains("阆中尚雅"), Hotel.user_id == user.id).first()
if not langzhong:
    langzhong = Hotel(
        user_id=user.id,
        name="阆中天府明宇尚雅酒店",
        brand="明宇商旅",
        address="四川省南充市阆中市",
        phone="0817-6288888",
        star_rating=5,
        room_count=200,
        highlights=["嘉陵江畔", "五星级", "明宇旗下高端品牌", "会议设施齐全", "中餐厅川菜"],
        reply_tone="亲切温暖专业", ai_provider="minimax",
    )
    db.add(langzhong)
    db.flush()

    # 知识库
    knowledge_data = [
        ("hotel_info", "酒店全称", "阆中天府明宇尚雅酒店"),
        ("hotel_info", "酒店地址", "四川省南充市阆中市滨江路88号"),
        ("hotel_info", "联系电话", "0817-6288888"),
        ("hotel_info", "酒店定位", "嘉陵江畔五星级高端商务度假酒店"),
        ("service_feature", "特色设施", "江景客房、宴会厅、中餐厅、健身房、游泳池"),
        ("service_feature", "周边景点", "阆中古城（5A）、嘉陵江、锦屏山"),
        ("service_feature", "餐饮特色", "明宇中餐厅主打川菜，嘉陵江河鲜为特色"),
        ("nearby", "交通", "距阆中火车站15分钟车程，距南充高坪机场1小时"),
        ("policy", "入住时间", "14:00后，退房12:00前"),
    ]
    for cat, key, val in knowledge_data:
        db.add(KnowledgeEntry(hotel_id=langzhong.id, category=cat, key=key, value=val, priority=10))

    # 回复模板
    template_data = [
        ("好评-江景服务", "positive", "尊敬的宾客，感谢您对阆中明宇尚雅酒店的高度评价！我们坐落于嘉陵江畔，江景和优质服务是我们的骄傲。期待您的再次光临，我们将继续为您提供美好的入住体验！"),
        ("好评-餐饮", "positive", "尊敬的宾客，非常感谢您对我们餐饮的认可！明宇中餐厅以正宗川菜和嘉陵江河鲜为特色，我们会继续努力，为您带来更多美食体验。欢迎再次光临！"),
        ("好评-通用", "positive", "尊敬的宾客，感谢您的五星好评！您的满意是我们最大的动力。阆中天府明宇尚雅酒店全体员工期待您的再次光临！"),
        ("差评-卫生", "negative", "尊敬的宾客，对于您入住期间遇到的卫生问题，我们深表歉意。我们已立即将您反馈的问题通报客房部负责人，并将在全部门开展卫生标准再培训。如有任何需要，请随时联系我们：0817-6288888。希望您能给我们一个改进的机会。"),
        ("差评-服务", "negative", "尊敬的宾客，感谢您指出我们服务中的不足。我们对您的不愉快体验深表歉意，已将您的反馈传达至相关部门进行整改。我们会加强员工服务培训，确保类似情况不再发生。如有需要请致电0817-6288888，我们诚挚邀请您再次体验我们的改进。"),
        ("差评-设施", "negative", "尊敬的宾客，很抱歉设施问题影响了您的入住体验。我们已经安排工程部进行排查维修。您的反馈对我们非常重要，我们会在后续不断提升硬件设施。期待您的再次光临！"),
        ("中评-通用", "neutral", "尊敬的宾客，感谢您抽出宝贵时间为我们点评。您的反馈我们已经认真记录，会针对您提到的方面进行改进。阆中天府明宇尚雅酒店期待再次为您服务，希望能带给您更好的体验！"),
    ]
    for name, cat, text in template_data:
        db.add(ReplyTemplate(hotel_id=langzhong.id, name=name, category=cat, text=text))

    print(f"创建酒店: {langzhong.name}")

# === 西金阁酒店 ===
xijinge = db.query(Hotel).filter(Hotel.name.contains("西金阁"), Hotel.user_id == user.id).first()
if not xijinge:
    xijinge = Hotel(
        user_id=user.id,
        name="成都西金阁酒店",
        brand="",
        address="四川省成都市",
        phone="028-88888888",
        star_rating=4,
        room_count=120,
        highlights=["成都市区", "商务出行", "性价比高", "近地铁"],
        reply_tone="亲切温暖",
    )
    db.add(xijinge)
    db.flush()

    knowledge_data = [
        ("hotel_info", "酒店全称", "成都西金阁酒店"),
        ("hotel_info", "酒店地址", "四川省成都市锦江区"),
        ("hotel_info", "联系电话", "028-88888888"),
        ("hotel_info", "酒店定位", "成都市区商务型酒店，交通便利，性价比高"),
        ("service_feature", "特色设施", "商务会议室、自助餐厅、健身房"),
        ("service_feature", "周边", "近地铁站、春熙路商圈、太古里"),
        ("nearby", "交通", "近地铁2号线，距成都东站20分钟，距双流机场40分钟"),
        ("policy", "入住时间", "14:00后，退房12:00前"),
    ]
    for cat, key, val in knowledge_data:
        db.add(KnowledgeEntry(hotel_id=xijinge.id, category=cat, key=key, value=val, priority=10))

    template_data = [
        ("好评-位置", "positive", "尊敬的宾客，感谢您选择成都西金阁酒店！我们位于成都市中心，交通便利，周边商圈林立。很高兴您满意我们的位置和服务，期待您的再次光临！"),
        ("好评-通用", "positive", "尊敬的宾客，感谢您的五星好评！您的认可让我们倍感荣幸。成都西金阁酒店将一如既往为您提供舒适的住宿体验，欢迎再次光临！"),
        ("差评-卫生", "negative", "尊敬的宾客，对于您反馈的卫生问题，我们深表歉意。我们已立即通知客房部进行全面检查整改。酒店管理层高度重视您的反馈，将严格加强卫生管理。如有需要请联系028-88888888。"),
        ("差评-服务", "negative", "尊敬的宾客，很抱歉我们的服务未能让您满意。我们已对相关员工进行再培训，并将持续优化服务流程。您的反馈是我们进步的动力，希望能再次为您服务。"),
        ("中评-通用", "neutral", "尊敬的宾客，感谢您的反馈和建议。我们会认真对待您提到的每一个细节，不断改进提升。成都西金阁酒店期待再次为您服务！"),
    ]
    for name, cat, text in template_data:
        db.add(ReplyTemplate(hotel_id=xijinge.id, name=name, category=cat, text=text))

    print(f"创建酒店: {xijinge.name}")

db.commit()
db.close()
print("\n种子数据导入完成！")
print("登录信息: 用户名 peter / 密码 admin123")
