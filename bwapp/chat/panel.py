"""Claude chat block: streaming text, tool calls shown as small lines (details on request), image attach, Stop."""
import base64
import html
import mimetypes
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QInputDialog, QLineEdit, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextBrowser, QVBoxLayout,
                               QWidget)

from bwapp import theme
from bwapp.chat import keystore
from bwapp.chat.api import ApiChat
from bwapp.chat.cli import CliChat

MODELS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1", "claude-haiku-4-5"]


def md_html(md: str) -> str:
    d = QTextDocument()
    d.setMarkdown(md)
    return d.toHtml().split("<body", 1)[-1].split(">", 1)[-1].rsplit("</body>", 1)[0]


class ChatPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.items = []                    # [kind, text, extra] with kind user | assistant | tool
        self.images = []
        self.view = QTextBrowser()
        self.box = QPlainTextEdit()
        self.box.setPlaceholderText("Ask Claude about your project...   (Ctrl+Enter to send)")
        self.box.setFixedHeight(70)
        self.send_b, self.stop_b, self.attach_b = QPushButton("Send"), QPushButton("Stop"), QPushButton("Attach image")
        self.details = QCheckBox("Tool details")
        self.backend = QComboBox()
        self.backend.addItems(["Claude Code login", "API key"])
        self.model = QComboBox()
        self.model.addItems(MODELS)
        self.key_b = QPushButton("API key...")
        self.new_b = QPushButton("New chat")
        top = QHBoxLayout()
        for w in (self.backend, self.model, self.key_b, self.new_b):
            top.addWidget(w)
        top.addStretch()
        self.info = QLabel("")
        self.info.setProperty("role", "dim")
        row = QHBoxLayout()
        for w in (self.attach_b, self.details):
            row.addWidget(w)
        row.addStretch()
        row.addWidget(self.stop_b)
        row.addWidget(self.send_b)
        self.setMinimumWidth(340)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.box)
        lay.addLayout(row)
        lay.addWidget(self.info)
        self.stop_b.setEnabled(False)
        self.send_b.clicked.connect(self.send)
        self.stop_b.clicked.connect(self.stop)
        self.attach_b.clicked.connect(self.attach)
        self.details.toggled.connect(self.render)
        self.box.installEventFilter(self)
        self.chat = None
        self.key_b.setVisible(False)
        self.backend.currentIndexChanged.connect(self.new_chat)
        self.model.currentIndexChanged.connect(self.new_chat)
        self.new_b.clicked.connect(self.new_chat)
        self.key_b.clicked.connect(self.ask_key)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.render)
        self.new_chat()

    def new_chat(self, *_):
        """(Re)start the conversation with the chosen backend and model."""
        if self.chat is not None:
            self.chat.close()
        api = self.backend.currentIndex() == 1
        self.key_b.setVisible(api)
        self.chat = (ApiChat if api else CliChat)(self.model.currentText())
        c = self.chat
        c.text.connect(self.on_text)
        c.tool.connect(self.on_tool)
        c.tool_result.connect(self.on_result)
        c.finished.connect(self.on_done)
        c.failed.connect(lambda m: self.on_done("failed: " + m, 0))
        self.items.clear()
        self.info.setText("API key stored" if api and keystore.get() else "")
        self.send_b.setEnabled(True)
        self.stop_b.setEnabled(False)
        self.render()

    def ask_key(self):
        k, ok = QInputDialog.getText(self, "Anthropic API key", "Paste your API key (kept in Windows Credential Manager):", QLineEdit.Password)
        if ok and k.strip():
            keystore.put(k)
            self.info.setText("API key stored")

    def eventFilter(self, obj, ev):
        if obj is self.box and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Return, Qt.Key_Enter) and ev.modifiers() & Qt.ControlModifier:
            self.send()
            return True
        return super().eventFilter(obj, ev)

    def attach(self):
        f, _ = QFileDialog.getOpenFileName(self, "Attach image", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if f:
            self.images.append((mimetypes.guess_type(f)[0] or "image/png", base64.b64encode(Path(f).read_bytes()).decode()))
            self.info.setText(f"{len(self.images)} image(s) attached")

    def send(self):
        text = self.box.toPlainText().strip()
        if not text or self.chat.busy:
            return
        self.items.append(["user", text + (f"  [{len(self.images)} image(s)]" if self.images else ""), None])
        self.items.append(["assistant", "", None])
        self.box.clear()
        self.chat.send(text, self.images)
        self.images = []
        self.info.setText("thinking...")
        self.send_b.setEnabled(False)
        self.stop_b.setEnabled(True)
        self.render()

    def stop(self):
        self.chat.stop()
        self.on_done("stopped", 0)

    def _assistant(self):
        if not self.items or self.items[-1][0] != "assistant":
            self.items.append(["assistant", "", None])
        return self.items[-1]

    def on_text(self, t):
        self._assistant()[1] += t
        if not self.timer.isActive():
            self.timer.start(100)

    def on_tool(self, tid, name, args):
        self.items.append(["tool", name, {"id": tid, "args": args, "result": None, "err": False}])
        self.render()

    def on_result(self, tid, text, err):
        for it in self.items:
            if it[0] == "tool" and it[2]["id"] == tid:
                it[2].update(result=text, err=err)
        self.render()

    def on_done(self, reason, cost):
        self.info.setText(reason + (f" - ${cost:.3f}" if cost else ""))
        self.send_b.setEnabled(True)
        self.stop_b.setEnabled(False)
        self.render()

    def closeEvent(self, e):
        self.chat.close()
        super().closeEvent(e)

    def render(self, *_):
        out = []
        for kind, text, extra in self.items:
            if kind == "user":
                out.append(f'<p style="color:{theme.ACCENT}"><b>You</b><br>{html.escape(text)}</p>')
            elif kind == "assistant" and text:
                out.append(f"<p><b>Claude</b></p>{md_html(text)}")
            elif kind == "tool":
                mark = "x" if extra["err"] else ("..." if extra["result"] is None else "ok")
                line = f'<p style="color:{theme.DIM}">&#9656; {html.escape(text)} [{mark}]</p>'
                if self.details.isChecked():
                    line += (f'<pre style="color:{theme.DIM}">{html.escape(extra["args"][:600])}\n-> '
                             f'{html.escape((extra["result"] or "")[:900])}</pre>')
                out.append(line)
        sb = self.view.verticalScrollBar()
        stick = sb.value() >= sb.maximum() - 20
        self.view.setHtml("".join(out))
        if stick:
            sb.setValue(sb.maximum())
