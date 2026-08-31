from typing import Optional, List, Tuple
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QSpinBox,
    QDoubleSpinBox, QCheckBox, QComboBox, QMessageBox, QGroupBox,
    QLineEdit, QWidget
)

from buzz.locale import _
from buzz.multi_speaker_merge import MultiSpeakerTranscriptionMerger


class MultiSpeakerMergeDialog(QDialog):
    """Dialog for merging multiple speaker transcription files"""
    
    merge_completed = pyqtSignal(str)  # Emits output file path
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle(_("Merge Multi-Speaker Transcriptions"))
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        self.transcription_files: List[Tuple[str, str]] = []
        
        self._setup_ui()
    
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
        self.file_table = QTableWidget()
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
        
        file_btn_layout.addStretch()
        file_layout.addLayout(file_btn_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
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
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Output file section
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel(_("Output file:")))
        self.output_path_edit = QLineEdit()
        output_layout.addWidget(self.output_path_edit)
        
        self.browse_output_btn = QPushButton(_("Browse..."))
        self.browse_output_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.browse_output_btn)
        
        layout.addLayout(output_layout)
        
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
        
        # Connect signals
        self.file_table.itemSelectionChanged.connect(self._update_buttons)
    
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
        
        for file_path in file_paths:
            # Auto-generate speaker name from filename (user can edit it in the table)
            default_speaker = Path(file_path).stem.replace('_', ' ').title()
            self._add_file_to_table(file_path, default_speaker)
        
        self._update_buttons()
    
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
    
    def _browse_output(self):
        """Browse for output file location"""
        current_format = self.format_combo.currentText()
        
        filters = {
            'txt': _("Text Files (*.txt)"),
            'srt': _("SRT Files (*.srt)"),
            'json': _("JSON Files (*.json)")
        }
        
        file_path, _filter = QFileDialog.getSaveFileName(
            self,
            _("Save Merged Transcription"),
            "",
            filters.get(current_format, _("All Files (*)"))
        )
        
        if file_path:
            self.output_path_edit.setText(file_path)
            self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current state"""
        has_selection = len(self.file_table.selectedItems()) > 0
        has_files = self.file_table.rowCount() >= 2
        has_output = bool(self.output_path_edit.text().strip())
        
        self.remove_file_btn.setEnabled(has_selection)
        self.merge_btn.setEnabled(has_files and has_output)
    
    def _merge(self):
        """Perform the merge operation"""
        output_path = self.output_path_edit.text().strip()
        
        if not output_path:
            QMessageBox.warning(self, _("Error"), _("Please specify an output file"))
            return
        
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
                output_format=self.format_combo.currentText(),
                include_timestamps=self.timestamps_check.isChecked(),
                include_speaker=self.speaker_check.isChecked()
            )
            
            QMessageBox.information(
                self,
                _("Success"),
                _("Successfully merged {} transcription files.\nOutput saved to:\n{}").format(
                    len(transcription_files), output_path
                )
            )
            
            self.merge_completed.emit(output_path)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                _("Error"),
                _("Failed to merge transcriptions:\n{}").format(str(e))
            )
