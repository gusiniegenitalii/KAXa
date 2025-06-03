import sys
import os
import shutil
import uuid
import sqlite3 # Для работы с SQLite

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QDateTimeEdit, QMessageBox, QDialog, QDialogButtonBox, QLabel,
    QTextEdit, QCheckBox, QMenu, QTreeView, QSplitter, QTabWidget,
    QInputDialog
)
from PyQt6.QtCore import (
    Qt, QDateTime, QTimer, QDir, QFileInfo, QModelIndex, QVariant, QPoint
)
from PyQt6.QtGui import QFileSystemModel, QAction, QFont, QIcon, QColor

# --- Глобальные константы ---
# Для To-Do
PRIORITIES = {
    1: {"name": "P1 (Высокий)", "color": QColor("red")},
    2: {"name": "P2 (Средний)", "color": QColor("orange")},
    3: {"name": "P3 (Низкий)", "color": QColor("blue")},
    4: {"name": "P4 (Нет)", "color": QColor("gray")}
}
DATABASE_NAME = './project/todo.db'

# Для Заметок
DEFAULT_VAULT_NAME = "notes"
APP_NAME_NOTES = "KAXa Notes" # Изменено, чтобы не конфликтовать с общим APP_NAME
APP_NAME_TODO = "KAXa To-Do"
COMBINED_APP_NAME = "KAXa Suite"

# --- Класс Задачи (для To-Do) ---
class Task:
    def __init__(self, text, priority=4, reminder_dt=None, completed=False, id_str=None, reminder_shown=False):
        self.id = id_str if id_str else str(uuid.uuid4())
        self.text = text
        self.priority = int(priority)
        self.reminder_datetime = reminder_dt
        self.completed = bool(completed)
        self.reminder_shown = bool(reminder_shown)

    def __repr__(self):
        return (f"Task(id={self.id}, text='{self.text[:20]}...', priority={self.priority}, "
                f"reminder={self.reminder_datetime}, completed={self.completed}, "
                f"reminder_shown={self.reminder_shown})")

