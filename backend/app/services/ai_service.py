from openai import AsyncOpenAI
from app.config import settings
from typing import Optional

PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "MiniMax-Text-01",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
}


def build_system_prompt(hotel_name: str, reply_tone: str, knowledge_text: str, template_text: str) -> str:
    return f"""你是{hotel_name}的宾客关系经理，正在回复客人在携程上留下的点评。

## 酒店信息
{knowledge_text}

## 回复风格
语气：{reply_tone}
- 好评（4-5分）：感谢客人具体提到的点，呼应酒店特色，邀请再次光临，50-100字
- 差评（1-3分）：先诚恳道歉，针对具体问题说明改进措施，提供联系方式，150-200字
- 中评（3-4分）：感谢反馈，说明会改进，委婉邀请再体验，80-120字
- 必须称呼客人"尊敬的宾客"或"亲爱的客人"
- 不得使用"亲"等网购用语
- 回复要有温度，像真人写的，不要机械套话
- 必须提到点评中的具体内容

## 参考模板（仅供风格参考，不要照抄）
{template_text}"""


def build_user_prompt(review_content: str, rating: float) -> str:
    return f"""客人评分: {rating}/5
客人点评内容:
{review_content}

请为该点评撰写回复。只输出回复内容，不要加任何前缀说明。"""


async def generate_reply(
    review_content: str,
    rating: float,
    hotel_name: str,
    reply_tone: str,
    knowledge_text: str,
    template_text: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    provider = provider or settings.AI_PROVIDER
    if provider not in PROVIDERS:
        provider = "deepseek"
    config = PROVIDERS[provider]
    model = model or config["default_model"]

    client = AsyncOpenAI(
        base_url=config["base_url"],
        api_key=settings.AI_API_KEY,
        timeout=30.0,
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": build_system_prompt(hotel_name, reply_tone, knowledge_text, template_text)},
            {"role": "user", "content": build_user_prompt(review_content, rating)},
        ],
        temperature=0.7,
        max_tokens=500,
    )

    return response.choices[0].message.content or ""
