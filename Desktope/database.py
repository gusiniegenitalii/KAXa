# database.py

import sqlite3
import datetime
from collections import Counter

class DatabaseManager:
    def __init__(self, db_name="zettelkasten.db"):
        """Инициализация менеджера БД, подключение и создание таблиц."""
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row # Позволяет обращаться к колонкам по имени
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Создает таблицы tasks и reminders, если они не существуют."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                details TEXT,
                tags TEXT,
                due_date TEXT,
                is_completed BOOLEAN DEFAULT 0,
                is_important BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                reminder_datetime TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

        # Заполняем данными, если таблица пуста
        self.cursor.execute("SELECT COUNT(id) FROM tasks")
        if self.cursor.fetchone()[0] == 0:
            self._seed_data()

    def _seed_data(self):
        """Добавляет одну тестовую задачу при первом запуске."""
        self.add_task(
            title="Поприветствовать Zettelkasten!",
            details="Это первая задача в вашем новом приложении. Вы можете редактировать ее двойным кликом или добавлять напоминания.",
            tags="Начало, Zettelkasten",
            is_important=True
        )
    
    def _clean_tags(self, tags_string: str) -> str:
        """Очищает строку с тегами от пробелов и пустых значений."""
        return ','.join(tag.strip() for tag in tags_string.split(',') if tag.strip())

    def add_task(self, title, details="", tags="", due_date=None, is_important=False):
        """Добавляет новую задачу в БД."""
        now = datetime.datetime.now().isoformat()
        if isinstance(due_date, datetime.date):
            due_date = due_date.isoformat()
        
        cleaned_tags = self._clean_tags(tags)

        self.cursor.execute('''
            INSERT INTO tasks (title, details, tags, due_date, is_important, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, details, cleaned_tags, due_date, is_important, now))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_tasks(self, filter_by='all', value=None, start_date=None, end_date=None):
        """Получает задачи по разным фильтрам и возвращает их как список словарей."""
        query = "SELECT * FROM tasks"
        params = []
        conditions = []
        
        filter_conditions = {
            'important': ("is_important = 1", []),
            'completed': ("is_completed = 1", []),
            'tag': ("(tags = ? OR tags LIKE ? OR tags LIKE ? OR tags LIKE ?)", [value, f'{value},%', f'%,{value},%', f'%,{value}']),
            'date': ("due_date = ?", [value]),
            'date_range': ("due_date BETWEEN ? AND ?", [start_date, end_date])
        }

        # ### ИСПРАВЛЕННАЯ СТРОКА ###
        # Проверяем, что фильтры 'important' и 'completed' работают без значения value
        if filter_by in ['important', 'completed'] or \
           (filter_by in filter_conditions and value is not None) or \
           filter_by == 'date_range':
            
            condition, p = filter_conditions[filter_by]
            conditions.append(condition)
            params.extend(p)

        # Дополнительное условие для незавершенных задач
        if filter_by not in ['completed', 'date_range', 'all']:
             conditions.append("is_completed = 0")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        # Сортировка
        order_clauses = {
            'completed': " ORDER BY created_at DESC",
            'date_range': " ORDER BY due_date ASC, created_at DESC",
            'default': " ORDER BY is_important DESC, due_date ASC, created_at DESC"
        }
        query += order_clauses.get(filter_by, order_clauses['default'])
        
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def get_task_by_id(self, task_id):
        """Получает одну задачу по ее ID."""
        self.cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_task_status(self, task_id, is_completed):
        """Обновляет статус выполнения задачи."""
        self.cursor.execute("UPDATE tasks SET is_completed = ? WHERE id = ?", (is_completed, task_id))
        self.conn.commit()

    def update_task_importance(self, task_id, is_important):
        """Обновляет флаг важности задачи."""
        self.cursor.execute("UPDATE tasks SET is_important = ? WHERE id = ?", (is_important, task_id))
        self.conn.commit()
        
    def update_task(self, task_id, data: dict):
        """Обновляет данные задачи по словарю."""
        if 'tags' in data:
            data['tags'] = self._clean_tags(data['tags'])
            
        # Формируем запрос динамически, чтобы не обновлять лишние поля
        fields_to_update = [f"{key} = ?" for key in data]
        if not fields_to_update: return

        query = f"UPDATE tasks SET {', '.join(fields_to_update)} WHERE id = ?"
        params = list(data.values()) + [task_id]
        
        self.cursor.execute(query, params)
        self.conn.commit()

    def search_tasks(self, query_str):
        """Ищет задачи по строке запроса в названии, деталях или тегах."""
        search_pattern = f"%{query_str}%"
        query = """
            SELECT * FROM tasks 
            WHERE (title LIKE ? OR details LIKE ? OR tags LIKE ?) AND is_completed = 0
            ORDER BY is_important DESC, due_date ASC, created_at DESC
        """
        self.cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_tags_with_counts(self):
        """Собирает все уникальные теги из всех незавершенных задач."""
        self.cursor.execute("SELECT tags FROM tasks WHERE is_completed = 0 AND tags IS NOT NULL AND tags != ''")
        all_tags = [tag.strip() for row in self.cursor.fetchall() for tag in row['tags'].split(',') if tag.strip()]
        return Counter(all_tags)

    def add_reminder(self, task_id, reminder_datetime):
        """Добавляет напоминание для задачи."""
        self.cursor.execute("INSERT INTO reminders (task_id, reminder_datetime) VALUES (?, ?)", (task_id, reminder_datetime))
        self.conn.commit()

    def get_reminders_for_task(self, task_id):
        """Получает все напоминания для конкретной задачи."""
        self.cursor.execute("SELECT * FROM reminders WHERE task_id = ? ORDER BY reminder_datetime ASC", (task_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def delete_reminder(self, reminder_id):
        """Удаляет конкретное напоминание по его ID."""
        self.cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()
        
    def replace_all_reminders_for_task(self, task_id, datetimes_list):
        """Полностью заменяет все напоминания для задачи."""
        self.cursor.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
        if datetimes_list:
            data_to_insert = [(task_id, dt) for dt in datetimes_list]
            self.cursor.executemany("INSERT INTO reminders (task_id, reminder_datetime) VALUES (?, ?)", data_to_insert)
        self.conn.commit()

    def get_due_reminders(self, current_datetime_iso):
        """Получает все напоминания, время которых уже наступило."""
        query = """
            SELECT r.id as reminder_id, r.reminder_datetime, t.id as task_id, t.title
            FROM reminders r
            JOIN tasks t ON r.task_id = t.id
            WHERE r.reminder_datetime <= ? AND t.is_completed = 0
        """
        self.cursor.execute(query, (current_datetime_iso,))
        return [dict(row) for row in self.cursor.fetchall()]

    def close(self):
        """Закрывает соединение с БД."""
        self.conn.close()