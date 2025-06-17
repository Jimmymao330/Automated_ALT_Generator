# -*- coding: utf-8 -*-
import sys
import os
import base64
import mimetypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QStackedWidget, QListWidget, QListWidgetItem, QLineEdit,
    QProgressBar, QScrollArea, QTabWidget, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QObject
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QIcon, QImage

from bs4 import BeautifulSoup
from groq import Groq

# ##############################################################################
# ##                          請在此處填寫您的 API KEY                          ##
# ##############################################################################
# 前往 https://console.groq.com/keys 取得您的 API Key
GROQ_API_KEY = "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"
# ##############################################################################
# ##                                API KEY 結束                               ##
# ##############################################################################

# --- 色彩與樣式設定 ---
class StyleConfig:
    MAIN_BG = "#FFFFFF"
    PRIMARY_GRAY = "#575757"
    SECONDARY_GRAY = "#9a9a9a"
    LIGHT_GRAY = "#c2c2c2"
    CONFIRM_GREEN = "#1ba400"
    CANCEL_RED = "#ff3939"
    MODE_BLUE = "#39a9ff"
    DISABLED_GRAY = "#8e8e8e"
    TEXT_DARK = "#000000"
    TEXT_LIGHT = "#FFFFFF"

    @staticmethod
    def get_stylesheet():
        return f"""
            QWidget {{
                font-family: 'Microsoft JhengHei UI', '微軟正黑體', sans-serif;
                color: {StyleConfig.TEXT_DARK};
            }}
            QMainWindow, QDialog {{
                background-color: {StyleConfig.MAIN_BG};
            }}
            QLabel#TitleLabel {{
                font-size: 28px;
                font-weight: bold;
                color: {StyleConfig.PRIMARY_GRAY};
                padding: 10px;
            }}
            QLabel#DropAreaLabel {{
                border: 2px dashed {StyleConfig.LIGHT_GRAY};
                border-radius: 10px;
                background-color: #f9f9f9;
                font-size: 16px;
                color: {StyleConfig.SECONDARY_GRAY};
            }}
            QLabel#FileListLabel {{
                font-size: 12px;
                color: {StyleConfig.PRIMARY_GRAY};
                padding: 5px 15px;
            }}
            QPushButton {{
                font-size: 14px;
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid {StyleConfig.LIGHT_GRAY};
            }}
            QPushButton:disabled {{
                background-color: {StyleConfig.DISABLED_GRAY};
                color: {StyleConfig.TEXT_LIGHT};
                border-color: {StyleConfig.DISABLED_GRAY};
            }}
            QPushButton#ConfirmButton {{
                background-color: {StyleConfig.CONFIRM_GREEN};
                color: {StyleConfig.TEXT_LIGHT};
                border: none;
            }}
            QPushButton#CancelButton {{
                background-color: {StyleConfig.CANCEL_RED};
                color: {StyleConfig.TEXT_LIGHT};
                border: none;
            }}
            QPushButton#ModeButton {{
                background-color: {StyleConfig.MODE_BLUE};
                color: {StyleConfig.TEXT_LIGHT};
                border: 2px solid {StyleConfig.MODE_BLUE};
            }}
            QPushButton#ModeButton:checked {{
                border: 3px solid {StyleConfig.CONFIRM_GREEN};
            }}
            QPushButton#SelectFileButton {{
                background-color: #f0f0f0;
                border: 1px solid {StyleConfig.LIGHT_GRAY};
            }}
            QLineEdit {{
                border: 1px solid {StyleConfig.LIGHT_GRAY};
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                background-color: {StyleConfig.MAIN_BG};
            }}
            QProgressBar {{
                border: 1px solid {StyleConfig.SECONDARY_GRAY};
                border-radius: 5px;
                text-align: center;
                color: {StyleConfig.TEXT_DARK};
            }}
            QProgressBar::chunk {{
                background-color: {StyleConfig.MODE_BLUE};
                border-radius: 5px;
            }}
            QTabWidget::pane {{
                border-top: 2px solid {StyleConfig.LIGHT_GRAY};
            }}
            QTabBar::tab {{
                background: #e0e0e0;
                border: 1px solid {StyleConfig.LIGHT_GRAY};
                border-bottom: none;
                padding: 10px 15px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                margin-right: 2px;
                color: {StyleConfig.PRIMARY_GRAY};
            }}
            QTabBar::tab:selected {{
                background: {StyleConfig.MAIN_BG};
                color: {StyleConfig.TEXT_DARK};
                font-weight: bold;
            }}
            QScrollArea {{
                border: none;
            }}
        """

