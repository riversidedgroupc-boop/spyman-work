"""Global application context singleton."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppContext(QObject):
    """Singleton holding current customer/project/spec/camera/model selection.

    All pages read from this; ProjectSelector writes to it.
    """

    customer_changed = Signal(str)
    project_changed = Signal(str)
    spec_changed = Signal(str)
    camera_config_changed = Signal(str)
    model_changed = Signal(str)

    _instance: AppContext | None = None

    def __init__(self) -> None:
        if AppContext._instance is not None:
            raise RuntimeError("Use AppContext.instance()")
        super().__init__()
        self._current_customer_id = ""
        self._current_customer_name = ""
        self._current_project_id = ""
        self._current_project_name = ""
        self._current_spec_id = ""
        self._current_spec_name = ""
        self._current_camera_config_id = ""
        self._current_model_id = ""
        AppContext._instance = self

    @classmethod
    def instance(cls) -> AppContext:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def current_customer_id(self) -> str:
        return self._current_customer_id

    @property
    def current_customer_name(self) -> str:
        return self._current_customer_name

    @property
    def current_project_id(self) -> str:
        return self._current_project_id

    @property
    def current_project_name(self) -> str:
        return self._current_project_name

    @property
    def current_spec_id(self) -> str:
        return self._current_spec_id

    @property
    def current_spec_name(self) -> str:
        return self._current_spec_name

    @property
    def current_camera_config_id(self) -> str:
        return self._current_camera_config_id

    @property
    def current_model_id(self) -> str:
        return self._current_model_id

    def set_current_customer(self, customer_id: str, name: str = "") -> None:
        self._current_customer_id = customer_id
        self._current_customer_name = name
        self._clear_dependents()
        self.customer_changed.emit(customer_id)

    def set_current_project(self, project_id: str, name: str = "") -> None:
        self._current_project_id = project_id
        self._current_project_name = name
        self._current_spec_id = ""
        self._current_spec_name = ""
        self._current_camera_config_id = ""
        self.project_changed.emit(project_id)

    def set_current_spec(self, spec_id: str, name: str = "") -> None:
        self._current_spec_id = spec_id
        self._current_spec_name = name
        self.spec_changed.emit(spec_id)

    def set_current_camera_config(self, config_id: str) -> None:
        self._current_camera_config_id = config_id
        self.camera_config_changed.emit(config_id)

    def set_current_model(self, model_id: str) -> None:
        self._current_model_id = model_id
        self.model_changed.emit(model_id)

    def clear_all(self) -> None:
        self._current_customer_id = ""
        self._current_customer_name = ""
        self._clear_dependents()

    def _clear_dependents(self) -> None:
        self._current_project_id = ""
        self._current_project_name = ""
        self._current_spec_id = ""
        self._current_spec_name = ""
        self._current_camera_config_id = ""
        self._current_model_id = ""
