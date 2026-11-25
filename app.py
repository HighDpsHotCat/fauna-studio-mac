import os
from pathlib import Path
import sys
from threading import Event

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QMainWindow,
    QMessageBox, QProgressBar, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from PIL.Image import DecompressionBombError

from classifier import AnimalClassifier, open_photo
from commons import search_photos, thumbnail
from lowpoly_dialog import LowPolyDialog
from mesh_panel import MeshPanel
from ui import PhotoCard, Picture, STYLE, button, label, panel
from web_viewer import LocalViewer


EXAMPLE = Path(__file__).with_name("assets") / "red-fox.jpg"
EXAMPLE_SOURCE = "https://commons.wikimedia.org/wiki/File:Vulpes_vulpes_Mallnitz_01.jpg"


class Events(QObject):
    done = Signal(str, int, object)
    failed = Signal(str, int, str)
    progress = Signal(int, str)

    def __init__(self, parent):
        super().__init__(parent)
        self.closed = Event()


class Job(QRunnable):
    def __init__(self, events, kind, ticket, function, *args):
        super().__init__()
        self.events, self.kind, self.ticket = events, kind, ticket
        self.function, self.args = function, args

    def run(self):
        try:
            result = self.function(*self.args)
        except Exception as error:
            if not self.events.closed.is_set():
                self.events.failed.emit(self.kind, self.ticket, f"{type(error).__name__}: {error}")
        else:
            if not self.events.closed.is_set():
                self.events.done.emit(self.kind, self.ticket, result)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if widget := item.widget():
            widget.hide()
            widget.deleteLater()


def open_url(url):
    QDesktopServices.openUrl(QUrl(url))


