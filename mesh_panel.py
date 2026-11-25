import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QProcess, QProcessEnvironment, QStandardPaths, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QFrame, QProgressBar, QVBoxLayout

from ui import button, label


WORKER = Path(__file__).resolve().with_name("mesh_worker.py")


def choose_glb_output(parent, caption, proposed):
    dialog = QFileDialog(parent, caption, str(proposed.parent))
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setNameFilter("GLB 3D 모델 (*.glb)")
    dialog.setDefaultSuffix("glb")
    dialog.selectFile(proposed.name)
    if dialog.exec():
        return Path(dialog.selectedFiles()[0])
    return None


def same_file(a, b):
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))


class GlbTaskPanel(QFrame):
    busy_changed = Signal(bool)
    saved = Signal(str)
    view_requested = Signal(str)

    def __init__(self, heading, tool, action, prefix=""):
        super().__init__()
        self.setObjectName("paper")
        self.tool = tool
        self.action = action
        self.prefix = prefix
        self.directory = None
        self.output = None
        self.proc = QProcess(self)
        self.proc.readyReadStandardOutput.connect(self.read_progress)
        self.proc.readyReadStandardError.connect(self.read_errors)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.addWidget(label(heading, "section"))
        self.selected = label("", "fileTitle", True)
        layout.addWidget(self.selected)
        self.note = label("", "hint", True)
        layout.addWidget(self.note)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        self.stop = button(f"{action} 취소", self.cancel)
        layout.addWidget(self.stop)
        self.folder = button("저장 폴더 열기", self.open_folder)
        self.view_model = button("3D 뷰어로 열기", lambda: self.view_requested.emit(str(self.output)), "primary")
        self.view_model.hide()
        layout.addWidget(self.view_model)
        layout.addWidget(self.folder)
        self.hide()

    @property
    def busy(self):
        return self.directory is not None

    def run_worker(self, title, output, executable, prepare_args, *, environment=None, original=None):
        if self.busy:
            return
        self.show()
        self.view_model.hide()
        self.folder.hide()
        self.stop.hide()
        self.bar.hide()
        self.note.setToolTip("")
        self.selected.setText(title)
        if output.suffix.lower() != ".glb":
            self.note.setText("저장 파일의 확장자를 .glb로 선택해 주세요.")
            return
        self.output = output
        self.original = original
        self.cancelled = False
        self.errors = b""
        self.stage = f"{self.tool} 시작 중"
        try:
            if original is not None and same_file(original, output):
                self.note.setText("원본과 다른 파일 이름 또는 위치를 선택해 주세요.")
                return
            # Staging on the destination volume makes the final replace atomic.
            self.directory = TemporaryDirectory(prefix=".fauna-", dir=output.parent)
            work = Path(self.directory.name)
            args = prepare_args(work)
        except OSError as error:
            self.finish_ui(f"입력 또는 저장 위치를 준비할 수 없습니다.\n{error}")
            return
        self.note.setText(self.stage)
        self.bar.show()
        self.stop.setEnabled(True)
        self.stop.show()
        self.busy_changed.emit(True)
        if environment is not None:
            self.proc.setProcessEnvironment(environment)
        self.proc.start(str(executable), args)

    def read_progress(self):
        while self.proc.canReadLine():
            line = bytes(self.proc.readLine()).decode("utf-8", errors="replace").strip()
            if line and line.startswith(self.prefix):
                self.stage = line.removeprefix(self.prefix)
                if not self.cancelled:
                    self.note.setText(self.stage)

    def read_errors(self):
        self.errors = (self.errors + bytes(self.proc.readAllStandardError()))[-6500:]

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.busy:
            self.finish_ui(f"{self.tool} 프로세스를 열 수 없습니다.\n" + self.proc.errorString())

    def finished(self, exit_code, exit_status):
        if not self.busy:
            return
        self.read_progress()
        self.read_errors()
        if self.cancelled:
            self.finish_ui(f"{self.action}을 취소했습니다.")
            return
        if exit_code or exit_status != QProcess.ExitStatus.NormalExit:
            detail = self.errors.decode("utf-8", errors="replace").strip().splitlines()
            self.note.setToolTip("\n".join(detail))
            self.finish_ui(f"{self.action} 실패 · " + (detail[-1][:420] if detail else self.proc.errorString()))
            return
        try:
            if self.original is not None and same_file(self.original, self.output):
                raise OSError("원본과 저장 위치가 같습니다.")
            os.replace(Path(self.directory.name) / "mesh.glb", self.output)
        except OSError as error:
            self.finish_ui(f"파일을 저장할 수 없습니다.\n{error}")
            return
        self.folder.show()
        self.view_model.show()
        self.note.setToolTip(str(self.output))
        self.finish_ui(f"저장 완료 · {self.stage}\n{self.output.name}")
        self.saved.emit(str(self.output))

    def finish_ui(self, text):
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None
        self.bar.hide()
        self.stop.hide()
        self.note.setText(text)
        self.busy_changed.emit(False)

    def cancel(self):
        if self.busy:
            self.cancelled = True
            self.stop.setEnabled(False)
            self.note.setText(f"{self.action} 취소 중…")
            self.proc.kill()

    def shutdown(self):
        if self.busy:
            self.cancel()
            self.proc.waitForFinished(-1)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output.parent)))


class MeshPanel(GlbTaskPanel):
    lowpoly_requested = Signal(str)

    def __init__(self):
        super().__init__("3D 모델 · TripoSR", "TripoSR", "생성")
        self.last_folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation))
        self.lowpoly = button("로우폴리로 변환…", lambda: self.lowpoly_requested.emit(str(self.output)))
        self.layout().addWidget(self.lowpoly)
        self.lowpoly.hide()
        self.saved.connect(lambda _: self.lowpoly.show())

    def choose_output(self, title):
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(title).stem)[:85].strip(" .")
        return choose_glb_output(self, "3D 모델 저장 위치", self.last_folder / f"{stem or 'animal'}-3D.glb")

    def start(self, source, image=None):
        if self.busy:
            return
        output = self.choose_output(source["title"])
        if output is None:
            return
        self.last_folder = output.parent
        self.lowpoly.hide()

        def prepare_args(work):
            (work / "source.json").write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            if image is not None:
                image.save(work / "input.png", format="PNG")
            return ["-X", "utf8", "-u", str(WORKER), str(work)]

        # Launch the interpreter itself so killing the QProcess stops inference.
        env = QProcessEnvironment.systemEnvironment()
        env.remove("__PYVENV_LAUNCHER__")
        executable = Path(sys.executable)
        if sys.platform == "win32":
            # Windows venv executables are redirectors. Start Python directly.
            env.insert("__PYVENV_LAUNCHER__", str(executable.with_name("python.exe")))
            executable = Path(sys._base_executable).with_name("python.exe")
        self.run_worker(source["title"], output, executable, prepare_args, environment=env)
