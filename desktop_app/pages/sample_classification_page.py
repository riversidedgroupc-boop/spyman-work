"""Sample classification page: 12-image queue labeling workflow."""

from __future__ import annotations

import os

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QMouseEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.capture_session import (
    add_captured_image,
    get_capture_session,
    get_session_task_type,
    list_captured_images,
    list_capture_sessions,
    session_output_root,
    set_image_classification,
    set_session_task_type,
)
from core.label_policy import is_defect_label, is_review_label
from desktop_app.app_context import AppContext
from desktop_app.display import class_label, session_status_label
from desktop_app.i18n import I18nManager, tr
from desktop_app.label_config import (
    add_label,
    label_color,
    load_label_options,
    move_label,
    remove_label,
    rename_label,
)
from desktop_app.widgets.image_viewer import ImageViewer
from desktop_app.widgets.thumbnail_grid import ThumbnailGrid
from desktop_app.theme_manager import ThemeManager

BATCH_SIZE = 12
IMAGE_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
LABEL_DRAG_MIME = "application/x-copper-label-value"


def batch_start_for_index(index: int, batch_size: int = BATCH_SIZE) -> int:
    return max(0, (index // batch_size) * batch_size)


def next_index_after_label(index: int, total: int) -> int:
    return min(index + 1, max(total - 1, 0))


class DraggableLabelButton(QPushButton):
    dropped_on_label = Signal(str, str)

    def __init__(self, label_value: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._label_value = label_value
        self._drag_start_position: QPoint | None = None
        self.setAcceptDrops(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start_position is None:
            super().mouseMoveEvent(event)
            return
        drag_distance = (event.position().toPoint() - self._drag_start_position).manhattanLength()
        if drag_distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        mime = QMimeData()
        mime.setData(LABEL_DRAG_MIME, self._label_value.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(LABEL_DRAG_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(LABEL_DRAG_MIME):
            return
        source_value = bytes(event.mimeData().data(LABEL_DRAG_MIME)).decode("utf-8")
        if source_value != self._label_value:
            self.dropped_on_label.emit(source_value, self._label_value)
        event.acceptProposedAction()


class SampleClassificationPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._current_session_id = ""
        self._current_index = -1
        self._batch_start = 0
        self._image_paths: list[str] = []
        self._labels: dict[str, str] = {}
        self._cameras: dict[str, str] = {}
        self._label_options = load_label_options()
        self._stat_labels: dict[str, QLabel] = {}
        self._shortcuts: list[QShortcut] = []
        self._build_ui()
        self._install_shortcuts()
        I18nManager.instance().language_changed.connect(self._refresh_text)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel(tr("ui.label_session")))

        self._session_combo = QComboBox()
        self._session_combo.currentIndexChanged.connect(self._on_session_changed)
        top.addWidget(self._session_combo, 1)

        refresh_btn = QPushButton(tr("app.refresh"))
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._refresh_sessions)
        top.addWidget(refresh_btn)

        import_btn = QPushButton(tr("classify.import_folder"))
        import_btn.clicked.connect(self._import_local_folder)
        top.addWidget(import_btn)
        layout.addLayout(top)

        # ── Task type selector ──
        task_row = QHBoxLayout()
        task_row.setSpacing(8)
        task_row.addWidget(QLabel(tr("ui.label_task_type")))
        self._task_type_combo = QComboBox()
        self._task_type_combo.addItem(tr("classify.task_yolo"), "yolo_detection")
        self._task_type_combo.addItem(tr("classify.task_cls"), "image_classification")
        self._task_type_combo.addItem(tr("classify.task_anomaly"), "anomaly_detection")
        self._task_type_combo.currentIndexChanged.connect(self._on_task_type_changed)
        task_row.addWidget(self._task_type_combo)
        task_row.addStretch()
        self._open_bbox_btn = QPushButton(tr("task.open_bbox"))
        self._open_bbox_btn.setObjectName("primaryBtn")
        self._open_bbox_btn.clicked.connect(self._open_bbox_annotation)
        self._open_bbox_btn.hide()
        task_row.addWidget(self._open_bbox_btn)
        layout.addLayout(task_row)

        self._task_hint_label = QLabel("")
        self._task_hint_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._task_hint_label)

        self._current_label = QLabel("")
        self._current_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 13px; padding: 4px 0;")
        layout.addWidget(self._current_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._grid = ThumbnailGrid()
        self._grid.set_label_options(self._label_pairs())
        self._grid.image_selected.connect(self._on_image_selected)
        self._grid.filter_changed.connect(self._render_batch)
        splitter.addWidget(self._grid)

        self._viewer = ImageViewer()
        splitter.addWidget(self._viewer)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 0, 0, 0)

        stats_group = QGroupBox(tr("ui.label_stats"))
        self._stats_grid = QGridLayout(stats_group)
        side_layout.addWidget(stats_group)

        label_group = QGroupBox(tr("ui.label_label_current"))
        self._label_button_layout = QVBoxLayout(label_group)
        side_layout.addWidget(label_group)

        manage_group = QGroupBox(tr("ui.label_defect_settings"))
        manage_layout = QVBoxLayout(manage_group)
        self._new_label_edit = QLineEdit()
        self._new_label_edit.setPlaceholderText(tr("classify.new_label_placeholder"))
        self._new_label_edit.returnPressed.connect(self._add_custom_label)
        manage_layout.addWidget(self._new_label_edit)

        manage_buttons = QHBoxLayout()
        add_btn = QPushButton(tr("ui.btn_add"))
        add_btn.clicked.connect(self._add_custom_label)
        manage_buttons.addWidget(add_btn)
        delete_btn = QPushButton(tr("ui.btn_delete_selected"))
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self._delete_selected_label)
        manage_buttons.addWidget(delete_btn)
        manage_layout.addLayout(manage_buttons)

        self._delete_label_combo = QComboBox()
        self._delete_label_combo.currentIndexChanged.connect(self._sync_selected_label_name)
        manage_layout.addWidget(self._delete_label_combo)

        rename_row = QHBoxLayout()
        self._edit_label_name = QLineEdit()
        self._edit_label_name.setPlaceholderText(tr("classify.edit_label_placeholder"))
        self._edit_label_name.returnPressed.connect(self._rename_selected_label)
        rename_row.addWidget(self._edit_label_name, 1)
        rename_btn = QPushButton(tr("ui.btn_rename"))
        rename_btn.clicked.connect(self._rename_selected_label)
        rename_row.addWidget(rename_btn)
        manage_layout.addLayout(rename_row)
        side_layout.addWidget(manage_group)

        side_layout.addStretch()
        splitter.addWidget(side)

        self._rebuild_stats_and_label_buttons()
        splitter.setSizes([430, 790, 260])
        layout.addWidget(splitter, 1)

        hint = QLabel(tr("ui.hint_shortcuts"))
        hint.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 10px; padding: 2px 5px;")
        layout.addWidget(hint)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _install_shortcuts(self) -> None:
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(str(i)), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda index=i - 1: self._classify_by_index(index))
            self._shortcuts.append(shortcut)
        for key, handler in [
            ("A", lambda: self._navigate(-1)),
            ("D", lambda: self._navigate(1)),
            ("Space", lambda: self._navigate(1)),
            ("Ctrl+S", self._save_to_db),
        ]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _refresh_text(self, lang: str = "") -> None:
        self._refresh_sessions()
        # Update task type combo items for language switch
        self._task_type_combo.setItemText(0, tr("classify.task_yolo"))
        self._task_type_combo.setItemText(1, tr("classify.task_cls"))
        self._task_type_combo.setItemText(2, tr("classify.task_anomaly"))
        # Update task hint
        task_type = self._task_type_combo.currentData()
        if task_type:
            self._update_task_hint(task_type)
        self._update_current_label()
        self._update_stats()

    def _refresh_sessions(self) -> None:
        self._session_combo.blockSignals(True)
        current = self._current_session_id
        self._session_combo.clear()
        self._session_combo.addItem(tr("classify.select_session"), "")
        pid = self._ctx.current_project_id
        if pid:
            for session in list_capture_sessions(pid):
                self._session_combo.addItem(
                    f"{session.session_name} ({session_status_label(session.status)})",
                    session.session_id,
                )
        if current:
            idx = self._session_combo.findData(current)
            if idx >= 0:
                self._session_combo.setCurrentIndex(idx)
        self._session_combo.blockSignals(False)

    def _on_session_changed(self, index: int) -> None:
        session_id = self._session_combo.itemData(index)
        if not session_id:
            return
        self._current_session_id = session_id
        # Load existing task type from session
        task_type = get_session_task_type(session_id) or "image_classification"
        idx = self._task_type_combo.findData(task_type)
        if idx >= 0:
            self._task_type_combo.blockSignals(True)
            self._task_type_combo.setCurrentIndex(idx)
            self._task_type_combo.blockSignals(False)
        self._update_task_hint(task_type)
        self._load_images(session_id)

    def _on_task_type_changed(self, _index: int) -> None:
        task_type = self._task_type_combo.currentData()
        if not task_type or not self._current_session_id:
            return
        set_session_task_type(self._current_session_id, task_type)
        self._update_task_hint(task_type)

    def _update_task_hint(self, task_type: str) -> None:
        hints = {
            "yolo_detection": tr("task.yolo_hint"),
            "image_classification": tr("task.cls_hint"),
            "anomaly_detection": tr("task.anomaly_hint"),
        }
        self._task_hint_label.setText(hints.get(task_type, ""))
        self._open_bbox_btn.setVisible(task_type == "yolo_detection")
        self._update_open_bbox_btn_text()

    def _update_open_bbox_btn_text(self) -> None:
        """Update the bbox button text with pending counts."""
        if not self._image_paths:
            self._open_bbox_btn.setText(tr("bbox.open_bbox"))
            return
        needs_bbox_count = 0
        has_bbox_count = 0
        review_count = 0
        for path in self._image_paths:
            label = self._labels.get(path, "")
            if is_defect_label(label):
                if self._has_bbox_sidecar(path):
                    has_bbox_count += 1
                else:
                    needs_bbox_count += 1
            elif is_review_label(label):
                review_count += 1
        parts: list[str] = []
        if needs_bbox_count:
            parts.append(f"{needs_bbox_count}{tr('ui.label_pending_bbox')}")
        if has_bbox_count:
            parts.append(f"{has_bbox_count}{tr('ui.label_has_bbox')}")
        if review_count:
            parts.append(f"{review_count}{tr('ui.label_pending_review')}")
        if parts:
            self._open_bbox_btn.setText(tr("ui.label_bbox_enter", parts=" / ".join(parts)))
        else:
            self._open_bbox_btn.setText(tr("bbox.open_bbox"))

    @staticmethod
    def _has_bbox_sidecar(image_path: str) -> bool:
        """Check if a YOLO .txt sidecar file exists with at least one bbox."""
        import os as _os

        stem, _ = _os.path.splitext(image_path)
        txt_path = stem + ".txt"
        if not _os.path.isfile(txt_path):
            return False
        try:
            with open(txt_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and len(line.split()) >= 5:
                        return True
        except Exception:
            return False
        return False

    def _open_bbox_annotation(self) -> None:
        """Navigate to the bbox annotation page tab, defaulting to needs_bbox filter."""
        parent = self.window()
        if hasattr(parent, "_sample_review_tabs"):
            parent._sample_review_tabs.setCurrentIndex(1)
        elif hasattr(parent, "_data_tabs"):
            parent._data_tabs.setCurrentIndex(2)
        if hasattr(parent, "_on_page_selected"):
            parent._on_page_selected("sample_review")
        # Set bbox page to "needs_bbox" filter mode
        bbox_page = getattr(parent, "_review_bbox_page", None) or getattr(parent, "_bbox_page", None)
        if bbox_page is not None:
            refresh = getattr(bbox_page, "refresh", None)
            if callable(refresh):
                refresh()
            bbox_page._set_filter("needs_bbox")

    def _load_images(self, session_id: str) -> None:
        session = get_capture_session(session_id)
        if not session:
            return

        paths: list[str] = []
        cameras: dict[str, str] = {}
        labels: dict[str, str] = {}
        output_root = session.output_dir or session_output_root(session.project_id)
        raw_dir = os.path.join(output_root, session_id, "raw")

        if os.path.isdir(raw_dir):
            for cam_dir in sorted(os.listdir(raw_dir)):
                cam_path = os.path.join(raw_dir, cam_dir)
                if not os.path.isdir(cam_path):
                    continue
                for fname in sorted(os.listdir(cam_path)):
                    path = os.path.join(cam_path, fname)
                    if self._is_image_file(path):
                        paths.append(path)
                        cameras[path] = cam_dir

        for image in list_captured_images(session_id):
            image_path = image.get("image_path", "")
            if image_path and os.path.isfile(image_path) and image_path not in paths:
                paths.append(image_path)
            if image_path:
                cameras[image_path] = image.get("camera_id", "")
                label = image.get("classification_label", "")
                if label:
                    labels[image_path] = label

        self._image_paths = paths
        self._cameras = cameras
        self._labels = labels
        self._current_index = 0 if paths else -1
        self._batch_start = 0
        self._show_current_image()
        self._update_stats()

    def _import_local_folder(self) -> None:
        if not self._current_session_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_session"))
            return
        project_id = self._ctx.current_project_id
        if not project_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project"))
            return
        folder = QFileDialog.getExistingDirectory(self, tr("classify.import_folder"))
        if not folder:
            return
        count = 0
        for fname in sorted(os.listdir(folder)):
            path = os.path.join(folder, fname)
            if self._is_image_file(path):
                add_captured_image(
                    self._current_session_id, project_id, path, fname, camera_id="local"
                )
                count += 1
        self._load_images(self._current_session_id)
        QMessageBox.information(
            self, tr("app.completed"), tr("classify.import_complete", count=count)
        )
        self.data_changed.emit()

    def _on_image_selected(self, path: str) -> None:
        if path in self._image_paths:
            self._current_index = self._image_paths.index(path)
            self._show_current_image()

    def _classify_by_index(self, index: int) -> None:
        if index < len(self._label_options):
            self._classify_current(self._label_options[index].value)

    def _classify_current(self, label: str) -> None:
        if not (0 <= self._current_index < len(self._image_paths)):
            return
        path = self._image_paths[self._current_index]
        visible_paths = self._grid.get_visible_paths() if self._grid.has_active_filter() else []
        self._labels[path] = label
        self._save_label_for_path(path, label)
        if visible_paths:
            self._move_to_next_visible_path(path, visible_paths)
        else:
            self._current_index = next_index_after_label(
                self._current_index, len(self._image_paths)
            )
        self._show_current_image()
        self._update_stats()

    def _save_label_for_path(self, path: str, label: str) -> None:
        if not self._current_session_id:
            return
        session = get_capture_session(self._current_session_id)
        project_id = self._ctx.current_project_id or (session.project_id if session else "")
        if not project_id:
            return
        image_id = add_captured_image(
            self._current_session_id,
            project_id,
            path,
            os.path.basename(path),
            camera_id=self._cameras.get(path, ""),
        )
        set_image_classification(image_id, label)
        self.data_changed.emit()

    def _show_current_image(self) -> None:
        if not self._image_paths:
            self._grid.set_images([])
            self._viewer.clear()
            self._update_current_label()
            return
        self._current_index = max(0, min(self._current_index, len(self._image_paths) - 1))
        self._batch_start = batch_start_for_index(self._current_index)
        current_path = self._image_paths[self._current_index]
        self._viewer.load_image(current_path)
        self._render_batch()
        self._update_current_label()

    def _render_batch(self) -> None:
        if not self._image_paths:
            return
        batch = (
            self._image_paths
            if self._grid.has_active_filter()
            else self._image_paths[self._batch_start : self._batch_start + BATCH_SIZE]
        )
        self._grid.set_label_options(self._label_pairs())
        self._grid.set_images(batch, self._cameras, dict(self._labels))
        self._grid.select_path(self._image_paths[self._current_index])

    def _update_current_label(self) -> None:
        if not (0 <= self._current_index < len(self._image_paths)):
            self._current_label.setText(tr("classify.no_images"))
            return
        path = self._image_paths[self._current_index]
        label = self._labels.get(path, "")
        batch_end = min(self._batch_start + BATCH_SIZE, len(self._image_paths))
        self._current_label.setText(
            tr(
                "ui.label_current_fmt",
                current=self._current_index + 1,
                total=len(self._image_paths),
                batch_start=self._batch_start + 1,
                batch_end=batch_end,
                label=class_label(label) if label else tr("classify.unlabeled"),
            )
        )

    def _update_stats(self) -> None:
        counts = {option.value: 0 for option in self._label_options}
        for label in self._labels.values():
            if label in counts:
                counts[label] += 1
        for value, count in counts.items():
            widget = self._stat_labels.get(value)
            if widget:
                widget.setText(str(count))
        self._update_open_bbox_btn_text()

    def _navigate(self, delta: int) -> None:
        if not self._image_paths:
            return
        if self._grid.has_active_filter():
            visible_paths = self._grid.get_visible_paths()
            if visible_paths:
                current_path = self._image_paths[self._current_index]
                if current_path in visible_paths:
                    visible_index = visible_paths.index(current_path)
                    target_index = max(0, min(visible_index + delta, len(visible_paths) - 1))
                else:
                    target_index = 0 if delta >= 0 else len(visible_paths) - 1
                self._current_index = self._image_paths.index(visible_paths[target_index])
                self._show_current_image()
                return
        self._current_index = max(0, min(self._current_index + delta, len(self._image_paths) - 1))
        self._show_current_image()

    def _move_to_next_visible_path(self, current_path: str, visible_paths: list[str]) -> None:
        if current_path not in visible_paths:
            return
        current_visible_index = visible_paths.index(current_path)
        remaining_paths = [path for path in visible_paths if path != current_path]
        if not remaining_paths:
            return
        target_visible_index = min(current_visible_index, len(remaining_paths) - 1)
        self._current_index = self._image_paths.index(remaining_paths[target_visible_index])

    def keyPressEvent(self, event) -> None:
        super().keyPressEvent(event)

    def _save_to_db(self) -> None:
        saved = 0
        for path, label in self._labels.items():
            self._save_label_for_path(path, label)
            saved += 1
        QMessageBox.information(self, tr("app.save"), tr("classify.save_complete", saved=saved))

    def _label_pairs(self) -> list[tuple[str, str]]:
        return [(option.value, option.label) for option in self._label_options]

    def _rebuild_stats_and_label_buttons(self) -> None:
        self._clear_layout(self._stats_grid)
        self._stat_labels.clear()
        for row, option in enumerate(self._label_options):
            name = QLabel(option.label)
            name.setStyleSheet(f"color: {option.color}; font-weight: bold;")
            count = QLabel("0")
            count.setStyleSheet("font-size: 16px;")
            self._stats_grid.addWidget(name, row, 0)
            self._stats_grid.addWidget(count, row, 1)
            self._stat_labels[option.value] = count

        self._clear_layout(self._label_button_layout)
        for idx, option in enumerate(self._label_options[:9], start=1):
            button = DraggableLabelButton(option.value, f"{idx}  {option.label}")
            button.setMinimumHeight(38)
            button.setStyleSheet(
                f"background-color: {label_color(option.value)}; "
                "color: white; font-size: 14px; font-weight: bold; padding: 8px;"
            )
            button.dropped_on_label.connect(self._move_label_before)
            button.clicked.connect(
                lambda checked=False, value=option.value: self._classify_current(value)
            )
            self._label_button_layout.addWidget(button)
        if len(self._label_options) > 9:
            self._label_button_layout.addWidget(QLabel(tr("classify.first_9_hint")))

        self._delete_label_combo.clear()
        for option in self._label_options:
            self._delete_label_combo.addItem(option.label, option.value)
        self._sync_selected_label_name()

    def _add_custom_label(self) -> None:
        text = self._new_label_edit.text().strip()
        if not text:
            return
        add_label(text)
        self._new_label_edit.clear()
        self._reload_label_options()

    def _delete_selected_label(self) -> None:
        value = self._delete_label_combo.currentData()
        if not value:
            return
        remove_label(value)
        self._reload_label_options()

    def _rename_selected_label(self) -> None:
        value = self._delete_label_combo.currentData()
        text = self._edit_label_name.text().strip()
        if not value or not text:
            return
        rename_label(value, text)
        self._reload_label_options()

    def _sync_selected_label_name(self) -> None:
        if not hasattr(self, "_edit_label_name"):
            return
        current_value = self._delete_label_combo.currentData()
        current_label = ""
        for option in self._label_options:
            if option.value == current_value:
                current_label = option.label
                break
        self._edit_label_name.setText(current_label)

    def _move_label_before(self, source_value: str, target_value: str) -> None:
        values = [option.value for option in self._label_options]
        if source_value not in values or target_value not in values or source_value == target_value:
            return
        values.remove(source_value)
        move_label(source_value, values.index(target_value))
        self._reload_label_options()

    def _reload_label_options(self) -> None:
        self._label_options = load_label_options()
        self._rebuild_stats_and_label_buttons()
        if self._image_paths:
            self._render_batch()
        self._update_stats()

    def _is_image_file(self, path: str) -> bool:
        return os.path.isfile(path) and os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_sessions()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._task_hint_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")
        self._current_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 13px;")

