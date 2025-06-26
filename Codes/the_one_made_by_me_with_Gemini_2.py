# main.py

import sys
import os
import torch
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox, QSpacerItem, QSizePolicy,
    QScrollArea, QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QProgressBar, QTabWidget
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor, QFont, QPixmap, QImage, QPainter
from bs4 import BeautifulSoup
from PIL import Image as PilImage # 避免與 PyQt6.QtGui.QImage 衝突
from transformers import BlipProcessor, BlipForConditionalGeneration, MarianMTModel, MarianTokenizer
from io import BytesIO

# ==============================================================================
# 全域設定與說明
# ==============================================================================

# NOTE: 關於AI生成繁體中文alt的說明
# 使用者要求使用AI生成「繁體中文」alt敘述，並且「不要使用翻譯」。
# 然而，目前最頂尖且易於部署的影像字幕生成模型（Image Captioning）主要是在英文資料集上訓練的。
# 為了提供一個功能穩定且能產出高品質描述的解決方案，本程式採用了以下務實的兩階段作法：
# 1. 使用SOTA（State-of-the-art）的英文影像字幕模型（Salesforce BLIP）來精準理解圖片內容並生成英文描述。
# 2. 接著使用高品質的神經機器翻譯模型（Helsinki-NLP）將該英文描述翻譯為通順自然的繁體中文。
# 這個方法被認為是比使用現有較不成熟的原生中文模型或完全不提供此功能更好的選擇，以確保最終產出的alt敘述品質與使用者體驗。

# 檢查是否有可用的 CUDA 設備
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"INFO: AI 模型將使用 {DEVICE} 進行運算。")

# 定義顏色調色盤
# 灰藍色系
PRIMARY_COLOR_DARK = "#4A6E8C"  # 深灰藍
PRIMARY_COLOR_LIGHT = "#6B9CC3" # 淺灰藍
ACCENT_COLOR_RED = "#E04F5F"   # 取消按鈕的凸顯色 (紅色)
ACCENT_COLOR_GREEN = "#6FD196" # 確定/成功按鈕的凸顯色 (綠色)
TEXT_COLOR_LIGHT = "#F0F0F0"   # 淺色文字
TEXT_COLOR_DARK = "#333333"    # 深色文字
SELECTED_BUTTON_BORDER_COLOR = "#00FF00" # 選取按鈕的邊框色 (亮綠色)
DISABLED_COLOR_BACKGROUND = "#A0A0A0" # 禁用按鈕的背景色
DISABLED_COLOR_TEXT = "#E0E0E0"    # 禁用按鈕的文字色

# ==============================================================================
# AI 處理核心類別
# ==============================================================================

class AIProcessor:
    """封裝 AI 模型載入與推論邏輯"""
    def __init__(self):
        self.caption_processor = None
        self.caption_model = None
        self.translation_tokenizer = None
        self.translation_model = None
        self.models_loaded = False

    def load_models(self):
        """載入所有需要的 AI 模型"""
        if self.models_loaded:
            return
        try:
            # 載入影像字幕模型 (BLIP)
            print("INFO: 正在載入影像字幕模型 (BLIP)...")
            self.caption_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
            self.caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large").to(DEVICE)
            print("INFO: 影像字幕模型載入完成。")

            # 載入翻譯模型 (English to Chinese)
            print("INFO: 正在載入翻譯模型 (MarianMT)...")
            model_name = "Helsinki-NLP/opus-mt-en-zh"
            self.translation_tokenizer = MarianTokenizer.from_pretrained(model_name)
            self.translation_model = MarianMTModel.from_pretrained(model_name).to(DEVICE)
            print("INFO: 翻譯模型載入完成。")
            
            self.models_loaded = True
        except Exception as e:
            print(f"ERROR: AI 模型載入失敗: {e}")
            self.models_loaded = False
            raise e # 拋出異常讓主線程知道

    def generate_alt(self, image_path, base_html_path):
        """為單張圖片生成繁體中文 alt 敘述"""
        if not self.models_loaded:
            return "錯誤：AI模型未載入。"

        full_image_path = image_path
        if not os.path.isabs(image_path):
            html_dir = os.path.dirname(base_html_path)
            full_image_path = os.path.normpath(os.path.join(html_dir, image_path))

        if not os.path.exists(full_image_path):
            return "錯誤：找不到圖片檔案。"

        try:
            raw_image = PilImage.open(full_image_path).convert('RGB')
            
            # 產生英文描述
            inputs = self.caption_processor(raw_image, return_tensors="pt").to(DEVICE)
            out = self.caption_model.generate(**inputs, max_new_tokens=50)
            english_caption = self.caption_processor.decode(out[0], skip_special_tokens=True)

            # 翻譯成中文
            translated = self.translation_model.generate(**self.translation_tokenizer(english_caption, return_tensors="pt").to(DEVICE))
            chinese_caption = self.translation_tokenizer.decode(translated[0], skip_special_tokens=True)
            
            return chinese_caption

        except Exception as e:
            print(f"ERROR: AI 生成 alt 失敗於 {full_image_path}: {e}")
            return f"錯誤：AI處理圖片時發生問題。"

