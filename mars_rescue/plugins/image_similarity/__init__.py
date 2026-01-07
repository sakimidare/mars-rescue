from io import BytesIO

import httpx
import imagehash
from PIL import Image
from nonebot import get_plugin_config, on_message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment, Message
from nonebot.plugin import PluginMetadata

from .config import Config
from .database import *

__plugin_meta__ = PluginMetadata(
    name="image_similarity",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)
init_db()

# 监听所有消息事件，方便处理群聊和私聊
image_checker = on_message(priority=5, block=False)


@image_checker.handle()
async def check_similar_image(bot: Bot, event: MessageEvent):
    # 1. 提取图片消息段并过滤动画表情

    target_segments = []

    for seg in event.get_message():
        if seg.type == "image":
            sub_type = seg.data.get('sub_type')
            file_name = seg.data.get('file', '').lower()

            # 过滤规则：
            # 1. sub_type 字段不为 0 或 None (sub_type=1 通常是动画表情或特殊类型)
            # 2. 文件名后缀是 .gif

            # **注意：我们使用您的示例中的 sub_type=1 进行精确过滤**
            is_animated_type = sub_type == '1' or sub_type == 1
            is_gif_file = file_name.endswith('.gif')

            if is_animated_type or is_gif_file:
                logger.info(f"过滤掉动画表情/特殊类型图片: sub_type={sub_type}, file={file_name}")
                # 遇到动画表情或特殊 sub_type 直接跳过
                continue

            # 通过过滤，保留静态图片
            target_segments.append(seg)

    if not target_segments:
        # 如果消息中有图片，但都被过滤了，则退出
        return

    # 2. 选取第一张静态图片进行处理
    first_image_segment = target_segments[0]
    file_id = first_image_segment.data.get('file')

    if not file_id:
        return

    # 确定当前会话ID：群聊返回 group_id，私聊返回 None
    group_id = event.group_id if hasattr(event, 'group_id') else None

    try:
        # 2. 获取图片下载链接并下载到内存
        image_info = await bot.get_image(file=file_id)
        image_url = image_info.get('url')

        if not image_url:
            await bot.send(event, "⚠️ 无法获取图片的下载链接。", at_sender=True)
            return

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(image_url)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))

        # 3. 计算新图片的 pHash
        image_hash = imagehash.phash(image)
        new_hash_str = str(image_hash)

        # 4. **会话隔离查找**：只读取当前会话中存储的 Hash
        stored_hashes_map = get_hashes_by_session(group_id)

        found_similar_id: Optional[int] = None
        min_distance = float('inf')

        # 线性遍历和对比 (这是 pHash 方案的特性)
        for stored_hash_str, message_id in stored_hashes_map.items():
            stored_hash = imagehash.hex_to_hash(stored_hash_str)
            distance = image_hash - stored_hash

            if distance <= SIMILARITY_THRESHOLD and distance < min_distance:
                min_distance = distance
                found_similar_id = message_id

        # 5. 处理结果：引用回复或保存
        if found_similar_id is not None:
            # 找到相似图片，构造引用回复
            reply_segment = MessageSegment.reply(found_similar_id)

            reply_message = Message(
                [
                    reply_segment,
                    MessageSegment.text(
                        f"✅ 在本会话历史中发现相似图片！汉明距离：{min_distance} (阈值 ≤ {SIMILARITY_THRESHOLD})")
                ]
            )
            await bot.send(event, reply_message)

        else:
            # 未找到相似图片，保存新图片信息
            insert_image(new_hash_str, event.message_id, group_id, file_id)
            # 提示：这里可以选择不回复，避免刷屏
            # await bot.send(event, "已保存新图片记录，未检测到本会话中的相似历史。", at_sender=True)

    except httpx.HTTPStatusError as e:
        logger.error(f"图片下载失败：HTTP 错误 {e.response.status_code}")
        await bot.send(event, f"❌ 图片下载失败。", at_sender=True)
    except Exception as e:
        logger.error(f"处理图片时发生未知错误: {e}")
        await bot.send(event, "❌ 处理图片时发生未知错误。", at_sender=True)