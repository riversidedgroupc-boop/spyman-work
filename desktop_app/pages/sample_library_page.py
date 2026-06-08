"""Sample library page — cross-project historical sample browse and provenance tracking."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QLabel,
    QFileDialog,
    QMessageBox,
)

from core.sample_library import (
    list_entries,
    search_samples,
    SampleSearchFilter,
    SOURCE_KIND_CURRENT,
    SOURCE_KIND_IMPORT,
    SOURCE_KIND_REFERENCE,
    get_source_kind_counts,
    import_samples,
    reference_samples,
)
from desktop_app.app_context import AppContext
from desktop_app.i18n import tr, I18nManager
from desktop_app.theme_manager import ThemeManager


class SampleLibraryPage(QWidget):
    """Browse historical samples with provenance tracking."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = AppContext.instance()
        self._build_ui()
        self._ctx.project_changed.connect(self.refresh)
        I18nManager.instance().language_changed.connect(self._on_lang_changed)
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Search bar
        search_w = QWidget()
        search_layout = QHBoxLayout(search_w)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("sample_library.search_placeholder"))
        self._search_edit.setMinimumWidth(180)
        search_layout.addWidget(self._search_edit)

        self._source_filter = QComboBox()
        self._source_filter.addItem(tr("app.all"), "")
        self._source_filter.addItem(tr("sample_library.source_current"), SOURCE_KIND_CURRENT)
        self._source_filter.addItem(tr("sample_library.source_import"), SOURCE_KIND_IMPORT)
        self._source_filter.addItem(tr("sample_library.source_reference"), SOURCE_KIND_REFERENCE)
        search_layout.addWidget(self._source_filter)

        search_btn = QPushButton(tr("app.refresh"))
        search_btn.clicked.connect(self.refresh)
        search_layout.addWidget(search_btn)

        self._import_btn = QPushButton(tr("sample_library.import_selected"))
        self._import_btn.clicked.connect(self._import_selected)
        search_layout.addWidget(self._import_btn)

        self._reference_btn = QPushButton(tr("sample_library.reference_selected"))
        self._reference_btn.clicked.connect(self._reference_selected)
        search_layout.addWidget(self._reference_btn)

        search_layout.addStretch()
        layout.addWidget(search_w)

        # Source counts
        self._counts_label = QLabel()
        self._counts_label.setStyleSheet(f"color: {ThemeManager.current().TEXT_SECONDARY}; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._counts_label)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            [
                tr("sample_library.col_image"),
                tr("sample_library.col_label"),
                tr("sample_library.col_source"),
                tr("sample_library.col_source_project"),
                tr("sample_library.col_review"),
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._table.setRowCount(0)
        project_id = self._ctx.current_project_id

        if not project_id:
            self._counts_label.setText(tr("app.select_project_first"))
            return

        source_kind = self._source_filter.currentData() or ""
        label_filter = self._search_edit.text().strip()

        if label_filter or source_kind:
            filt = SampleSearchFilter(
                label=label_filter,
                source_kind=source_kind,
                exclude_project_id="",
            )
            entries = search_samples(filt)
        else:
            entries = list_entries(project_id=project_id)

        # Source counts
        try:
            counts = get_source_kind_counts(project_id)
            self._counts_label.setText(
                tr(
                    "sample_library.counts",
                    current=counts.get(SOURCE_KIND_CURRENT, 0),
                    imported=counts.get(SOURCE_KIND_IMPORT, 0),
                    referenced=counts.get(SOURCE_KIND_REFERENCE, 0),
                )
            )
        except Exception:
            self._counts_label.setText(f"{len(entries)} {tr('sample_library.entries_found')}")

        source_map = {
            SOURCE_KIND_CURRENT: tr("sample_library.source_current"),
            SOURCE_KIND_IMPORT: tr("sample_library.source_import"),
            SOURCE_KIND_REFERENCE: tr("sample_library.source_reference"),
        }

        self._table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            img_name = (
                entry.current_image_path.rsplit("/", 1)[-1] if entry.current_image_path else "—"
            )
            self._table.setItem(i, 0, QTableWidgetItem(img_name))
            if entry.current_image_path:
                self._table.item(i, 0).setToolTip(entry.current_image_path)
            self._table.item(i, 0).setData(Qt.ItemDataRole.UserRole, entry.entry_id)
            self._table.setItem(i, 1, QTableWidgetItem(entry.current_label or "—"))
            self._table.setItem(
                i, 2, QTableWidgetItem(source_map.get(entry.source_kind, entry.source_kind))
            )
            self._table.setItem(i, 3, QTableWidgetItem(entry.source_project_id or "—"))
            self._table.setItem(i, 4, QTableWidgetItem(entry.human_review_status or "—"))

    def _on_lang_changed(self, _lang: str) -> None:
        self._import_btn.setText(tr("sample_library.import_selected"))
        self._reference_btn.setText(tr("sample_library.reference_selected"))
        self.refresh()

    def _selected_entry_ids(self) -> list[str]:
        ids: list[str] = []
        for idx in self._table.selectionModel().selectedRows():
            item = self._table.item(idx.row(), 0)
            entry_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
            if entry_id:
                ids.append(str(entry_id))
        return ids

    def _import_selected(self) -> None:
        project_id = self._ctx.current_project_id
        entry_ids = self._selected_entry_ids()
        if not project_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project_first"))
            return
        if not entry_ids:
            QMessageBox.information(self, tr("app.tip"), tr("sample_library.select_entries"))
            return
        target_dir = QFileDialog.getExistingDirectory(self, tr("sample_library.select_target_dir"))
        if not target_dir:
            return
        result = import_samples(
            entry_ids,
            project_id,
            target_dir,
            import_reason="Imported from sample library",
        )
        QMessageBox.information(
            self,
            tr("app.tip"),
            tr(
                "sample_library.import_result",
                imported=result.imported_count,
                skipped=result.skipped_count,
            ),
        )
        self.refresh()

    def _reference_selected(self) -> None:
        project_id = self._ctx.current_project_id
        entry_ids = self._selected_entry_ids()
        if not project_id:
            QMessageBox.information(self, tr("app.tip"), tr("app.select_project_first"))
            return
        if not entry_ids:
            QMessageBox.information(self, tr("app.tip"), tr("sample_library.select_entries"))
            return
        result = reference_samples(
            entry_ids,
            project_id,
            import_reason="Referenced from sample library",
        )
        QMessageBox.information(
            self,
            tr("app.tip"),
            tr(
                "sample_library.reference_result",
                referenced=result.referenced_count,
                skipped=result.skipped_count,
            ),
        )
        self.refresh()

    def _on_theme_changed(self) -> None:
        """Re-apply inline styles after theme toggle."""
        c = ThemeManager.current()
        self._counts_label.setStyleSheet(f"color: {c.TEXT_SECONDARY}; font-size: 11px;")