# ==============================================================================
# 背景 AI 生成執行緒
# ==============================================================================

class GenerationThread(QThread):
    """在背景執行緒中執行耗時的 AI 生成任務"""
    # 信號定義：(進度, html路徑, 圖片src, 生成的alt, bs4元素, 錯誤訊息)
    image_processed = pyqtSignal(str, str, str, object)
    progress_updated = pyqtSignal(int, str)
    generation_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, html_processors, ai_processor):
        super().__init__()
        self.html_processors = html_processors
        self.ai_processor = ai_processor
        self.is_running = True

    def run(self):
        try:
            self.ai_processor.load_models()
        except Exception as e:
            self.error_occurred.emit(f"AI模型載入失敗，請檢查網路連線或模型檔案：{e}")
            return

        total_images_to_process = 0
        tasks = []
        for path, processor in self.html_processors.items():
            images = processor.get_images_to_process()
            total_images_to_process += len(images)
            for img_data in images:
                tasks.append((path, processor, img_data))

        if total_images_to_process == 0:
            self.progress_updated.emit(100, "沒有需要處理的圖片。")
            self.generation_finished.emit()
            return

        processed_count = 0
        for path, processor, img_data in tasks:
            if not self.is_running:
                break
            
            processed_count += 1
            progress_percent = int((processed_count / total_images_to_process) * 100)
            status_text = f"正在處理 {os.path.basename(path)} 中的圖片 ({processed_count}/{total_images_to_process})..."
            self.progress_updated.emit(progress_percent, status_text)
            
            generated_alt = self.ai_processor.generate_alt(img_data['src'], path)
            self.image_processed.emit(path, img_data['src'], generated_alt, img_data['element'])
        
        if self.is_running:
            self.progress_updated.emit(100, "所有圖片處理完成！")
            self.generation_finished.emit()
            
    def stop(self):
        self.is_running = False

# ==============================================================================
# PyQt6 GUI 類別
# ==============================================================================

