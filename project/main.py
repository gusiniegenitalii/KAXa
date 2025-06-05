import sys
import os
import shutil
import uuid
import sqlite3

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QDateTimeEdit, QMessageBox, QDialog, QDialogButtonBox, QLabel,
    QTextEdit, QCheckBox, QMenu, QTreeView, QSplitter, QTabWidget,
    QInputDialog, QToolBar, QSizePolicy, QStyle, QCalendarWidget,
    QToolButton
)

from PyQt6.QtCore import (
    Qt, QDateTime, QTimer, QDir, QFileInfo, QModelIndex, QVariant, QPoint, QSize,
    QDate, QTime, QLocale, QRect
)

from PyQt6.QtGui import (
    QFileSystemModel, QAction, QFont, QIcon, QColor, QTextCharFormat,
    QPainter, QPalette, QTextOption, QFontMetrics
)

PRIORITIES = {
    1: {"name": "Высокий", "color": QColor("red")},
    2: {"name": "Средний", "color": QColor("orange")},
    3: {"name": "Низкий", "color": QColor("green")},
    4: {"name": "Нет", "color": QColor("gray")}
}

DATABASE_NAME = './project/todo.db'
DEFAULT_VAULT_NAME = "notes"

APP_NAME_NOTES = "KAXa Заметки"
APP_NAME_CALENDAR = "KAXa Календарь"
COMBINED_APP_NAME = "KAXa"


ABOUT_INFO = {
    "program_name": COMBINED_APP_NAME,
    "version": "0.3a",
    "authors": "eggs",
    "copyright": "© 2025 egg's Team. Все права защищены.",
    "description": (
        "KAXa - это комплексное приложение, разработанное в рамках курсового проекта. "
        "Оно объединяет в себе функционал для ведения заметок и управления задачами через календарь."
    )
}

### КЛАСС: Task - Описывает элемент списка дел.
class Task:
    ### --- Метод: __init__ --- Инициализирует новую задачу.
    def __init__(self, text, priority=4, reminder_dt=None, completed=False, id_str=None, reminder_shown=False):
        self.id = id_str if id_str else str(uuid.uuid4())
        self.text = text
        self.priority = int(priority)
        self.reminder_datetime = reminder_dt
        self.completed = bool(completed)
        self.reminder_shown = bool(reminder_shown)

    ### --- Метод: __repr__ --- Возвращает строковое представление задачи.
    def __repr__(self):
        return (f"Task(id={self.id}, text='{self.text[:20]}...', priority={self.priority}, "
                f"reminder={self.reminder_datetime}, completed={self.completed}, "
                f"reminder_shown={self.reminder_shown})")

