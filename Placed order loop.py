#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import random
import string
import re
import os
from datetime import datetime
from typing import List, Optional

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

# ------------------------- Simple random data -------------------------
FIRST_NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Riley", "Drew", "Cameron", "Jamie", "Avery"]
LAST_NAMES  = ["Lee", "Patel", "Garcia", "Singh", "Kim", "Chen", "Khan", "Brown", "Davis", "Martin"]
STREETS     = ["Main St", "High St", "Park Ave", "Oak St", "Maple Ave", "Pine St", "Cedar Rd", "Lakeview Dr"]
CITIES      = ["Mumbai", "Pune", "Bengaluru", "Delhi", "Hyderabad", "Chennai", "Kolkata"]
POSTCODES   = ["400001", "560001", "110001", "500001", "600001", "700001", "411001"]

def rand_first(): return random.choice(FIRST_NAMES)
def rand_last():  return random.choice(LAST_NAMES)
def rand_house(): return str(random.randint(10, 999))
def rand_street():return f"{rand_house()} {random.choice(STREETS)}"
def rand_city():  return random.choice(CITIES)
def rand_postal():return random.choice(POSTCODES)
def rand_email(first, last):
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{first.lower()}.{last.lower()}{suffix}@example.com"

# ------------------------- Helpers -------------------------
async def safe_fill(page: Page, selector: str, value: str, name: Optional[str] = None, timeout: int = 15000):
    label = name or selector
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await el.fill(value)
        print(f"✔ Filled {label}: {value}")
    except PlaywrightTimeoutError:
        print(f"⚠ Could not find {label} (selector: {selector}). Skipping.")

async def safe_click(page: Page, locator_or_text: str, timeout: int = 15000, role_button: bool = False):
    try:
        if role_button:
            loc = page.get_by_role("button", name=locator_or_text, exact=False)
        else:
            loc = page.locator(locator_or_text)
        await loc.first.wait_for(state="visible", timeout=timeout)
        await loc.first.click()
        print(f"✔ Clicked: {locator_or_text}")
        return True
    except PlaywrightTimeoutError:
        print(f"⚠ Button/element not clickable: {locator_or_text}")
        return False

async def click_first_that_exists(page: Page, candidates: List[str], timeout_each: int = 8000):
    for cand in candidates:
        ok = await safe_click(page, cand, timeout=timeout_each, role_button=True)
        if ok:
            return True
    return False

async def wait_and_click_continue(page: Page):
    """
    Finds the primary continue/next button on checkout, waits until it's enabled, then clicks it.
    Works across different locales/steps.
    """
    texts = [
        re.compile("Continue to shipping", re.I),
        re.compile("Continue to delivery", re.I),
        re.compile("Continue to payment", re.I),
        re.compile("Continue", re.I),
        re.compile("Next", re.I),
        re.compile("Review order", re.I),
    ]
    for t in texts:
        btn = page.get_by_role("button", name=t)
        try:
            await btn.first.wait_for(state="visible", timeout=6000)
            handle = await btn.first.element_handle()
            if handle:
                await page.wait_for_function(
                    "(b) => b && !b.hasAttribute('disabled') && !b.getAttribute('aria-disabled')",
                    arg=handle,
                    timeout=8000,
                )
            await btn.first.click()
            label = t.pattern if hasattr(t, "pattern") else str(t)
            print(f"✔ Clicked continue button: {label}")
            return True
        except Exception:
            continue
    return False

async def fill_card_iframe_field(page: Page, frame_name_prefix: str, input_name: str, value: str):
    iframe = page.frame_locator(f"iframe[name^='{frame_name_prefix}']").first
    field = iframe.locator(f"input[name='{input_name}']")
    await field.wait_for(state="visible", timeout=15000)
    await field.click()
    await field.fill(value)
    await page.wait_for_timeout(400)