# --- AI Worker (執行緒) ---
class GroqWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, images_to_process, html_path):
        super().__init__()
        self.images_to_process = images_to_process
        self.html_path = html_path
        self.client = None

    def run(self):
        if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY":
            self.error.emit("錯誤：尚未設定 Groq API Key。")
            return

        try:
            self.client = Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            self.error.emit(f"API 客戶端初始化失敗: {e}")
            return
            
        results = []
        total_images = len(self.images_to_process)

        for i, (tag, img_path) in enumerate(self.images_to_process):
            self.progress.emit(int((i / total_images) * 100), f"正在處理圖片 {i+1}/{total_images}...")
            
            # 建立圖片的絕對路徑
            if not os.path.isabs(img_path):
                img_full_path = os.path.join(os.path.dirname(self.html_path), img_path)
            else:
                img_full_path = img_path

            if not os.path.exists(img_full_path):
                alt_text = "錯誤：找不到圖片檔案"
                results.append((tag, img_path, alt_text))
                continue

            try:
                # 讀取圖片並轉為 Base64
                mime_type, _ = mimetypes.guess_type(img_full_path)
                if not mime_type or not mime_type.startswith('image'):
                    raise ValueError("不支援的檔案類型")

                with open(img_full_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

                prompt_text = """
## 任務與目的
* 為這張圖片生成一段符合 WCAG 2.1 AA 級無障礙標準的 alt 敘述。
* 這段敘述應該簡潔、準確地描述圖片的內容與功能。
* 請直接輸出描述文字，不要包含 "alt=" 或任何額外的引號或標籤。

## 範例
* 好的範例: "一位穿著紅色外套的女士正在公園裡遛狗。"
* 不好的範例: "圖片", "照片", "alt='女士遛狗'"
"""
                
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                    model="llama3-70b-8192",
                )
                alt_text = chat_completion.choices[0].message.content.strip()
                results.append((tag, img_path, alt_text))

            except Exception as e:
                error_msg = f"圖片 '{os.path.basename(img_path)}' 處理失敗: {e}"
                self.error.emit(error_msg)
                results.append((tag, img_path, f"AI生成失敗: {e}"))

        self.progress.emit(100, "所有圖片處理完成！")
        self.finished.emit(results)

