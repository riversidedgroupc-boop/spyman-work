"""Dialog for creating or editing a product specification."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QDialogButtonBox,
    QMessageBox,
    QLabel,
)

from core.project import list_projects
from desktop_app.i18n import tr, bind

VALID_MATERIALS = [
    "铜",
    "铜合金",
    "铝",
    "铝合金",
    "不锈钢",
    "碳钢",
    "钛合金",
    "塑料",
    "复合材料",
    "其他",
]
VALID_GEOMETRIES = ["管", "棒", "线", "板", "带", "扁管", "异形件", "其他"]


class CreateProductSpecDialog(QDialog):
    def __init__(self, parent=None, project_id: str = "", edit_data: dict | None = None) -> None:
        super().__init__(parent)
        self._project_id = project_id
        self._edit_data = edit_data
        bind(self, "spec.title_edit" if edit_data else "spec.title_new", setter="setWindowTitle")
        self.setMinimumWidth(450)
        self._build_ui()
        if edit_data:
            self._populate(edit_data)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Project selector (for new specs — pick which project this belongs to)
        self._project_combo = QComboBox()
        projects = list_projects()
        for p in projects:
            self._project_combo.addItem(p.project_name, p.project_id)
        if self._project_id:
            idx = self._project_combo.findData(self._project_id)
            if idx >= 0:
                self._project_combo.setCurrentIndex(idx)
        elif projects:
            self._project_combo.setCurrentIndex(0)
        self._project_combo.setVisible(not self._edit_data and len(projects) > 1)
        if not self._edit_data:
            project_label = QLabel()
            bind(project_label, "selector.project")
            form.addRow(project_label, self._project_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("spec.name_placeholder"))
        name_label = QLabel()
        bind(name_label, "spec.name")
        form.addRow(name_label, self._name_edit)

        self._material_combo = QComboBox()
        self._material_combo.addItems(VALID_MATERIALS)
        material_label = QLabel()
        bind(material_label, "spec.material")
        form.addRow(material_label, self._material_combo)

        self._geometry_combo = QComboBox()
        self._geometry_combo.addItems(VALID_GEOMETRIES)
        geometry_label = QLabel()
        bind(geometry_label, "spec.geometry")
        form.addRow(geometry_label, self._geometry_combo)

        self._surface_edit = QLineEdit()
        self._surface_edit.setPlaceholderText(tr("spec.surface_type"))
        surface_label = QLabel()
        bind(surface_label, "spec.surface_type")
        form.addRow(surface_label, self._surface_edit)

        self._min_speed = QDoubleSpinBox()
        self._min_speed.setRange(0, 200)
        self._min_speed.setValue(10.0)
        self._min_speed.setSuffix(" m/min")
        min_speed_label = QLabel()
        bind(min_speed_label, "spec.min_speed")
        form.addRow(min_speed_label, self._min_speed)

        self._max_speed = QDoubleSpinBox()
        self._max_speed.setRange(0, 200)
        self._max_speed.setValue(200.0)
        self._max_speed.setSuffix(" m/min")
        max_speed_label = QLabel()
        bind(max_speed_label, "spec.max_speed")
        form.addRow(max_speed_label, self._max_speed)

        self._target_speed = QDoubleSpinBox()
        self._target_speed.setRange(0, 200)
        self._target_speed.setValue(80.0)
        self._target_speed.setSuffix(" m/min")
        target_speed_label = QLabel()
        bind(target_speed_label, "spec.target_speed")
        form.addRow(target_speed_label, self._target_speed)

        self._camera_count = QSpinBox()
        self._camera_count.setRange(1, 6)
        self._camera_count.setValue(3)
        camera_label = QLabel()
        bind(camera_label, "spec.camera_count")
        form.addRow(camera_label, self._camera_count)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText(tr("app.notes"))
        notes_label = QLabel()
        bind(notes_label, "app.notes")
        form.addRow(notes_label, self._notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, data: dict) -> None:
        self._name_edit.setText(data.get("product_name", ""))
        idx = self._material_combo.findText(data.get("material", ""))
        if idx >= 0:
            self._material_combo.setCurrentIndex(idx)
        idx = self._geometry_combo.findText(data.get("geometry_type", ""))
        if idx >= 0:
            self._geometry_combo.setCurrentIndex(idx)
        self._surface_edit.setText(data.get("surface_type", ""))
        self._min_speed.setValue(data.get("line_speed_min_mpm", 10.0))
        self._max_speed.setValue(data.get("line_speed_max_mpm", 200.0))
        self._target_speed.setValue(data.get("target_speed_mpm", 80.0))
        self._camera_count.setValue(data.get("camera_count", 3))
        self._notes_edit.setText(data.get("notes", ""))

    def _validate_and_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("spec.name_required"))
            return
        if self._min_speed.value() > self._max_speed.value():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("spec.speed_range_invalid"))
            return
        target = self._target_speed.value()
        if target < self._min_speed.value() or target > self._max_speed.value():
            QMessageBox.warning(self, tr("app.validation_failed"), tr("spec.target_speed_invalid"))
            return
        self.accept()

    @property
    def project_id(self) -> str:
        if self._edit_data:
            return self._project_id
        return self._project_combo.currentData() or self._project_id

    def get_data(self) -> dict:
        return {
            "product_name": self._name_edit.text().strip(),
            "material": self._material_combo.currentText(),
            "geometry_type": self._geometry_combo.currentText(),
            "surface_type": self._surface_edit.text().strip(),
            "line_speed_min_mpm": self._min_speed.value(),
            "line_speed_max_mpm": self._max_speed.value(),
            "target_speed_mpm": self._target_speed.value(),
            "camera_count": self._camera_count.value(),
            "notes": self._notes_edit.text().strip() or None,
        }
