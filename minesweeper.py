from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import itertools
import random


# สร้าง options ก่อน แล้วใช้แค่ครั้งเดียว
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

actions = ActionChains(driver)

# ------------- Helpers -------------
def detect_size():
    script = """
      const cells = document.querySelectorAll('.square');
      let maxR=0, maxC=0;
      cells.forEach(c=>{
          const [r,c2] = c.id.split('_').map(Number);
          maxR = Math.max(maxR, r);
          maxC = Math.max(maxC, c2);
      });
      return [maxR, maxC];
    """
    return driver.execute_script(script)

def scrape_grid(rows, cols):
    script = """
        const rows = arguments[0], cols = arguments[1];
        const grid = Array.from({ length: rows }, () => Array(cols).fill(0));
        const cells = Array.from(document.querySelectorAll('.square'))
                            .filter(c => /^\\d+_\\d+$/.test(c.id));
        cells.forEach(cell => {
            const [r, c] = cell.id.split('_').map(Number);
            const cls = Array.from(cell.classList);
            let v;
            if (cls.includes('bombflagged')) {
            v = 'F';
            } else if (cls.some(cl => cl.startsWith('open'))) {
            const oc = cls.find(cl => cl.startsWith('open'));
            v = parseInt(oc.replace('open',''), 10);
            } else {
            v = 0;
            }
            if (r>=1 && r<=rows && c>=1 && c<=cols) {
            grid[r-1][c-1] = v;
            }
        });
        return grid;
    """

    return driver.execute_script(script, rows, cols)


def click_cell(r, c, flag=False):
    el = driver.find_element(By.ID, f"{r+1}_{c+1}")
    if flag:
        actions.context_click(el).perform()
    else:
        el.click()

def is_game_over():
    face = driver.find_element(By.ID, 'face')
    cls = face.get_attribute('class')
    return 'facedead' in cls or 'facewin' in cls

def print_grid(grid):
    for row in grid:
        print(' '.join(
            'F' if cell=='F'
            else '.' if cell==0
            else str(cell) if isinstance(cell,int)
            else '#'
            for cell in row
        ))

# ------------- Initial click -------------
rows, cols = detect_size()
click_cell(rows//2, cols//2)  # คลิกกลางบอร์ดเพื่อเริ่มเกม
time.sleep(0.5)

# ------------- Deterministic logic -------------
def deterministic(grid):
    rows, cols = len(grid), len(grid[0])
    changed = False
    for r in range(rows):
        for c in range(cols):
            k = grid[r][c]
            if not isinstance(k, int) or k<=0: continue
            nbrs = [(r+dr,c+dc) for dr,dc in itertools.product([-1,0,1],repeat=2)
                    if not (dr==dc==0)]
            unopened = [(i,j) for i,j in nbrs
                        if 0<=i<rows and 0<=j<cols and grid[i][j]==0]
            flagged = [(i,j) for i,j in nbrs
                       if 0<=i<rows and 0<=j<cols and grid[i][j]=='F']
            if len(unopened)==k:
                for (i,j) in unopened:
                    click_cell(i,j, flag=True)
                    grid[i][j] = 'F'
                    changed = True
            elif len(flagged)==k and unopened:
                for (i,j) in unopened:
                    click_cell(i,j, flag=False)
                    changed = True
    return changed

# ------------- Probabilistic fallback -------------
def compute_prob(frontier, grid):
    n = len(frontier)
    solutions = []
    assignment = [None]*n

    # nested valid & prune
    def valid():
        for r in range(len(grid)):
            for c in range(len(grid[0])):
                k = grid[r][c]
                if isinstance(k,int) and k>0:
                    nbrs = [(r+dr,c+dc) for dr,dc in itertools.product([-1,0,1],repeat=2)
                            if not (dr==dc==0)]
                    vals = [assignment[i] for i,(fr,fc) in enumerate(frontier)
                            if (fr,fc) in nbrs and assignment[i] is not None]
                    if len(vals)==sum(1 for i,(fr,fc) in enumerate(frontier) if (fr,fc) in nbrs) \
                       and sum(vals)!=k:
                        return False
        return True

    def prune(idx):
        fr,fc = frontier[idx]
        nbrs = [(fr+dr,fc+dc) for dr,dc in itertools.product([-1,0,1],repeat=2)
                if not (dr==dc==0)]
        klist = []
        for r,c in nbrs:
            if 0<=r<len(grid) and 0<=c<len(grid[0]):
                if isinstance(grid[r][c],int) and grid[r][c]>0:
                    klist.append(((r,c), grid[r][c]))
        for (r,c),k in klist:
            nbrs2 = [(r+dr,c+dc) for dr,dc in itertools.product([-1,0,1],repeat=2)
                     if not (dr==dc==0)]
            vals = [assignment[i] for i,(fr,fc) in enumerate(frontier)
                    if (fr,fc) in nbrs2 and assignment[i] is not None]
            unopened = sum(1 for (fr,fc) in frontier
                           if (fr,fc) in nbrs2 and assignment[frontier.index((fr,fc))] is None)
            if sum(vals)>k or sum(vals)+unopened<k:
                return False
        return True

    def backtrack(idx=0):
        if idx==n:
            if valid(): solutions.append(assignment.copy())
            return
        for b in (0,1):
            assignment[idx]=b
            if prune(idx):
                backtrack(idx+1)
        assignment[idx]=None

    backtrack()
    total = len(solutions)
    # if no solution, fallback to random
    if total==0:
        return None
    counts = [sum(sol[i] for sol in solutions) for i in range(n)]
    return { frontier[i]: counts[i]/total for i in range(n) }

def probabilistic_move(grid):
    rows,cols = len(grid), len(grid[0])
    frontier = [(r,c) for r in range(rows) for c in range(cols)
                if grid[r][c]==0 and any(isinstance(grid[i][j],int) and grid[i][j]>0
                   for i,j in [(r+dr,c+dc) for dr,dc in itertools.product([-1,0,1],repeat=2)
                               if not (dr==dc==0) and 0<=r+dr<rows and 0<=c+dc<cols])]
    if not frontier:
        return False
    probs = compute_prob(frontier, grid)
    if probs:
        cell = min(probs, key=probs.get)
    else:
        cell = random.choice(frontier)
    click_cell(*cell)
    return True

# ------------- Game Loop -------------
while not is_game_over():
    grid = scrape_grid(rows, cols)
    if deterministic(grid):
        time.sleep(0.1); continue
    if probabilistic_move(grid):
        time.sleep(0.1); continue
    # no moves left
    break

# ------------- End -------------
final_grid = scrape_grid(rows, cols)
print_grid(final_grid)
print("Game finished")
