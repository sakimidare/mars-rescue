import sqlite3
from typing import Optional, Dict
from nonebot.log import logger


# ====================================================================
# 【配置区】
# ====================================================================

# 数据库文件路径 (推荐使用绝对路径或在项目根目录下的相对路径)
# 为简化示例，我们使用当前插件目录下的相对路径
DB_PATH = "phash_store.db"
SIMILARITY_THRESHOLD = 8  # 汉明距离阈值 (0-64)，越小越相似

# ====================================================================
# 【数据库操作函数】
# ====================================================================

def init_db():
    """初始化数据库和表结构"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 【修改点 1：移除 PRIMARY KEY，新增自增 ID】
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 新增自增主键
                hash_str TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                group_id INTEGER,
                file_id TEXT NOT NULL
            )
        """)

        # 【修改点 2：增加联合唯一索引】
        # 确保同一个群/私聊不会存储重复的 hash_str
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_hash_session 
            ON images (hash_str, group_id);
        """)

        # 保留 group_id 索引以加速查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_group ON images (group_id)")

        conn.commit()
        conn.close()
        logger.info(f"数据库初始化成功: {DB_PATH}")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

def get_hashes_by_session(group_id: Optional[int]) -> Dict[str, int]:
    """
    根据 group_id 从数据库中获取当前会话中存储的 pHash 和对应的 message_id。
    group_id 为 None 时查询私聊记录。
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if group_id is not None:
        # 群聊：查询 group_id 匹配的记录
        cursor.execute(
            "SELECT hash_str, message_id FROM images WHERE group_id = ?",
            (group_id,)
        )
    else:
        # 私聊：查询 group_id 为 NULL 的记录
        cursor.execute(
            "SELECT hash_str, message_id FROM images WHERE group_id IS NULL"
        )

    # 返回 {hash_str: message_id} 字典
    results = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return results

def insert_image(hash_str: str, message_id: int, group_id: Optional[int], file_id: str):
    """将新的图片记录插入数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # INSERT 语句不变，SQLite 会自动处理 id 字段
        cursor.execute(
            "INSERT INTO images (hash_str, message_id, group_id, file_id) VALUES (?, ?, ?, ?)",
            (hash_str, message_id, group_id, file_id)
        )
        conn.commit()
        logger.info(f"新图片记录已保存到会话: {group_id if group_id is not None else '私聊'}")
    except sqlite3.IntegrityError:
        # 此时的 IntegrityError 是由联合唯一索引触发的，
        # 表示这张图在当前会话中已经存储过了，不需要重复保存。
        logger.warning(f"pHash {hash_str} 在会话 {group_id} 已存在，忽略插入。")
    except Exception as e:
        logger.error(f"数据库插入错误: {e}")
    finally:
        conn.close()