# --- Диалог редактирования/добавления задачи (для To-Do) ---
class EditTaskDialog(QDialog):
    def __init__(self, task=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать задачу" if task else "Новая задача")
        self.task = task

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        if task:
            self.text_edit.setText(task.text)
        layout.addWidget(QLabel("Описание задачи:"))
        layout.addWidget(self.text_edit)

        self.priority_combo = QComboBox()
        for p_val, p_data in sorted(PRIORITIES.items()):
            self.priority_combo.addItem(p_data["name"], p_val)
        if task:
            self.priority_combo.setCurrentIndex(self.priority_combo.findData(task.priority))
        else:
            self.priority_combo.setCurrentIndex(self.priority_combo.findData(4))

        layout.addWidget(QLabel("Приоритет:"))
        layout.addWidget(self.priority_combo)

        self.reminder_checkbox = QCheckBox("Включить напоминание")
        layout.addWidget(self.reminder_checkbox)

        self.reminder_datetime_edit = QDateTimeEdit()
        self.reminder_datetime_edit.setCalendarPopup(True)
        self.reminder_datetime_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.reminder_datetime_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.reminder_datetime_edit.setEnabled(False)
        if task and task.reminder_datetime and task.reminder_datetime.isValid():
            self.reminder_datetime_edit.setDateTime(task.reminder_datetime)
            self.reminder_checkbox.setChecked(True)
            self.reminder_datetime_edit.setEnabled(True)

        self.reminder_checkbox.stateChanged.connect(
            lambda state: self.reminder_datetime_edit.setEnabled(state == Qt.CheckState.Checked.value)
        )

        layout.addWidget(QLabel("Напомнить в:"))
        layout.addWidget(self.reminder_datetime_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_task_data(self):
        text = self.text_edit.toPlainText().strip()
        priority = self.priority_combo.currentData()
        reminder_dt = None
        if self.reminder_checkbox.isChecked():
            reminder_dt = self.reminder_datetime_edit.dateTime()
            if not self.task or (self.task and self.task.reminder_datetime != reminder_dt):
                 if reminder_dt <= QDateTime.currentDateTime():
                    QMessageBox.warning(self, "Внимание", "Время напоминания не может быть в прошлом. Пожалуйста, выберите будущее время.")
                    return None

        if not text:
            QMessageBox.warning(self, "Ошибка", "Описание задачи не может быть пустым.")
            return None
        return text, priority, reminder_dt

# --- Кастомная модель для дерева файлов (для Заметок) ---
class SimpleTreeModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder_font = QFont()
        self._folder_font.setBold(True)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return QVariant()
        file_info = self.fileInfo(index)

        if role == Qt.ItemDataRole.FontRole:
            return self._folder_font if file_info.isDir() else QVariant()
        elif role == Qt.ItemDataRole.DecorationRole:
            # Возвращаем QVariant(), чтобы стандартные иконки не отображались,
            # если мы хотим полностью кастомные через QSS или вообще без них.
            # Если вы хотите стандартные иконки для файлов/папок, уберите эту ветку.
            return QVariant()
        elif role == Qt.ItemDataRole.DisplayRole:
            if file_info.isFile() and file_info.suffix().lower() == 'md':
                return (f"— {file_info.baseName()}")
        return super().data(index, role)

# --- Виджет для Заметок ---
class NoteWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_vault_path = None
        self.current_file_path = None
        self.unsaved_changes = False
        
        # Инициализация хранилища
        try:
            script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        except NameError: script_dir = os.getcwd()
        
        project_dir = os.path.join(script_dir, "notes") # Убедимся что project папка существует
        if not os.path.exists(project_dir):
            try: os.makedirs(project_dir)
            except OSError as e:
                 QMessageBox.critical(self, "Ошибка", f"Не удалось создать директорию project: {e}")

        self.current_vault_path = os.path.join(project_dir, DEFAULT_VAULT_NAME) # Хранилище внутри project
        if not os.path.exists(self.current_vault_path):
            try: os.makedirs(self.current_vault_path)
            except OSError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать хранилище заметок: {e}")
                self.current_vault_path = None
        
        self._setup_ui()

        if self.current_vault_path:
            root_idx = self.file_model.index(self.current_vault_path)
            self.file_model.setRootPath(self.current_vault_path)
            self.file_tree.setRootIndex(root_idx)
            if root_idx.isValid(): self.file_tree.expand(root_idx)
            self.create_note_button.setEnabled(True)
            self.create_folder_button.setEnabled(True)
            self.editor.setPlaceholderText("Создайте или выберите заметку.")
        else:
            self.editor.setPlaceholderText("Хранилище заметок не инициализировано.")
            self.create_note_button.setEnabled(False)
            self.create_folder_button.setEnabled(False)
        self._update_ui_states()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel_widget = QWidget()
        lp_layout = QVBoxLayout(left_panel_widget)
        lp_layout.setContentsMargins(0,0,0,0)
        
        self.create_folder_button = QPushButton("Создать папку")
        self.create_folder_button.clicked.connect(self.create_folder)
        self.create_note_button = QPushButton("Создать заметку")
        self.create_note_button.clicked.connect(self.new_note)
        lp_layout.addWidget(self.create_folder_button)
        lp_layout.addWidget(self.create_note_button)

        self.file_tree = QTreeView()
        self.file_tree.setAnimated(True)
        self.file_tree.setIndentation(15)
        
        self.file_model = SimpleTreeModel()
        self.file_model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files)
        self.file_model.setNameFilters(["*.md"])
        self.file_model.setNameFilterDisables(False) 
        self.file_tree.setModel(self.file_model)

        for i in range(1, self.file_model.columnCount()): self.file_tree.setColumnHidden(i, True)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.clicked.connect(self.on_file_tree_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        lp_layout.addWidget(self.file_tree)
        splitter.addWidget(left_panel_widget)
        
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.textChanged.connect(self._mark_unsaved_changes)
        splitter.addWidget(self.editor)
        splitter.setSizes([220, 730])
        main_layout.addWidget(splitter, 1)
        
        bottom_buttons_layout = QHBoxLayout()
        bottom_buttons_layout.addStretch(1)
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.clicked.connect(self.revert_changes)
        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.save_note)
        bottom_buttons_layout.addWidget(self.cancel_button)
        bottom_buttons_layout.addWidget(self.save_button)
        main_layout.addLayout(bottom_buttons_layout)

    def _update_ui_states(self):
        # Обновление состояния кнопок и плейсхолдера редактора
        # Заголовок окна теперь управляется CombinedApp
        can_act = bool(self.current_file_path and self.unsaved_changes)
        self.save_button.setEnabled(can_act)
        self.cancel_button.setEnabled(can_act)
        if not self.current_file_path:
             self.editor.setPlaceholderText("Создайте или выберите заметку." if self.current_vault_path else "Хранилище заметок не инициализировано.")


    def _mark_unsaved_changes(self):
        if self.current_file_path: self.unsaved_changes = True
        self._update_ui_states()

    def _get_base_create_path(self):
        idx = self.file_tree.currentIndex()
        if idx.isValid():
            path = self.file_model.filePath(idx)
            return path if self.file_model.isDir(idx) else os.path.dirname(path)
        return self.current_vault_path

    def _clean_name_for_path(self, name: str, is_file: bool = False) -> str:
        invalid_chars = '<>:"/\\|?*'
        cleaned_name = "".join(c for c in name if c not in invalid_chars).strip()
        cleaned_name = ' '.join(cleaned_name.split())
        
        if is_file and not cleaned_name: return "Новая заметка"
        elif not is_file and not cleaned_name: return "Новая папка"
        return cleaned_name

    def create_folder(self):
        if not self.current_vault_path: QMessageBox.information(self, "Инфо", "Хранилище не готово."); return
        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:")
        if ok and name:
            cleaned_name = self._clean_name_for_path(name, is_file=False)
            if not cleaned_name: QMessageBox.warning(self, "Ошибка", "Некорректное имя папки."); return
            path = os.path.join(self._get_base_create_path(), cleaned_name)
            if os.path.exists(path): QMessageBox.warning(self, "Ошибка", f"Папка '{cleaned_name}' существует."); return
            try: os.makedirs(path)
            except Exception as e: QMessageBox.critical(self, "Ошибка", f"Создание папки: {e}")
        elif ok: QMessageBox.warning(self, "Ошибка", "Имя папки пустое.")

    def on_file_tree_clicked(self, index: QModelIndex):
        if not index.isValid() or self.file_model.isDir(index): return
        path = self.file_model.filePath(index)
        if not (self.file_model.fileInfo(index).isFile() and path.lower().endswith(".md")): return
        if path == self.current_file_path: return
        if self.unsaved_changes and not self._confirm_discard("Переход к другой заметке?"):
            if self.current_file_path:
                prev_idx = self.file_model.index(self.current_file_path)
                if prev_idx.isValid(): self.file_tree.setCurrentIndex(prev_idx)
            return
        self.load_note(path)

    def load_note(self, file_path: str, is_revert: bool = False):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            self.editor.blockSignals(True); self.editor.setPlainText(content); self.editor.blockSignals(False)
            self.current_file_path = file_path
            if not is_revert: self.unsaved_changes = False
            self._update_ui_states()
            # Сообщаем родительскому окну об изменении файла для обновления заголовка
            if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp): # Hacky way to get main window
                 self.parentWidget().parentWidget().parentWidget().update_window_title()

        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Загрузка заметки: {e}")
            self.current_file_path = None; self.editor.clear(); self.unsaved_changes = False; self._update_ui_states()
            if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp):
                 self.parentWidget().parentWidget().parentWidget().update_window_title()


    def save_note(self):
        if not self.current_file_path: return
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f: f.write(self.editor.toPlainText())
            self.unsaved_changes = False; self._update_ui_states()
            if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp):
                 self.parentWidget().parentWidget().parentWidget().update_window_title()
        except Exception as e: QMessageBox.warning(self, "Ошибка", f"Сохранение заметки: {e}")

    def new_note(self):
        if not self.current_vault_path: QMessageBox.information(self, "Инфо", "Хранилище не готово."); return
        if self.unsaved_changes and not self._confirm_discard("Создание новой заметки?"): return
        
        name, ok = QInputDialog.getText(self, "Создать заметку", "Имя заметки:")
        if ok and name:
            cleaned_name = self._clean_name_for_path(name, is_file=True)
            if not cleaned_name: QMessageBox.warning(self, "Ошибка", "Некорректное имя."); return
            path = os.path.join(self._get_base_create_path(), f"{cleaned_name}.md")
            if os.path.exists(path): QMessageBox.warning(self, "Ошибка", f"Заметка '{cleaned_name}' существует."); return
            try:
                with open(path, 'w', encoding='utf-8') as f: f.write("")
                self.load_note(path) 
                self.editor.setPlaceholderText("Я ваше полотно для ваших мыслей!")
                new_idx = self.file_model.index(path)
                if new_idx.isValid():
                    self.file_tree.setCurrentIndex(new_idx)
                    p_idx = self.file_model.parent(new_idx)
                    if p_idx.isValid() and p_idx != self.file_tree.rootIndex():
                        self.file_tree.expand(p_idx)
                    self.file_tree.scrollTo(new_idx)
            except Exception as e: QMessageBox.warning(self, "Ошибка", f"Создание заметки: {e}")
        elif ok: QMessageBox.warning(self, "Ошибка", "Имя заметки пустое.")

    def revert_changes(self):
        if self.current_file_path and self.unsaved_changes:
            if QMessageBox.question(self,"Отменить","Отменить несохраненные изменения?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.load_note(self.current_file_path, True)
                self.unsaved_changes = False; self._update_ui_states()
                if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp):
                     self.parentWidget().parentWidget().parentWidget().update_window_title()


    def _confirm_discard(self, action_text: str = "Действие") -> bool:
        if not self.unsaved_changes: return True
        return QMessageBox.question(self,"Несохраненные изменения",f"{action_text}\nЭто приведет к потере несохраненных изменений.\nПродолжить?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _show_tree_context_menu(self, position: QPoint):
        idx = self.file_tree.indexAt(position)
        if not idx.isValid(): return
        path = self.file_model.filePath(idx)
        if not path or path == self.current_vault_path: return

        menu = QMenu(self)
        rename_action = QAction("Переименовать", self)
        rename_action.triggered.connect(lambda: self._rename_item_at_index(idx))
        menu.addAction(rename_action)

        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self._delete_item_at_index(idx))
        menu.addAction(delete_action)
        
        menu.exec(self.file_tree.viewport().mapToGlobal(position))

    def _rename_item_at_index(self, index: QModelIndex):
        if not index.isValid(): return
        
        old_path = self.file_model.filePath(index)
        file_info = self.file_model.fileInfo(index)
        
        is_dir = file_info.isDir()
        old_name_display = file_info.baseName() if file_info.isFile() and file_info.suffix().lower() == 'md' else file_info.fileName()
        item_type = "папки" if is_dir else "заметки"
        
        new_name, ok = QInputDialog.getText(self, f"Переименовать {item_type}", f"Новое имя для '{old_name_display}':", text=old_name_display)
        if not ok: return
        if not new_name.strip(): QMessageBox.warning(self, "Ошибка", f"Имя {item_type} не может быть пустым."); return

        cleaned_new_name = self._clean_name_for_path(new_name, is_file=not is_dir)
        if not cleaned_new_name: QMessageBox.warning(self, "Ошибка", f"Некорректное новое имя для {item_type}."); return

        final_new_name = cleaned_new_name
        if not is_dir and not final_new_name.lower().endswith(".md"): final_new_name += ".md"

        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, final_new_name)

        if old_path == new_path: return
        if os.path.exists(new_path): QMessageBox.warning(self, "Ошибка", f"Имя '{final_new_name}' уже существует."); return
        
        unsaved_related = False
        if self.unsaved_changes and self.current_file_path:
            if (not is_dir and old_path == self.current_file_path) or \
               (is_dir and self.current_file_path.startswith(old_path + os.sep)):
                if not self._confirm_discard(f"Переименование {item_type} '{old_name_display}'"): return
                unsaved_related = True
        try:
            os.rename(old_path, new_path)
            if self.current_file_path:
                if not is_dir and old_path == self.current_file_path:
                    self.current_file_path = new_path; self.unsaved_changes = False
                    self.editor.setPlaceholderText("Создайте или выберите заметку.")
                elif is_dir and self.current_file_path.startswith(old_path + os.sep):
                    relative_path_after_rename = os.path.relpath(self.current_file_path, old_path)
                    self.current_file_path = os.path.join(new_path, relative_path_after_rename)
                    self.unsaved_changes = False
            self.file_model.setRootPath(self.current_vault_path) # Обновление модели
            self._update_ui_states()
            if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp):
                 self.parentWidget().parentWidget().parentWidget().update_window_title()
        except Exception as e: QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать: {e}")
    
    def _delete_item_at_index(self, index: QModelIndex):
        if not index.isValid(): return
        path, info = self.file_model.filePath(index), self.file_model.fileInfo(index)
        name = info.baseName() if info.isFile() and info.suffix()=='md' else info.fileName()
        type_str, content_str = ("папку", " и всё её содержимое") if info.isDir() else ("заметку", "")
        msg = f"Удалить {type_str} '{name}'{content_str}?"
        
        related_unsaved = False
        if self.current_file_path and self.unsaved_changes:
            if (info.isFile() and path == self.current_file_path) or \
               (info.isDir() and self.current_file_path.startswith(path + os.sep)):
                related_unsaved = True
                msg += f"\n\nВнимание: Открытая заметка '{QFileInfo(self.current_file_path).baseName()}' не сохранена и будет потеряна."
        
        if QMessageBox.question(self,"Удаление",msg,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                if info.isDir(): shutil.rmtree(path)
                else: os.remove(path)
                if related_unsaved or (self.current_file_path and self.current_file_path == path):
                    self.editor.blockSignals(True); self.editor.clear(); self.editor.blockSignals(False)
                    self.current_file_path, self.unsaved_changes = None, False
                    self.editor.setPlaceholderText("Создайте или выберите заметку.")
                    if self.parentWidget() and self.parentWidget().parentWidget() and isinstance(self.parentWidget().parentWidget().parentWidget(), CombinedApp):
                        self.parentWidget().parentWidget().parentWidget().update_window_title()

            except Exception as e: QMessageBox.critical(self, "Ошибка", f"Удаление: {e}")
            finally: self._update_ui_states()

# --- Виджет для To-Do ---
class TodoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self.db_conn = None

        self.init_db()
        self._setup_ui()
        self.load_tasks_from_db() # Загрузка после UI

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)

        input_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Новая задача (текст, Enter для деталей)...")
        self.task_input.returnPressed.connect(self.open_add_task_dialog)
        input_layout.addWidget(self.task_input, 1)

        self.add_button = QPushButton("Добавить задачу")
        self.add_button.clicked.connect(self.open_add_task_dialog)
        input_layout.addWidget(self.add_button)
        self.main_layout.addLayout(input_layout)

        self.task_list_widget = QListWidget()
        self.task_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list_widget.customContextMenuRequested.connect(self.show_task_context_menu)
        self.task_list_widget.itemDoubleClicked.connect(self.edit_selected_task_from_list)
        self.main_layout.addWidget(self.task_list_widget)

        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(15 * 1000)

    def init_db(self):
        try:
            self.db_conn = sqlite3.connect(DATABASE_NAME) # DATABASE_NAME уже включает ./project/
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    priority INTEGER,
                    reminder_datetime TEXT,
                    completed INTEGER DEFAULT 0,
                    reminder_shown INTEGER DEFAULT 0
                )
            ''')
            self.db_conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось инициализировать БД To-Do: {e}")
            # Consider how to handle this; exiting might be too drastic in a combined app
            # QApplication.quit() 

    def load_tasks_from_db(self):
        if not self.db_conn: return
        self.tasks = []
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, text, priority, reminder_datetime, completed, reminder_shown FROM tasks")
            rows = cursor.fetchall()
            for row in rows:
                id_str, text, priority, reminder_dt_str, completed, reminder_shown = row
                reminder_dt = None
                if reminder_dt_str:
                    temp_dt = QDateTime.fromString(reminder_dt_str, Qt.DateFormat.ISODate)
                    if not temp_dt.isValid():
                         temp_dt = QDateTime.fromString(reminder_dt_str, Qt.DateFormat.ISODateWithMs)
                    if temp_dt.isValid(): reminder_dt = temp_dt
                    else: print(f"Warning: Failed to parse reminder_datetime: {reminder_dt_str} for task ID: {id_str}")
                task = Task(text, priority, reminder_dt, bool(completed), id_str, bool(reminder_shown))
                self.tasks.append(task)
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Ошибка Базы Данных", f"Не удалось загрузить задачи To-Do: {e}")
        self.refresh_task_list()

    def save_task_to_db(self, task: Task):
        if not self.db_conn: return False
        reminder_dt_str = task.reminder_datetime.toString(Qt.DateFormat.ISODateWithMs) \
            if task.reminder_datetime and task.reminder_datetime.isValid() else None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (id, text, priority, reminder_datetime, completed, reminder_shown)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task.id, task.text, task.priority, reminder_dt_str, int(task.completed), int(task.reminder_shown)))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось сохранить задачу To-Do: {e}")
            return False

    def update_task_in_db(self, task: Task):
        if not self.db_conn: return False
        reminder_dt_str = task.reminder_datetime.toString(Qt.DateFormat.ISODateWithMs) \
            if task.reminder_datetime and task.reminder_datetime.isValid() else None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                UPDATE tasks
                SET text = ?, priority = ?, reminder_datetime = ?, completed = ?, reminder_shown = ?
                WHERE id = ?
            ''', (task.text, task.priority, reminder_dt_str, int(task.completed), int(task.reminder_shown), task.id))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось обновить задачу To-Do: {e}")
            return False

    def delete_task_from_db(self, task_id: str):
        if not self.db_conn: return False
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось удалить задачу To-Do: {e}")
            return False

    def open_add_task_dialog(self):
        initial_text = self.task_input.text().strip()
        dialog = EditTaskDialog(parent=self)
        if initial_text:
            dialog.text_edit.setText(initial_text)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if task_data:
                text, priority, reminder_dt = task_data
                new_task = Task(text, priority, reminder_dt)
                if self.save_task_to_db(new_task):
                    self.tasks.append(new_task)
                    self.task_input.clear()
                    self.refresh_task_list()

    def edit_selected_task_from_list(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        self.edit_task_by_id(task_id)

    def edit_task_by_id(self, task_id):
        task_to_edit = next((t for t in self.tasks if t.id == task_id), None)
        if not task_to_edit: return
        dialog = EditTaskDialog(task_to_edit, self)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if task_data:
                text, priority, reminder_dt = task_data
                task_to_edit.text = text
                task_to_edit.priority = priority
                if task_to_edit.reminder_datetime != reminder_dt:
                    task_to_edit.reminder_shown = False
                task_to_edit.reminder_datetime = reminder_dt
                if self.update_task_in_db(task_to_edit):
                    self.refresh_task_list()

    def refresh_task_list(self):
        self.task_list_widget.clear()
        self.tasks.sort(key=lambda t: (
            t.completed, t.priority,
            t.reminder_datetime if t.reminder_datetime and t.reminder_datetime.isValid() else QDateTime.currentDateTime().addYears(200)
        ))
        for task in self.tasks:
            item_text_parts = [task.text]
            if task.reminder_datetime and task.reminder_datetime.isValid():
                item_text_parts.append(f"(Напомнить: {task.reminder_datetime.toString('dd.MM.yyyy HH:mm')})")
            if task.priority != 4:
                 item_text_parts.append(f"[{PRIORITIES[task.priority]['name'].split(' ')[0]}]")
            list_item = QListWidgetItem(" ".join(item_text_parts))
            list_item.setData(Qt.ItemDataRole.UserRole, task.id)
            font = list_item.font()
            if task.completed:
                font.setStrikeOut(True); list_item.setForeground(Qt.GlobalColor.darkGray)
            else:
                font.setStrikeOut(False); list_item.setForeground(PRIORITIES.get(task.priority, {}).get("color", Qt.GlobalColor.black))
            list_item.setFont(font)
            self.task_list_widget.addItem(list_item)

    def show_task_context_menu(self, position):
        selected_item = self.task_list_widget.itemAt(position)
        if not selected_item: return
        task_id = selected_item.data(Qt.ItemDataRole.UserRole)
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task: return
        menu = QMenu()
        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(lambda: self.edit_task_by_id(task_id))
        menu.addAction(edit_action)
        toggle_complete_action = QAction("Снять отметку о выполнении" if task.completed else "Отметить как выполненную", self)
        toggle_complete_action.triggered.connect(lambda: self.toggle_task_completion(task_id))
        menu.addAction(toggle_complete_action)
        if not task.completed and task.reminder_datetime and task.reminder_datetime.isValid() and task.reminder_shown:
            reset_reminder_action = QAction("Сбросить показанное напоминание", self)
            reset_reminder_action.triggered.connect(lambda: self.reset_reminder_shown_status(task_id))
            menu.addAction(reset_reminder_action)
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.confirm_delete_task(task_id))
        menu.addAction(delete_action)
        menu.exec(self.task_list_widget.mapToGlobal(position))

    def reset_reminder_shown_status(self, task_id):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.reminder_shown = False
            if self.update_task_in_db(task):
                QMessageBox.information(self, "Напоминание сброшено", f"Напоминание для задачи '{task.text[:30]}...' будет показано снова.")
                self.refresh_task_list()

    def toggle_task_completion(self, task_id):
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task:
            task.completed = not task.completed
            if not task.completed and task.reminder_datetime and task.reminder_datetime.isValid() and \
               task.reminder_datetime <= QDateTime.currentDateTime() and task.reminder_shown:
                task.reminder_shown = False
            if self.update_task_in_db(task):
                self.refresh_task_list()

    def confirm_delete_task(self, task_id):
        task_to_delete = next((t for t in self.tasks if t.id == task_id), None)
        if not task_to_delete: return
        reply = QMessageBox.question(self, "Удалить задачу", f"Удалить задачу:\n'{task_to_delete.text}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.delete_task_from_db(task_id):
                self.tasks = [t for t in self.tasks if t.id != task_id]
                self.refresh_task_list()

    def check_reminders(self):
        now = QDateTime.currentDateTime()
        tasks_to_update_in_db = []
        for task in self.tasks:
            if not task.completed and task.reminder_datetime and \
               task.reminder_datetime.isValid() and \
               task.reminder_datetime <= now and not task.reminder_shown:
                QTimer.singleShot(0, lambda t=task: QMessageBox.information(self, "Напоминание!",
                                            f"Пора выполнить задачу:\n\n{t.text}\n\n"
                                            f"Приоритет: {PRIORITIES[t.priority]['name']}"))
                task.reminder_shown = True
                tasks_to_update_in_db.append(task)
        if tasks_to_update_in_db and self.db_conn:
            try:
                cursor = self.db_conn.cursor()
                updates_data = [(int(t.reminder_shown), t.id) for t in tasks_to_update_in_db]
                cursor.executemany("UPDATE tasks SET reminder_shown = ? WHERE id = ?", updates_data)
                self.db_conn.commit()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось обновить статус напоминания: {e}")

    def close_db(self):
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None

# --- Основное приложение ---
class CombinedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(COMBINED_APP_NAME)
        self.setGeometry(100, 100, 1000, 700) # Увеличил размер для двух вкладок

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.note_widget_instance = NoteWidget(self)
        self.todo_widget_instance = TodoWidget(self)

        self.tab_widget.addTab(self.note_widget_instance, "Заметки")
        self.tab_widget.addTab(self.todo_widget_instance, "To-Do")

        self.tab_widget.currentChanged.connect(self.update_window_title)
        self.update_window_title() # Initial title update

    def update_window_title(self):
        current_tab_index = self.tab_widget.currentIndex()
        title = COMBINED_APP_NAME

        if current_tab_index == 0: # Заметки
            title = APP_NAME_NOTES
            if self.note_widget_instance.current_file_path:
                title = f"{QFileInfo(self.note_widget_instance.current_file_path).baseName()} - {APP_NAME_NOTES}"
                if self.note_widget_instance.unsaved_changes:
                    title += "*"
        elif current_tab_index == 1: # To-Do
            title = APP_NAME_TODO
        
        self.setWindowTitle(title)

    def closeEvent(self, event):
        # Сохранение несохраненных изменений в заметках (если есть открытая)
        if self.note_widget_instance.unsaved_changes:
            reply = QMessageBox.question(self, 'Несохраненные изменения',
                                         "Есть несохраненные изменения в текущей заметке. Сохранить перед выходом?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.note_widget_instance.save_note()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        
        # Закрытие БД для To-Do
        self.todo_widget_instance.close_db()
        super().closeEvent(event)

# --- Запуск приложения ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # --- QSS для темной темы (из оригинального NoteApp) ---
    dark_stylesheet = """
    /* Общие цвета фона и текста */
    QWidget {
        background-color: #202020; 
        color: #C0C0C0; 
        selection-background-color: #4A90D9; 
        selection-color: #FFFFFF; 
    }
    QMainWindow { background-color: #202020; }
    QTabWidget::pane { border: 1px solid #3A3A3A; }
    QTabBar::tab {
        background-color: #282828;
        color: #A0A0A0;
        border: 1px solid #3A3A3A;
        border-bottom: none; 
        padding: 8px 15px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: #202020; /* Фон активной вкладки совпадает с основным фоном */
        color: #E0E0E0;
        border-color: #3A3A3A;
    }
    QTabBar::tab:hover {
        background-color: #333333;
    }
    QPushButton {
        background-color: #333333; border: 1px solid #555555;
        border-radius: 4px; padding: 5px 15px; color: #E0E0E0;
    }
    QPushButton:hover { background-color: #444444; border-color: #666666; }
    QPushButton:pressed { background-color: #222222; border-color: #444444; }
    QPushButton:disabled { background-color: #282828; border-color: #383838; color: #808080; }
    QTextEdit, QLineEdit {
        background-color: #1A1A1A; color: #D4D4D4;
        border: 1px solid #3A3A3A; padding: 5px;
    }
    QTextEdit::placeholder, QLineEdit::placeholder { color: #707070; }
    QTreeView {
        background-color: #252525; color: #C0C0C0;
        border: 1px solid #3A3A3A; alternate-background-color: #2A2A2A;
        show-decoration-selected: 1; 
    }
    QTreeView::item { padding: 3px; color: #C0C0C0; }
    QTreeView::item:hover { background-color: #3A3A3A; }
    QTreeView::item:selected { background-color: #4A90D9; color: #FFFFFF; }
    QTreeView::branch:closed:has-children { image: url(./project/icons/arrow_closed.png); }
    QTreeView::branch:open:has-children { image: url(./project/icons/arrow_open.png); }
    QListWidget {
        background-color: #252525; color: #C0C0C0;
        border: 1px solid #3A3A3A; alternate-background-color: #2A2A2A;
    }
    QListWidget::item { padding: 4px; }
    QListWidget::item:hover { background-color: #3A3A3A; }
    QListWidget::item:selected { background-color: #4A90D9; color: #FFFFFF; }
    QSplitter::handle { background-color: #333333; width: 2px; }
    QSplitter::handle:hover { background-color: #4A90D9; }
    QMenu {
        background-color: #2F2F2F; border: 1px solid #454545; color: #E0E0E0;
    }
    QMenu::item { padding: 5px 20px 5px 20px; }
    QMenu::item:selected { background-color: #4A90D9; color: #FFFFFF; }
    QMenu::separator { height: 1px; background-color: #454545; margin: 5px 10px; }
    QDialog, QInputDialog, QMessageBox { background-color: #202020; color: #C0C0C0; }
    QDialog QLabel, QInputDialog QLabel, QMessageBox QLabel { color: #C0C0C0; }
    QDialog QLineEdit, QInputDialog QLineEdit { /* Already covered by general QLineEdit */ }
    QComboBox {
        background-color: #1A1A1A; color: #D4D4D4;
        border: 1px solid #3A3A3A; padding: 3px 5px;
        selection-background-color: #4A90D9;
    }
    QComboBox::drop-down { border: none; background-color: #333333; }
    QComboBox QAbstractItemView { /* Dropdown list */
        background-color: #1A1A1A;
        border: 1px solid #3A3A3A;
        selection-background-color: #4A90D9;
        color: #D4D4D4;
    }
    QDateTimeEdit {
        background-color: #1A1A1A; color: #D4D4D4;
        border: 1px solid #3A3A3A; padding: 3px;
    }
    QDateTimeEdit::up-button, QDateTimeEdit::down-button { width: 16px; }
    QCheckBox::indicator { width: 13px; height: 13px; }
    """
    app.setStyleSheet(dark_stylesheet)
    app_icon_path = "./project/icons/app_icon.png"
    app.setStyle("Fusion") 
    app.setWindowIcon(QIcon(app_icon_path))
    main_win = CombinedApp()
    main_win.show()
    sys.exit(app.exec())