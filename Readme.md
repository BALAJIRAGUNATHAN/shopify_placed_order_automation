# Shopify Placed order Automation (Python + Playwright)



> ⚠️ **For Testing Only**  
> This script is intended for use on Shopify test stores and should **not** be run on production stores. You should only use this against development or staging environments with a test payment gateway enabled (e.g., Shopify's "Bogus Gateway" or Shopify Payments in **test mode**).

---

## Requirements

Before running the script, ensure that you have the following installed:

### 1. Python 3.9+

Verify that Python is installed by running:

```bash


python3 --version

python3 -m venv venv
source venv/bin/activate


pip install playwright
python -m playwright install

source venv/bin/activate

python cart.py