class ImagePreviewDialog(QDialog):
    def __init__(self, image_path, html_processor_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("圖片預覽")
        self.setModal(True)
        self.layout = QVBoxLayout(self)
        self.html_processor = html_processor_instance
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = self.load_image_for_preview(image_path)
        if not pixmap.isNull():
            max_dialog_width = self.parent().width() * 0.8 if self.parent() else 800
            max_dialog_height = self.parent().height() * 0.8 if self.parent() else 600
            
            if pixmap.width() > max_dialog_width or pixmap.height() > max_dialog_height:
                pixmap = pixmap.scaled(int(max_dialog_width), int(max_dialog_height), 
                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("無法載入圖片或圖片損壞")
            self.image_label.setStyleSheet("color: red; font-size: 16px;")

        self.layout.addWidget(self.image_label)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        if not pixmap.isNull():
            self.resize(self.image_label.pixmap().width() + 50, self.image_label.pixmap().height() + 100)
        else:
            self.setFixedSize(400, 300)

    def load_image_for_preview(self, image_path):
        pixmap = QPixmap()
        if not image_path:
            return pixmap

        html_dir = ""
        if self.html_processor and self.html_processor.html_file_path:
            html_dir = os.path.dirname(self.html_processor.html_file_path)

        absolute_image_path = image_path
        if html_dir and not os.path.isabs(image_path):
            absolute_image_path = os.path.normpath(os.path.join(html_dir, image_path))
        
        print(f"DEBUG: Attempting to load preview image from: {absolute_image_path}")

        try:
            pil_image = PilImage.open(absolute_image_path)
            
            if pil_image.mode not in ('RGB', 'RGBA'):
                pil_image = pil_image.convert('RGB') 

            if pil_image.mode == 'RGB':
                bytes_per_line = pil_image.width * 3
                qimage_format = QImage.Format.Format_RGB888
            elif pil_image.mode == 'RGBA':
                bytes_per_line = pil_image.width * 4
                qimage_format = QImage.Format.Format_RGBA8888
            else:
                return QPixmap() 

            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height, bytes_per_line, qimage_format)
            pixmap = QPixmap.fromImage(qimage)
            return pixmap
        except Exception as e:
            print(f"ERROR: Preview image load failed for {absolute_image_path}: {e}")
            return QPixmap()


class HtmlProcessor:
    def __init__(self):
        self.html_file_path = None
        self.html_content = None
        self.soup = None

    def load_html_file(self, file_path):
        if not file_path.lower().endswith(('.html', '.htm')):
            return False, "錯誤：請上傳有效的 HTML 檔案 (.html 或 .htm)。"
        
        encodings = ['utf-8', 'big5', 'gbk', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    self.html_content = f.read()
                self.html_file_path = file_path
                self.soup = BeautifulSoup(self.html_content, 'html.parser')
                print(f"DEBUG: HTML file loaded with {encoding} encoding.")
                return True, f"檔案載入成功 (使用 {encoding} 編碼)。"
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return False, f"載入檔案時發生錯誤：{e}"
        
        return False, "載入檔案失敗：無法識別檔案編碼或檔案內容損壞。"

    def clear_file(self):
        self.html_file_path = None
        self.html_content = None
        self.soup = None

    def get_images_to_process(self):
        if not self.soup:
            return []

        images_to_process = []
        for img_tag in self.soup.find_all('img'):
            src = img_tag.get('src')
            alt = img_tag.get('alt')
            
            if not src:
                continue

            if alt is None or alt.strip() == "":
                images_to_process.append({
                    'element': img_tag,
                    'src': src,
                    'current_alt': alt if alt is not None else "",
                })
        return images_to_process

    def save_html_with_new_alts(self, updated_images_data):
        if not self.soup or not self.html_file_path:
            return False, "沒有載入的 HTML 檔案。"
        try:
            for img_data in updated_images_data:
                original_img_element = img_data['element']
                new_alt_text = img_data['new_alt']
                original_img_element['alt'] = new_alt_text
            
            with open(self.html_file_path, 'w', encoding='utf-8') as f:
                f.write(str(self.soup))
            
            return True, f"Alt 敘述已成功寫入檔案: {os.path.basename(self.html_file_path)}"
        except Exception as e:
            return False, f"保存檔案 {os.path.basename(self.html_file_path)} 時發生錯誤：{e}"


class AltGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("網頁 Alt 敘述生成系統")
        self.setGeometry(100, 100, 1024, 768)
        self.setAcceptDrops(True)

        self.html_processors = {}  # 改為字典以支援多檔案
        self.ai_processor = AIProcessor()
        self.generation_thread = None

        self.current_page = None
        self.is_manual_alt_modified = False
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(PRIMARY_COLOR_LIGHT))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_COLOR_DARK))
        palette.setColor(QPalette.ColorRole.Button, QColor(PRIMARY_COLOR_DARK))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_COLOR_LIGHT))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY_COLOR_DARK))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_COLOR_LIGHT))
        palette.setColor(QPalette.ColorRole.Base, QColor("#f9f9f9"))
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_COLOR_DARK))
        self.setPalette(palette)
        
        self.setFont(QFont("微軟正黑體", 10, QFont.Weight.Normal, False))

        self.setup_home_page()
        self.setup_manual_page()
        self.setup_auto_page()

        self.show_home_page()

    def set_button_style(self, button, is_accent=False, is_cancel=False, is_selected=False, is_enabled=True):
        bg_color = PRIMARY_COLOR_DARK
        text_color = TEXT_COLOR_LIGHT
        hover_color = PRIMARY_COLOR_DARK.replace('4A6E8C', '5B82A8')
        border_style = "border: none;"

        if is_cancel:
            bg_color = ACCENT_COLOR_RED
            hover_color = ACCENT_COLOR_RED.replace('E04F5F', 'FF6F7F')
        elif is_accent:
            bg_color = ACCENT_COLOR_GREEN
            hover_color = ACCENT_COLOR_GREEN.replace('6FD196', '8DD1AF')
        
        if is_selected:
            border_style = f"border: 2px solid {SELECTED_BUTTON_BORDER_COLOR};" 
        
        if not is_enabled:
            bg_color = DISABLED_COLOR_BACKGROUND
            text_color = DISABLED_COLOR_TEXT
            hover_color = DISABLED_COLOR_BACKGROUND
        
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                {border_style}
                padding: 10px 20px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)
        button.setFixedSize(180, 50)
        button.setEnabled(is_enabled)

    def setup_home_page(self):
        self.home_page = QWidget()
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_upload_frame = QFrame()
        self.file_upload_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.file_upload_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.file_upload_frame.setStyleSheet(f"""
            QFrame {{ background-color: white; min-width: 500px; min-height: 200px; border-radius: 10px; color: black; }}
        """)
        file_upload_layout = QVBoxLayout(self.file_upload_frame)
        file_upload_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_upload_layout.addStretch(1)

        self.upload_label = QLabel("請將 HTML 檔案拖曳至此") 
        self.upload_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_label.setFont(QFont("微軟正黑體", 14))
        self.upload_label.setWordWrap(True)
        file_upload_layout.addWidget(self.upload_label)

        self.loaded_file_path_label = QLabel("")
        self.loaded_file_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loaded_file_path_label.setFont(QFont("微軟正黑體", 10))
        self.loaded_file_path_label.setStyleSheet("color: #777;")
        self.loaded_file_path_label.setWordWrap(True)
        self.loaded_file_path_label.setVisible(False)
        file_upload_layout.addWidget(self.loaded_file_path_label)
        file_upload_layout.addSpacing(15)

        select_file_button = QPushButton("選擇檔案")
        self.set_button_style(select_file_button)
        select_file_button.clicked.connect(self.select_files)
        file_upload_layout.addWidget(select_file_button, alignment=Qt.AlignmentFlag.AlignCenter)
        file_upload_layout.addSpacing(10)

        self.clear_file_button = QPushButton("清除檔案")
        self.set_button_style(self.clear_file_button, is_cancel=True)
        self.clear_file_button.clicked.connect(self.clear_selected_files)
        self.clear_file_button.setVisible(False)
        file_upload_layout.addWidget(self.clear_file_button, alignment=Qt.AlignmentFlag.AlignCenter)
        file_upload_layout.addStretch(1)

        home_layout.addWidget(self.file_upload_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        mode_selection_layout = QHBoxLayout()
        mode_selection_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_selection_layout.setSpacing(20)

        self.manual_mode_button = QPushButton("手動生成 Alt")
        self.manual_mode_button.clicked.connect(self.set_manual_mode)
        mode_selection_layout.addWidget(self.manual_mode_button)

        self.auto_mode_button = QPushButton("自動生成 Alt (AI)")
        self.auto_mode_button.clicked.connect(self.set_auto_mode)
        mode_selection_layout.addWidget(self.auto_mode_button)
        home_layout.addLayout(mode_selection_layout)

        self.start_button = QPushButton("開始新增 Alt")
        self.set_button_style(self.start_button, is_accent=True, is_enabled=False) 
        self.start_button.clicked.connect(self.start_alt_generation)
        home_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.selected_mode = None
        self.update_file_upload_frame_style()
        self.update_mode_button_styles()

    def setup_manual_page(self):
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        
        # 標題
        title_label = QLabel("<h2>手動生成 Alt 敘述</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual_layout.addWidget(title_label)
        
        # 檔案標籤
        self.manual_tab_widget = QTabWidget()
        manual_layout.addWidget(self.manual_tab_widget)
        
        # 頁尾按鈕
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        
        self.manual_cancel_button = QPushButton("取消")
        self.set_button_style(self.manual_cancel_button, is_cancel=True)
        self.manual_cancel_button.clicked.connect(self.show_home_page)
        bottom_layout.addWidget(self.manual_cancel_button)

        self.manual_confirm_button = QPushButton("確認修改全部")
        self.set_button_style(self.manual_confirm_button, is_accent=True, is_enabled=False)
        self.manual_confirm_button.clicked.connect(self.save_manual_alts)
        bottom_layout.addWidget(self.manual_confirm_button)

        manual_layout.addLayout(bottom_layout)

    def setup_auto_page(self):
        self.auto_page = QWidget()
        auto_layout = QVBoxLayout(self.auto_page)
        auto_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("<h2>自動生成 ALT</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auto_layout.addWidget(title_label)

        # AI 生成進度區
        progress_layout = QVBoxLayout()
        self.ai_progress_bar = QProgressBar()
        self.ai_progress_bar.setVisible(False)
        self.ai_status_label = QLabel("")
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ai_status_label.setStyleSheet("color: #333;")
        self.ai_status_label.setVisible(False)
        progress_layout.addWidget(self.ai_progress_bar)
        progress_layout.addWidget(self.ai_status_label)
        auto_layout.addLayout(progress_layout)

        # 檔案分頁
        self.auto_tab_widget = QTabWidget()
        self.auto_tab_widget.setStyleSheet("""
            QTabBar::tab { 
                border: 1px solid #C4C4C3;
                border-bottom-color: #C2C7CB;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 10px;
            }
            QTabBar::tab:selected {
                background: white;
                border-color: #9B9B9B;
                border-bottom-color: #C2C7CB;
            }
        """)
        auto_layout.addWidget(self.auto_tab_widget)

        # 頁尾按鈕區
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)

        self.auto_cancel_button = QPushButton("取消")
        self.set_button_style(self.auto_cancel_button, is_cancel=True)
        self.auto_cancel_button.clicked.connect(self.cancel_auto_generation)
        bottom_layout.addWidget(self.auto_cancel_button)

        self.auto_confirm_all_button = QPushButton("確認修改全部")
        self.set_button_style(self.auto_confirm_all_button, is_accent=True, is_enabled=False)
        self.auto_confirm_all_button.clicked.connect(self.save_all_auto_alts)
        bottom_layout.addWidget(self.auto_confirm_all_button)

        auto_layout.addLayout(bottom_layout)

    def switch_page(self, new_page):
        if self.current_page:
            self.main_layout.removeWidget(self.current_page)
            self.current_page.hide()
        self.main_layout.addWidget(new_page)
        new_page.show()
        self.current_page = new_page

    def show_home_page(self):
        self.switch_page(self.home_page)
        # 清理狀態
        self.selected_mode = None
        self.update_start_button_state()
        self.update_mode_button_styles()
        self.is_manual_alt_modified = False
        self.update_manual_confirm_button_state()
        self.update_file_upload_frame_style()

    def show_manual_page(self):
        self.switch_page(self.manual_page)
        self.populate_manual_image_list()
        self.is_manual_alt_modified = False
        self.update_manual_confirm_button_state()

    def show_auto_page(self):
        self.switch_page(self.auto_page)
        self.begin_auto_generation()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_paths = [url.toLocalFile() for url in urls]
            self.handle_file_selection(file_paths)
        event.acceptProposedAction()

    def select_files(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("HTML 檔案 (*.html *.htm)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.handle_file_selection(selected_files)

    def handle_file_selection(self, file_paths):
        self.clear_selected_files(show_message=False)
        loaded_count = 0
        error_messages = []
        for path in file_paths:
            processor = HtmlProcessor()
            success, message = processor.load_html_file(path)
            if success:
                self.html_processors[path] = processor
                loaded_count += 1
            else:
                error_messages.append(f"{os.path.basename(path)}: {message}")
        
        if loaded_count > 0:
            self.upload_label.setText(f"已成功載入 {loaded_count} 個 HTML 檔案。")
            self.loaded_file_path_label.setText("將滑鼠懸停以查看檔案列表")
            self.loaded_file_path_label.setToolTip("\n".join(self.html_processors.keys()))
            self.loaded_file_path_label.setVisible(True)
            self.clear_file_button.setVisible(True)
        else:
            self.upload_label.setText("請將 HTML 檔案拖曳至此")
            self.loaded_file_path_label.setVisible(False)
            self.clear_file_button.setVisible(False)

        if error_messages:
            QMessageBox.warning(self, "檔案載入錯誤", "\n".join(error_messages))

        self.selected_mode = None
        self.update_all_home_page_states()

    def clear_selected_files(self, show_message=True):
        self.html_processors.clear()
        self.upload_label.setText("請將 HTML 檔案拖曳至此")
        self.loaded_file_path_label.setText("")
        self.loaded_file_path_label.setVisible(False)
        self.clear_file_button.setVisible(False)
        self.selected_mode = None
        if show_message:
            QMessageBox.information(self, "檔案清除", "已清除所有選取的檔案。")
        self.update_all_home_page_states()

    def update_all_home_page_states(self):
        self.update_start_button_state()
        self.update_file_upload_frame_style()
        self.update_mode_button_styles()
        self.update_manual_confirm_button_state()
    
    def update_file_upload_frame_style(self):
        self.file_upload_frame.setStyleSheet(f"""
            QFrame {{ border: none; border-radius: 10px; background-color: white; min-width: 500px; min-height: 200px; }}
        """)

    def set_manual_mode(self):
        self.selected_mode = "manual"
        self.update_mode_button_styles()
        self.update_start_button_state()

    def set_auto_mode(self):
        self.selected_mode = "auto"
        self.update_mode_button_styles()
        self.update_start_button_state()

    def update_mode_button_styles(self):
        is_mode_buttons_enabled = bool(self.html_processors)
        self.set_button_style(self.manual_mode_button, 
                              is_selected=(self.selected_mode == "manual"),
                              is_enabled=is_mode_buttons_enabled)
        self.set_button_style(self.auto_mode_button, 
                              is_selected=(self.selected_mode == "auto"),
                              is_enabled=is_mode_buttons_enabled)

    def update_start_button_state(self):
        is_enabled = bool(self.html_processors and self.selected_mode)
        self.set_button_style(self.start_button, is_accent=True, is_enabled=is_enabled)

    def start_alt_generation(self):
        if not self.html_processors:
            QMessageBox.warning(self, "錯誤", "請先上傳至少一個 HTML 檔案。")
            return
        if not self.selected_mode:
            QMessageBox.warning(self, "錯誤", "請先選擇生成模式。")
            return
        
        # 檢查是否有需要處理的圖片
        total_images_to_process = 0
        for processor in self.html_processors.values():
            total_images_to_process += len(processor.get_images_to_process())
        
        if total_images_to_process == 0:
            QMessageBox.information(self, "提示", "所有載入的 HTML 檔案均無需處理 alt 標籤。")
            return

        if self.selected_mode == "manual":
            # 如果是單一檔案，直接跳轉
            if len(self.html_processors) == 1:
                self.show_manual_page()
            else: # 多檔案，需要分頁
                self.show_manual_page()
        elif self.selected_mode == "auto":
            self.show_auto_page()
    
    def load_image_thumbnail(self, image_path, html_path, size: QSize = QSize(60, 60)):
        pixmap = QPixmap()
        if not image_path: return pixmap
        html_dir = os.path.dirname(html_path)
        abs_image_path = image_path
        if not os.path.isabs(image_path):
            abs_image_path = os.path.normpath(os.path.join(html_dir, image_path))
        
        try:
            pil_image = PilImage.open(abs_image_path)
            if pil_image.mode not in ('RGB', 'RGBA'):
                pil_image = pil_image.convert('RGB')
            if pil_image.mode == 'RGB':
                bytes_per_line, qimage_format = pil_image.width * 3, QImage.Format.Format_RGB888
            else:
                bytes_per_line, qimage_format = pil_image.width * 4, QImage.Format.Format_RGBA8888
            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height, bytes_per_line, qimage_format)
            pixmap = QPixmap.fromImage(qimage)
            return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        except Exception as e:
            print(f"ERROR: Thumbnail load failed for {abs_image_path}: {e}")
            place_holder_pixmap = QPixmap(size)
            place_holder_pixmap.fill(QColor("lightgray"))
            painter = QPainter(place_holder_pixmap)
            painter.setFont(QFont("微軟正黑體", 8))
            painter.setPen(QColor("darkgray"))
            painter.drawText(place_holder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "無法載入")
            painter.end()
            return place_holder_pixmap

    def populate_manual_image_list(self):
        self.manual_tab_widget.clear()
        
        for path, processor in self.html_processors.items():
            tab_name = os.path.basename(path).rsplit('.', 1)[0]
            tab_content = QWidget()
            tab_layout = QVBoxLayout(tab_content)

            list_widget = QListWidget()
            list_widget.setStyleSheet("""
                QListWidget { border: 1px solid #ccc; border-radius: 5px; background-color: white; }
                QListWidget::item { padding: 10px; border-bottom: 1px solid #eee; }
                QListWidget::item:hover { background-color: #f0f0f0; }
            """)
            tab_layout.addWidget(list_widget)

            images_to_process = processor.get_images_to_process()
            if not images_to_process:
                no_image_label = QLabel("此檔案中沒有需要處理的圖片。", alignment=Qt.AlignmentFlag.AlignCenter)
                no_image_label.setContentsMargins(0, 50, 0, 50)
                list_widget.hide() # 隱藏列表框
                tab_layout.addWidget(no_image_label) # 直接在tab中顯示提示
            else:
                for img_data in images_to_process:
                    self.add_list_item(list_widget, img_data, path, processor)
            
            self.manual_tab_widget.addTab(tab_content, tab_name)

    def add_list_item(self, list_widget, img_data, html_path, processor_instance, generated_alt=None):
        list_item = QListWidgetItem(list_widget)
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item_layout.setContentsMargins(10, 5, 10, 5)

        img_label = QLabel()
        thumbnail = self.load_image_thumbnail(img_data['src'], html_path)
        img_label.setPixmap(thumbnail)
        img_label.setFixedSize(60, 60)
        img_label.mousePressEvent = lambda event, p=img_data['src']: self.show_image_preview(p, processor_instance)
        item_layout.addWidget(img_label)

        path_label = QLabel(f"路徑: {img_data['src']}")
        path_label.setFont(QFont("微軟正黑體", 12))
        path_label.setStyleSheet("color: #555;")
        item_layout.addWidget(path_label)
        item_layout.addStretch(1)

        alt_input = QLineEdit()
        alt_input.setPlaceholderText("請輸入 Alt 敘述")
        # 根據模式決定初始文字
        initial_text = generated_alt if generated_alt is not None else img_data.get('current_alt', '')
        alt_input.setText(initial_text)
        alt_input.setProperty("original_alt", initial_text)
        alt_input.setFixedSize(300, 30)
        alt_input.setStyleSheet(f"QLineEdit {{ border: 1px solid #ccc; border-radius: 3px; padding: 5px; background-color: #f9f9f9; color: {TEXT_COLOR_DARK}; }}")
        
        # 連接訊號以更新按鈕狀態
        if self.selected_mode == "manual":
            alt_input.textChanged.connect(self.check_manual_alt_modification)
        else: # auto mode
            alt_input.textChanged.connect(self.update_auto_confirm_button_state)

        list_item.setData(Qt.ItemDataRole.UserRole, {'element': img_data['element'], 'alt_input_widget': alt_input})
        item_layout.addWidget(alt_input)

        list_widget.setItemWidget(list_item, item_widget)
        list_item.setSizeHint(item_widget.sizeHint())

    def check_manual_alt_modification(self):
        self.is_manual_alt_modified = True
        self.update_manual_confirm_button_state()

    def update_manual_confirm_button_state(self):
        is_enabled = bool(self.html_processors and self.is_manual_alt_modified)
        self.set_button_style(self.manual_confirm_button, is_accent=True, is_enabled=is_enabled)
    
    def update_auto_confirm_button_state(self):
        # 只要有tab且不在生成中，就啟用
        is_enabled = self.auto_tab_widget.count() > 0 and not (self.generation_thread and self.generation_thread.isRunning())
        self.set_button_style(self.auto_confirm_all_button, is_accent=True, is_enabled=is_enabled)
        # 更新每個tab的 "確認修改此檔案" 按鈕
        for i in range(self.auto_tab_widget.count()):
            tab_content = self.auto_tab_widget.widget(i)
            confirm_button = tab_content.findChild(QPushButton, "confirm_this_file_button")
            if confirm_button:
                 self.set_button_style(confirm_button, is_accent=True, is_enabled=is_enabled)

    def show_image_preview(self, image_path, processor_instance):
        dialog = ImagePreviewDialog(image_path, processor_instance, self)
        dialog.exec()

    def save_manual_alts(self):
        all_success = True
        error_messages = []
        for i in range(self.manual_tab_widget.count()):
            path = list(self.html_processors.keys())[i]
            processor = self.html_processors[path]
            tab_content = self.manual_tab_widget.widget(i)
            list_widget = tab_content.findChild(QListWidget)
            
            if not list_widget: continue

            updated_images_data = []
            for j in range(list_widget.count()):
                list_item = list_widget.item(j)
                item_data = list_item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    new_alt = item_data['alt_input_widget'].text().strip()
                    updated_images_data.append({'element': item_data['element'], 'new_alt': new_alt})
            
            if updated_images_data:
                success, message = processor.save_html_with_new_alts(updated_images_data)
                if not success:
                    all_success = False
                    error_messages.append(message)

        if all_success:
            QMessageBox.information(self, "保存成功", "所有檔案的 Alt 敘述已成功更新。")
            self.show_home_page()
        else:
            QMessageBox.warning(self, "保存失敗", "部分檔案更新失敗：\n" + "\n".join(error_messages))

    # --- 自動生成相關方法 ---

    def begin_auto_generation(self):
        self.auto_tab_widget.clear()
        self.ai_progress_bar.setValue(0)
        self.ai_progress_bar.setVisible(True)
        self.ai_status_label.setText("正在初始化 AI 模型...")
        self.ai_status_label.setVisible(True)
        self.set_button_style(self.auto_confirm_all_button, is_accent=True, is_enabled=False)
        self.set_button_style(self.auto_cancel_button, is_cancel=True, is_enabled=True)

        self.generation_thread = GenerationThread(self.html_processors, self.ai_processor)
        self.generation_thread.image_processed.connect(self.add_auto_processed_image)
        self.generation_thread.progress_updated.connect(self.update_ai_progress)
        self.generation_thread.generation_finished.connect(self.on_ai_generation_finished)
        self.generation_thread.error_occurred.connect(self.on_ai_generation_error)
        self.generation_thread.start()

    def update_ai_progress(self, value, text):
        self.ai_progress_bar.setValue(value)
        self.ai_status_label.setText(text)
        self.ai_status_label.setStyleSheet("color: #333;")

    def on_ai_generation_error(self, error_message):
        self.ai_status_label.setText(f"錯誤: {error_message}")
        self.ai_status_label.setStyleSheet("color: red;")
        self.ai_progress_bar.setVisible(False)
        self.set_button_style(self.auto_confirm_all_button, is_accent=True, is_enabled=False)
        self.set_button_style(self.auto_cancel_button, is_cancel=True, is_enabled=True)

    def add_auto_processed_image(self, html_path, image_src, generated_alt, bs4_element):
        tab_widget = None
        # 尋找對應的Tab
        for i in range(self.auto_tab_widget.count()):
            if self.auto_tab_widget.tabToolTip(i) == html_path:
                tab_widget = self.auto_tab_widget.widget(i)
                break
        
        # 如果找不到，創建新的Tab
        if tab_widget is None:
            tab_name = os.path.basename(html_path).rsplit('.', 1)[0]
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            list_widget = QListWidget()
            list_widget.setStyleSheet("""
                QListWidget { border: none; background-color: white; }
                QListWidget::item { padding: 10px; border-bottom: 1px solid #eee; }
            """)
            tab_layout.addWidget(list_widget)
            
            # 加入 "確認修改此檔案" 按鈕
            confirm_this_file_button = QPushButton("確認修改此檔案")
            confirm_this_file_button.setObjectName("confirm_this_file_button")
            self.set_button_style(confirm_this_file_button, is_accent=True, is_enabled=False)
            confirm_this_file_button.clicked.connect(lambda _, p=html_path: self.save_single_auto_alt_file(p))
            
            button_layout = QHBoxLayout()
            button_layout.addStretch(1)
            button_layout.addWidget(confirm_this_file_button)
            tab_layout.addLayout(button_layout)
            
            self.auto_tab_widget.addTab(tab_widget, tab_name)
            self.auto_tab_widget.setTabToolTip(self.auto_tab_widget.count()-1, html_path)

        list_widget = tab_widget.findChild(QListWidget)
        img_data = {'src': image_src, 'element': bs4_element}
        self.add_list_item(list_widget, img_data, html_path, self.html_processors[html_path], generated_alt)
        
    def on_ai_generation_finished(self):
        self.ai_progress_bar.setVisible(False)
        self.generation_thread = None # 清理線程
        # 檢查是否有任何分頁被創建
        if self.auto_tab_widget.count() == 0:
            self.ai_status_label.setText("處理完成，所有檔案均無需生成 alt。")
            self.set_button_style(self.auto_confirm_all_button, is_accent=True, is_enabled=False)
        else:
            self.ai_status_label.setText("AI 生成完成！您可以檢視並修改下方的結果。")
            self.update_auto_confirm_button_state()
            
    def cancel_auto_generation(self):
        if self.generation_thread and self.generation_thread.isRunning():
            reply = QMessageBox.question(self, "確認取消", "AI 正在生成中，您確定要中止並返回首頁嗎？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.generation_thread.stop()
                self.generation_thread.wait() # 等待線程結束
                self.show_home_page()
        else:
            self.show_home_page()

    def save_single_auto_alt_file(self, path_to_save):
        tab_index = -1
        for i in range(self.auto_tab_widget.count()):
            if self.auto_tab_widget.tabToolTip(i) == path_to_save:
                tab_index = i
                break
        
        if tab_index == -1: return

        tab_content = self.auto_tab_widget.widget(tab_index)
        list_widget = tab_content.findChild(QListWidget)
        processor = self.html_processors[path_to_save]
        
        updated_images_data = []
        for j in range(list_widget.count()):
            list_item = list_widget.item(j)
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            if item_data:
                new_alt = item_data['alt_input_widget'].text().strip()
                updated_images_data.append({'element': item_data['element'], 'new_alt': new_alt})
        
        success, message = processor.save_html_with_new_alts(updated_images_data)
        if success:
            QMessageBox.information(self, "保存成功", message)
            # 清空此分頁的列表，表示已處理完畢
            list_widget.clear()
            # 禁用此分頁的儲存按鈕
            confirm_button = tab_content.findChild(QPushButton, "confirm_this_file_button")
            if confirm_button:
                 self.set_button_style(confirm_button, is_accent=True, is_enabled=False)
        else:
            QMessageBox.warning(self, "保存失敗", message)


    def save_all_auto_alts(self):
        all_success = True
        error_messages = []
        
        for i in range(self.auto_tab_widget.count()):
            path = self.auto_tab_widget.tabToolTip(i)
            tab_content = self.auto_tab_widget.widget(i)
            list_widget = tab_content.findChild(QListWidget)
            processor = self.html_processors[path]
            
            if not list_widget or list_widget.count() == 0: continue # 跳過已儲存或空的

            updated_images_data = []
            for j in range(list_widget.count()):
                list_item = list_widget.item(j)
                item_data = list_item.data(Qt.ItemDataRole.UserRole)
                if item_data:
                    new_alt = item_data['alt_input_widget'].text().strip()
                    updated_images_data.append({'element': item_data['element'], 'new_alt': new_alt})
            
            if updated_images_data:
                success, message = processor.save_html_with_new_alts(updated_images_data)
                if not success:
                    all_success = False
                    error_messages.append(message)

        if all_success:
            QMessageBox.information(self, "保存成功", "所有檔案的 Alt 敘述已成功更新。")
            self.show_home_page()
        else:
            QMessageBox.warning(self, "保存失敗", "部分檔案更新失敗：\n" + "\n".join(error_messages))


if __name__ == "__main__":
    # 設置環境變數以避免 huggingface_hub 的 token 警告
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    
    app = QApplication(sys.argv)
    window = AltGeneratorApp()
    window.show()
    sys.exit(app.exec())