# ------------------------- Main run -------------------------
async def run(
    store_base: str = "https://teststore-12-1.myshopify.com",
    password: str   = "z",
    product_path: str = "/products/t-shirt",
    headless: bool = False,
    screenshots_dir: str = "checkout_result",
):
    # Ensure screenshot folder exists at startup
    os.makedirs(screenshots_dir, exist_ok=True)

    password_url = f"{store_base}/password"
    product_url  = f"{store_base}{product_path}"

    # Random user/shipping data
    first_name = rand_first()
    last_name  = rand_last()
    email      = rand_email(first_name, last_name)
    addr1      = rand_street()
    addr2      = "Apt " + str(random.randint(1, 50))
    city       = rand_city()
    postal     = rand_postal()

    print("=== Shopify automation start ===")
    print(f"Time: {datetime.now().isoformat()}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(30000)

        # ---- Loop the process 10 times ----
        for i in range(10):
            print(f"\n🌟 Running iteration {i+1} of 10")

            # ---- STEP 1: password page ----
            print("→ Step 1: Opening password page…")
            await page.goto(password_url, wait_until="domcontentloaded")
            await safe_fill(page, "input#password.form-input", password, name="password")
            clicked_enter = await click_first_that_exists(page, ["Enter"])
            if not clicked_enter:
                await safe_click(page, "button[type='submit']", timeout=8000)

            # ---- STEP 2: product & robust Buy it now ----
            print("→ Step 2: Visiting product and clicking Buy it now…")
            await page.goto(product_url, wait_until="domcontentloaded")

            async def try_click_buy_now_and_wait():
                buy_now_selector = "button.shopify-payment-button__button--unbranded"

                # Prepare a popup listener BEFORE clicking (for Shop Pay, etc.)
                popup_task = asyncio.create_task(context.wait_for_event("page"))

                # Click the button (class first, then text)
                clicked = await safe_click(page, buy_now_selector, timeout=10000)
                if not clicked:
                    clicked = await safe_click(page, "Buy it now", timeout=10000, role_button=True)

                # Try to receive a popup quickly; if none, cancel the task
                try:
                    popup = await asyncio.wait_for(popup_task, timeout=5)
                    print("ℹ Detected a popup (likely Shop Pay). Closing it.")
                    await popup.close()
                except asyncio.TimeoutError:
                    popup_task.cancel()
                except Exception:
                    popup_task.cancel()

                # Now, wait for checkout URL change or email field
                try:
                    await page.wait_for_url(re.compile(r"(checkout|checkouts)"), timeout=25000)
                    print(f"✔ Reached checkout via URL: {page.url}")
                    return True
                except PlaywrightTimeoutError:
                    pass

                try:
                    await page.locator("#email").first.wait_for(state="visible", timeout=8000)
                    print("✔ Reached checkout (email field visible).")
                    return True
                except PlaywrightTimeoutError:
                    return False

            reached_checkout = await try_click_buy_now_and_wait()

            # Fallback: add to cart → /checkout
            if not reached_checkout:
                print("↪ Fallback: using Add to cart → /checkout …")
                added = await click_first_that_exists(page, [
                    "Add to cart",
                    "Add to bag",
                ])
                if not added:
                    added = await safe_click(page, "button[name='add']", timeout=8000)
                if not added:
                    added = await safe_click(page, "form[action*='/cart/add'] button[type='submit']", timeout=8000)
                await page.goto(f"{store_base}/checkout", wait_until="domcontentloaded")
                await page.locator("#email").first.wait_for(state="visible", timeout=15000)
                print("✔ Checkout reached after fallback.")

            # ---- STEP 3: checkout fields ----
            print("→ Step 3: Filling checkout contact & delivery…")

            # Contact (email)
            await safe_fill(page, "#email", email, name="email")

            # Marketing consent checkbox
            try:
                cb = page.locator("#marketing_opt_in").first
                await cb.wait_for(state="attached", timeout=5000)
                if not await cb.is_checked():
                    await cb.check()
                print("✔ Ticked marketing consent")
            except PlaywrightTimeoutError:
                print("⚠ Marketing consent checkbox not found (id=marketing_opt_in). Skipping.")

            # Delivery details — use stable name= attributes
            await safe_fill(page, "input[name='firstName']", first_name, name="firstName")
            await safe_fill(page, "input[name='lastName']",  last_name,  name="lastName")
            await safe_fill(page, "#shipping-address1",      addr1,      name="address1")
            await safe_fill(page, "input[name='address2']",  addr2,      name="address2")
            await safe_fill(page, "input[name='postalCode']", postal,    name="postalCode")

            # City may be hidden/auto-derived per locale; fill if present
            await safe_fill(page, "input[autocomplete*='address-level2']", city,   name="city")

            # Continue buttons across steps (wait until enabled)
            print("→ Advancing checkout steps…")
            if not await wait_and_click_continue(page):
                print("ℹ No continue button clickable at this step (may jump straight to payment).")

            # Shipping method (if shown)
            try:
                shipping_radio = page.locator("input[type='radio'][name='shipping_method']").first
                await shipping_radio.wait_for(state="visible", timeout=8000)
                await shipping_radio.check()
                print("✔ Selected first shipping method")
                await wait_and_click_continue(page)
            except PlaywrightTimeoutError:
                print("ℹ No separate shipping method step detected (or auto-selected).")

            # Payment iframes
            print("→ Filling payment card fields…")
            await fill_card_iframe_field(page, "card-fields-number", "number", "1")
            await fill_card_iframe_field(page, "card-fields-expiry", "expiry", "12/32")
            await fill_card_iframe_field(page, "card-fields-verification_value", "verification_value", "111")
            await fill_card_iframe_field(page, "card-fields-name", "name", f"{first_name} {last_name}")
            print("👉 Filled credit card info")

            # Pay now
            print("→ Clicking Pay now…")
            clicked_pay = await safe_click(page, "Pay now", timeout=60000, role_button=True)
            if not clicked_pay:
                clicked_pay = await safe_click(page, "button:has-text('Pay now')", timeout=60000)
            if not clicked_pay:
                await safe_click(page, "button[type='submit']", timeout=60000)
            print("👉 Clicked Pay now button")

            # Confirmation / thank you
            try:
                await page.wait_for_url(re.compile(r"/(orders|thank_you|checkouts/.+/thank_you)"), timeout=60000)
                print(f"✅ Reached confirmation URL: {page.url}")
            except PlaywrightTimeoutError:
                try:
                    await page.locator("text=Thank you").first.wait_for(state="visible", timeout=60000)
                    print("✅ Thank you message visible")
                except PlaywrightTimeoutError:
                    print("⚠️ Confirmation not detected; review the screenshot/logs.")

            # Screenshot (into checkout_result/)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            ss_path = os.path.join(screenshots_dir, f"checkout_result_{ts}.png")
            await page.screenshot(path=ss_path, full_page=True)
            print(f"📸 Saved screenshot: {ss_path}")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run(
        store_base="https://teststore-12-1.myshopify.com",
        password="z",
        product_path="/products/t-shirt",
        headless=False,                 # set True for CI/headless runs
        screenshots_dir="checkout_result",  # all screenshots saved here
    ))
