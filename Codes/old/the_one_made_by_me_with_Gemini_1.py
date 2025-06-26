import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox, QSpacerItem, QSizePolicy,
    QScrollArea, QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QMimeData, QUrl, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor, QFont, QPixmap, QImage, QPainter
from bs4 import BeautifulSoup
from PIL import Image as PilImage # 避免與 PyQt6.QtGui.QImage 衝突
from io import BytesIO


# 定義顏色調色盤
# 灰藍色系
PRIMARY_COLOR_DARK = "#4A6E8C"  # 深灰藍
PRIMARY_COLOR_LIGHT = "#6B9CC3" # 淺灰藍
ACCENT_COLOR_RED = "#E04F5F"   # 取消按鈕的凸顯色 (紅色)
ACCENT_COLOR_GREEN = "#6FD196" # 確定/成功按鈕的凸顯色 (綠色)
TEXT_COLOR_LIGHT = "#F0F0F0"   # 淺色文字
TEXT_COLOR_DARK = "#333333"    # 深色文字 (用於深色背景上的淺色文字，或淺色背景上的深色文字)
SELECTED_BUTTON_BORDER_COLOR = "#00FF00" # 選取按鈕的邊框色 (亮綠色)
DISABLED_COLOR_BACKGROUND = "#A0A0A0" # 禁用按鈕的背景色
DISABLED_COLOR_TEXT = "#E0E0E0"    # 禁用按鈕的文字色


class ImagePreviewDialog(QDialog):
    """
    圖片放大預覽對話框
    """
    def __init__(self, image_path, html_processor_instance, parent=None): # 新增 html_processor_instance 參數
        super().__init__(parent)
        self.setWindowTitle("圖片預覽")
        self.setModal(True) # 設為模態對話框
        self.layout = QVBoxLayout(self)
        self.html_processor = html_processor_instance # 儲存實例以便解析路徑
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 嘗試載入圖片
        pixmap = self.load_image_for_preview(image_path)
        if not pixmap.isNull():
            # 限制圖片最大尺寸，避免顯示過大的圖片導致視窗過大或崩潰
            # 考慮視窗邊距，所以實際限制尺寸會小於視窗大小
            max_dialog_width = self.parent().width() * 0.8 if self.parent() else 800 # 限制為主視窗的80%寬度
            max_dialog_height = self.parent().height() * 0.8 if self.parent() else 600 # 限制為主視窗的80%高度
            
            if pixmap.width() > max_dialog_width or pixmap.height() > max_dialog_height:
                pixmap = pixmap.scaled(int(max_dialog_width), int(max_dialog_height), 
                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("無法載入圖片或圖片損壞")
            self.image_label.setStyleSheet("color: red; font-size: 16px;")

        self.layout.addWidget(self.image_label)

        # 增加關閉按鈕
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject) # 點擊關閉按鈕關閉對話框
        self.layout.addWidget(button_box)

        # 根據圖片大小調整對話框大小，加一些邊距
        # 如果圖片被縮放，則使用縮放後的尺寸
        if not pixmap.isNull():
            self.resize(self.image_label.pixmap().width() + 50, self.image_label.pixmap().height() + 100)
        else: # 如果圖片無法載入，給一個預設大小
            self.setFixedSize(400, 300)


    def load_image_for_preview(self, image_path):
        """
        載入圖片以供預覽。
        嘗試解析相對路徑，並使用 PilImage 處理更廣泛的圖片格式。
        """
        pixmap = QPixmap()
        if not image_path:
            return pixmap # 返回空的 QPixmap

        html_dir = ""
        if self.html_processor and self.html_processor.html_file_path:
            html_dir = os.path.dirname(self.html_processor.html_file_path)

        absolute_image_path = image_path
        # 處理相對路徑，考慮圖片路徑本身是否是絕對路徑
        if html_dir and not os.path.isabs(image_path):
            absolute_image_path = os.path.normpath(os.path.join(html_dir, image_path))
        
        # 打印嘗試載入的絕對路徑，用於調試
        print(f"DEBUG: Attempting to load preview image from: {absolute_image_path}")

        try:
            # 嘗試使用 Pillow 載入圖片，可以處理更多格式和潛在的問題
            pil_image = PilImage.open(absolute_image_path)
            
            # 修正：確保圖片是 RGB 或 RGBA 模式，並明確計算 bytesPerLine
            if pil_image.mode not in ('RGB', 'RGBA'):
                # 轉換為 RGB 模式，以確保兼容性，並移除 alpha 通道如果存在
                # 如果需要保留透明度，則應轉換為 RGBA
                pil_image = pil_image.convert('RGB') 

            # 計算正確的 bytesPerLine
            if pil_image.mode == 'RGB':
                # 每個像素 3 bytes (R, G, B)
                bytes_per_line = pil_image.width * 3
                qimage_format = QImage.Format.Format_RGB888
            elif pil_image.mode == 'RGBA':
                # 每個像素 4 bytes (R, G, B, A)
                bytes_per_line = pil_image.width * 4
                qimage_format = QImage.Format.Format_RGBA8888
            else: # Fallback (理論上不會走到這裡，因為前面已經 convert 了)
                return QPixmap() 

            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height, bytes_per_line, qimage_format)
            
            pixmap = QPixmap.fromImage(qimage)
            return pixmap

        except Exception as e:
            print(f"ERROR: Preview image load failed for {absolute_image_path}: {e}")
            # 如果 Pillow 載入失敗，返回空的 QPixmap
            return QPixmap()

