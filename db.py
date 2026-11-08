import aiosqlite

DB_NAME = "/root/bot_u451/bot_data.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                subgroup INTEGER
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        except Exception:
            pass
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploader_id INTEGER,
                file_id TEXT,
                file_type TEXT,
                subject TEXT,
                title TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_week', '1_3')")
        await db.commit()

async def ensure_user_started(uid: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        await db.commit()

async def get_user(uid: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT full_name, subgroup FROM users WHERE user_id = ?", (uid,)) as cur:
            return await cur.fetchone()

async def save_user(uid: int, name: str, sub: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, full_name, subgroup) VALUES (?, ?, ?)", (uid, name, sub))
        await db.commit()

async def update_user_name(uid: int, name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (name, uid))
        await db.commit()

async def update_user_subgroup(uid: int, sub: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET subgroup = ? WHERE user_id = ?", (sub, uid))
        await db.commit()

async def get_all_active_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, full_name, subgroup FROM users WHERE subgroup IS NOT NULL AND full_name IS NOT NULL") as cur:
            return await cur.fetchall()

async def get_all_users_raw():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, full_name, subgroup FROM users ORDER BY full_name ASC") as cur:
            return await cur.fetchall()

async def get_user_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_started = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE full_name IS NOT NULL AND subgroup IS NOT NULL") as cur:
            total_registered = (await cur.fetchone())[0]
        return total_started, total_registered

async def get_current_week():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'current_week'") as cur:
            row = await cur.fetchone()
            return row[0] if row else "1_3"

async def set_current_week(week: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = 'current_week'", (week,))
        await db.commit()

async def add_material(uploader_id: int, file_id: str, ftype: str, subject: str, title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO materials (uploader_id, file_id, file_type, subject, title, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (uploader_id, file_id, ftype, subject, title)
        )
        mid = cur.lastrowid
        await db.commit()
        return mid

async def get_material(mid: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT uploader_id, title, subject FROM materials WHERE id = ?", (mid,)) as cur:
            return await cur.fetchone()

async def update_material_status(mid: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE materials SET status = ? WHERE id = ?", (status, mid))
        await db.commit()

async def get_approved_materials(subject: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, title, file_id, file_type FROM materials WHERE subject = ? AND status = 'approved'", (subject,)) as cur:
            return await cur.fetchall()

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            u_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM materials WHERE status = 'approved'") as cur:
            m_count = (await cur.fetchone())[0]
        return u_count, m_count
