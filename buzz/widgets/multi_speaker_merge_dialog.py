from typing import Optional, List, Tuple
from pathlib import Path
import json
import os
import re
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QSpinBox,
    QDoubleSpinBox, QCheckBox, QComboBox, QMessageBox, QGroupBox,
    QLineEdit, QWidget
)
from platformdirs import user_config_dir

from buzz.locale import _
from buzz.multi_speaker_merge import MultiSpeakerTranscriptionMerger
from buzz.widgets.name_map_dialog import (
    NameMapDialog, list_name_map_templates, load_name_map_template
)


class FileDropTableWidget(QTableWidget):
    """Table that accepts transcription files dropped from the file manager"""

    SUPPORTED_EXTENSIONS = {".srt", ".vtt", ".json", ".txt"}
    files_dropped = pyqtSignal(list)  # list[str]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.DragDropMode.DropOnly)

    def _has_supported_files(self, event) -> bool:
        return event.mimeData().hasUrls()

    def dragEnterEvent(self, event):
        if self._has_supported_files(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._has_supported_files(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    paths.append(str(path))
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class MultiSpeakerMergeDialog(QDialog):
    """Dialog for merging multiple speaker transcription files"""
    
    merge_completed = pyqtSignal(str)  # Emits output file path
    
    # Default settings
    DEFAULT_TIME_DELTA = 2.0
    DEFAULT_CONSOLIDATE = True
    DEFAULT_FIX_OVERLAPPING = True
    DEFAULT_OVERLAP_THRESHOLD = 0.1
    DEFAULT_WPM = 150
    DEFAULT_SPACING = 0.1
    DEFAULT_FORMAT = "txt"
    DEFAULT_TIMESTAMPS = True
    DEFAULT_SPEAKER = True
    DEFAULT_OUTPUT_NAME = "merged_transcription"
    DEFAULT_TRIM_EMPTY = False
    DEFAULT_TRIM_END_ONLY = False
    DEFAULT_TRIM_MIN_DURATION = 0.5
    DEFAULT_TRIM_MAX_FACTOR = 1.5
    DEFAULT_DATE_FORMAT = "Y-M-D"
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle(_("Merge Multi-Speaker Transcriptions"))
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        self.transcription_files: List[Tuple[str, str]] = []
        self._loading = True  # suppress saving until settings are loaded
        
        # Set up config file path
        config_dir = user_config_dir("Buzz")
        os.makedirs(config_dir, exist_ok=True)
        self.config_file = os.path.join(config_dir, "multi_speaker_merge.json")
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(
            _("Add transcription files from different speakers. Each file should "
              "contain timestamps (SRT, VTT, or JSON format). The tool will merge "
              "them chronologically and consolidate consecutive lines from the same speaker.")
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # File list section
        file_group = QGroupBox(_("Transcription Files"))
        file_layout = QVBoxLayout()
        
        # Table for files
        self.file_table = FileDropTableWidget()
        self.file_table.files_dropped.connect(self._add_files)
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels([_("File Path"), _("Speaker Name")])
        self.file_table.horizontalHeader().setStretchLastSection(False)
        self.file_table.horizontalHeader().setDefaultSectionSize(300)
        self.file_table.setColumnWidth(0, 400)
        self.file_table.setColumnWidth(1, 200)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        file_layout.addWidget(self.file_table)
        
        # File control buttons
        file_btn_layout = QHBoxLayout()
        
        self.add_file_btn = QPushButton(_("Add File..."))
        self.add_file_btn.clicked.connect(self._add_file)
        file_btn_layout.addWidget(self.add_file_btn)
        
        self.remove_file_btn = QPushButton(_("Remove Selected"))
        self.remove_file_btn.clicked.connect(self._remove_file)
        self.remove_file_btn.setEnabled(False)
        file_btn_layout.addWidget(self.remove_file_btn)
        
        self.clear_files_btn = QPushButton(_("Clear All"))
        self.clear_files_btn.clicked.connect(self._clear_files)
        self.clear_files_btn.setEnabled(False)
        file_btn_layout.addWidget(self.clear_files_btn)
        
        file_btn_layout.addStretch()
        file_layout.addLayout(file_btn_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Name map (right after the file list)
        name_map_layout = QHBoxLayout()
        self.use_name_map_check = QCheckBox(_("Use name map"))
        self.use_name_map_check.setChecked(True)
        name_map_layout.addWidget(self.use_name_map_check)
        self.name_map_combo = QComboBox()
        self.name_map_combo.setMinimumWidth(180)
        name_map_layout.addWidget(self.name_map_combo)
        self.edit_name_map_btn = QPushButton(_("Edit Name Maps..."))
        self.edit_name_map_btn.clicked.connect(self._open_name_map_editor)
        name_map_layout.addWidget(self.edit_name_map_btn)
        self.update_names_btn = QPushButton(_("Update names"))
        self.update_names_btn.setToolTip(
            _("Apply the selected name map to the speaker names of all listed files")
        )
        self.update_names_btn.clicked.connect(self._update_names)
        name_map_layout.addWidget(self.update_names_btn)
        name_map_layout.addStretch()
        layout.addLayout(name_map_layout)
        self._refresh_name_map_combo()
        self.use_name_map_check.toggled.connect(self.name_map_combo.setEnabled)
        self.name_map_combo.setEnabled(True)
        self.use_name_map_check.toggled.connect(self._save_settings)
        self.name_map_combo.currentTextChanged.connect(self._save_settings)
        
        # Options section
        options_group = QGroupBox(_("Merge Options"))
        options_layout = QVBoxLayout()
        
        # Time delta
        time_delta_layout = QHBoxLayout()
        time_delta_layout.addWidget(QLabel(_("Time delta (seconds):")))
        self.time_delta_spin = QDoubleSpinBox()
        self.time_delta_spin.setRange(0.1, 30.0)
        self.time_delta_spin.setValue(2.0)
        self.time_delta_spin.setSingleStep(0.5)
        self.time_delta_spin.setToolTip(
            _("Maximum pause between segments from the same speaker before creating a line break")
        )
        time_delta_layout.addWidget(self.time_delta_spin)
        time_delta_layout.addStretch()
        options_layout.addLayout(time_delta_layout)
        
        # Consolidate checkbox
        self.consolidate_check = QCheckBox(_("Consolidate consecutive speaker lines"))
        self.consolidate_check.setChecked(True)
        self.consolidate_check.setToolTip(
            _("Merge consecutive segments from the same speaker into single lines")
        )
        options_layout.addWidget(self.consolidate_check)
        
        # Fix overlapping speech checkbox
        self.fix_overlapping_check = QCheckBox(_("Fix overlapping speech"))
        self.fix_overlapping_check.setChecked(True)
        self.fix_overlapping_check.setToolTip(
            _("Intelligently merge segments when speakers talk simultaneously.\nShorter lines (interjections) are placed first, followed by the speaker who started first.")
        )
        options_layout.addWidget(self.fix_overlapping_check)
        
        # Trim empty spaces checkbox
        self.trim_empty_check = QCheckBox(_("Trim empty spaces"))
        self.trim_empty_check.setChecked(self.DEFAULT_TRIM_EMPTY)
        self.trim_empty_check.setToolTip(
            _("Shorten segments whose time span is much longer than their text needs "
              "(e.g. one short word lasting 2-3 seconds).\nApplied before overlap fixing "
              "to avoid false overlaps.")
        )
        options_layout.addWidget(self.trim_empty_check)
        
        # Trim parameters
        trim_params_layout = QHBoxLayout()
        trim_params_layout.setContentsMargins(20, 0, 0, 0)
        self.trim_end_only_check = QCheckBox(_("Cut only end"))
        self.trim_end_only_check.setChecked(self.DEFAULT_TRIM_END_ONLY)
        self.trim_end_only_check.setToolTip(
            _("Always trim the end time only and never move the start time")
        )
        trim_params_layout.addWidget(self.trim_end_only_check)
        
        trim_params_layout.addWidget(QLabel(_("Min duration (s):")))
        self.trim_min_duration_spin = QDoubleSpinBox()
        self.trim_min_duration_spin.setRange(0.1, 5.0)
        self.trim_min_duration_spin.setSingleStep(0.1)
        self.trim_min_duration_spin.setDecimals(2)
        self.trim_min_duration_spin.setValue(self.DEFAULT_TRIM_MIN_DURATION)
        self.trim_min_duration_spin.setToolTip(
            _("Segments shorter than this are never trimmed")
        )
        trim_params_layout.addWidget(self.trim_min_duration_spin)
        
        trim_params_layout.addWidget(QLabel(_("Max factor:")))
        self.trim_max_factor_spin = QDoubleSpinBox()
        self.trim_max_factor_spin.setRange(1.0, 10.0)
        self.trim_max_factor_spin.setSingleStep(0.1)
        self.trim_max_factor_spin.setDecimals(2)
        self.trim_max_factor_spin.setValue(self.DEFAULT_TRIM_MAX_FACTOR)
        self.trim_max_factor_spin.setToolTip(
            _("Allowed duration = estimated speaking duration * this factor.\n"
              "Lower values trim more aggressively.")
        )
        trim_params_layout.addWidget(self.trim_max_factor_spin)
        trim_params_layout.addStretch()
        options_layout.addLayout(trim_params_layout)
        
        self._trim_param_widgets = [
            self.trim_end_only_check, self.trim_min_duration_spin, self.trim_max_factor_spin
        ]
        
        def toggle_trim_params(enabled: bool):
            for widget in self._trim_param_widgets:
                widget.setEnabled(enabled)
        
        self.trim_empty_check.toggled.connect(toggle_trim_params)
        toggle_trim_params(self.trim_empty_check.isChecked())
        
        self.trim_empty_check.toggled.connect(self._save_settings)
        self.trim_end_only_check.toggled.connect(self._save_settings)
        self.trim_min_duration_spin.valueChanged.connect(self._save_settings)
        self.trim_max_factor_spin.valueChanged.connect(self._save_settings)
        
        # Overlapping speech parameters (sub-options)
        overlap_params_group = QGroupBox(_("Overlapping Speech Parameters"))
        overlap_params_layout = QVBoxLayout()
        
        # Overlap threshold
        overlap_threshold_layout = QHBoxLayout()
        overlap_threshold_layout.addWidget(QLabel(_("Overlap threshold (seconds):")))
        self.overlap_threshold_spin = QDoubleSpinBox()
        self.overlap_threshold_spin.setRange(0.01, 5.0)
        self.overlap_threshold_spin.setValue(0.1)
        self.overlap_threshold_spin.setSingleStep(0.05)
        self.overlap_threshold_spin.setDecimals(2)
        self.overlap_threshold_spin.setToolTip(
            _("Maximum time gap between segments to consider as overlapping speech.\nLower values detect tighter overlaps. Try 0.1-0.3 seconds.")
        )
        overlap_threshold_layout.addWidget(self.overlap_threshold_spin)
        overlap_threshold_layout.addStretch()
        overlap_params_layout.addLayout(overlap_threshold_layout)
        
        # Duration estimation WPM
        wpm_layout = QHBoxLayout()
        wpm_layout.addWidget(QLabel(_("Speaking rate (words/min):")))
        self.wpm_spin = QSpinBox()
        self.wpm_spin.setRange(50, 300)
        self.wpm_spin.setValue(150)
        self.wpm_spin.setSingleStep(10)
        self.wpm_spin.setToolTip(
            _("Estimated speaking rate for duration calculation when consolidating overlaps.\nTypical range: 120-180 words per minute.")
        )
        wpm_layout.addWidget(self.wpm_spin)
        wpm_layout.addStretch()
        overlap_params_layout.addLayout(wpm_layout)
        
        # Sequential spacing
        spacing_layout = QHBoxLayout()
        spacing_layout.addWidget(QLabel(_("Gap between speakers (seconds):")))
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(0.0, 2.0)
        self.spacing_spin.setValue(0.1)
        self.spacing_spin.setSingleStep(0.05)
        self.spacing_spin.setDecimals(2)
        self.spacing_spin.setToolTip(
            _("Time gap to insert between consolidated speaker segments.\nTypical: 0.05-0.2 seconds.")
        )
        spacing_layout.addWidget(self.spacing_spin)
        spacing_layout.addStretch()
        overlap_params_layout.addLayout(spacing_layout)
        
        overlap_params_group.setLayout(overlap_params_layout)
        options_layout.addWidget(overlap_params_group)
        
        # Enable/disable overlap parameters based on checkbox
        def toggle_overlap_params():
            enabled = self.fix_overlapping_check.isChecked()
            overlap_params_group.setEnabled(enabled)
        
        self.fix_overlapping_check.toggled.connect(toggle_overlap_params)
        toggle_overlap_params()  # Set initial state
        
        # Output format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel(_("Output format:")))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["txt", "srt", "json"])
        self.format_combo.setCurrentText("txt")
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        options_layout.addLayout(format_layout)
        
        # Text output options
        self.timestamps_check = QCheckBox(_("Include timestamps in text output"))
        self.timestamps_check.setChecked(True)
        options_layout.addWidget(self.timestamps_check)
        
        self.speaker_check = QCheckBox(_("Include speaker labels in text output"))
        self.speaker_check.setChecked(True)
        options_layout.addWidget(self.speaker_check)
        
        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        self.reset_btn = QPushButton(_("Reset to Defaults"))
        self.reset_btn.clicked.connect(self._reset_settings)
        reset_layout.addWidget(self.reset_btn)
        options_layout.addLayout(reset_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Output section
        source_path_layout = QHBoxLayout()
        self.get_source_path_check = QCheckBox(_("Get source path"))
        self.get_source_path_check.setChecked(True)
        self.get_source_path_check.setToolTip(
            _("Use the folder of the first added file as the output path")
        )
        source_path_layout.addWidget(self.get_source_path_check)
        self.get_path_btn = QPushButton(_("Get path"))
        self.get_path_btn.setToolTip(_("Set the output path from the first file in the list"))
        self.get_path_btn.clicked.connect(self._get_source_path)
        source_path_layout.addWidget(self.get_path_btn)
        source_path_layout.addStretch()
        layout.addLayout(source_path_layout)
        
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel(_("Output path:")))
        self.output_path_edit = QLineEdit()
        output_layout.addWidget(self.output_path_edit)
        
        self.browse_output_btn = QPushButton(_("Browse..."))
        self.browse_output_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.browse_output_btn)
        
        layout.addLayout(output_layout)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(_("Output file name:")))
        self.output_name_edit = QLineEdit(self.DEFAULT_OUTPUT_NAME)
        name_layout.addWidget(self.output_name_edit)
        layout.addLayout(name_layout)
        
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel(_("Date format for {date}:")))
        self.date_format_edit = QLineEdit(self.DEFAULT_DATE_FORMAT)
        self.date_format_edit.setToolTip(
            _("Tokens: Y=year (4 digits), y=year (2 digits), M=month, D=day, "
              "H=hour, N=minute, S=second. Any other character is kept as is.\n"
              "Use {date} in the file name to insert the date at any position.")
        )
        date_layout.addWidget(self.date_format_edit)
        self.name_preview_label = QLabel()
        date_layout.addWidget(self.name_preview_label)
        layout.addLayout(date_layout)
        
        self.output_name_edit.textChanged.connect(self._update_name_preview)
        self.date_format_edit.textChanged.connect(self._update_name_preview)
        self.date_format_edit.textChanged.connect(self._save_settings)
        self.format_combo.currentTextChanged.connect(self._update_name_preview)
        self._update_name_preview()
        
        self.output_path_edit.textChanged.connect(self._update_buttons)
        self.output_path_edit.textChanged.connect(self._save_settings)
        self.output_name_edit.textChanged.connect(self._save_settings)
        self.get_source_path_check.toggled.connect(self._save_settings)
        self.get_source_path_check.toggled.connect(
            lambda checked: self._get_source_path() if checked and not self._loading else None
        )
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.merge_btn = QPushButton(_("Merge"))
        self.merge_btn.clicked.connect(self._merge)
        self.merge_btn.setEnabled(False)
        button_layout.addWidget(self.merge_btn)
        
        self.close_btn = QPushButton(_("Close"))
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signals for button updates
        self.file_table.itemSelectionChanged.connect(self._update_buttons)
        self.file_table.itemChanged.connect(lambda _item: self._save_settings())
        
        # Text-only options are ignored for srt/json output
        self.format_combo.currentTextChanged.connect(self._update_text_options)
        self._update_text_options(self.format_combo.currentText())
        
        # Connect signals for auto-save on value changes
        self.time_delta_spin.valueChanged.connect(self._save_settings)
        self.overlap_threshold_spin.valueChanged.connect(self._save_settings)
        self.wpm_spin.valueChanged.connect(self._save_settings)
        self.spacing_spin.valueChanged.connect(self._save_settings)
        self.consolidate_check.toggled.connect(self._save_settings)
        self.fix_overlapping_check.toggled.connect(self._save_settings)
        self.timestamps_check.toggled.connect(self._save_settings)
        self.speaker_check.toggled.connect(self._save_settings)
        self.format_combo.currentTextChanged.connect(self._save_settings)
    
    def reject(self):
        """Handle dialog rejection (Close button or Escape key)"""
        self._save_settings()
        super().reject()
    
    def closeEvent(self, event):
        """Save settings when dialog is closed with X button"""
        self._save_settings()
        super().closeEvent(event)
    
    def _add_file(self):
        """Add a transcription file to the list"""
        file_paths, _filter = QFileDialog.getOpenFileNames(
            self,
            _("Select Transcription Files"),
            "",
            _("Transcription Files (*.srt *.vtt *.json *.txt);;All Files (*)")
        )
        
        if not file_paths:
            return
        
        self._add_files(file_paths)
    
    def _add_files(self, file_paths: List[str]):
        """Add multiple files (from dialog or drag and drop), skipping duplicates"""
        existing = {self.file_table.item(r, 0).text() for r in range(self.file_table.rowCount())
                    if self.file_table.item(r, 0)}
        name_map = self._get_active_name_map()
        was_empty = self.file_table.rowCount() == 0
        for file_path in file_paths:
            if file_path in existing:
                continue
            existing.add(file_path)
            # Auto-generate speaker name from filename (user can edit it in the table)
            default_speaker = (self._match_name_map(file_path, name_map)
                               or Path(file_path).stem.replace('_', ' ').title())
            self._add_file_to_table(file_path, default_speaker)
        
        if was_empty and self.get_source_path_check.isChecked():
            self._get_source_path()
        
        self._update_buttons()
        self._save_settings()
    
    def _get_active_name_map(self) -> dict:
        """Return the selected name map, or empty dict if disabled / None selected"""
        if not self.use_name_map_check.isChecked():
            return {}
        template = self.name_map_combo.currentData()
        if not template:
            return {}
        try:
            return load_name_map_template(template)
        except Exception:
            return {}
    
    @staticmethod
    def _match_name_map(file_path: str, name_map: dict) -> Optional[str]:
        """Find final name whose nickname occurs in the file name (longest nickname wins)"""
        file_name = Path(file_path).name.lower()
        for nickname in sorted(name_map, key=len, reverse=True):
            if nickname.lower() in file_name:
                return name_map[nickname]
        return None
    
    def _update_names(self):
        """Force-apply the selected name map to all speaker names in the list"""
        template = self.name_map_combo.currentData()
        if not template:
            return
        try:
            name_map = load_name_map_template(template)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to load template: {}").format(e))
            return
        for row in range(self.file_table.rowCount()):
            path_item = self.file_table.item(row, 0)
            if not path_item:
                continue
            final_name = self._match_name_map(path_item.text(), name_map)
            if final_name:
                self.file_table.setItem(row, 1, QTableWidgetItem(final_name))
        self._save_settings()
    
    def _add_file_to_table(self, file_path: str, speaker_name: str):
        """Add a file entry to the table"""
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        
        self.file_table.setItem(row, 0, QTableWidgetItem(file_path))
        self.file_table.setItem(row, 1, QTableWidgetItem(speaker_name))
        
        self.transcription_files.append((file_path, speaker_name))
    
    def _remove_file(self):
        """Remove selected file from the list"""
        selected_rows = sorted(set(item.row() for item in self.file_table.selectedItems()), reverse=True)
        
        for row in selected_rows:
            self.file_table.removeRow(row)
            if row < len(self.transcription_files):
                del self.transcription_files[row]
        
        self._update_buttons()
        self._save_settings()
    
    def _browse_output(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Output Folder"),
            self.output_path_edit.text().strip()
        )
        
        if folder:
            self.output_path_edit.setText(folder)
            self._update_buttons()
    
    @staticmethod
    def _format_date(date_format: str) -> str:
        """Convert a custom date format (Y y M D H N S tokens) to the current date string"""
        now = datetime.now()
        tokens = {
            "Y": f"{now.year:04d}", "y": f"{now.year % 100:02d}",
            "M": f"{now.month:02d}", "D": f"{now.day:02d}",
            "H": f"{now.hour:02d}", "N": f"{now.minute:02d}", "S": f"{now.second:02d}",
        }
        return "".join(tokens.get(ch, ch) for ch in date_format)
    
    def _build_output_name(self) -> str:
        """Output file name (without extension) with {date} replaced"""
        name = self.output_name_edit.text().strip() or self.DEFAULT_OUTPUT_NAME
        date_str = self._format_date(self.date_format_edit.text())
        name = name.replace("{date}", date_str)
        # Remove characters not allowed in file names
        return re.sub(r'[\\/:*?"<>|]', "_", name)
    
    def _update_name_preview(self, *_args):
        self.name_preview_label.setText(
            f"→ {self._build_output_name()}.{self.format_combo.currentText()}"
        )
    
    def _get_source_path(self):
        """Set the output folder from the first file in the list"""
        if self.file_table.rowCount() == 0:
            return
        item = self.file_table.item(0, 0)
        if item:
            self.output_path_edit.setText(str(Path(item.text()).parent))
    
    def _refresh_name_map_combo(self):
        """Reload template list, keeping the current selection if possible"""
        current = self.name_map_combo.currentData()
        self.name_map_combo.blockSignals(True)
        self.name_map_combo.clear()
        self.name_map_combo.addItem(_("None"), None)
        for name in list_name_map_templates():
            self.name_map_combo.addItem(name, name)
        index = self.name_map_combo.findData(current) if current else 0
        self.name_map_combo.setCurrentIndex(max(index, 0))
        self.name_map_combo.blockSignals(False)

    def _open_name_map_editor(self):
        dialog = NameMapDialog(self)
        dialog.exec()
        self._refresh_name_map_combo()
        self._save_settings()

    def _update_text_options(self, format_text: str):
        """Timestamp/speaker checkboxes only apply to txt output"""
        is_txt = format_text == "txt"
        self.timestamps_check.setEnabled(is_txt)
        self.speaker_check.setEnabled(is_txt)
    
    def _update_buttons(self):
        """Update button states based on current state"""
        has_selection = len(self.file_table.selectedItems()) > 0
        has_files = self.file_table.rowCount() >= 2
        has_output = bool(self.output_path_edit.text().strip())
        
        self.remove_file_btn.setEnabled(has_selection)
        self.clear_files_btn.setEnabled(self.file_table.rowCount() > 0)
        self.merge_btn.setEnabled(has_files and has_output)
    
    def _load_settings(self):
        """Load saved settings from JSON config file"""
        if not os.path.exists(self.config_file):
            self._loading = False
            return
        
        try:
            with open(self.config_file, 'r') as f:
                settings = json.load(f)
            
            # Load numeric settings
            self.time_delta_spin.setValue(settings.get("time_delta", self.DEFAULT_TIME_DELTA))
            self.overlap_threshold_spin.setValue(settings.get("overlap_threshold", self.DEFAULT_OVERLAP_THRESHOLD))
            self.wpm_spin.setValue(settings.get("duration_estimation_wpm", self.DEFAULT_WPM))
            self.spacing_spin.setValue(settings.get("sequential_spacing", self.DEFAULT_SPACING))
            
            # Load checkbox settings
            self.consolidate_check.setChecked(settings.get("consolidate", self.DEFAULT_CONSOLIDATE))
            self.fix_overlapping_check.setChecked(settings.get("fix_overlapping", self.DEFAULT_FIX_OVERLAPPING))
            self.trim_empty_check.setChecked(settings.get("trim_empty", self.DEFAULT_TRIM_EMPTY))
            self.trim_end_only_check.setChecked(settings.get("trim_end_only", self.DEFAULT_TRIM_END_ONLY))
            self.trim_min_duration_spin.setValue(settings.get("trim_min_duration", self.DEFAULT_TRIM_MIN_DURATION))
            self.trim_max_factor_spin.setValue(settings.get("trim_max_factor", self.DEFAULT_TRIM_MAX_FACTOR))
            self.timestamps_check.setChecked(settings.get("timestamps", self.DEFAULT_TIMESTAMPS))
            self.speaker_check.setChecked(settings.get("speaker", self.DEFAULT_SPEAKER))
            
            # Load format
            format_value = settings.get("format", self.DEFAULT_FORMAT)
            index = self.format_combo.findText(format_value)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
            
            # Load name map settings
            index = self.name_map_combo.findData(settings.get("name_map_template") or None)
            if index >= 0:
                self.name_map_combo.setCurrentIndex(index)
            self.use_name_map_check.setChecked(settings.get("use_name_map", True))
            
            # Restore output settings
            self.get_source_path_check.setChecked(settings.get("get_source_path", True))
            self.output_path_edit.setText(settings.get("output_dir", ""))
            self.output_name_edit.setText(
                settings.get("output_name") or self.DEFAULT_OUTPUT_NAME
            )
            self.date_format_edit.setText(
                settings.get("date_format") or self.DEFAULT_DATE_FORMAT
            )
            
            # Restore file list
            for entry in settings.get("files", []):
                file_path, speaker_name = entry[0], entry[1]
                if os.path.isfile(file_path):
                    self._add_file_to_table(file_path, speaker_name)
            self._update_buttons()
        except Exception as e:
            # If there's any error loading settings, just use defaults
            pass
        finally:
            self._loading = False
    
    def _collect_files(self) -> List[Tuple[str, str]]:
        """Read current (file path, speaker name) pairs from the table"""
        files = []
        for row in range(self.file_table.rowCount()):
            path_item = self.file_table.item(row, 0)
            speaker_item = self.file_table.item(row, 1)
            if path_item:
                files.append((path_item.text(), speaker_item.text() if speaker_item else ""))
        return files
    
    def _save_settings(self):
        """Save current settings to JSON config file"""
        if self._loading:
            return
        settings = {
            "files": self._collect_files(),
            "output_dir": self.output_path_edit.text(),
            "output_name": self.output_name_edit.text(),
            "date_format": self.date_format_edit.text(),
            "get_source_path": self.get_source_path_check.isChecked(),
            "time_delta": self.time_delta_spin.value(),
            "overlap_threshold": self.overlap_threshold_spin.value(),
            "duration_estimation_wpm": self.wpm_spin.value(),
            "sequential_spacing": self.spacing_spin.value(),
            "consolidate": self.consolidate_check.isChecked(),
            "fix_overlapping": self.fix_overlapping_check.isChecked(),
            "trim_empty": self.trim_empty_check.isChecked(),
            "trim_end_only": self.trim_end_only_check.isChecked(),
            "trim_min_duration": self.trim_min_duration_spin.value(),
            "trim_max_factor": self.trim_max_factor_spin.value(),
            "timestamps": self.timestamps_check.isChecked(),
            "speaker": self.speaker_check.isChecked(),
            "format": self.format_combo.currentText(),
            "use_name_map": self.use_name_map_check.isChecked(),
            "name_map_template": self.name_map_combo.currentData() or ""
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            # Silently fail if we can't save settings
            pass
    
    def _reset_settings(self):
        """Reset all settings to default values"""
        self.time_delta_spin.setValue(self.DEFAULT_TIME_DELTA)
        self.overlap_threshold_spin.setValue(self.DEFAULT_OVERLAP_THRESHOLD)
        self.wpm_spin.setValue(self.DEFAULT_WPM)
        self.spacing_spin.setValue(self.DEFAULT_SPACING)
        self.consolidate_check.setChecked(self.DEFAULT_CONSOLIDATE)
        self.fix_overlapping_check.setChecked(self.DEFAULT_FIX_OVERLAPPING)
        self.trim_empty_check.setChecked(self.DEFAULT_TRIM_EMPTY)
        self.trim_end_only_check.setChecked(self.DEFAULT_TRIM_END_ONLY)
        self.trim_min_duration_spin.setValue(self.DEFAULT_TRIM_MIN_DURATION)
        self.trim_max_factor_spin.setValue(self.DEFAULT_TRIM_MAX_FACTOR)
        self.timestamps_check.setChecked(self.DEFAULT_TIMESTAMPS)
        self.speaker_check.setChecked(self.DEFAULT_SPEAKER)
        
        index = self.format_combo.findText(self.DEFAULT_FORMAT)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
    
    def _clear_files(self):
        """Clear all files from the list"""
        self.file_table.setRowCount(0)
        self.transcription_files.clear()
        self._update_buttons()
        self._save_settings()
    
    def _merge(self):
        """Perform the merge operation"""
        output_dir = self.output_path_edit.text().strip()
        file_name = self._build_output_name()
        
        if not output_dir:
            QMessageBox.warning(self, _("Error"), _("Please specify an output path"))
            return
        
        output_path = str(Path(output_dir) / f"{file_name}.{self.format_combo.currentText()}")
        
        if self.file_table.rowCount() < 2:
            QMessageBox.warning(self, _("Error"), _("Please add at least 2 transcription files"))
            return
        
        # Collect files from table
        transcription_files = []
        for row in range(self.file_table.rowCount()):
            file_path = self.file_table.item(row, 0).text()
            speaker_name = self.file_table.item(row, 1).text()
            transcription_files.append((file_path, speaker_name))
        
        try:
            from buzz.multi_speaker_merge import merge_multi_speaker_transcriptions
            
            merge_multi_speaker_transcriptions(
                transcription_files=transcription_files,
                output_path=output_path,
                time_delta=self.time_delta_spin.value(),
                consolidate=self.consolidate_check.isChecked(),
                fix_overlapping_speech=self.fix_overlapping_check.isChecked(),
                overlap_threshold=self.overlap_threshold_spin.value(),
                duration_estimation_wpm=self.wpm_spin.value(),
                sequential_spacing=self.spacing_spin.value(),
                output_format=self.format_combo.currentText(),
                include_timestamps=self.timestamps_check.isChecked(),
                include_speaker=self.speaker_check.isChecked(),
                trim_empty_spaces=self.trim_empty_check.isChecked(),
                trim_end_only=self.trim_end_only_check.isChecked(),
                trim_min_duration=self.trim_min_duration_spin.value(),
                trim_max_factor=self.trim_max_factor_spin.value()
            )
            
            QMessageBox.information(
                self,
                _("Success"),
                _("Successfully merged {} transcription files.\nOutput saved to:\n{}").format(
                    len(transcription_files), output_path
                )
            )
            
            # Save settings for next time
            self._save_settings()
            
            self.merge_completed.emit(output_path)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                _("Error"),
                _("Failed to merge transcriptions:\n{}").format(str(e))
            )
