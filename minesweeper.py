from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import random
import time

# --- Setup Selenium Chrome Driver ---
options = Options()
options.add_argument("--log-level=3")  # แสดงเฉพาะ ERROR

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

driver.get("https://minesweeperonline.com/")
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "inner-container"))
)


def click_cell(r, c, flag, timeout=500):
    print(f"Clicking cell ({r},{c}) {'flag' if flag else 'open'}")
    locator = (By.ID, f"{r}_{c}")
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    WebDriverWait(driver, timeout).until(lambda d: True)
    if flag:
        print(f"locator: {locator}, element ID: {el.get_attribute('id')}")
        ActionChains(driver).context_click(el).perform()
    else:
        el.click()
    print(f"Clicked cell ({r},{c}) {'flagged' if flag else 'opened'}")

def detect_size():
    script = '''
      const cells = document.querySelectorAll('.square');
      let maxR=0, maxC=0;
      cells.forEach(c => {
          const [r, c2] = c.id.split('_').map(Number);
          maxR = Math.max(maxR, r);
          maxC = Math.max(maxC, c2);
      });
      return [maxR+1, maxC+1];
    '''
    return driver.execute_script(script)
def scrape_grid(rows, cols):
    script = '''
        const rows = arguments[0], cols = arguments[1];
        const grid = Array.from({ length: rows }, () => Array(cols).fill(null));
        document.querySelectorAll('.square').forEach(cell => {
            const id = cell.id;
            const match = id.match(/^(\d+)_(\d+)$/);
            if (!match) return;
            const r = +match[1], c = +match[2];
            const cls = Array.from(cell.classList);
            let v = null;
            if (cls.includes('bombflagged')) v = 'F';
            else if (cls.some(cl => cl.startsWith('open'))) {
                const oc = cls.find(cl => cl.startsWith('open'));
                v = parseInt(oc.replace('open',''), 10);
            }
            if (r < rows && c < cols) grid[r][c] = v;
        });
        return grid;
    '''
    return driver.execute_script(script, rows, cols)

def deterministic_one_move(grid):
    rows, cols = len(grid), len(grid[0])
    for r in range(rows):
        for c in range(cols):
            val = grid[r][c]
            if not isinstance(val, int) or val <= 0:
                continue
            nbrs = []
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if dr == dc == 0: continue
                    rr, cc = r+dr, c+dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        nbrs.append((rr, cc))
            # print(f"Cell ({r},{c}) has {val} unopened neighbors: {nbrs}")
            unopened = [(i,j) for (i,j) in nbrs if grid[i][j] is None]
            flagged  = [(i,j) for (i,j) in nbrs if grid[i][j] == 'F']
            print(f"Cell ({r},{c}) has {val} Neighbours:, {nbrs} unopened neighbors: {unopened}, flagged: {flagged}")
            # ถ้า unseen+flag == val -> flag rest
            if len(unopened) + len(flagged) == val and unopened:
                i,j = unopened[0]
                click_cell(i,j, flag=True)
                grid = scrape_grid(rows, cols)
                for r in range(rows):
                    for c in range(cols):
                        print(grid[r][c], end=" ")
                    print()
                return True
            # ถ้า flagged == val -> open rest
            if len(flagged) == val and unopened:
                i,j = unopened[0]
                click_cell(i,j, flag=False)
                return True
    return False


# Main
rows, cols = detect_size()
# initial click center
time.sleep(1)
click_cell(rows//2, cols//2, flag=False)
grid = scrape_grid(rows, cols)
for r in range(rows):
    for c in range(cols):
        print(grid[r][c], end=" ")
    print()
grid = scrape_grid(rows, cols)

# Loop deterministic moves until none left
# while True:
#     grid = scrape_grid(rows, cols)
#     if not deterministic_one_move(grid):
#         print('No more deterministic moves - stopping.')
#         break
time.sleep(100)
print('Finished.')
