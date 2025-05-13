import sys
import os
import json
import csv
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QFileDialog, QScrollArea,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QDialog, QComboBox,
    QMessageBox
)
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPen
from PyQt5.QtCore import Qt, QRectF
from PIL import Image

class TrimmingDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.trim_rect = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("画像トリミング")
        self.setGeometry(100, 100, 600, 600)
        layout = QVBoxLayout()

        # 画像表示
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        pixmap = QPixmap(self.image_path)
        self.pixmap_item = self.scene.addPixmap(pixmap.scaled(500, 500, Qt.KeepAspectRatio))
        layout.addWidget(self.view)

        # トリミング枠（固定100x100）
        self.rect_item = QGraphicsRectItem(0, 0, 100, 100)
        self.rect_item.setPen(QPen(Qt.red, 2))
        self.rect_item.setFlag(QGraphicsRectItem.ItemIsMovable)
        self.scene.addItem(self.rect_item)

        # ボタン
        trim_button = QPushButton("トリミング確定")
        trim_button.clicked.connect(self.accept)
        layout.addWidget(trim_button)

        self.setLayout(layout)

    def get_trim_rect(self):
        pos = self.rect_item.pos()
        return QRectF(pos.x(), pos.y(), 100, 100)

class CharacterRegisterWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel("画像をここにドロップ")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("border: 2px dashed gray; padding: 20px;")
        layout.addWidget(self.label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("人物名を入力")
        layout.addWidget(self.name_input)

        self.register_button = QPushButton("登録")
        self.register_button.clicked.connect(self.register_character)
        layout.addWidget(self.register_button)

        self.setLayout(layout)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self.image_path = urls[0].toLocalFile()
            pixmap = QPixmap(self.image_path).scaled(100, 100)
            self.label.setPixmap(pixmap)

    def register_character(self):
        if not hasattr(self, 'image_path') or not self.name_input.text():
            QMessageBox.warning(self, "エラー", "画像と人物名を入力してください")
            return
        # キャラ名のバリデーション
        char_name = self.name_input.text().strip()
        if not re.match(r'^[a-zA-Z0-9_]+$', char_name):
            QMessageBox.warning(self, "エラー", "人物名は英数字とアンダースコアのみ使用してください")
            return
        # トリミングダイアログを表示
        trim_dialog = TrimmingDialog(self.image_path, self)
        if trim_dialog.exec_():
            rect = trim_dialog.get_trim_rect()
            img = Image.open(self.image_path)
            # スケール計算
            pixmap_size = trim_dialog.pixmap_item.pixmap().size()
            img_scale = min(img.width / pixmap_size.width(), img.height / pixmap_size.height())
            crop_area = (
                int(rect.x() * img_scale), int(rect.y() * img_scale),
                int((rect.x() + rect.width()) * img_scale), int((rect.y() + rect.height()) * img_scale)
            )
            img = img.crop(crop_area)
            img = img.resize((100, 100))  # 最終リサイズ
            save_path = os.path.join("script_project", f"{char_name}.jpg")  # 拡張子修正
            os.makedirs("script_project", exist_ok=True)
            img.save(save_path, quality=85)
            self.parent.characters[char_name] = save_path
            self.parent.switch_to_main()

class ScriptWriterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.characters = {}  # {name: image_path}
        self.script = []  # セリフデータ
        self.dialogue_widgets = []  # (char_name, dialogue_input, image_label, char_combo)
        self.current_line = 1
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("台本作成アプリ")
        self.setGeometry(100, 100, 800, 600)

        # 中央ウィジェット
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.script_widget = QWidget()
        self.script_layout = QVBoxLayout(self.script_widget)
        self.scroll_area.setWidget(self.script_widget)
        self.main_layout.addWidget(self.scroll_area)

        # 追加ボタン
        self.add_button = QPushButton("+ セリフ追加")
        self.add_button.clicked.connect(self.add_dialogue)
        self.main_layout.addWidget(self.add_button)

        # メニューバー
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        save_action = file_menu.addAction("保存")
        save_action.triggered.connect(self.save_script)
        load_action = file_menu.addAction("ロード")
        load_action.triggered.connect(self.load_script)
        export_csv_action = file_menu.addAction("CSV出力")
        export_csv_action.triggered.connect(lambda: self.export_script("csv"))
        export_json_action = file_menu.addAction("JSON出力")
        export_json_action.triggered.connect(lambda: self.export_script("json"))
        register_action = file_menu.addAction("人物登録")
        register_action.triggered.connect(self.switch_to_register)

        # 初期画面は人物登録
        self.switch_to_register()

    def switch_to_register(self):
        self.central_widget = CharacterRegisterWidget(self)
        self.setCentralWidget(self.central_widget)

    def switch_to_main(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.script_widget = QWidget()
        self.script_layout = QVBoxLayout(self.script_widget)
        self.scroll_area.setWidget(self.script_widget)
        self.main_layout.addWidget(self.scroll_area)
        self.add_button = QPushButton("+ セリフ追加")
        self.add_button.clicked.connect(self.add_dialogue)
        self.main_layout.addWidget(self.add_button)
        # 既存のセリフを再描画（ロード時用）
        for dialogue in self.script:
            self.add_dialogue_from_data(dialogue)

    def add_dialogue(self):
        if not self.characters:
            QMessageBox.warning(self, "エラー", "先に人物を登録してください")
            return
        dialogue_widget = QWidget()
        dialogue_layout = QHBoxLayout(dialogue_widget)

        # キャラ選択
        char_combo = QComboBox()
        char_combo.addItems(self.characters.keys())
        char_combo.currentTextChanged.connect(
            lambda: self.update_character_image(dialogue_widget, char_combo.currentText())
        )
        dialogue_layout.addWidget(char_combo)

        # キャラ画像
        image_label = QLabel()
        image_label.setFixedSize(50, 50)
        char_name = char_combo.currentText()
        pixmap = QPixmap(self.characters[char_name]).scaled(50, 50) if char_name else QPixmap()
        image_label.setPixmap(pixmap)
        image_label.setStyleSheet("border: 1px solid gray;")
        image_label.mousePressEvent = lambda event: self.change_character(dialogue_widget, char_combo)
        dialogue_layout.addWidget(image_label)

        # セリフ入力
        dialogue_input = QTextEdit()
        dialogue_input.setFixedHeight(50)
        dialogue_layout.addWidget(dialogue_input)

        self.script_layout.addWidget(dialogue_widget)
        self.dialogue_widgets.append((char_name, dialogue_input, image_label, char_combo))

    def add_dialogue_from_data(self, dialogue):
        dialogue_widget = QWidget()
        dialogue_layout = QHBoxLayout(dialogue_widget)

        char_name = dialogue["character_name"]
        # キャラ選択
        char_combo = QComboBox()
        char_combo.addItems(self.characters.keys())
        char_combo.setCurrentText(char_name)
        char_combo.currentTextChanged.connect(
            lambda: self.update_character_image(dialogue_widget, char_combo.currentText())
        )
        dialogue_layout.addWidget(char_combo)

        # キャラ画像
        image_label = QLabel()
        image_label.setFixedSize(50, 50)
        image_path = os.path.join("script_project", dialogue["image_name"])
        pixmap = QPixmap(image_path).scaled(50, 50) if os.path.exists(image_path) else QPixmap()
        image_label.setPixmap(pixmap)
        image_label.setStyleSheet("border: 1px solid gray;")
        image_label.mousePressEvent = lambda event: self.change_character(dialogue_widget, char_combo)
        dialogue_layout.addWidget(image_label)

        dialogue_input = QTextEdit()
        dialogue_input.setFixedHeight(50)
        dialogue_input.setText(dialogue["dialogue"])
        dialogue_layout.addWidget(dialogue_input)

        self.script_layout.addWidget(dialogue_widget)
        self.dialogue_widgets.append((char_name, dialogue_input, image_label, char_combo))

    def update_character_image(self, dialogue_widget, char_name):
        for i, (name, input_widget, image_label, combo) in enumerate(self.dialogue_widgets):
            if combo == dialogue_widget.findChild(QComboBox):
                image_label.setPixmap(QPixmap(self.characters[char_name]).scaled(50, 50))
                self.dialogue_widgets[i] = (char_name, input_widget, image_label, combo)
                break

    def change_character(self, dialogue_widget, char_combo):
        char_combo.showPopup()  # コンボボックスを開く

    def save_script(self):
        self.script = []
        self.current_line = 1
        for char_name, dialogue_input, _, _ in self.dialogue_widgets:
            dialogue = dialogue_input.toPlainText()
            if dialogue:
                self.script.append({
                    "image_name": os.path.basename(self.characters[char_name]),
                    "character_name": char_name,
                    "line_number": self.current_line,
                    "dialogue": dialogue
                })
                self.current_line += 1
        file_name, _ = QFileDialog.getSaveFileName(self, "台本保存", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(self.script, f, ensure_ascii=False, indent=2)

    def load_script(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "台本ロード", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as f:
                self.script = json.load(f)
            self.dialogue_widgets = []
            self.current_line = max([d["line_number"] for d in self.script], default=0) + 1
            self.switch_to_main()

    def export_script(self, format_type):
        self.save_script()  # 現在のセリフをscriptに反映
        file_name, _ = QFileDialog.getSaveFileName(self, f"{format_type.upper()}出力", "", f"{format_type.upper()} Files (*.{format_type})")
        if file_name:
            if format_type == "json":
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(self.script, f, ensure_ascii=False, indent=2)
            elif format_type == "csv":
                with open(file_name, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=["image_name", "character_name", "line_number", "dialogue"])
                    writer.writeheader()
                    writer.writerows(self.script)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ScriptWriterWindow()
    window.show()
    sys.exit(app.exec_())