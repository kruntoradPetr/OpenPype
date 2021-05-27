from Qt import QtWidgets, QtGui, QtCore
from .categories import (
    CategoryState,
    SystemWidget,
    ProjectWidget
)
from .widgets import ShadowWidget
from . import style

from openpype.tools.settings import (
    is_password_required,
    PasswordDialog
)


class MainWidget(QtWidgets.QWidget):
    widget_width = 1000
    widget_height = 600

    def __init__(self, user_role, parent=None):
        super(MainWidget, self).__init__(parent)

        self._user_passed = False
        self._reset_on_show = True

        self._password_dialog = None

        self.setObjectName("MainWidget")
        self.setWindowTitle("OpenPype Settings")

        self.resize(self.widget_width, self.widget_height)

        stylesheet = style.load_stylesheet()
        self.setStyleSheet(stylesheet)
        self.setWindowIcon(QtGui.QIcon(style.app_icon_path()))

        header_tab_widget = QtWidgets.QTabWidget(parent=self)

        studio_widget = SystemWidget(user_role, header_tab_widget)
        project_widget = ProjectWidget(user_role, header_tab_widget)

        tab_widgets = [
            studio_widget,
            project_widget
        ]

        header_tab_widget.addTab(studio_widget, "System")
        header_tab_widget.addTab(project_widget, "Project")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        layout.addWidget(header_tab_widget)

        self.setLayout(layout)

        self._shadow_widget = ShadowWidget("Working...", self)
        self._shadow_widget.setVisible(False)

        for tab_widget in tab_widgets:
            tab_widget.saved.connect(self._on_tab_save)
            tab_widget.state_changed.connect(self._on_state_change)
            tab_widget.restart_required_trigger.connect(
                self._on_restart_required
            )

        self.tab_widgets = tab_widgets

    def _on_tab_save(self, source_widget):
        for tab_widget in self.tab_widgets:
            tab_widget.on_saved(source_widget)

    def _on_state_change(self):
        any_working = False
        for widget in self.tab_widgets:
            if widget.state is CategoryState.Working:
                any_working = True
                break

        if (
            (any_working and self._shadow_widget.isVisible())
            or (not any_working and not self._shadow_widget.isVisible())
        ):
            return

        self._shadow_widget.setVisible(any_working)

        # Process events to apply shadow widget visibility
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()

    def showEvent(self, event):
        super(MainWidget, self).showEvent(event)
        if self._reset_on_show:
            self.reset()

    def _show_password_dialog(self):
        if self._password_dialog:
            self._password_dialog.open()

    def _on_password_dialog_close(self, password_passed):
        # Store result for future settings reset
        self._user_passed = password_passed
        # Remove reference to password dialog
        self._password_dialog = None
        if password_passed:
            self.reset()
        else:
            self.close()

    def reset(self):
        if self._password_dialog:
            return

        if not self._user_passed:
            self._user_passed = not is_password_required()

        self._on_state_change()

        if not self._user_passed:
            # Avoid doubled dialog
            dialog = PasswordDialog(self)
            dialog.setModal(True)
            dialog.finished.connect(self._on_password_dialog_close)

            self._password_dialog = dialog

            QtCore.QTimer.singleShot(100, self._show_password_dialog)

            return

        if self._reset_on_show:
            self._reset_on_show = False

        for tab_widget in self.tab_widgets:
            tab_widget.reset()

    def _on_restart_required(self):
        pass
