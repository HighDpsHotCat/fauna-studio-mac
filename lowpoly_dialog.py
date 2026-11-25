import os
from pathlib import Path
import re
import shutil
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QSpinBox, QVBoxLayout

from glb_info import triangle_count
from mesh_panel import GlbTaskPanel, choose_glb_output
from ui import button, label, panel


WORKER = Path(__file__).resolve().with_name("blender_lowpoly.py")


def blender_executable(path):
    path = Path(path).expanduser()
    if path.suffix.lower() == ".app":
        path = path / "Contents" / "MacOS" / "Blender"
    return path if path.is_file() else None


def find_blender():
    saved = QSettings("Fauna Studio", "Fauna Studio").value("blender/executable", "")
    command = "blender.exe" if sys.platform == "win32" else "blender"
    for candidate in (saved, shutil.which(command)):
        if candidate:
            executable = blender_executable(candidate)
            if executable:
                return executable
    if sys.platform == "darwin":
        for folder in (Path("/Applications"), Path.home() / "Applications"):
            for bundle in sorted(folder.glob("Blender*.app")):
                executable = blender_executable(bundle)
                if executable:
                    return executable
        return None
    folders = []
    for base in (os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            for subdir in ("Blender Foundation", "Programs/Blender Foundation"):
                folders.extend((Path(base) / subdir).glob("Blender */blender.exe"))
    return max(folders, default=None, key=lambda p: tuple(map(int, re.findall(r"\d+", p.parent.name))))


class LowPolyDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("lowpoly")
        self.setWindowTitle("Blender 로우폴리 변환")
        self.setMinimumWidth(410)
        self.source = None
        self.blender = find_blender()
        layout = QVBoxLayout(self)
        settings, box = panel()
        layout.addWidget(settings)
        row = QHBoxLayout()
        row.addWidget(label("원본 GLB", "section"))
        row.addStretch()
        self.choose = button("GLB 선택…", self.browse)
        row.addWidget(self.choose)
        box.addLayout(row)
        self.input_info = label("변환할 GLB 파일을 선택하세요.", "hint", True)
        box.addWidget(self.input_info)
        row = QHBoxLayout()
        row.addWidget(label("목표 삼각형 수"))
        self.target = QSpinBox()
        self.target.setRange(1, 2_147_483_647)
        self.target.setValue(3000)
        self.target.setGroupSeparatorShown(True)
        self.target.setAccelerated(True)
        self.target.setAccessibleName("목표 삼각형 수")
        row.addWidget(self.target, 1)
        box.addLayout(row)
        self.blender_button = button("", self.browse_blender, "link")
        self.blender_button.setToolTip(str(self.blender or "Blender"))
        self.blender_button.setText("Blender 실행 파일 변경…" if self.blender else "Blender 실행 파일 선택…")
        box.addWidget(self.blender_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.convert = button("변환하여 별도 GLB 저장…", self.start, "primary")
        self.convert.setEnabled(False)
        box.addWidget(self.convert)
        self.job = GlbTaskPanel("변환 결과", "Blender", "변환", "FAUNA ")
        self.job.selected.hide()
        layout.addWidget(self.job)
        self.job.busy_changed.connect(self.busy_changed)

    def browse(self):
        start = str(self.source.parent) if self.source else ""
        path, _ = QFileDialog.getOpenFileName(self, "원본 GLB 선택", start, "GLB 3D 모델 (*.glb)")
        if path:
            self.set_source(path)

    def set_source(self, path):
        if self.job.busy:
            return
        path = Path(path).resolve()
        self.job.hide()
        try:
            count = triangle_count(path)
        except (OSError, ValueError) as error:
            self.source = None
            self.convert.setEnabled(False)
            self.input_info.setText(f"{path.name}\n{error}")
        else:
            self.source = path
            self.convert.setEnabled(True)
            self.input_info.setText(f"{path.name}\n원본 삼각형 {count:,}개")
        self.input_info.setToolTip(str(path))

    def browse_blender(self):
        if sys.platform == "darwin":
            path = QFileDialog.getExistingDirectory(
                self, "Blender.app 폴더 선택", "/Applications",
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Blender 실행 파일 선택",
                                                  str(self.blender or ""), "Blender (blender.exe blender)")
        if path:
            executable = blender_executable(path)
            if executable is None:
                self.blender_button.setText("Blender 실행 파일을 찾을 수 없습니다. 다시 선택…")
                return
            self.blender = executable
            self.blender_button.setText("Blender 실행 파일 변경…")
            self.blender_button.setToolTip(str(executable))
            QSettings("Fauna Studio", "Fauna Studio").setValue("blender/executable", str(executable))

    def choose_output(self, proposed):
        return choose_glb_output(self, "로우폴리 모델 저장 위치", proposed)

    def start(self):
        if self.job.busy or self.source is None:
            return
        if not self.blender or not self.blender.is_file():
            self.browse_blender()
            if not self.blender or not self.blender.is_file():
                return
        target = self.target.value()
        source = self.source
        proposed = source.with_name(f"{source.stem}-lowpoly-{target}.glb")
        output = self.choose_output(proposed)
        if output is None:
            return

        def prepare_args(work):
            return ["--background", "--factory-startup", "--disable-autoexec",
                    "--python-exit-code", "1", "--python", str(WORKER), "--",
                    str(source), str(target), str(work / "mesh.glb")]

        self.job.run_worker(source.name, output, self.blender, prepare_args, original=source)

    def busy_changed(self, busy):
        self.choose.setEnabled(not busy)
        self.target.setEnabled(not busy)
        self.blender_button.setEnabled(not busy)
        self.convert.setEnabled(not busy and self.source is not None)