class HtmlProcessor:
    """
    HTML 檔案處理類別
    負責 HTML 檔案的讀取、解析、檢查和修改。
    """
    def __init__(self):
        self.html_file_path = None
        self.html_content = None
        self.soup = None # BeautifulSoup 物件

    def load_html_file(self, file_path):
        """
        載入 HTML 檔案。
        """
        if not file_path.lower().endswith(('.html', '.htm')):
            return False, "錯誤：請上傳有效的 HTML 檔案 (.html 或 .htm)。"
        
        # 嘗試以多種編碼讀取
        encodings = ['utf-8', 'big5', 'gbk', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    self.html_content = f.read()
                self.html_file_path = file_path
                self.soup = BeautifulSoup(self.html_content, 'html.parser') # 解析 HTML
                print(f"DEBUG: HTML file loaded with {encoding} encoding.")
                return True, f"檔案載入成功 (使用 {encoding} 編碼)。"
            except UnicodeDecodeError:
                continue # 嘗試下一個編碼
            except Exception as e:
                return False, f"載入檔案時發生錯誤：{e}"
        
        return False, "載入檔案失敗：無法識別檔案編碼或檔案內容損壞。"


    def clear_file(self):
        """
        清除已載入的檔案資訊。
        """
        self.html_file_path = None
        self.html_content = None
        self.soup = None

    def get_images_to_process(self):
        """
        獲取需要被加入或修改 alt 屬性的圖片元素。
        條件：
        1. 沒有 alt 屬性的 <img> 元素。
        2. alt 屬性值為空字串或只有空格的 <img> 元素 (簡易判斷不符合規範)。
        返回一個列表，每個元素是一個字典：
        {
            'element': <img> 標籤物件,
            'src': 圖片路徑,
            'current_alt': 當前 alt 屬性值 (如果有的話),
            'needs_alt': True/False (是否需要新增/修改 alt)
        }
        """
        if not self.soup:
            return []

        images_to_process = []
        for img_tag in self.soup.find_all('img'):
            src = img_tag.get('src')
            alt = img_tag.get('alt')
            
            # 跳過沒有 src 的 img 標籤 (雖然不常見，但為避免錯誤)
            if not src:
                continue

            needs_alt = False
            # 判斷是否需要處理 (無 alt 或 alt 為空/空格)
            if alt is None or alt.strip() == "":
                needs_alt = True
            # TODO: 這裡未來需要加入更詳細的中華民國行政院數位發展部無障礙網頁敘述規範檢查
            # 例如：判斷 alt 是否過短、是否有意義、是否重複等等。

            if needs_alt:
                images_to_process.append({
                    'element': img_tag,
                    'src': src,
                    'current_alt': alt if alt is not None else "", # 如果為 None 則給空字串
                    'needs_alt': True
                })
        return images_to_process

    def save_html_with_new_alts(self, updated_images_data):
        """
        將新的 alt 屬性寫回 HTML 內容並保存檔案。
        updated_images_data 是一個列表，每個元素是一個字典：
        {
            'element': 原始的 <img> 標籤物件,
            'new_alt': 新的 alt 文本
        }
        """
        if not self.soup or not self.html_file_path:
            return False, "沒有載入的 HTML 檔案。"

        try:
            for img_data in updated_images_data:
                original_img_element = img_data['element']
                new_alt_text = img_data['new_alt']
                
                # 直接在傳入的 BeautifulSoup 元素上更新 alt 屬性
                # BeautifulSoup 的 Tag 對象是可變的，直接修改即可
                original_img_element['alt'] = new_alt_text
            
            # 將修改後的 BeautifulSoup 物件寫回檔案
            # 為了兼容性，建議在寫入時指定 encoding
            # 如果原始檔案有 BOM，BeautifulSoup 會保留
            with open(self.html_file_path, 'w', encoding='utf-8') as f:
                f.write(str(self.soup))
            
            return True, "Alt 敘述已成功寫入 HTML 檔案。"
        except Exception as e:
            return False, f"保存檔案時發生錯誤：{e}"


class AltGeneratorApp(QWidget):
    """
    主應用程式視窗類別
    """
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("網頁 Alt 敘述生成系統")
        self.setGeometry(100, 100, 800, 600) # 設定視窗初始大小
        self.setAcceptDrops(True) # 允許拖曳檔案

        self.html_processor = HtmlProcessor() # 實例化 HTML 處理器

        self.current_page = None # 記錄當前顯示的頁面
        self.is_manual_alt_modified = False # 新增：追蹤手動修改頁面是否有變動
        self.init_ui()

    def init_ui(self):
        """
        初始化使用者介面。
        設定主視窗的佈局和切換頁面。
        """
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # 設定整體應用程式的調色盤
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(PRIMARY_COLOR_LIGHT)) # 背景色
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_COLOR_DARK)) # 一般文字顏色
        palette.setColor(QPalette.ColorRole.Button, QColor(PRIMARY_COLOR_DARK)) # 按鈕背景色
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_COLOR_LIGHT)) # 按鈕文字顏色
        palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY_COLOR_DARK)) # 選中項目背景色
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_COLOR_LIGHT)) # 選中項目文字顏色
        # 設定 QLineEdit 相關的顏色
        palette.setColor(QPalette.ColorRole.Base, QColor("#f9f9f9"))  # QLineEdit 背景色
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_COLOR_DARK)) # QLineEdit 文字顏色 (重要修正)
        self.setPalette(palette)
        
        # 解決字體警告：嘗試使用系統預設的中文字體或更廣泛支持的字體
        # 如果警告依然存在，建議替換為 macOS 系統常用的中文字體，例如 "PingFang TC", "Heiti TC"
        self.setFont(QFont("微軟正黑體", 10, QFont.Weight.Normal, False))

        self.setup_home_page()
        self.setup_manual_page()
        self.setup_auto_page()

        self.show_home_page() # 預設顯示首頁

    def set_button_style(self, button, is_accent=False, is_cancel=False, is_selected=False, is_enabled=True):
        """
        設定按鈕樣式。
        is_enabled: 控制按鈕是否啟用，禁用時顯示淺灰色。
        """
        bg_color = PRIMARY_COLOR_DARK
        text_color = TEXT_COLOR_LIGHT
        hover_color = PRIMARY_COLOR_DARK.replace('4A6E8C', '5B82A8')
        border_style = "border: none;" # 預設無邊框

        if is_cancel:
            bg_color = ACCENT_COLOR_RED
            hover_color = ACCENT_COLOR_RED.replace('E04F5F', 'FF6F7F')
        elif is_accent:
            bg_color = ACCENT_COLOR_GREEN
            hover_color = ACCENT_COLOR_GREEN.replace('6FD196', '8DD1AF')
        
        # 如果是選中狀態，則設定綠色邊框
        if is_selected:
            border_style = f"border: 2px solid {SELECTED_BUTTON_BORDER_COLOR};" 
        
        # 如果按鈕被禁用，使用禁用顏色
        if not is_enabled:
            bg_color = DISABLED_COLOR_BACKGROUND
            text_color = DISABLED_COLOR_TEXT
            hover_color = DISABLED_COLOR_BACKGROUND # 禁用時 hover 效果也一樣
        
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
        button.setFixedSize(180, 50) # 固定按鈕大小
        button.setEnabled(is_enabled) # 設定按鈕的啟用狀態

    def setup_home_page(self):
        """
        設定首頁的 GUI 元素。
        """
        self.home_page = QWidget()
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 垂直居中

        # 檔案上傳區
        self.file_upload_frame = QFrame()
        self.file_upload_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.file_upload_frame.setFrameShadow(QFrame.Shadow.Raised)
        # 初始時不設定邊框，由 update_file_upload_frame_style 控制
        # 這裡只需要設定基本樣式，邊框由 update_file_upload_frame_style 動態控制
        self.file_upload_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white; /* 底色改為白色 */
                min-width: 500px; /* 設置最小寬度 */
                min-height: 0px; /* 設置最小高度 */
                border-radius: 10px; /* 保持圓角 */
                color: black;
            }}
        """)
        file_upload_layout = QVBoxLayout(self.file_upload_frame)
        file_upload_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 內容垂直居中

        file_upload_layout.addStretch(1) # 添加彈簧

        # 更新提示文字
        self.upload_label = QLabel("請將檔案拖曳至此") 
        self.upload_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_label.setFont(QFont("微軟正黑體", 14)) # 字體放大至 14px
        self.upload_label.setWordWrap(True) # 允許文字換行
        file_upload_layout.addWidget(self.upload_label)

        # 新增一個用於顯示完整路徑的 QLabel
        self.loaded_file_path_label = QLabel("")
        self.loaded_file_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loaded_file_path_label.setFont(QFont("微軟正黑體", 10))
        self.loaded_file_path_label.setStyleSheet("color: #777;")
        self.loaded_file_path_label.setWordWrap(True)
        self.loaded_file_path_label.setVisible(False) # 預設隱藏
        file_upload_layout.addWidget(self.loaded_file_path_label)


        file_upload_layout.addSpacing(15) # 在標籤和按鈕之間增加一些間距

        select_file_button = QPushButton("選擇檔案")
        self.set_button_style(select_file_button)
        select_file_button.clicked.connect(self.select_file)
        file_upload_layout.addWidget(select_file_button, alignment=Qt.AlignmentFlag.AlignCenter)

        file_upload_layout.addSpacing(10) # 在兩個按鈕之間增加間距

        self.clear_file_button = QPushButton("清除檔案")
        self.set_button_style(self.clear_file_button, is_cancel=True)
        self.clear_file_button.clicked.connect(self.clear_selected_file)
        self.clear_file_button.setVisible(False) # 預設隱藏
        file_upload_layout.addWidget(self.clear_file_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        file_upload_layout.addStretch(1) # 添加彈簧

        home_layout.addWidget(self.file_upload_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # 模式選擇按鈕
        mode_selection_layout = QHBoxLayout()
        mode_selection_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_selection_layout.setSpacing(20) # 按鈕間距

        self.manual_mode_button = QPushButton("手動生成 Alt")
        self.manual_mode_button.clicked.connect(self.set_manual_mode)
        mode_selection_layout.addWidget(self.manual_mode_button)

        self.auto_mode_button = QPushButton("自動生成 Alt (AI)")
        self.auto_mode_button.clicked.connect(self.set_auto_mode)
        mode_selection_layout.addWidget(self.auto_mode_button)

        home_layout.addLayout(mode_selection_layout)

        # 開始新增 Alt 按鈕
        self.start_button = QPushButton("開始新增 Alt")
        self.set_button_style(self.start_button, is_accent=True, is_enabled=False) 
        self.start_button.clicked.connect(self.start_alt_generation)
        home_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.selected_mode = None # 記錄使用者選擇的模式
        self.update_file_upload_frame_style() # 初始化拖曳框樣式
        self.update_mode_button_styles() # 初始化模式按鈕樣式

    def setup_manual_page(self):
        """
        設定手動生成功能頁的 GUI 元素。
        """
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        
        manual_layout.addWidget(QLabel("<h2>手動生成 Alt 敘述</h2>", alignment=Qt.AlignmentFlag.AlignCenter))
        
        # 圖片列表區
        self.manual_image_list_widget = QListWidget()
        self.manual_image_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
        """)
        manual_layout.addWidget(self.manual_image_list_widget)

        # 頁尾按鈕區
        bottom_layout = QHBoxLayout()
        bottom_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)) # 將按鈕推到右邊

        self.manual_cancel_button = QPushButton("取消")
        self.set_button_style(self.manual_cancel_button, is_cancel=True)
        self.manual_cancel_button.clicked.connect(self.show_home_page)
        bottom_layout.addWidget(self.manual_cancel_button)

        self.manual_confirm_button = QPushButton("確定並儲存")
        self.set_button_style(self.manual_confirm_button, is_accent=True, is_enabled=False)
        self.manual_confirm_button.clicked.connect(self.save_manual_alts)
        bottom_layout.addWidget(self.manual_confirm_button)

        manual_layout.addLayout(bottom_layout)

    def setup_auto_page(self):
        """
        設定自動生成功能頁的 GUI 元素。
        """
        self.auto_page = QWidget()
        auto_layout = QVBoxLayout(self.auto_page)
        auto_layout.addWidget(QLabel("<h2>自動生成 Alt 敘述 (開發中...)</h2>", alignment=Qt.AlignmentFlag.AlignCenter))

        # 返回按鈕佈局，確保靠左下
        bottom_layout = QHBoxLayout()
        bottom_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)) # 將按鈕推到右邊
        
        back_to_home_button = QPushButton("返回首頁")
        self.set_button_style(back_to_home_button, is_cancel=True)
        back_to_home_button.clicked.connect(self.show_home_page)
        bottom_layout.addWidget(back_to_home_button)
        
        auto_layout.addStretch(1) # 將上面的內容推到頂部
        auto_layout.addLayout(bottom_layout)

    def show_home_page(self):
        """顯示首頁並隱藏其他頁面。"""
        if self.current_page:
            self.main_layout.removeWidget(self.current_page)
            self.current_page.hide()
        self.main_layout.addWidget(self.home_page)
        self.home_page.show()
        self.current_page = self.home_page
        self.update_start_button_state() # 確保返回首頁時按鈕狀態正確
        self.update_mode_button_styles() # 返回首頁時重置模式按鈕樣式
        self.is_manual_alt_modified = False # 返回首頁時重置修改狀態
        self.update_manual_confirm_button_state() # 確保手動頁面按鈕狀態在切換回來時正確
        self.update_file_upload_frame_style() # 返回首頁時更新拖曳框樣式


    def show_manual_page(self):
        """顯示手動生成頁面並隱藏其他頁面。"""
        if self.current_page:
            self.main_layout.removeWidget(self.current_page)
            self.current_page.hide()
        self.main_layout.addWidget(self.manual_page)
        self.manual_page.show()
        self.current_page = self.manual_page
        self.populate_manual_image_list() # 填充手動頁面的圖片列表
        self.is_manual_alt_modified = False # 進入手動頁面時，預設為未修改
        self.update_manual_confirm_button_state() # 初始化按鈕狀態

    def show_auto_page(self):
        """顯示自動生成頁面並隱藏其他頁面。"""
        if self.current_page:
            self.main_layout.removeWidget(self.current_page)
            self.current_page.hide()
        self.main_layout.addWidget(self.auto_page)
        self.auto_page.show()
        self.current_page = self.auto_page
        if self.html_processor.html_file_path:
            pass 


    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        處理拖曳進入事件。
        允許拖曳 HTML 檔案。
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """
        處理拖曳放下事件。
        載入拖曳的 HTML 檔案。
        """
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.handle_file_drop(file_path)
        event.acceptProposedAction()

    def select_file(self):
        """
        透過檔案對話框選擇 HTML 檔案。
        """
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("HTML 檔案 (*.html *.htm)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.handle_file_drop(selected_files[0])

    def handle_file_drop(self, file_path):
        """
        處理檔案拖曳或選擇後的邏輯。
        """
        success, message = self.html_processor.load_html_file(file_path)
        if success:
            # 顯示檔名在 upload_label
            self.upload_label.setText(f"已載入檔案：\n{os.path.basename(file_path)}")
            # 顯示完整路徑在新的 QLabel
            self.loaded_file_path_label.setText(f"路徑: {file_path}")
            self.loaded_file_path_label.setVisible(True) # 顯示路徑 QLabel
            self.clear_file_button.setVisible(True) # 顯示清除按鈕
            QMessageBox.information(self, "檔案載入", message)
        else:
            QMessageBox.warning(self, "檔案錯誤", message)
            self.html_processor.clear_file() # 清除不合規的檔案
            self.upload_label.setText("請將檔案拖曳至此") # 恢復預設提示
            self.loaded_file_path_label.setText("") # 清空路徑
            self.loaded_file_path_label.setVisible(False) # 隱藏路徑 QLabel
            self.clear_file_button.setVisible(False) # 隱藏清除按鈕
        
        self.selected_mode = None # 清除模式選擇
        self.update_start_button_state()
        self.update_file_upload_frame_style() # 更新拖曳框樣式
        self.update_mode_button_styles() # 更新模式按鈕樣式


    def clear_selected_file(self):
        """
        清除已選擇的檔案。
        """
        self.html_processor.clear_file()
        self.upload_label.setText("請將檔案拖曳至此") # 恢復預設提示
        self.loaded_file_path_label.setText("") # 清空路徑
        self.loaded_file_path_label.setVisible(False) # 隱藏路徑 QLabel
        self.clear_file_button.setVisible(False)
        self.update_start_button_state()
        QMessageBox.information(self, "檔案清除", "已清除選取的檔案。")
        self.selected_mode = None # 清除模式選擇
        self.update_mode_button_styles() # 重置模式按鈕樣式
        self.is_manual_alt_modified = False # 重置修改狀態
        self.update_manual_confirm_button_state() # 確保手動頁面按鈕狀態在清除檔案時正確
        self.update_file_upload_frame_style() # 更新拖曳框樣式

    def update_file_upload_frame_style(self):
        """
        無論是否有檔案載入，拖曳框都將沒有邊框。
        """
        self.file_upload_frame.setStyleSheet(f"""
            QFrame {{
                border: none; /* 始終沒有邊框 */
                border-radius: 10px;
                background-color: white;
                min-width: 500px;
                min-height: 200px;
            }}
        """)


    def set_manual_mode(self):
        """
        設定為手動生成模式，並更新按鈕樣式。
        """
        self.selected_mode = "manual"
        self.update_mode_button_styles() # 更新模式按鈕樣式
        self.update_start_button_state()

    def set_auto_mode(self):
        """
        設定為自動生成模式，並更新按鈕樣式。
        """
        self.selected_mode = "auto"
        self.update_mode_button_styles() # 更新模式按鈕樣式
        self.update_start_button_state()

    def update_mode_button_styles(self):
        """
        根據當前選定的模式，更新模式選擇按鈕的樣式。
        """
        # 模式選擇按鈕的啟用狀態只取決於是否有檔案載入
        is_mode_buttons_enabled = bool(self.html_processor.html_file_path)

        self.set_button_style(self.manual_mode_button, 
                              is_selected=(self.selected_mode == "manual"),
                              is_enabled=is_mode_buttons_enabled)
        self.set_button_style(self.auto_mode_button, 
                              is_selected=(self.selected_mode == "auto"),
                              is_enabled=is_mode_buttons_enabled)

    def update_start_button_state(self):
        """
        根據檔案和模式選擇狀態更新開始按鈕的啟用狀態。
        """
        is_enabled = bool(self.html_processor.html_file_path and self.selected_mode)
        self.set_button_style(self.start_button, is_accent=True, is_enabled=is_enabled)


    def start_alt_generation(self):
        """
        根據選擇的模式導向不同頁面。
        """
        if not self.html_processor.html_file_path:
            QMessageBox.warning(self, "錯誤", "請先上傳 HTML 檔案。")
            return
        if not self.selected_mode:
            QMessageBox.warning(self, "錯誤", "請先選擇生成模式。")
            return

        if self.selected_mode == "manual":
            self.show_manual_page()
        elif self.selected_mode == "auto":
            QMessageBox.information(self, "功能開發中", "自動生成 Alt (AI) 功能正在積極開發中，敬請期待！")
            # 保持在首頁，不需要跳轉到 auto_page
            # self.show_auto_page() 

    def load_image_thumbnail(self, image_path, size: QSize = QSize(60, 60)):
        """
        載入圖片並生成縮圖。
        處理相對路徑。
        """
        pixmap = QPixmap()
        if not image_path:
            return pixmap # 返回空的 QPixmap

        html_dir = os.path.dirname(self.html_processor.html_file_path) if self.html_processor.html_file_path else ""
        
        # 處理絕對路徑 vs 相對路徑
        abs_image_path = image_path
        if html_dir and not os.path.isabs(image_path): # 只有當有 HTML 目錄且圖片路徑為相對路徑時才進行拼接
            abs_image_path = os.path.normpath(os.path.join(html_dir, image_path))
        
        print(f"DEBUG: Attempting to load thumbnail from: {abs_image_path}") # 加強調試輸出
        try:
            # 嘗試使用 Pillow 載入圖片，可以處理更多格式和潛在的問題
            pil_image = PilImage.open(abs_image_path)
            
            # 修正：確保圖片是 RGB 或 RGBA 模式，並明確計算 bytesPerLine
            if pil_image.mode not in ('RGB', 'RGBA'):
                pil_image = pil_image.convert('RGB') # 如果需要保留透明度，請使用 'RGBA'

            # 計算正確的 bytesPerLine
            if pil_image.mode == 'RGB':
                bytes_per_line = pil_image.width * 3
                qimage_format = QImage.Format.Format_RGB888
            elif pil_image.mode == 'RGBA':
                bytes_per_line = pil_image.width * 4
                qimage_format = QImage.Format.Format_RGBA8888
            else: # Fallback (理論上不會走到這裡，因為前面已經 convert 了)
                return QPixmap() 

            qimage = QImage(pil_image.tobytes(), pil_image.width, pil_image.height, bytes_per_line, qimage_format)
            
            pixmap = QPixmap.fromImage(qimage)
            return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        except Exception as e:
            print(f"ERROR: Thumbnail load failed for {abs_image_path}: {e}") # 詳細錯誤信息
            # 如果圖片載入失敗，返回一個預設的佔位符圖片
            place_holder_pixmap = QPixmap(size)
            place_holder_pixmap.fill(QColor("lightgray"))
            painter = QPainter(place_holder_pixmap)
            painter.setFont(QFont("微軟正黑體", 8)) 
            painter.setPen(QColor("darkgray"))
            painter.drawText(place_holder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "無法載入圖片")
            painter.end()
            return place_holder_pixmap


    def populate_manual_image_list(self):
        """
        填充手動生成頁面的圖片列表。
        """
        self.manual_image_list_widget.clear() # 清空現有列表
        images_to_process = self.html_processor.get_images_to_process()

        if not images_to_process:
            item = QListWidgetItem(self.manual_image_list_widget)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable) # 不可選中
            # 自定義一個簡單的提示 widget
            no_image_widget = QWidget()
            no_image_layout = QVBoxLayout(no_image_widget)
            no_image_layout.addWidget(QLabel("此 HTML 檔案中沒有需要處理的圖片元素。", alignment=Qt.AlignmentFlag.AlignCenter))
            no_image_layout.setContentsMargins(0, 50, 0, 50) # 增加一些上下間距
            self.manual_image_list_widget.setItemWidget(item, no_image_widget)
            item.setSizeHint(no_image_widget.sizeHint())
            return

        for img_data in images_to_process:
            list_item = QListWidgetItem(self.manual_image_list_widget)
            
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item_layout.setContentsMargins(10, 5, 10, 5) # 內部邊距增加左右

            # 圖片預覽
            img_label = QLabel()
            thumbnail = self.load_image_thumbnail(img_data['src'])
            img_label.setPixmap(thumbnail)
            img_label.setFixedSize(60, 60) # 保持一致的縮圖大小
            # 點擊圖片放大
            img_label.mousePressEvent = lambda event, path=img_data['src']: self.show_image_preview(path)
            
            item_layout.addWidget(img_label)

            # 圖片原始路徑
            path_label = QLabel(f"路徑: {img_data['src']}")
            path_label.setFont(QFont("微軟正黑體", 14)) # 字體放大至 14px (修正點3)
            path_label.setStyleSheet("color: #555;") # 深灰色
            item_layout.addWidget(path_label)

            item_layout.addStretch(1) # 推開圖片路徑

            # Alt 輸入欄位
            alt_input = QLineEdit()
            alt_input.setPlaceholderText("請輸入 Alt 敘述")
            alt_input.setText(img_data['current_alt']) # 載入當前 alt
            alt_input.setProperty("original_alt", img_data['current_alt']) # 儲存原始 alt 值
            alt_input.setFixedSize(250, 30) # 固定輸入框大小
            alt_input.setStyleSheet(f"""
                QLineEdit {{
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 5px;
                    background-color: #f9f9f9;
                    color: {TEXT_COLOR_DARK}; /* 明確設定文字顏色為深色 (修正點2) */
                }}
            """)
            # 連接 textChanged 信號來追蹤修改
            alt_input.textChanged.connect(self.check_manual_alt_modification)
            
            # 將 alt_input 儲存到 list_item 的數據中，方便後續讀取
            list_item.setData(Qt.ItemDataRole.UserRole, {'element': img_data['element'], 'alt_input_widget': alt_input})
            item_layout.addWidget(alt_input)

            self.manual_image_list_widget.setItemWidget(list_item, item_widget)
            list_item.setSizeHint(item_widget.sizeHint()) # 根據 widget 調整 item 高度

    def check_manual_alt_modification(self):
        """
        檢查手動生成頁面中是否有任何 Alt 敘述被修改。
        """
        modified = False
        for i in range(self.manual_image_list_widget.count()):
            list_item = self.manual_image_list_widget.item(i)
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            if item_data:
                alt_input_widget = item_data['alt_input_widget']
                current_text = alt_input_widget.text().strip()
                original_text = alt_input_widget.property("original_alt").strip()
                if current_text != original_text:
                    modified = True
                    break
        self.is_manual_alt_modified = modified
        self.update_manual_confirm_button_state()

    def update_manual_confirm_button_state(self):
        """
        更新手動頁面「確定並儲存」按鈕的啟用狀態。
        """
        # 只有當有圖片需要處理且有內容被修改時，按鈕才啟用
        images_to_process = self.html_processor.get_images_to_process()
        is_enabled = bool(images_to_process and self.is_manual_alt_modified)
        self.set_button_style(self.manual_confirm_button, is_accent=True, is_enabled=is_enabled)


    def show_image_preview(self, image_path):
        """
        顯示圖片放大預覽對話框。
        """
        # 將 html_processor 實例傳遞給對話框
        dialog = ImagePreviewDialog(image_path, self.html_processor, self)
        dialog.exec() # 以模態方式顯示對話框

    def save_manual_alts(self):
        """
        從手動生成頁面收集新的 Alt 敘述並保存到 HTML 檔案。
        """
        updated_images_data = []
        # 遍歷所有列表項，即使它們是提示訊息 (但要跳過沒有數據的)
        for i in range(self.manual_image_list_widget.count()):
            list_item = self.manual_image_list_widget.item(i)
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            
            if item_data: # 如果是有效數據項 (非提示訊息)
                img_element = item_data['element']
                alt_input_widget = item_data['alt_input_widget']
                new_alt = alt_input_widget.text().strip()
                
                updated_images_data.append({
                    'element': img_element,
                    'new_alt': new_alt
                })

        success, message = self.html_processor.save_html_with_new_alts(updated_images_data)

        if success:
            QMessageBox.information(self, "保存成功", message)
            self.show_home_page() # 保存成功後返回首頁
        else:
            QMessageBox.warning(self, "保存失敗", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AltGeneratorApp()
    window.show()
    sys.exit(app.exec())