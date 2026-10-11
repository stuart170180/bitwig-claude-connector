"""One-line mastering advice from the live numbers (same rules as the old page)."""
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from bwapp import theme


class Advice(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.label = QLabel("Waiting for audio...")
        self.label.setWordWrap(True)
        self.label.setStyleSheet(f"color:{theme.DIM};font-size:13px")
        QVBoxLayout(self).addWidget(self.label)
        feed.frame.connect(self.update_frame)

    def update_frame(self, d):
        t = d.get("target") or {}
        mom = d.get("momentary")
        if mom is None or mom < -70:
            self.label.setText("No signal - press play in Bitwig.")
            return
        tips = []
        g = d.get("gain_to_target")
        if d.get("integrated") is not None and g is not None and abs(g) > 1:
            tips.append(f"<b>{'Raise' if g > 0 else 'Lower'} ~{abs(g):.1f} dB</b> to hit {t.get('lufs')} LUFS ({t.get('name')}).")
        if d.get("true_peak_max", -99) > t.get("tp", -1):
            tips.append(f"<b>True peak {d['true_peak_max']:.2f} dBTP</b> is over the {t.get('tp')} dBTP ceiling.")
        if d.get("correlation", 1) < 0.2:
            tips.append(f"<b>Low correlation ({d['correlation']:.2f})</b> - check mono compatibility.")
        if d.get("clipped_samples"):
            tips.append(f"<b>{d['clipped_samples']} clipped samples</b> since reset.")
        self.label.setText("  &middot;  ".join(tips) or "Within target. Integrated loudness and LRA build up over time - press Reset when you start a new pass.")
