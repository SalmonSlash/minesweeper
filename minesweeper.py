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
import itertools
from collections import defaultdict

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

def is_game_over():
    # 1. หา <div id="face"> ซึ่งจะมี class="facedead" เมื่อแพ้ หรือ class="facewin" เมื่อชนะ
    face = driver.find_element(By.ID, "face")
    # 2. อ่านชื่อคลาสทั้งหมด (สตริง)
    cls  = face.get_attribute("class")
    # 3. คืน True ถ้ามีคำว่า facedead (แพ้) หรือ facewin (ชนะ) อยู่ในคลาส
    return "facedead" in cls or "facewin" in cls

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
                    if dr == dc == 0:
                        continue
                    rr, cc = r+dr, c+dc
                    # กรองให้ 1 <= rr <= rows-2 และ 1 <= cc <= cols-2
                    if 1 <= rr < rows-1 and 1 <= cc < cols-1:
                        nbrs.append((rr, cc))

            unopened = [(i,j) for (i,j) in nbrs if grid[i][j] is None]
            flagged  = [(i,j) for (i,j) in nbrs if grid[i][j] == 'F']
            # print(f"Cell ({r},{c}) val={val} nbrs={nbrs} unopen={unopened} flagged={flagged}")

            # ปักธง
            if len(unopened) + len(flagged) == val and unopened:
                i, j = unopened[0]
                click_cell(i, j, flag=True)
                return True

            # เปิดช่อง
            if len(flagged) == val and unopened:
                i, j = unopened[0]
                click_cell(i, j, flag=False)
                return True

    return False

def find_frontier(grid):
    rows, cols = len(grid), len(grid[0])
    frontier = set()
    constraints = []

    for r in range(rows):
        for c in range(cols):
            k = grid[r][c]
            if isinstance(k, int) and k > 0:
                nbrs = []
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        if dr==dc==0: continue
                        rr, cc = r+dr, c+dc
                        # อยู่ในบอร์ด และข้ามแถว/คอลัมน์ 0 กับ index สุดท้าย
                        if 1 <= rr < rows-1 and 1 <= cc < cols-1:
                            nbrs.append((rr,cc))

                unopened = [(rr,cc) for (rr,cc) in nbrs if grid[rr][cc] is None]
                flagged  = sum(1 for (rr,cc) in nbrs if grid[rr][cc]=='F')
                if unopened:
                    frontier.update(unopened)
                    constraints.append((unopened, k-flagged))

    # เรียงลำดับเพื่อให้ดูง่าย จากบนลงล่าง ซ้ายไปขวา
    frontier = sorted(frontier, key=lambda x:(x[0], x[1]))
    return frontier, constraints


import itertools
from collections import defaultdict
import time

def compute_prob(frontier, constraints):
    """
    frontier: list of (r,c)
    constraints: list of (list of (r,c), required_mines)
    คืน dict {(r,c): probability} หรือ None ถ้าไม่มีชุด valid
    """

    n = len(frontier)
    # แปลง constraints ให้อยู่ในรูป index ของ frontier
    idx_map = { cell:i for i,cell in enumerate(frontier) }
    constr_idx = []
    for cells, required in constraints:
        idxs = [idx_map[cell] for cell in cells if cell in idx_map]
        constr_idx.append((idxs, required))

    solutions = 0
    counts = [0]*n
    nodes = 0
    start = time.time()

    assignment = [None]*n

    def prune(idx):
        # หลังกำหนด assignment[idx], ตรวจ partial constraints
        for idxs, required in constr_idx:
            s = 0
            unknown = 0
            for j in idxs:
                v = assignment[j]
                if v is None:
                    unknown += 1
                else:
                    s += v
            if s > required or s + unknown < required:
                return False
        return True

    def backtrack(i=0):
        nonlocal solutions, nodes
        if i == n:
            # valid full assignment
            solutions += 1
            for j,v in enumerate(assignment):
                if v:
                    counts[j] += 1
            # log every 1000 solutions
            if solutions % 1000 == 0:
                print(f"[{solutions}] valid assignments found, nodes visited {nodes}")
            return

        for val in (0,1):
            assignment[i] = val
            nodes += 1
            # log progress every 10000 nodes
            if nodes % 10000 == 0:
                elapsed = time.time() - start
                print(f"Visited {nodes} nodes, solutions={solutions}, elapsed={elapsed:.1f}s")
            if prune(i):
                backtrack(i+1)
        assignment[i] = None

    # เริ่ม backtracking
    backtrack()

    if solutions == 0:
        return None

    # คำนวณ probability
    probs = { frontier[i]: counts[i] / solutions for i in range(n) }
    print(f"Done: {solutions} valid in {nodes} nodes, time {time.time()-start:.1f}s")
    return probs

def is_game_over():
    try:
        face = driver.find_element(By.ID, "face")
        cls  = face.get_attribute("class")
        return "facedead" in cls or "facewin" in cls
    except:
        return True  # ถ้าหาไม่เจอเลยก็ถือว่าจบ


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

last_click = None
same_click_count = 0
MAX_SAME_CLICKS = 5   # ถ้าเกิน 3 ครั้ง ถือว่าค้าง

# Loop deterministic moves until none left
while True:
    if is_game_over():
        break

    # 1) deterministic
    while True:
        if is_game_over():
            break
        grid = scrape_grid(rows, cols)
        if not deterministic_one_move(grid):
            break
        time.sleep(0.05)

    if is_game_over():
        break

    grid = scrape_grid(rows, cols)   # รอบนี้ปลอดภัย เพราะเช็คแล้ว
    frontier, constraints = find_frontier(grid)
    if not frontier:
        break

    probs = compute_prob(frontier, constraints)

    if probs:
        target = min(probs, key=probs.get)
    else:
        target = random.choice(frontier)

    # check repeated clicks
    if target == last_click:
        same_click_count += 1
    else:
        same_click_count = 0
        last_click = target

    if same_click_count >= MAX_SAME_CLICKS:
        print(f"🔴 Clicked {target} ซ้ำ {same_click_count} รอบ เกมน่าจะค้าง จบ หรือ แพ้")
        break

    click_cell(*target, flag=False)
    time.sleep(0.05)


print('Finished.')
print('Waiting 500 seconds... program will quit.')
time.sleep(500)
driver.quit()