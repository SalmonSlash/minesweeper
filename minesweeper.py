from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def detect_grid_size():
    script = """
        // รับ arguments[0..] จาก Python
        const cells = document.querySelectorAll('.square');  // :contentReference[oaicite:1]{index=1}
        let maxR = 0, maxC = 0;
        cells.forEach(cell => {
            const [r, c] = cell.id.split('_').map(Number);   // :contentReference[oaicite:2]{index=2}
            if (r > maxR) maxR = r;
            if (c > maxC) maxC = c;
        });
        return [maxR, maxC];
    """
    maxR, maxC = driver.execute_script(script)
    return maxR, maxC

def scrape_grid(rows, cols):
    script = """
        const rows = arguments[0], cols = arguments[1];      // :contentReference[oaicite:5]{index=5}
        const grid = Array.from({length: rows},               // :contentReference[oaicite:6]{index=6}
                                () => Array(cols).fill(0));
        document.querySelectorAll('.square').forEach(cell => { // :contentReference[oaicite:7]{index=7}
            const [r, c] = cell.id.split('_').map(Number);    // :contentReference[oaicite:8]{index=8}
            const openClass = Array.from(cell.classList)      // :contentReference[oaicite:9]{index=9}
                                 .find(cl => cl.startsWith('open'));
            const value = openClass
                          ? parseInt(openClass.replace('open',''), 10)
                          : 0;
            grid[r-1][c-1] = value;
        });
        return grid;
    """
    return driver.execute_script(script, rows, cols)

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

# ตรวจขนาดบอร์ดอัตโนมัติ
rows, cols = detect_grid_size()
print(f"Detected grid size: {rows}×{cols}")

# ดึงค่าทุกเซลล์
grid = scrape_grid(rows, cols)
print(grid)