# --- 圖片預覽 Dialog ---
class ImagePreviewDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("圖片預覽")
        self.layout = QVBoxLayout(self)
        
        self.label = QLabel()
        self.label.setPixmap(pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        self.layout.addWidget(self.label)
        self.setFixedSize(self.label.pixmap().size())

# --- 列表中的自訂 Widget ---
class ImageAltItemWidget(QWidget):
    text_changed = pyqtSignal()
    
    def __init__(self, tag, image_path, html_path, alt_text="", parent=None):
        super().__init__(parent)
        self.tag = tag
        self.image_path = image_path
        self.html_path = html_path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 圖片預覽
        self.image_label = QLabel()
        self.image_label.setFixedSize(100, 100)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if not os.path.isabs(image_path):
            full_img_path = os.path.join(os.path.dirname(html_path), image_path)
        else:
            full_img_path = image_path

        self.pixmap = QPixmap(full_img_path)
        if self.pixmap.isNull():
            self.image_label.setText("圖片載入失敗")
        else:
            self.image_label.setPixmap(self.pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        self.image_label.mousePressEvent = self.show_full_image
        layout.addWidget(self.image_label)

        # ALT 輸入框
        self.alt_input = QLineEdit()
        self.alt_input.setPlaceholderText("請輸入此圖片的 ALT 敘述...")
        self.alt_input.setText(alt_text)
        self.alt_input.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self.alt_input)
        
        self.setLayout(layout)

    def show_full_image(self, event):
        if not self.pixmap.isNull():
            dialog = ImagePreviewDialog(self.pixmap, self)
            dialog.exec()

    def get_data(self):
        return self.tag, self.alt_input.text()

# --- 檔案拖曳區 Widget ---
class DropArea(QLabel):
    files_dropped = pyqtSignal(list)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DropAreaLabel")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        self.files_dropped.emit(urls)

# --- 首頁 ---
class HomePageWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files = []
        self.selected_mode = None # "manual" or "auto"
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(20)

        # 標題
        title_label = QLabel("自動網頁ALT生成系統")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 拖曳區
        self.drop_area = DropArea("將檔案或資料夾拖曳至此")
        self.drop_area.setMinimumHeight(200)
        self.drop_area.files_dropped.connect(self.handle_files)
        
        drop_layout = QVBoxLayout(self.drop_area)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_list_label = QLabel("尚未選擇任何檔案")
        self.file_list_label.setObjectName("FileListLabel")
        self.file_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.select_file_btn = QPushButton("選擇檔案或資料夾")
        self.select_file_btn.setObjectName("SelectFileButton")
        self.select_file_btn.setFixedSize(200, 50)
        self.select_file_btn.clicked.connect(self.open_file_dialog)

        drop_layout.addWidget(self.file_list_label)
        drop_layout.addStretch()
        drop_layout.addWidget(self.select_file_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addStretch()

        layout.addWidget(self.drop_area)

        # 模式選擇
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(15)
        self.manual_btn = QPushButton("手動生成 ALT")
        self.manual_btn.setObjectName("ModeButton")
        self.manual_btn.setCheckable(True)
        self.manual_btn.clicked.connect(lambda: self.set_mode("manual"))
        
        self.auto_btn = QPushButton("自動生成 ALT")
        self.auto_btn.setObjectName("ModeButton")
        self.auto_btn.setCheckable(True)
        self.auto_btn.clicked.connect(lambda: self.set_mode("auto"))
        
        mode_layout.addWidget(self.manual_btn)
        mode_layout.addWidget(self.auto_btn)
        layout.addLayout(mode_layout)

        # 確認按鈕
        self.confirm_btn = QPushButton("確認")
        self.confirm_btn.setObjectName("ConfirmButton")
        self.confirm_btn.setEnabled(False)
        layout.addWidget(self.confirm_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def open_file_dialog(self):
        # 允許使用者同時選擇檔案和資料夾
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        # 為了讓使用者能選資料夾，我們提供一個選項
        # 這是一個小技巧，因為QT原生對話框通常不同時支援檔案和資料夾
        # 我們用一個按鈕來切換
        # 但更簡單的方式是提示使用者
        file_path, _ = QFileDialog.getOpenFileNames(self, "選擇 HTML 檔案", "", "HTML Files (*.html *.htm)")
        if file_path:
             self.handle_files(file_path)
        else: # 如果使用者取消了檔案選擇，再讓他選資料夾
            dir_path = QFileDialog.getExistingDirectory(self, "選擇資料夾")
            if dir_path:
                self.handle_files([dir_path])

    def handle_files(self, paths):
        html_files = []
        for path in paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(('.html', '.htm')):
                            html_files.append(os.path.join(root, file))
            elif os.path.isfile(path) and path.lower().endswith(('.html', '.htm')):
                html_files.append(path)
        
        if not html_files:
            QMessageBox.warning(self, "格式錯誤", "您拖曳或選擇的項目中不包含任何有效的 HTML 檔案 (.html, .htm)。")
            return

        self.selected_files = html_files
        if len(self.selected_files) > 1:
            self.file_list_label.setText(f"已選擇 {len(self.selected_files)} 個檔案")
        elif self.selected_files:
            self.file_list_label.setText(f"已選擇: {os.path.basename(self.selected_files[0])}")
        
        self.update_confirm_button_state()
        
    def set_mode(self, mode):
        self.selected_mode = mode
        if mode == "manual":
            self.auto_btn.setChecked(False)
        else:
            self.manual_btn.setChecked(False)
        self.update_confirm_button_state()

    def update_confirm_button_state(self):
        if self.selected_files and self.selected_mode:
            self.confirm_btn.setEnabled(True)
        else:
            self.confirm_btn.setEnabled(False)

    def reset_state(self):
        self.selected_files = []
        self.selected_mode = None
        self.file_list_label.setText("尚未選擇任何檔案")
        self.manual_btn.setChecked(False)
        self.auto_btn.setChecked(False)
        self.confirm_btn.setEnabled(False)

# --- 編輯頁面 ---
class EditPageWidget(QWidget):
    back_to_home = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self.mode = ""
        self.html_soups = {} # {filepath: BeautifulSoup object}
        self.all_list_items = {} # {tab_index: [ImageAltItemWidget]}
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        self.title_label = QLabel("")
        self.title_label.setObjectName("TitleLabel")
        self.main_layout.addWidget(self.title_label)

        # 進度條 (自動模式用)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {StyleConfig.CANCEL_RED};")
        self.error_label.setVisible(False)
        self.main_layout.addWidget(self.error_label)
        
        # 分頁
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True) # 讓macOS樣式更好看
        self.main_layout.addWidget(self.tab_widget)

        # 底部按鈕
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.confirm_all_btn = QPushButton("確認修改全部")
        self.confirm_all_btn.setObjectName("ConfirmButton")
        self.confirm_all_btn.clicked.connect(self.save_all_files)
        self.confirm_all_btn.setEnabled(False)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("CancelButton")
        self.cancel_btn.clicked.connect(self.go_back)

        bottom_layout.addWidget(self.cancel_btn)
        bottom_layout.addWidget(self.confirm_all_btn)
        self.main_layout.addLayout(bottom_layout)

    def load_files(self, files, mode):
        self.reset_state()
        self.files = files
        self.mode = mode
        title_prefix = "手動生成 ALT" if mode == "manual" else "自動生成 ALT"
        self.title_label.setText(title_prefix)

        if not self.files:
            self.go_back()
            return
            
        for file_path in self.files:
            self._add_tab_for_file(file_path)

        if self.mode == "auto":
            self.process_files_auto()
        else: # manual
            self.process_files_manual()

    def _add_tab_for_file(self, file_path):
        tab_name = os.path.splitext(os.path.basename(file_path))[0]
        tab_content_widget = QWidget()
        tab_layout = QVBoxLayout(tab_content_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        list_container = QWidget()
        self.list_layout = QVBoxLayout(list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(list_container)
        tab_layout.addWidget(scroll_area)

        # "確認修改此檔案" 按鈕
        if len(self.files) > 1:
            confirm_this_btn = QPushButton("確認修改此檔案")
            confirm_this_btn.setObjectName("ConfirmButton")
            confirm_this_btn.setEnabled(False)
            # 使用 lambda 捕捉當前的 tab_content_widget
            confirm_this_btn.clicked.connect(lambda ch, w=list_container, p=file_path, b=confirm_this_btn: self.save_single_file(w, p, b))
            tab_layout.addWidget(confirm_this_btn, alignment=Qt.AlignmentFlag.AlignRight)
            
            # 將按鈕與其對應的列表容器關聯起來
            list_container.setProperty("confirm_button", confirm_this_btn)

        self.tab_widget.addTab(tab_content_widget, tab_name)
        
        # 存儲佈局以便後續添加項目
        tab_index = self.tab_widget.indexOf(tab_content_widget)
        self.all_list_items[tab_index] = []
        tab_content_widget.setProperty("list_layout", self.list_layout)
        tab_content_widget.setProperty("file_path", file_path)


    def process_files_manual(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            file_path = tab.property("file_path")
            images_to_process = self._parse_html(file_path)
            
            if images_to_process:
                self.populate_ui_for_tab(i, images_to_process)
            else:
                 self._handle_no_images_found(i)

    def process_files_auto(self):
        # 暫時禁用所有互動
        self.tab_widget.setEnabled(False)
        self.confirm_all_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.error_label.setVisible(False)
        self.error_label.setText("")

        # 這裡我們一次只處理一個檔案的AI請求來簡化流程
        # 如果需要並行處理，需要更複雜的執行緒管理
        self.current_auto_processing_tab = 0
        self._start_next_auto_job()

    def _start_next_auto_job(self):
        if self.current_auto_processing_tab >= self.tab_widget.count():
            # 所有檔案處理完成
            self.progress_bar.setVisible(False)
            self.tab_widget.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            # 檢查是否有可儲存的項目
            self.check_any_item_changed()
            return
            
        tab_index = self.current_auto_processing_tab
        tab = self.tab_widget.widget(tab_index)
        file_path = tab.property("file_path")
        self.tab_widget.setCurrentIndex(tab_index)

        images_to_process = self._parse_html(file_path)

        if not images_to_process:
            self._handle_no_images_found(tab_index)
            self.current_auto_processing_tab += 1
            self._start_next_auto_job()
            return

        self.worker = GroqWorker(images_to_process, file_path)
        self.worker.progress.connect(self.update_progress)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.on_auto_finished)
        self.worker.start()

    def on_auto_finished(self, results):
        tab_index = self.current_auto_processing_tab
        # 將結果轉換為與手動模式相同的格式
        processed_data = [(tag, img_path, alt) for tag, img_path, alt in results]
        self.populate_ui_for_tab(tab_index, processed_data, is_auto=True)
        
        self.current_auto_processing_tab += 1
        self._start_next_auto_job()

    def _parse_html(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                self.html_soups[file_path] = soup
            
            images_to_process = []
            img_tags = soup.find_all('img')
            for tag in img_tags:
                alt = tag.get('alt', None)
                if alt is None or alt.strip() == "":
                    src = tag.get('src')
                    if src:
                        images_to_process.append((tag, src))
            return images_to_process
        except Exception as e:
            self.show_error(f"解析檔案 {os.path.basename(file_path)} 失敗: {e}")
            return []
    
    def _handle_no_images_found(self, tab_index):
        tab = self.tab_widget.widget(tab_index)
        list_layout = tab.property("list_layout")
        no_img_label = QLabel("此檔案中所有圖片均符合標準或已包含 ALT 敘述。")
        no_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_layout.addWidget(no_img_label)
        
        # 禁用單檔儲存按鈕
        confirm_this_btn = tab.findChild(QPushButton, "ConfirmButton")
        if confirm_this_btn:
            confirm_this_btn.setEnabled(False)


    def populate_ui_for_tab(self, tab_index, images_data, is_auto=False):
        tab = self.tab_widget.widget(tab_index)
        list_layout = tab.property("list_layout")
        file_path = tab.property("file_path")

        for item_data in images_data:
            if is_auto:
                tag, img_path, alt_text = item_data
            else:
                tag, img_path = item_data
                alt_text = ""

            item_widget = ImageAltItemWidget(tag, img_path, file_path, alt_text)
            item_widget.text_changed.connect(self.check_any_item_changed)
            
            list_layout.addWidget(item_widget)
            self.all_list_items[tab_index].append(item_widget)
        
        self.check_any_item_changed()

    def update_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(text)

    def show_error(self, message):
        self.error_label.setVisible(True)
        current_text = self.error_label.text()
        self.error_label.setText(current_text + message + "\n")

    def check_any_item_changed(self):
        any_items_exist = False
        
        # 檢查並更新 "確認修改此檔案" 按鈕
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            list_container = tab.findChild(QWidget)
            if list_container:
                confirm_btn = list_container.property("confirm_button")
                if confirm_btn:
                    # 如果該分頁下有任何列表項，則啟用按鈕
                    if len(self.all_list_items.get(i, [])) > 0:
                        confirm_btn.setEnabled(True)
                        any_items_exist = True
                    else:
                        confirm_btn.setEnabled(False)

        # 檢查並更新 "確認修改全部" 按鈕
        # 如果任何一個分頁有列表項，就啟用 "確認修改全部"
        if any(len(items) > 0 for items in self.all_list_items.values()):
             self.confirm_all_btn.setEnabled(True)
        else:
             self.confirm_all_btn.setEnabled(False)

    def save_single_file(self, list_container, file_path, button):
        tab_index = self.tab_widget.currentIndex()
        item_widgets = self.all_list_items.get(tab_index, [])
        
        if not item_widgets:
            return

        soup = self.html_soups.get(file_path)
        if not soup:
            QMessageBox.critical(self, "錯誤", f"找不到檔案 {os.path.basename(file_path)} 的解析資料。")
            return
            
        for item in item_widgets:
            tag, alt_text = item.get_data()
            tag['alt'] = alt_text

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # 清空列表
            for item in reversed(item_widgets):
                item.deleteLater()
            self.all_list_items[tab_index].clear()
            
            QMessageBox.information(self, "成功", f"檔案 {os.path.basename(file_path)} 已成功更新。")
            button.setEnabled(False)
            self.check_any_item_changed()

        except Exception as e:
            QMessageBox.critical(self, "儲存失敗", f"寫入檔案 {os.path.basename(file_path)} 時發生錯誤: {e}")

    def save_all_files(self):
        error_files = []
        success_count = 0
        
        for i in range(self.tab_widget.count()):
            file_path = self.tab_widget.widget(i).property("file_path")
            item_widgets = self.all_list_items.get(i, [])
            soup = self.html_soups.get(file_path)
            
            if not soup or not item_widgets:
                continue

            for item in item_widgets:
                tag, alt_text = item.get_data()
                # 在 soup 物件中找到對應的 tag 並修改
                # 由於 tag 物件是可變的，之前的修改應該已經生效
                tag['alt'] = alt_text

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                success_count += 1
            except Exception as e:
                error_files.append(f"{os.path.basename(file_path)}: {e}")

        if error_files:
            QMessageBox.warning(self, "部分儲存失敗", f"成功儲存 {success_count} 個檔案。\n以下檔案儲存失敗：\n" + "\n".join(error_files))
        else:
            QMessageBox.information(self, "成功", f"全部 {success_count} 個檔案皆已成功更新。")
            
        self.go_back()

    def go_back(self):
        # 詢問使用者是否確定要放棄變更
        if any(len(items) > 0 for items in self.all_list_items.values()):
            reply = QMessageBox.question(self, '確認取消', 
                                         '您有尚未儲存的修改，確定要放棄並返回首頁嗎？',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
                
        self.back_to_home.emit()

    def reset_state(self):
        self.tab_widget.clear()
        self.files = []
        self.html_soups.clear()
        self.all_list_items.clear()
        self.confirm_all_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.error_label.setVisible(False)
        self.error_label.setText("")
        # 確保 worker 停止
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()


# --- 主視窗 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自動網頁ALT生成系統")
        self.setMinimumSize(800, 600)
        self.setWindowIcon(QIcon(self.create_icon()))

        # 設置樣式表
        self.setStyleSheet(StyleConfig.get_stylesheet())

        # 主容器和堆疊窗口
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # 創建頁面
        self.home_page = HomePageWidget()
        self.edit_page = EditPageWidget()

        # 添加頁面到堆疊窗口
        self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.edit_page)

        # 連接信號
        self.home_page.confirm_btn.clicked.connect(self.go_to_edit_page)
        self.edit_page.back_to_home.connect(self.go_to_home_page)

    def go_to_edit_page(self):
        files = self.home_page.selected_files
        mode = self.home_page.selected_mode
        if files and mode:
            self.edit_page.load_files(files, mode)
            self.stacked_widget.setCurrentWidget(self.edit_page)
        else:
             QMessageBox.warning(self, "資訊不完整", "請先選擇檔案並選擇一個生成模式。")


    def go_to_home_page(self):
        self.home_page.reset_state()
        self.stacked_widget.setCurrentWidget(self.home_page)

    def create_icon(self):
        # 創建一個簡單的程式圖標
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # 簡單畫一個 'A+'
        img = QImage(pixmap.toImage())
        from PyQt6.QtGui import QPainter, QFont, QColor
        
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        p.setBrush(QColor(StyleConfig.MODE_BLUE))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 60, 60)
        
        # 文字
        font = QFont("Arial", 30, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(StyleConfig.TEXT_LIGHT))
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, "A⁺")
        p.end()

        return QIcon(QPixmap.fromImage(img))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())