import json
import os
import re
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QComboBox, QMessageBox, QLineEdit, QWidget
)

from buzz.locale import _

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "settings",
    "renaming_templates",
)


def list_name_map_templates() -> List[str]:
    """Return names (without extension) of saved name map templates"""
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(TEMPLATES_DIR)
        if f.lower().endswith(".json")
    )


def template_path(name: str) -> str:
    return os.path.join(TEMPLATES_DIR, f"{name}.json")


def load_name_map_template(name: str) -> Dict[str, str]:
    """Load a template as {nickname: final_name}"""
    with open(template_path(name), "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): str(v) for k, v in data.get("mappings", {}).items()}


class NameMapDialog(QDialog):
    """Dialog for editing nickname -> final name mapping templates"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(_("Name Map Editor"))
        self.setMinimumSize(500, 450)

        layout = QVBoxLayout(self)

        # Load existing template
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel(_("Template:")))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(200)
        load_layout.addWidget(self.template_combo, 1)
        self.load_btn = QPushButton(_("Load"))
        self.load_btn.clicked.connect(self._load_template)
        load_layout.addWidget(self.load_btn)
        layout.addLayout(load_layout)

        # Mapping table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([_("Nickname"), _("Final Name")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        layout.addWidget(self.table)

        row_layout = QHBoxLayout()
        add_btn = QPushButton(_("Add Row"))
        add_btn.clicked.connect(lambda: self._add_row())
        row_layout.addWidget(add_btn)
        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self._remove_rows)
        row_layout.addWidget(remove_btn)
        clear_btn = QPushButton(_("Clear"))
        clear_btn.clicked.connect(lambda: self.table.setRowCount(0))
        row_layout.addWidget(clear_btn)
        row_layout.addStretch()
        layout.addLayout(row_layout)

        # Save
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel(_("Template name:")))
        self.name_edit = QLineEdit()
        save_layout.addWidget(self.name_edit, 1)
        self.save_btn = QPushButton(_("Save"))
        self.save_btn.clicked.connect(self._save_template)
        save_layout.addWidget(self.save_btn)
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.accept)
        save_layout.addWidget(close_btn)
        layout.addLayout(save_layout)

        self._refresh_templates()
        self._add_row()

    def _refresh_templates(self, select: Optional[str] = None):
        self.template_combo.clear()
        self.template_combo.addItems(list_name_map_templates())
        if select:
            index = self.template_combo.findText(select)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)
        self.load_btn.setEnabled(self.template_combo.count() > 0)

    def _add_row(self, nickname: str = "", final_name: str = ""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(nickname))
        self.table.setItem(row, 1, QTableWidgetItem(final_name))

    def _remove_rows(self):
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _load_template(self):
        name = self.template_combo.currentText()
        if not name:
            return
        try:
            mappings = load_name_map_template(name)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to load template: {}").format(e))
            return
        self.table.setRowCount(0)
        for nickname, final_name in mappings.items():
            self._add_row(nickname, final_name)
        self.name_edit.setText(name)

    def _collect_mappings(self) -> Dict[str, str]:
        mappings: Dict[str, str] = {}
        for row in range(self.table.rowCount()):
            nick_item = self.table.item(row, 0)
            final_item = self.table.item(row, 1)
            nickname = nick_item.text().strip() if nick_item else ""
            final_name = final_item.text().strip() if final_item else ""
            if nickname and final_name:
                mappings[nickname] = final_name
        return mappings

    def _save_template(self):
        name = self.name_edit.text().strip()
        if not name or re.search(r'[\\/:*?"<>|]', name):
            QMessageBox.warning(self, _("Error"), _("Please enter a valid template name"))
            return
        mappings = self._collect_mappings()
        if not mappings:
            QMessageBox.warning(self, _("Error"), _("The table has no complete rows to save"))
            return
        if os.path.exists(template_path(name)):
            answer = QMessageBox.question(
                self, _("Overwrite"), _("Template '{}' already exists. Overwrite?").format(name)
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
            with open(template_path(name), "w", encoding="utf-8") as f:
                json.dump({"mappings": mappings}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to save template: {}").format(e))
            return
        self._refresh_templates(select=name)
