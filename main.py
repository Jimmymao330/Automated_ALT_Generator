import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 使用webdriver-manager來管理ChromeDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# 定義密碼變數
password = 'Yy558746'  # 替換為你的密碼

try:
    # 打開目標網頁
    driver.get('https://tschool.tp.edu.tw/passport/tpeEntrance')

    # 等待網頁加載並找到超連結
    link = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.tab[href="/passport/tpeOAuth"]'))
    )

    # 點擊超連結
    link.click()

    # 等待重新導向的網頁加載
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, 'standard-basic'))
    )

    # 找到帳號輸入框，點擊並輸入帳號
    account_input = driver.find_element(By.ID, 'standard-basic')
    account_input.click()  # 點擊輸入框
    account_input.clear()  # 清空輸入框
    account_input.send_keys('tschool11330210')

    # 找到密碼輸入框，點擊並輸入密碼
    password_input = driver.find_element(By.ID, 'standard-password-input')
    password_input.click()  # 點擊輸入框
    password_input.clear()  # 清空輸入框
    password_input.send_keys(password)  # 使用變數來輸入密碼

    # 找到並點擊「登入」按鈕
    login_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
    )
    login_button.click()

    # 等待登入後的頁面加載
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="https://tschool.tp.edu.tw/nss/s/main/p/achievement"]'))
    )

    # 找到並點擊「學生成果」連結
    achievement_link = driver.find_element(By.CSS_SELECTOR, 'a[href="https://tschool.tp.edu.tw/nss/s/main/p/achievement"]')
    achievement_link.click()

finally:
    # 等待十秒
    time.sleep(10)
    # 關閉瀏覽器
    driver.quit()
