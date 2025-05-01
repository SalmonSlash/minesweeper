from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

# 1. ตั้งค่า WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
driver.get("https://minesweeperonline.com/")
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "inner-container"))
)
print("เจอแล้ว!")

# Python: ตรวจจับขนาดบอร์ด
def detect_grid_size():
    script = """
        const cells = document.querySelectorAll('.square');
        let maxR = 0, maxC = 0;
        cells.forEach(({ id }) => {
            const [r, c] = id.split('_').map(Number);
            if (r > maxR) maxR = r;
            if (c > maxC) maxC = c;
        });
        return [maxR, maxC];
    """
    return driver.execute_script(script)

# Python: ดึงกริดขนาดไดนามิก
def scrape_grid(rows, cols):
    script = """
        const rows = arguments[0], cols = arguments[1];
        // สร้างตาราง 2D อย่างถูกต้อง
        const grid = Array.from({ length: rows },
                                () => Array(cols).fill(0));
        document.querySelectorAll('.square').forEach(cell => {
            const [r, c] = cell.id.split('_').map(Number);
            const openClass = Array.from(cell.classList)
                                 .find(cl => cl.startsWith('open'));
            const value = openClass
                          ? parseInt(openClass.replace('open',''), 10)
                          : 0;
            // ตรวจสอบขอบเขตก่อนเซ็ต
            if (r > 0 && r <= rows && c > 0 && c <= cols) {
                grid[r-1][c-1] = value;
            } else {
                console.warn(`Out-of-bounds: (${r},${c}) vs size ${rows}×${cols}`);
            }
        });
        return grid;
    """
    return driver.execute_script(script, rows, cols)

# Main script
rows, cols = detect_grid_size()
print(f"Detected: {rows}×{cols}")
grid = scrape_grid(rows, cols)
print(grid)

time.sleep(5)  # รอ 5 วินาทีเพื่อดูผลลัพธ์