### КЛАСС: EditTaskDialog - Диалоговое окно для создания или редактирования задачи.
class EditTaskDialog(QDialog):
    ### --- Метод: __init__ --- Инициализирует диалоговое окно.
    def __init__(self, task=None, parent=None, default_date=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать задачу" if task else "Новая задача")
        self.task = task
        self._setup_ui(default_date)

    ### --- Метод: _setup_ui --- Создает элементы интерфейса для диалога.
    def _setup_ui(self, default_date):
        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        if self.task:
            self.text_edit.setText(self.task.text)
        layout.addWidget(QLabel("Описание задачи:"))
        layout.addWidget(self.text_edit)

        self.priority_combo = QComboBox()
        for p_val, p_data in sorted(PRIORITIES.items()):
            self.priority_combo.addItem(p_data["name"], p_val)
        if self.task:
            self.priority_combo.setCurrentIndex(self.priority_combo.findData(self.task.priority))
        else:
            self.priority_combo.setCurrentIndex(self.priority_combo.findData(4))
        layout.addWidget(QLabel("Приоритет:"))
        layout.addWidget(self.priority_combo)

        self.reminder_checkbox = QCheckBox("Установить дату/время (и напоминание)")
        layout.addWidget(self.reminder_checkbox)

        self.reminder_datetime_edit = QDateTimeEdit()
        self.reminder_datetime_edit.setCalendarPopup(True)
        self.reminder_datetime_edit.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.reminder_datetime_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.reminder_datetime_edit.setEnabled(False)

        if self.task and self.task.reminder_datetime and self.task.reminder_datetime.isValid():
            self.reminder_datetime_edit.setDateTime(self.task.reminder_datetime)
            self.reminder_checkbox.setChecked(True)
            self.reminder_datetime_edit.setEnabled(True)
        elif default_date:
            self.reminder_datetime_edit.setDateTime(QDateTime(default_date, QTime(9,0)))
            self.reminder_checkbox.setChecked(True)
            self.reminder_datetime_edit.setEnabled(True)

        self.reminder_checkbox.stateChanged.connect(
            lambda state: self.reminder_datetime_edit.setEnabled(state == Qt.CheckState.Checked.value)
        )
        layout.addWidget(QLabel("Дата и время задачи:"))
        layout.addWidget(self.reminder_datetime_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    ### --- Метод: get_task_data --- Извлекает и проверяет данные задачи из диалога.
    def get_task_data(self):
        text = self.text_edit.toPlainText().strip()
        priority = self.priority_combo.currentData()
        reminder_dt = None
        reminder_active = self.reminder_checkbox.isChecked()

        if not text:
            QMessageBox.warning(self, "Ошибка", "Описание задачи не может быть пустым.")
            return None

        if reminder_active:
            reminder_dt = self.reminder_datetime_edit.dateTime()
            is_new_task_or_reminder_changed = not self.task or \
                                             (self.task and self.task.reminder_datetime != reminder_dt)

            if is_new_task_or_reminder_changed and reminder_dt <= QDateTime.currentDateTime():
                reply = QMessageBox.warning(self, "Внимание",
                                            "Выбранное время задачи находится в прошлом. "
                                            "Напоминание для этого времени не сработает. Продолжить?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return None
        return text, priority, reminder_dt

### КЛАСС: SimpleTreeModel - Пользовательская модель файловой системы для дерева заметок.
class SimpleTreeModel(QFileSystemModel):
    ### --- Метод: __init__ --- Инициализирует модель.
    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder_font = QFont()
        self._folder_font.setBold(True)

    ### --- Метод: data --- Предоставляет данные для отображения в дереве.
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return QVariant()
        file_info = self.fileInfo(index)

        if role == Qt.ItemDataRole.FontRole:
            return self._folder_font if file_info.isDir() else QVariant()
        elif role == Qt.ItemDataRole.DecorationRole:
             return QVariant()
        elif role == Qt.ItemDataRole.DisplayRole:
            if file_info.isFile() and file_info.suffix().lower() == 'md':
                return file_info.baseName()
        return super().data(index, role)


### КЛАСС: NoteWidget - Управляет функциональностью заметок.
class NoteWidget(QWidget):
    ### --- Метод: __init__ --- Инициализирует виджет заметок.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_vault_path = None
        self.current_file_path = None
        self.unsaved_changes = False
        self._initialize_paths()
        self._setup_ui()
        self._post_setup_ui_logic()

    ### --- Метод: _initialize_paths --- Настраивает пути для хранения заметок.
    def _initialize_paths(self):
        try:
            script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        except NameError:
            script_dir = os.getcwd()

        project_notes_dir = os.path.join(script_dir, "notes")
        if not os.path.exists(project_notes_dir):
            try:
                os.makedirs(project_notes_dir)
            except OSError as e:
                 QMessageBox.critical(self, "Ошибка", f"Не удалось создать директорию заметок: {e}")

        self.current_vault_path = os.path.join(project_notes_dir, DEFAULT_VAULT_NAME)
        if not os.path.exists(self.current_vault_path):
            try:
                os.makedirs(self.current_vault_path)
            except OSError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать хранилище заметок '{DEFAULT_VAULT_NAME}': {e}")
                self.current_vault_path = None

    ### --- Метод: _setup_ui --- Создает элементы интерфейса для вкладки "Заметки".
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

    ### --- Метод: _post_setup_ui_logic --- Завершающая настройка UI после создания элементов.
    def _post_setup_ui_logic(self):
        if self.current_vault_path:
            root_idx = self.file_model.setRootPath(self.current_vault_path)
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

    ### --- Метод: _update_ui_states --- Обновляет состояние элементов UI (кнопки, плейсхолдеры).
    def _update_ui_states(self):
        can_act_on_current_file = bool(self.current_file_path and self.unsaved_changes)
        self.save_button.setEnabled(can_act_on_current_file)
        self.cancel_button.setEnabled(can_act_on_current_file)
        if not self.current_file_path:
             self.editor.setPlaceholderText("Создайте или выберите заметку." if self.current_vault_path else "Хранилище заметок не инициализировано.")

    ### --- Метод: _mark_unsaved_changes --- Помечает несохраненные изменения в редакторе.
    def _mark_unsaved_changes(self):
        if self.current_file_path:
            self.unsaved_changes = True
        self._update_ui_states()
        if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
            self.parentWidget().parentWidget().update_window_title()

    ### --- Метод: _get_base_create_path --- Определяет базовый путь для создания новых заметок/папок.
    def _get_base_create_path(self):
        idx = self.file_tree.currentIndex()
        if idx.isValid():
            path = self.file_model.filePath(idx)
            return path if self.file_model.isDir(idx) else os.path.dirname(path)
        return self.current_vault_path

    ### --- Метод: _clean_name_for_path --- Очищает имена для путей файлов/папок.
    def _clean_name_for_path(self, name: str, is_file: bool = False) -> str:
        invalid_chars = '<>:"/\\|?*'
        cleaned_name = "".join(c for c in name if c not in invalid_chars).strip()
        cleaned_name = ' '.join(cleaned_name.split())
        if is_file and not cleaned_name: return "Новая заметка"
        elif not is_file and not cleaned_name: return "Новая папка"
        return cleaned_name

    ### --- Метод: create_folder --- Обрабатывает создание новой папки.
    def create_folder(self):
        if not self.current_vault_path:
            QMessageBox.information(self, "Инфо", "Хранилище заметок не доступно."); return
        name, ok = QInputDialog.getText(self, "Создать папку", "Имя папки:")
        if ok and name:
            cleaned_name = self._clean_name_for_path(name, is_file=False)
            if not cleaned_name:
                QMessageBox.warning(self, "Ошибка", "Некорректное имя папки."); return
            path = os.path.join(self._get_base_create_path(), cleaned_name)
            if os.path.exists(path):
                QMessageBox.warning(self, "Ошибка", f"Папка '{cleaned_name}' уже существует."); return
            try:
                os.makedirs(path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку: {e}")
        elif ok and not name.strip():
            QMessageBox.warning(self, "Ошибка", "Имя папки не может быть пустым.")

    ### --- Метод: on_file_tree_clicked --- Обрабатывает клики по дереву файлов.
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

    ### --- Метод: load_note --- Загружает содержимое заметки в редактор.
    def load_note(self, file_path: str, is_revert: bool = False):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self.current_file_path = file_path
            if not is_revert:
                self.unsaved_changes = False
            self._update_ui_states()
            if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                 self.parentWidget().parentWidget().update_window_title()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить заметку: {e}")
            self.current_file_path = None
            self.editor.clear()
            self.unsaved_changes = False
            self._update_ui_states()
            if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                 self.parentWidget().parentWidget().update_window_title()

    ### --- Метод: save_note --- Сохраняет текущую заметку в файл.
    def save_note(self):
        if not self.current_file_path: return
        try:
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.unsaved_changes = False
            self._update_ui_states()
            if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                 self.parentWidget().parentWidget().update_window_title()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить заметку: {e}")

    ### --- Метод: new_note --- Обрабатывает создание новой заметки.
    def new_note(self):
        if not self.current_vault_path:
            QMessageBox.information(self, "Инфо", "Хранилище заметок не доступно."); return
        if self.unsaved_changes and not self._confirm_discard("Создание новой заметки?"): return
        name, ok = QInputDialog.getText(self, "Создать заметку", "Имя заметки:")
        if ok and name:
            cleaned_name = self._clean_name_for_path(name, is_file=True)
            if not cleaned_name:
                QMessageBox.warning(self, "Ошибка", "Некорректное имя заметки."); return
            path = os.path.join(self._get_base_create_path(), f"{cleaned_name}.md")
            if os.path.exists(path):
                QMessageBox.warning(self, "Ошибка", f"Заметка '{cleaned_name}.md' уже существует."); return
            try:
                with open(path, 'w', encoding='utf-8') as f: f.write("")
                self.load_note(path)
                self.editor.setPlaceholderText("Я ваше полотно для ваших мыслей!")
                new_idx = self.file_model.index(path)
                if new_idx.isValid():
                    self.file_tree.setCurrentIndex(new_idx)
                    parent_idx = self.file_model.parent(new_idx)
                    if parent_idx.isValid() and parent_idx != self.file_tree.rootIndex():
                        self.file_tree.expand(parent_idx)
                    self.file_tree.scrollTo(new_idx)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать заметку: {e}")
        elif ok and not name.strip():
            QMessageBox.warning(self, "Ошибка", "Имя заметки не может быть пустым.")

    ### --- Метод: revert_changes --- Отменяет несохраненные изменения в заметке.
    def revert_changes(self):
        if self.current_file_path and self.unsaved_changes:
            if QMessageBox.question(self,"Отменить","Отменить несохраненные изменения в текущей заметке?",
                                     QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.load_note(self.current_file_path, is_revert=True)
                self.unsaved_changes = False
                self._update_ui_states()
                if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                     self.parentWidget().parentWidget().update_window_title()

    ### --- Метод: _confirm_discard --- Запрашивает у пользователя подтверждение отмены несохраненных изменений.
    def _confirm_discard(self, action_text: str = "Действие") -> bool:
        if not self.unsaved_changes: return True
        return QMessageBox.question(self, "Несохраненные изменения",
                                   f"{action_text}\nЭто приведет к потере несохраненных изменений.\nПродолжить?",
                                   QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    ### --- Метод: _show_tree_context_menu --- Отображает контекстное меню для элементов дерева файлов.
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

    ### --- Метод: _rename_item_at_index --- Переименовывает файл или папку.
    def _rename_item_at_index(self, index: QModelIndex):
        if not index.isValid(): return
        old_path = self.file_model.filePath(index)
        file_info = self.file_model.fileInfo(index)
        is_dir = file_info.isDir()
        old_display_name = file_info.baseName() if file_info.isFile() and file_info.suffix().lower() == 'md' else file_info.fileName()
        item_type_str = "папки" if is_dir else "заметки"
        new_name, ok = QInputDialog.getText(self, f"Переименовать {item_type_str}",
                                            f"Новое имя для '{old_display_name}':", text=old_display_name)
        if not ok: return
        if not new_name.strip():
            QMessageBox.warning(self, "Ошибка", f"Имя {item_type_str} не может быть пустым."); return
        cleaned_new_name = self._clean_name_for_path(new_name, is_file=not is_dir)
        if not cleaned_new_name:
            QMessageBox.warning(self, "Ошибка", f"Некорректное новое имя для {item_type_str}."); return
        final_new_name_for_path = cleaned_new_name
        if not is_dir and not final_new_name_for_path.lower().endswith(".md"):
            final_new_name_for_path += ".md"
        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, final_new_name_for_path)
        if old_path.lower() == new_path.lower(): return
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Ошибка", f"Имя '{final_new_name_for_path}' уже существует в этой папке."); return
        active_note_affected = False
        if self.current_file_path:
            if not is_dir and old_path == self.current_file_path:
                active_note_affected = True
            elif is_dir and self.current_file_path.startswith(old_path + os.sep):
                active_note_affected = True
        if active_note_affected and self.unsaved_changes:
            if not self._confirm_discard(f"Переименование '{old_display_name}' (открытая заметка будет затронута)"):
                return
        try:
            os.rename(old_path, new_path)
            if active_note_affected:
                if not is_dir:
                    self.current_file_path = new_path
                else:
                    relative_path = os.path.relpath(self.current_file_path, old_path)
                    self.current_file_path = os.path.join(new_path, relative_path)
                self.unsaved_changes = False
            self._update_ui_states()
            if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                 self.parentWidget().parentWidget().update_window_title()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать: {e}")

    ### --- Метод: _delete_item_at_index --- Удаляет файл или папку.
    def _delete_item_at_index(self, index: QModelIndex):
        if not index.isValid(): return
        path = self.file_model.filePath(index)
        file_info = self.file_model.fileInfo(index)
        is_dir = file_info.isDir()
        display_name = file_info.baseName() if file_info.isFile() and file_info.suffix().lower() == 'md' else file_info.fileName()
        item_type_str = "папку" if is_dir else "заметку"
        content_str = " и всё её содержимое" if is_dir else ""
        msg = f"Вы уверены, что хотите удалить {item_type_str} '{display_name}'{content_str}?"
        active_note_affected_and_unsaved = False
        if self.current_file_path and self.unsaved_changes:
            if (not is_dir and path == self.current_file_path) or \
               (is_dir and self.current_file_path.startswith(path + os.sep)):
                active_note_affected_and_unsaved = True
                msg += f"\n\nВНИМАНИЕ: Открытая заметка '{QFileInfo(self.current_file_path).baseName()}' имеет несохраненные изменения, которые будут потеряны."
        if QMessageBox.question(self,"Подтверждение удаления", msg,
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                if is_dir: shutil.rmtree(path)
                else: os.remove(path)
                if (self.current_file_path and path == self.current_file_path) or \
                   (is_dir and self.current_file_path and self.current_file_path.startswith(path + os.sep)):
                    self.editor.blockSignals(True); self.editor.clear(); self.editor.blockSignals(False)
                    self.current_file_path = None
                    self.unsaved_changes = False
                    self.editor.setPlaceholderText("Создайте или выберите заметку.")
                    if self.parentWidget() and hasattr(self.parentWidget().parentWidget(), "update_window_title"):
                        self.parentWidget().parentWidget().update_window_title()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")
            finally:
                self._update_ui_states()

### КЛАСС: CustomCalendarWidget - Календарь с отображением количества задач.
class CustomCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_counts_for_month = {}  # Словарь {QDate: int} для хранения количества задач
        self._task_count_font = QFont()
        
        # Подбор размера шрифта для счетчика на основе основного шрифта календаря
        main_font_size = self.font().pointSize()
        if main_font_size > 0:
             self._task_count_font.setPointSize(max(6, int(main_font_size * 0.9))) # Немного меньше основного
        else:
            self._task_count_font.setPointSize(7) # Значение по умолчанию
        self._task_count_font.setBold(True) # Жирный шрифт для лучшей видимости
        
        # Цвет для счетчика задач (по умолчанию синий)
        self._task_count_color = QColor(Qt.GlobalColor.white)
        # Цвет для счетчика на выделенной дате (по умолчанию желтый)
        self._task_count_selected_color = QColor(Qt.GlobalColor.lightGray)


    def set_task_counts_for_month(self, counts: dict):
        """Устанавливает словарь с количеством задач для текущего месяца."""
        self._task_counts_for_month = counts
        self.updateCells()  # Запрос на перерисовку всех ячеек календаря

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        """Переопределенный метод для отрисовки ячейки календаря."""
        # Сначала вызываем стандартный метод отрисовки ячейки
        super().paintCell(painter, rect, date)

        count = self._task_counts_for_month.get(date)

        # Если для этой даты есть задачи (count > 0), рисуем их количество
        if count and count > 0:
            painter.save() # Сохраняем текущее состояние QPainter (шрифт, цвет и т.д.)
            painter.setFont(self._task_count_font) # Устанавливаем шрифт для счетчика

            # Выбираем цвет для счетчика в зависимости от того, выбрана ли дата
            if self.selectedDate() == date:
                painter.setPen(self._task_count_selected_color)
            else:
                painter.setPen(self._task_count_color)

            count_str = str(count) # Преобразуем количество в строку
            fm = QFontMetrics(self._task_count_font) # Для получения размеров текста
            
            # Рассчитываем позицию для счетчика (правый верхний угол ячейки)
            padding_x = 3  # Отступ справа
            padding_y = 2  # Отступ сверху
            
            text_width = fm.horizontalAdvance(count_str)
            # text_height = fm.height() # Полная высота символов
            ascent = fm.ascent() # Высота от базовой линии до верха

            # Координаты для отрисовки текста
            # x: правый край ячейки - ширина текста - отступ
            # y: верхний край ячейки + высота до базовой линии + отступ
            text_x = rect.right() - text_width - padding_x
            text_y = rect.top() + ascent + padding_y
            
            painter.drawText(QPoint(text_x, text_y), count_str) # Рисуем текст
            painter.restore() # Восстанавливаем состояние QPainter

### КЛАСС: CalendarWidget - Управляет календарем и списком задач.
class CalendarWidget(QWidget):
    ### --- Метод: __init__ --- Инициализирует виджет календаря.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_tasks = []
        self.db_conn = None
        self.current_calendar_qdate = QDate.currentDate()
        self.russian_locale = QLocale(QLocale.Language.Russian, QLocale.Country.Russia)
        self.init_db()
        self._setup_ui() # Здесь будет создан CustomCalendarWidget
        self._load_all_tasks_from_db()
        self._initial_calendar_setup()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(15 * 1000)

    ### --- Метод: _setup_ui --- Создает элементы интерфейса для вкладки "Календарь".
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        nav_layout = QHBoxLayout()
        self.prev_month_button = QPushButton("<")
        self.prev_month_button.setToolTip("Предыдущий месяц")
        self.prev_month_button.clicked.connect(self._go_to_previous_month)
        nav_layout.addWidget(self.prev_month_button)

        self.month_year_combo_container = QWidget()
        combo_box_layout = QHBoxLayout(self.month_year_combo_container)
        combo_box_layout.setContentsMargins(5,0,5,0)
        combo_box_layout.addStretch()

        self.month_combo = QComboBox()
        self.month_combo.setToolTip("Выберите месяц")
        for m in range(1, 13):
            month_name = self.russian_locale.monthName(m, QLocale.FormatType.LongFormat)
            self.month_combo.addItem(month_name.capitalize(), m)
        self.month_combo.currentIndexChanged.connect(self._combo_selection_changed)
        combo_box_layout.addWidget(self.month_combo)

        self.year_combo = QComboBox()
        self.year_combo.setToolTip("Выберите год")
        for year_val in range(2024, 2027 + 1):
            self.year_combo.addItem(str(year_val), year_val)
        self.year_combo.currentIndexChanged.connect(self._combo_selection_changed)
        combo_box_layout.addWidget(self.year_combo)

        combo_box_layout.addStretch()
        nav_layout.addWidget(self.month_year_combo_container, 1)

        self.next_month_button = QPushButton(">")
        self.next_month_button.setToolTip("Следующий месяц")
        self.next_month_button.clicked.connect(self._go_to_next_month)
        nav_layout.addWidget(self.next_month_button)

        self.today_button = QPushButton("Сегодня")
        self.today_button.setToolTip("Перейти к текущему месяцу")
        self.today_button.clicked.connect(self._go_to_today)
        nav_layout.addWidget(self.today_button)

        self.add_task_button_calendar = QPushButton("Добавить задачу")
        self.add_task_button_calendar.clicked.connect(self._open_add_task_dialog_calendar)
        nav_layout.addWidget(self.add_task_button_calendar)
        self.main_layout.addLayout(nav_layout)

        self.calendar_view = CustomCalendarWidget() # Используем наш кастомный календарь
        self.calendar_view.setGridVisible(True)
        self.calendar_view.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar_view.clicked[QDate].connect(self._date_selected_on_calendar)
        self.calendar_view.currentPageChanged.connect(self._calendar_page_has_changed)
        navigation_bar = self.calendar_view.findChild(QWidget, "qt_calendar_navigationbar")
        if navigation_bar:
            navigation_bar.setVisible(False)
        fmt_weekend = QTextCharFormat()
        fmt_weekend.setForeground(QColor("red"))
        self.calendar_view.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, fmt_weekend)
        self.calendar_view.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, fmt_weekend)
        self.main_layout.addWidget(self.calendar_view, 4)

        self.daily_task_list_widget = QListWidget()
        self.daily_task_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.daily_task_list_widget.customContextMenuRequested.connect(self.show_daily_task_context_menu)
        self.daily_task_list_widget.itemDoubleClicked.connect(self.edit_selected_daily_task)
        self.main_layout.addWidget(self.daily_task_list_widget, 1)

    ### --- Метод: _initial_calendar_setup --- Выполняет первоначальную настройку календаря.
    def _initial_calendar_setup(self):
        self.calendar_view.setCurrentPage(self.current_calendar_qdate.year(), self.current_calendar_qdate.month())
        today = QDate.currentDate()
        if self.current_calendar_qdate.year() == today.year() and self.current_calendar_qdate.month() == today.month():
            self.calendar_view.setSelectedDate(today)
        else:
            self.calendar_view.setSelectedDate(QDate(self.current_calendar_qdate.year(), self.current_calendar_qdate.month(), 1))

    ### --- Метод: _update_month_year_combos --- Синхронизирует выпадающие списки месяца/года.
    def _update_month_year_combos(self):
        self.month_combo.blockSignals(True)
        self.year_combo.blockSignals(True)
        month_idx = self.month_combo.findData(self.current_calendar_qdate.month())
        if month_idx != -1: self.month_combo.setCurrentIndex(month_idx)
        year_idx = self.year_combo.findData(self.current_calendar_qdate.year())
        if year_idx != -1: self.year_combo.setCurrentIndex(year_idx)
        self.month_combo.blockSignals(False)
        self.year_combo.blockSignals(False)

    ### --- Метод: _combo_selection_changed --- Обрабатывает изменение выбора в комбо-боксах месяца/года.
    def _combo_selection_changed(self):
        selected_month = self.month_combo.currentData()
        selected_year = self.year_combo.currentData()
        if selected_month is None or selected_year is None: return
        if (self.current_calendar_qdate.month() == selected_month and
            self.current_calendar_qdate.year() == selected_year):
            return
        self.current_calendar_qdate = QDate(selected_year, selected_month, 1)
        self.calendar_view.setCurrentPage(selected_year, selected_month)

    ### --- Метод: _go_to_previous_month --- Переход к предыдущему месяцу.
    def _go_to_previous_month(self):
        target_date = self.current_calendar_qdate.addMonths(-1)
        if target_date.year() < 2024: target_date = QDate(2024, 1, 1)
        self.current_calendar_qdate = target_date
        self.calendar_view.setCurrentPage(self.current_calendar_qdate.year(), self.current_calendar_qdate.month())

    ### --- Метод: _go_to_next_month --- Переход к следующему месяцу.
    def _go_to_next_month(self):
        target_date = self.current_calendar_qdate.addMonths(1)
        if target_date.year() > 2027: target_date = QDate(2027, 12, 1)
        self.current_calendar_qdate = target_date
        self.calendar_view.setCurrentPage(self.current_calendar_qdate.year(), self.current_calendar_qdate.month())

    ### --- Метод: _go_to_today --- Переход к текущему месяцу/дню.
    def _go_to_today(self):
        today = QDate.currentDate()
        if today.year() < 2024:
            self.current_calendar_qdate = QDate(2024, 1, 1)
        elif today.year() > 2027:
            self.current_calendar_qdate = QDate(2027, 12, 1)
        else:
            self.current_calendar_qdate = today
        self.calendar_view.setCurrentPage(self.current_calendar_qdate.year(), self.current_calendar_qdate.month())
        self.calendar_view.setSelectedDate(self.current_calendar_qdate)

    ### --- Метод: _calendar_page_has_changed --- Обрабатывает смену страницы (месяца/года) календаря.
    def _calendar_page_has_changed(self, year, month):
        if not (self.current_calendar_qdate.year() == year and self.current_calendar_qdate.month() == month):
             self.current_calendar_qdate = QDate(year, month, 1)
        self._update_month_year_combos()
        self._fetch_tasks_for_current_month_and_mark_calendar() # Здесь обновятся и счетчики
        new_selected_date = self.calendar_view.selectedDate()
        if not new_selected_date.isValid() or new_selected_date.month() != month or new_selected_date.year() != year:
            new_selected_date = QDate(year, month, 1)
            self.calendar_view.setSelectedDate(new_selected_date)
        else:
            self._update_daily_task_list(new_selected_date)

    ### --- Метод: _date_selected_on_calendar --- Обрабатывает выбор даты в календаре.
    def _date_selected_on_calendar(self, date: QDate):
        self._update_daily_task_list(date)

    ### --- Метод: _fetch_tasks_for_current_month_and_mark_calendar --- Загружает задачи и маркирует даты календаря (включая счетчики).
    def _fetch_tasks_for_current_month_and_mark_calendar(self):
        if not self.db_conn: return

        year = self.current_calendar_qdate.year()
        month = self.current_calendar_qdate.month()
        current_page_first_day = QDate(year, month, 1)

        # Сброс форматирования для дат текущего месяца
        fmt_default = QTextCharFormat()
        fmt_weekend_base = QTextCharFormat()
        fmt_weekend_base.setForeground(QColor("red"))
        for day_offset in range(current_page_first_day.daysInMonth()):
            date_to_clear = current_page_first_day.addDays(day_offset)
            day_of_week = date_to_clear.dayOfWeek()
            if day_of_week == Qt.DayOfWeek.Saturday.value or day_of_week == Qt.DayOfWeek.Sunday.value:
                self.calendar_view.setDateTextFormat(date_to_clear, fmt_weekend_base)
            else:
                self.calendar_view.setDateTextFormat(date_to_clear, fmt_default)

        # Сбор количества задач и дат с задачами
        tasks_counts_for_month = {} # {QDate: count}
        task_dates_for_bolding = set()

        for task in self.all_tasks: # self.all_tasks уже загружены и содержат все задачи
            if task.reminder_datetime and task.reminder_datetime.isValid():
                task_date = task.reminder_datetime.date()
                if task_date.year() == year and task_date.month() == month:
                    task_dates_for_bolding.add(task_date)
                    tasks_counts_for_month[task_date] = tasks_counts_for_month.get(task_date, 0) + 1
        
        # Применение жирного шрифта к датам с задачами
        for q_date in task_dates_for_bolding:
            current_format = self.calendar_view.dateTextFormat(q_date)
            current_format.setFontWeight(QFont.Weight.Bold)
            self.calendar_view.setDateTextFormat(q_date, current_format)
            
        # Передача словаря с количеством задач в CustomCalendarWidget
        # Проверка необходима, так как self.calendar_view теперь CustomCalendarWidget
        if hasattr(self.calendar_view, 'set_task_counts_for_month'):
            self.calendar_view.set_task_counts_for_month(tasks_counts_for_month)
        else: # Резервный вариант, если используется стандартный QCalendarWidget
            self.calendar_view.updateCells()


    ### --- Метод: _update_daily_task_list --- Обновляет список задач на выбранный день.
    def _update_daily_task_list(self, selected_date: QDate):
        self.daily_task_list_widget.clear()
        tasks_on_day = [
            task for task in self.all_tasks
            if task.reminder_datetime and task.reminder_datetime.isValid() and \
               task.reminder_datetime.date() == selected_date
        ]
        tasks_on_day.sort(key=lambda t: (
            t.completed, t.priority,
            t.reminder_datetime if t.reminder_datetime and t.reminder_datetime.isValid() else QDateTime()
        ))
        if not tasks_on_day:
            item = QListWidgetItem(f"Задач на {selected_date.toString('dd.MM.yyyy')} нет.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = item.font(); font.setItalic(True); item.setFont(font)
            item.setForeground(Qt.GlobalColor.gray)
            self.daily_task_list_widget.addItem(item)
            return
        for task in tasks_on_day:
            text_parts = []
            if task.reminder_datetime and task.reminder_datetime.isValid():
                 text_parts.append(f"[{task.reminder_datetime.toString('HH:mm')}]")
            text_parts.append(task.text)
            if task.priority != 4:
                 text_parts.append(f"[{PRIORITIES[task.priority]['name'].split(' ')[0]}]")
            list_item = QListWidgetItem(" ".join(text_parts))
            list_item.setData(Qt.ItemDataRole.UserRole, task.id)
            font = list_item.font()
            if task.completed:
                font.setStrikeOut(True)
                list_item.setForeground(Qt.GlobalColor.darkGray)
            else:
                font.setStrikeOut(False)
                list_item.setForeground(PRIORITIES.get(task.priority, {}).get("color", Qt.GlobalColor.black))
            list_item.setFont(font)
            self.daily_task_list_widget.addItem(list_item)

    ### --- Метод: init_db --- Инициализирует базу данных.
    def init_db(self):
        try:
            db_dir = os.path.dirname(DATABASE_NAME)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            self.db_conn = sqlite3.connect(DATABASE_NAME)
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, text TEXT NOT NULL, priority INTEGER,
                    reminder_datetime TEXT, completed INTEGER DEFAULT 0,
                    reminder_shown INTEGER DEFAULT 0 )
            ''')
            self.db_conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка Базы Данных", f"Не удалось инициализировать БД: {e}")
            self.db_conn = None

    ### --- Метод: _load_all_tasks_from_db --- Загружает все задачи из БД.
    def _load_all_tasks_from_db(self):
        if not self.db_conn: return
        self.all_tasks.clear()
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, text, priority, reminder_datetime, completed, reminder_shown FROM tasks")
            for row in cursor.fetchall():
                id_str, text, priority, dt_str, completed, shown = row
                reminder_dt = None
                if dt_str:
                    temp_dt = QDateTime.fromString(dt_str, Qt.DateFormat.ISODateWithMs)
                    if not temp_dt.isValid(): temp_dt = QDateTime.fromString(dt_str, Qt.DateFormat.ISODate)
                    if temp_dt.isValid(): reminder_dt = temp_dt
                self.all_tasks.append(Task(text, priority, reminder_dt, bool(completed), id_str, bool(shown)))
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Ошибка Базы Данных", f"Не удалось загрузить задачи: {e}")

    ### --- Метод: _refresh_calendar_and_list --- Обновляет календарь и список задач.
    def _refresh_calendar_and_list(self):
        self._load_all_tasks_from_db()
        self._fetch_tasks_for_current_month_and_mark_calendar() # Обновит и счетчики, и выделение
        self._update_daily_task_list(self.calendar_view.selectedDate())

    ### --- Метод: save_task_to_db --- Сохраняет задачу в БД.
    def save_task_to_db(self, task: Task) -> bool:
        if not self.db_conn: return False
        dt_str = task.reminder_datetime.toString(Qt.DateFormat.ISODateWithMs) if task.reminder_datetime and task.reminder_datetime.isValid() else None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                           (task.id, task.text, task.priority, dt_str, int(task.completed), int(task.reminder_shown)))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка БД", f"Сохранение задачи: {e}"); return False

    ### --- Метод: update_task_in_db --- Обновляет задачу в БД.
    def update_task_in_db(self, task: Task) -> bool:
        if not self.db_conn: return False
        dt_str = task.reminder_datetime.toString(Qt.DateFormat.ISODateWithMs) if task.reminder_datetime and task.reminder_datetime.isValid() else None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""UPDATE tasks SET text=?, priority=?, reminder_datetime=?,
                              completed=?, reminder_shown=? WHERE id=?""",
                           (task.text, task.priority, dt_str, int(task.completed), int(task.reminder_shown), task.id))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка БД", f"Обновление задачи: {e}"); return False

    ### --- Метод: delete_task_from_db --- Удаляет задачу из БД.
    def delete_task_from_db(self, task_id: str) -> bool:
        if not self.db_conn: return False
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            self.db_conn.commit()
            return True
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка БД", f"Удаление задачи: {e}"); return False

    ### --- Метод: _open_add_task_dialog_calendar --- Открывает диалог добавления задачи через календарь.
    def _open_add_task_dialog_calendar(self):
        selected_date = self.calendar_view.selectedDate()
        if not selected_date.isValid(): selected_date = QDate.currentDate()
        dialog = EditTaskDialog(parent=self, default_date=selected_date)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if task_data:
                text, priority, reminder_dt = task_data
                new_task = Task(text, priority, reminder_dt)
                if self.save_task_to_db(new_task):
                    self._refresh_calendar_and_list()

    ### --- Метод: edit_selected_daily_task --- Редактирует задачу по двойному клику в списке.
    def edit_selected_daily_task(self, item: QListWidgetItem):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id: self.edit_task_by_id(task_id)

    ### --- Метод: edit_task_by_id --- Открывает диалог редактирования задачи по ID.
    def edit_task_by_id(self, task_id: str):
        task_to_edit = next((t for t in self.all_tasks if t.id == task_id), None)
        if not task_to_edit: return
        dialog = EditTaskDialog(task_to_edit, self)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if task_data:
                text, priority, reminder_dt = task_data
                if task_to_edit.reminder_datetime != reminder_dt:
                    task_to_edit.reminder_shown = False
                task_to_edit.text, task_to_edit.priority, task_to_edit.reminder_datetime = text, priority, reminder_dt
                if self.update_task_in_db(task_to_edit):
                    self._refresh_calendar_and_list()

    ### --- Метод: show_daily_task_context_menu --- Отображает контекстное меню для задач в списке.
    def show_daily_task_context_menu(self, position: QPoint):
        selected_item = self.daily_task_list_widget.itemAt(position)
        if not selected_item: return
        task_id = selected_item.data(Qt.ItemDataRole.UserRole)
        if not task_id: return
        task = next((t for t in self.all_tasks if t.id == task_id), None)
        if not task: return
        menu = QMenu()
        menu.addAction("Редактировать", lambda: self.edit_task_by_id(task_id))
        toggle_text = "Снять отметку о выполнении" if task.completed else "Отметить как выполненную"
        menu.addAction(toggle_text, lambda: self.toggle_task_completion(task_id))
        if not task.completed and task.reminder_datetime and task.reminder_datetime.isValid() and task.reminder_shown:
            menu.addAction("Сбросить показанное напоминание", lambda: self.reset_reminder_shown_status(task_id))
        menu.addAction("Удалить", lambda: self.confirm_delete_task(task_id))
        menu.exec(self.daily_task_list_widget.mapToGlobal(position))

    ### --- Метод: reset_reminder_shown_status --- Сбрасывает флаг "напоминание показано".
    def reset_reminder_shown_status(self, task_id: str):
        task = next((t for t in self.all_tasks if t.id == task_id), None)
        if task:
            task.reminder_shown = False
            if self.update_task_in_db(task):
                QMessageBox.information(self, "Напоминание сброшено", f"Напоминание для задачи '{task.text[:30]}...' будет показано снова, если актуально.")
                self._refresh_calendar_and_list()

    ### --- Метод: toggle_task_completion --- Переключает статус выполнения задачи.
    def toggle_task_completion(self, task_id: str):
        task = next((t for t in self.all_tasks if t.id == task_id), None)
        if task:
            task.completed = not task.completed
            if not task.completed and task.reminder_datetime and task.reminder_datetime.isValid() and \
               task.reminder_datetime <= QDateTime.currentDateTime() and task.reminder_shown:
                task.reminder_shown = False
            if self.update_task_in_db(task):
                self._refresh_calendar_and_list()

    ### --- Метод: confirm_delete_task --- Запрашивает подтверждение удаления задачи.
    def confirm_delete_task(self, task_id: str):
        task = next((t for t in self.all_tasks if t.id == task_id), None)
        if not task: return
        if QMessageBox.question(self, "Удалить задачу", f"Удалить задачу:\n'{task.text}'?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if self.delete_task_from_db(task_id):
                self._refresh_calendar_and_list()

    ### --- Метод: check_reminders --- Проверяет и отображает напоминания.
    def check_reminders(self):
        now = QDateTime.currentDateTime()
        tasks_to_update_db_for = []
        reminders_to_show_ui = []
        for task in self.all_tasks:
            if task.reminder_datetime and task.reminder_datetime.isValid() and \
               not task.completed and not task.reminder_shown and task.reminder_datetime <= now:
                reminders_to_show_ui.append(task)
                task.reminder_shown = True
                tasks_to_update_db_for.append(task)
        for t in reminders_to_show_ui:
             QMessageBox.information(self, "Напоминание!",
                                    f"Пора выполнить задачу:\n\n{t.text}\n\n"
                                    f"Приоритет: {PRIORITIES[t.priority]['name']}")
        if tasks_to_update_db_for and self.db_conn:
            try:
                cursor = self.db_conn.cursor()
                updates = [(int(t.reminder_shown), t.id) for t in tasks_to_update_db_for]
                cursor.executemany("UPDATE tasks SET reminder_shown = ? WHERE id = ?", updates)
                self.db_conn.commit()
                if any(t.reminder_datetime.date() == self.calendar_view.selectedDate() for t in tasks_to_update_db_for):
                    self._update_daily_task_list(self.calendar_view.selectedDate())
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Ошибка БД", f"Обновление статуса напоминания: {e}")

    ### --- Метод: close_db --- Закрывает соединение с БД.
    def close_db(self):
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None


### КЛАСС: CombinedApp - Главное окно приложения.
class CombinedApp(QMainWindow):
    ### --- Метод: __init__ --- Инициализирует главное окно.
    def __init__(self):
        super().__init__()
        self.setWindowTitle(COMBINED_APP_NAME)
        self.setGeometry(100, 100, 1000, 750)
        QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
        self._setup_toolbar()
        self._setup_tabs()
        self.update_window_title()

    ### --- Метод: _setup_toolbar --- Создает панель инструментов.
    def _setup_toolbar(self):
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setIconSize(QSize(16,16))
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.main_toolbar) # MOVED TOOLBAR TO BOTTOM
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_toolbar.addWidget(spacer)
        about_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        about_action = QAction(about_icon, "", self)
        about_action.setToolTip("О программе")
        about_action.triggered.connect(self.show_about_dialog)
        self.main_toolbar.addAction(about_action)

    ### --- Метод: _setup_tabs --- Создает и заполняет виджет вкладок.
    def _setup_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.note_widget_instance = NoteWidget(self)
        self.calendar_widget_instance = CalendarWidget(self)
        self.tab_widget.addTab(self.note_widget_instance, "Заметки")
        self.tab_widget.addTab(self.calendar_widget_instance, "Календарь")
        self.tab_widget.currentChanged.connect(self.update_window_title)

    ### --- Метод: show_about_dialog --- Отображает диалог "О программе".
    def show_about_dialog(self):
        info = ABOUT_INFO
        QMessageBox.about(self, f"О программе {info['program_name']}",
                          f"<b>{info['program_name']}</b><br>"
                          f"Версия: {info['version']}<br><br>"
                          f"<b>Авторы:</b><br>{info['authors']}<br><br>"
                          f"<b>Описание:</b><br>{info['description']}<br><br>"
                          f"{info['copyright']}")

    ### --- Метод: update_window_title --- Обновляет заголовок окна.
    def update_window_title(self):
        current_tab_index = self.tab_widget.currentIndex()
        title_parts = [COMBINED_APP_NAME]
        if current_tab_index == 0:
            if self.note_widget_instance.current_file_path:
                file_name = QFileInfo(self.note_widget_instance.current_file_path).baseName()
                unsaved_marker = "*" if self.note_widget_instance.unsaved_changes else ""
                title_parts = [f"{file_name}{unsaved_marker}", APP_NAME_NOTES]
            else:
                title_parts = [APP_NAME_NOTES]
        elif current_tab_index == 1:
            title_parts = [APP_NAME_CALENDAR]
        self.setWindowTitle(" - ".join(title_parts))

    ### --- Метод: closeEvent --- Обрабатывает событие закрытия приложения.
    def closeEvent(self, event):
        if self.note_widget_instance.unsaved_changes:
            reply = QMessageBox.question(self, 'Несохраненные изменения',
                                         "В текущей заметке есть несохраненные изменения. Сохранить перед выходом?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.note_widget_instance.save_note()
                if self.note_widget_instance.unsaved_changes:
                    event.ignore(); return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore(); return
        self.calendar_widget_instance.close_db()
        super().closeEvent(event)


### --- Запуск основного приложения --- ###
if __name__ == '__main__':
    app = QApplication(sys.argv)
    dark_stylesheet = """
    QWidget {
        background-color: #202020; 
        color: #C0C0C0; 
        selection-background-color: #4A90D9; 
        selection-color: #FFFFFF; 
    }
    QMainWindow { background-color: #202020; }
    QTabWidget::pane { border: 1px solid #3A3A3A; }
    QTabBar::tab {
        background-color: #282828; color: #A0A0A0; 
        border: 1px solid #3A3A3A; border-bottom: none; 
        padding: 8px 15px; margin-right: 2px; 
        border-top-left-radius: 4px; border-top-right-radius: 4px; 
    }
    QTabBar::tab:selected { background-color: #202020; color: #E0E0E0; }
    QTabBar::tab:hover { background-color: #333333; }
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
    QComboBox {
        background-color: #1A1A1A; color: #D4D4D4;
        border: 1px solid #3A3A3A; padding: 3px 5px;
        selection-background-color: #4A90D9; min-height: 20px;
    }
    QComboBox::drop-down { border: none; background-color: #333333; }
    QComboBox QAbstractItemView {
        background-color: #1A1A1A; border: 1px solid #3A3A3A;
        selection-background-color: #4A90D9; color: #D4D4D4;
    }
    QDateTimeEdit {
        background-color: #1A1A1A; color: #D4D4D4;
        border: 1px solid #3A3A3A; padding: 3px;
    }
    QDateTimeEdit::up-button, QDateTimeEdit::down-button { width: 16px; }
    QCheckBox::indicator { width: 13px; height: 13px; }
    QToolBar {
        background-color: #202020; 
        border-top: 1px solid #3A3A3A; /* CHANGED border-bottom to border-top */
        padding: 2px; spacing: 3px; 
    }
    QToolBar QToolButton {
        background-color: transparent; color: #E0E0E0;
        border: none; padding: 4px; margin: 1px; border-radius: 3px;
    }
    QToolBar QToolButton:hover { background-color: #383838; }
    QToolBar QToolButton:pressed { background-color: #4A90D9; color: #FFFFFF; }

    QCalendarWidget QWidget#qt_calendar_calendarview { 
        alternate-background-color: #2A2A2A; 
    }
    QCalendarWidget QAbstractItemView:enabled { 
        color: #C0C0C0; 
        selection-background-color: #4A90D9; 
        selection-color: #FFFFFF; 
    }
    QCalendarWidget QAbstractItemView:disabled { 
        color: #606060;
    }
    QCalendarWidget QTableView QHeaderView::section {
        background-color: #252525; 
        color: #A0A0A0;            
        padding: 5px 0; border: none; font-weight: normal; 
    }
    """
    app.setStyleSheet(dark_stylesheet)

    from pathlib import Path
    script_dir = Path(__file__).resolve().parent
    app_icon_path = script_dir / "icons" / "app_icon.png"
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))
    else:
        print(f"Внимание: Иконка приложения не найдена по пути {app_icon_path}")

    app.setStyle("Fusion")

    main_win = CombinedApp()
    main_win.show()
    sys.exit(app.exec())