def scroll_view():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    canvas = QWidget()
    canvas.setObjectName("canvas")
    scroll.setWidget(canvas)
    return scroll, canvas


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fauna Studio · 동물 종 분류와 3D 모델링")
        self.resize(1150, 815)
        self.setMinimumSize(790, 570)
        self.setAcceptDrops(True)
        self.engine = None
        self.input_id = self.gallery_id = 0
        self.active = None
        self.candidates = []
        self.cards = []
        self.columns = 0
        self.events = Events(self)
        self.events.progress.connect(self.on_progress)
        self.events.done.connect(self.on_done)
        self.events.failed.connect(self.on_failure)
        self.model_pool = self.pool(1)
        self.search_pool = self.pool(2)
        self.image_pool = self.pool(3)
        self.viewer = LocalViewer()
        self.viewer_folder = Path(__file__).resolve().parent / "examples"
        self.lowpoly_dialog = LowPolyDialog(self)
        self.lowpoly_dialog.job.view_requested.connect(self.show_viewer)
        self.build()
        self.shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        self.shortcut.activated.connect(self.browse)

    def pool(self, size):
        pool = QThreadPool(self)
        pool.setMaxThreadCount(size)
        return pool

    def build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        mast = QFrame()
        mast.setObjectName("mast")
        bar = QHBoxLayout(mast)
        bar.setContentsMargins(26, 14, 26, 15)
        bar.setSpacing(18)
        bar.addWidget(label("Fauna Studio", "wordmark"))
        bar.addWidget(label("동물 종 분류 · 3D 모델링", "strap"))
        bar.addStretch()
        self.open_lowpoly = button("로우폴리 변환…", lambda: self.show_lowpoly())
        bar.addWidget(self.open_lowpoly)
        self.open_viewer = button("3D 뷰어…", self.browse_viewer)
        bar.addWidget(self.open_viewer)
        self.status = label("사진 대기 중", "status")
        bar.addWidget(self.status)
        layout.addWidget(mast)

        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 12)
        body.setSpacing(12)
        layout.addLayout(body, 1)
        side, side_canvas = scroll_view()
        side.setFixedWidth(306)
        left = QVBoxLayout(side_canvas)
        left.setContentsMargins(0, 0, 4, 0)
        left.setSpacing(12)
        body.addWidget(side)
        input_panel, input_box = panel()
        left.addWidget(input_panel)
        input_box.addWidget(label("입력 사진", "section"))
        self.drop_hint = label("동물 사진을 여기에 끌어 놓으세요\n\nJPG  ·  PNG  ·  WEBP", "empty")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setFixedHeight(155)
        input_box.addWidget(self.drop_hint)
        self.preview = Picture(155, cover=False)
        self.preview.hide()
        input_box.addWidget(self.preview)
        self.file_label = label("", "hint", True)
        self.file_label.hide()
        input_box.addWidget(self.file_label)
        self.choose = button("사진 열기…", self.browse, "primary")
        input_box.addWidget(self.choose)
        self.generate_original = button("원본으로 3D 생성…", self.mesh_from_original)
        self.generate_original.hide()
        input_box.addWidget(self.generate_original)
        self.mesh = MeshPanel()
        left.addWidget(self.mesh)
        self.mesh.busy_changed.connect(self.mesh_busy_changed)
        self.mesh.lowpoly_requested.connect(self.show_lowpoly)
        self.mesh.view_requested.connect(self.show_viewer)
        self.mesh.saved.connect(self.model_saved)
        self.side_scroll = side
        candidates_panel, candidates_box = panel()
        left.addWidget(candidates_panel)
        candidates_box.addWidget(label("분류 후보", "section"))
        self.model_note = label("사진을 열면 BioCLIP이 이 PC에서 종을 분류합니다.", "hint", True)
        candidates_box.addWidget(self.model_note)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        candidates_box.addWidget(self.progress)
        self.candidate_list = QVBoxLayout()
        self.candidate_list.setSpacing(5)
        candidates_box.addLayout(self.candidate_list)
        self.retry_model = button("분류 다시 시도", self.start_model)
        self.retry_model.hide()
        candidates_box.addWidget(self.retry_model)
        left.addStretch()

        self.scroll, canvas = scroll_view()
        body.addWidget(self.scroll, 1)
        right = QVBoxLayout(canvas)
        right.setContentsMargins(3, 0, 4, 0)
        right.setSpacing(12)
        self.header_frame, header = panel(margin=19)
        header.addWidget(label("Wikimedia Commons", "eyebrow"))
        self.title = label("동일 종 사진", "heading", True)
        header.addWidget(self.title)
        self.binomial = label("", "species", True)
        self.binomial.hide()
        header.addWidget(self.binomial)
        self.gallery_note = label("종을 분류하면 같은 종의 사진을 모아 보여줍니다.", "hint", True)
        header.addWidget(self.gallery_note)
        self.retry_search = button("검색 다시 시도", self.repeat_search)
        self.retry_search.hide()
        header.addWidget(self.retry_search, 0, Qt.AlignmentFlag.AlignLeft)
        right.addWidget(self.header_frame)

        self.example, sample = panel(margin=16)
        hero = Picture(None, cover=False)
        hero.set_picture(QPixmap(str(EXAMPLE)))
        sample.addWidget(hero)
        sample.addWidget(label("예제 사진 · 붉은여우", "section"))
        actions = QHBoxLayout()
        actions.addWidget(button("이 사진으로 분류하기", lambda: self.load_photo(EXAMPLE)))
        actions.addStretch()
        actions.addWidget(button("Uoaei1 · CC BY-SA 4.0 ↗", lambda: open_url(EXAMPLE_SOURCE), "link"))
        sample.addLayout(actions)
        right.addWidget(self.example)
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        right.addLayout(self.grid)
        right.addStretch()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "동물 사진 열기", "",
                                              "동물 사진 (*.jpg *.jpeg *.png *.webp)")
        if path:
            self.load_photo(Path(path))

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() == ".glb":
                self.show_lowpoly(str(path))
            else:
                self.load_photo(path)
            event.acceptProposedAction()

    def model_saved(self, path):
        if not self.lowpoly_dialog.isVisible():
            self.lowpoly_dialog.set_source(path)

    def browse_viewer(self):
        path, _ = QFileDialog.getOpenFileName(self, "3D 뷰어에서 열기", str(self.viewer_folder),
                                              "GLB 3D 모델 (*.glb)")
        if path:
            self.show_viewer(path)

    def show_viewer(self, path):
        try:
            url = self.viewer.url_for(path)
            if not QDesktopServices.openUrl(QUrl(url)):
                raise OSError("기본 브라우저를 열 수 없습니다.")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "3D 뷰어를 열 수 없습니다", str(error))
            return
        self.viewer_folder = Path(path).parent

    def show_lowpoly(self, path=None):
        if path:
            self.lowpoly_dialog.set_source(path)
        self.lowpoly_dialog.show()
        self.lowpoly_dialog.raise_()
        self.lowpoly_dialog.activateWindow()

    def load_photo(self, path):
        try:
            original, size = open_photo(path, preserve_alpha=True)
        except (ValueError, OSError, DecompressionBombError) as error:
            message = str(error) if isinstance(error, ValueError) else "파일 형식 또는 손상 여부를 확인해 주세요."
            QMessageBox.warning(self, "사진을 열 수 없습니다", message)
            return
        self.original = original
        self.original_path = path
        self.photo = photo = original.convert("RGB") if original.mode != "RGB" else original
        self.generate_original.show()
        rgb = photo.tobytes()
        img = QImage(rgb, photo.width, photo.height, photo.width * 3, QImage.Format.Format_RGB888)
        self.preview.set_picture(QPixmap.fromImage(img))
        self.preview.show()
        self.drop_hint.hide()
        self.example.hide()
        self.file_label.setText(f"{path.name}   ·   {size[0]} × {size[1]}")
        self.file_label.show()
        self.choose.setText("다른 사진 열기…")
        self.start_model()

    def mesh_from_original(self):
        source = {"title": self.original_path.name}
        if self.original_path.resolve() == EXAMPLE.resolve():
            source.update(author="Uoaei1", license="CC BY-SA 4.0", url=EXAMPLE_SOURCE)
        self.mesh.start(source, self.original)

    def mesh_from_commons(self, photo):
        self.mesh.start(dict(page_id=photo.page_id, title=photo.title, author=photo.author,
                             license=photo.license, url=photo.page_url))

    def mesh_busy_changed(self, busy):
        self.generate_original.setEnabled(not busy)
        for card in self.cards:
            card.generate.setEnabled(not busy)
        self.side_scroll.ensureWidgetVisible(self.mesh)

    def reset_gallery(self):
        self.gallery_id += 1
        self.search_pool.clear()
        self.image_pool.clear()
        clear_layout(self.grid)
        self.cards.clear()
        self.retry_search.hide()
        self.gallery_note.setToolTip("")
        self.scroll.verticalScrollBar().setValue(0)

    def start_model(self):
        self.input_id += 1
        self.model_pool.clear()
        self.reset_gallery()
        clear_layout(self.candidate_list)
        self.candidates = []
        self.active = None
        self.retry_model.hide()
        self.progress.show()
        self.model_note.setToolTip("")
        self.model_note.setText("BioCLIP 준비 중 · 처음 실행할 때 모델을 불러옵니다.")
        self.status.setText("로컬 분류 중")
        self.title.setText("동일 종 사진")
        self.binomial.hide()
        self.gallery_note.setText("분류가 끝나면 첫 번째 후보로 검색합니다.")
        self.model_pool.start(Job(self.events, "model", self.input_id,
                                 self.classify, self.photo, self.input_id))

    def classify(self, image, ticket):
        def progress(text):
            if self.events.closed.is_set():
                raise InterruptedError()
            self.events.progress.emit(ticket, text)
        if self.engine is None:
            self.engine = AnimalClassifier(progress)
        progress("사진과 동물 종 특징을 비교하는 중")
        return self.engine.predict(image), self.engine.device

    @Slot(int, str)
    def on_progress(self, ticket, text):
        if ticket == self.input_id:
            self.model_note.setText(text)

    def show_candidates(self, result):
        self.candidates, device = result
        self.progress.hide()
        self.status.setText(f"로컬 분류 완료 · {device.upper()}")
        self.model_note.setText("동물 종 후보 간 상대 점수입니다. 후보를 누르면 사진을 비교할 수 있습니다.")
        for index, candidate in enumerate(self.candidates):
            score = f"{candidate.score:.1%}" if candidate.score >= 0.001 else "< 0.1%"
            name = candidate.scientific
            if candidate.common:
                name += "\n" + candidate.common
            widget = button(f"{name}   ·   {score}", lambda _, i=index: self.select(i), "candidate")
            widget.setToolTip(f"{candidate.scientific} · {candidate.common} · {score}")
            widget.setAccessibleName(widget.toolTip())
            widget.setCheckable(True)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            self.candidate_list.addWidget(widget)
        self.select(0)

    def select(self, index):
        self.active = index
        self.reset_gallery()
        for i in range(len(self.candidates)):
            self.candidate_list.itemAt(i).widget().setChecked(i == index)
        c = self.candidates[index]
        self.title.setText(c.common or "동일 종 사진")
        self.binomial.setText(c.scientific)
        self.binomial.show()
        self.gallery_note.setText("학명으로 위키미디어 커먼스를 검색하는 중…")
        self.search_pool.start(Job(self.events, "search", self.gallery_id, search_photos, c.scientific))

    def repeat_search(self):
        if self.active is not None:
            self.select(self.active)

    def show_gallery(self, gallery):
        c = self.candidates[self.active]
        taxon = gallery.taxon
        self.title.setText(taxon.korean or c.common or "동일 종 사진")
        self.binomial.setText(taxon.scientific)
        info = f"BioCLIP 학명 {c.scientific}  ·  " if c.scientific != taxon.scientific else ""
        count = len(gallery.photos)
        self.gallery_note.setText(info + (f"참고 사진 {count}장" if count else
                                         "이 종의 사진을 찾지 못했습니다. 다른 후보를 선택해 보세요."))
        for index, photo in enumerate(gallery.photos):
            card = PhotoCard(photo, lambda _, url=photo.page_url: open_url(url),
                             lambda _, item=photo: self.mesh_from_commons(item))
            card.generate.setEnabled(not self.mesh.busy)
            self.cards.append(card)
            self.image_pool.start(Job(self.events, f"thumb-{index}", self.gallery_id,
                                      thumbnail, photo.thumbnail))
        self.arrange()

    def arrange(self):
        self.columns = 3 if self.scroll.viewport().width() >= 695 else 2
        for index, card in enumerate(self.cards):
            row, col = divmod(index, self.columns)
            self.grid.addWidget(card, row, col)
        for col in range(3):
            self.grid.setColumnStretch(col, int(col < self.columns))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.cards and self.columns != (3 if self.scroll.viewport().width() >= 695 else 2):
            self.arrange()

    @Slot(str, int, object)
    def on_done(self, kind, ticket, result):
        if kind == "model":
            if ticket == self.input_id:
                self.show_candidates(result)
        elif ticket == self.gallery_id:
            if kind == "search":
                self.show_gallery(result)
            else:
                pixmap = QPixmap()
                if pixmap.loadFromData(result):
                    self.cards[int(kind.split("-")[1])].picture.set_picture(pixmap)
                else:
                    self.on_failure(kind, ticket, "미리보기 형식을 읽을 수 없습니다.")

    @Slot(str, int, str)
    def on_failure(self, kind, ticket, details):
        if kind == "model" and ticket == self.input_id:
            self.status.setText("분류 실패")
            self.progress.hide()
            self.model_note.setText("모델을 실행할 수 없습니다. 최초 다운로드에는 인터넷 연결과 약 1.5 GB의 여유 공간이 필요합니다.")
            self.model_note.setToolTip(details)
            self.gallery_note.setText("분류를 다시 시도하거나 다른 사진을 열어 주세요.")
            self.retry_model.show()
        elif kind == "search" and ticket == self.gallery_id:
            self.gallery_note.setText("위키미디어에 연결할 수 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.")
            self.gallery_note.setToolTip(details)
            self.retry_search.show()
        elif kind.startswith("thumb-") and ticket == self.gallery_id:
            picture = self.cards[int(kind.split("-")[1])].picture
            picture.placeholder = "미리보기 없음"
            picture.setToolTip(details)
            picture.update()
            self.retry_search.show()

    def closeEvent(self, event):
        self.viewer.close()
        self.lowpoly_dialog.job.shutdown()
        self.mesh.shutdown()
        self.events.closed.set()
        for pool in (self.model_pool, self.search_pool, self.image_pool):
            pool.clear()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Fauna Studio")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    studio = Studio()
    studio.show()
    sys.exit(app.exec())
