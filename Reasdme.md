# 1) Clone or copy files into a folder, then:
python3 -m venv venv
source venv/bin/activate

# 2) Install dependencies
pip install playwright

# 3) Install Playwright browsers (Chromium)
python -m playwright install

# 4) Run
python shopify_checkout.py
