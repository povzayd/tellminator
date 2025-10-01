import requests
import time
import re
import argparse
import random
from datetime import datetime
from colorama import Fore, Style, init
from tqdm import tqdm
init(autoreset=True)

TELLONYM_API_URL = "https://api.tellonym.me/accounts/check"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Tellonym-Client": "web:3.143.0",
    "Content-Type": "application/json;charset=utf-8",
    "Origin": "https://tellonym.me",
    "Referer": "https://tellonym.me/",
}

EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

def is_email(value):
    return EMAIL_REGEX.match(value) is not None

def load_inputs(filepath):
    with open(filepath, "r") as file:
        return [line.strip() for line in file if line.strip()]

def load_proxies(filepath):
    with open(filepath, "r") as file:
        return [line.strip() for line in file if line.strip()]

def get_proxy(proxies):
    proxy = random.choice(proxies)
    return {"http": proxy, "https": proxy}

def save_result_to_log(result, log_path):
    with open(log_path, "a") as log_file:
        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        if result["status"] == "available":
            log_file.write(f"{ts} ✅ [{result['type']}] {result['value']} is available\n")
        elif result["status"] == "unavailable":
            log_file.write(f"{ts} ❌ [{result['type']}] {result['value']} is taken – {result.get('reason')}\n")
        else:
            log_file.write(f"{ts} ⚠️ Error checking {result['value']}: {result.get('reason')}\n")

def check_availability(value, check_email, proxy=None):
    params = {"limit": 25 if check_email else 4}
    if check_email:
        if not is_email(value):
            return {"value": value, "type": "email", "status": "error", "reason": "Invalid email format"}
        params["email"] = value
    else:
        params["username"] = value

    try:
        response = requests.get(TELLONYM_API_URL, headers=HEADERS, params=params, proxies=proxy, timeout=10)
    except Exception as e:
        return {"value": value, "type": "email" if check_email else "username", "status": "error", "reason": str(e)}

    if response.status_code != 200:
        return {"value": value, "status": "error", "reason": f"HTTP {response.status_code}"}

    data = response.json()

    if check_email:
        if data.get("email"):
            return {"value": value, "type": "email", "status": "available"}
        else:
            return {
                "value": value,
                "type": "email",
                "status": "unavailable",
                "reason": data.get("emailError", "Unknown error")
            }
    else:
        if data.get("username"):
            return {"value": value, "type": "username", "status": "available"}
        else:
            return {
                "value": value,
                "type": "username",
                "status": "unavailable",
                "reason": data.get("usernameError", {}).get("msg", "Unknown"),
                "suggestion": data.get("suggestion")
            }

def main():
    parser = argparse.ArgumentParser(description="Tellonym Username/Email OSINT Checker with Proxy Rotation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", action="store_true", help="Check email availability")
    group.add_argument("--username", action="store_true", help="Check username availability")
    parser.add_argument("--input", help="File with usernames/emails (one per line)")
    parser.add_argument("--value", help="Single username/email to check")
    parser.add_argument("--log", help="Path to log file")
    parser.add_argument("--proxyfile", help="File with list of proxies (http://IP:PORT, socks5://IP:PORT, etc.)")
    parser.add_argument("--rotate", type=int, default=5, help="Rotate IP after N checks")

    args = parser.parse_args()

    if not args.input and not args.value:
        print(Fore.RED + "❌ Provide either --input or --value")
        return

    values = load_inputs(args.input) if args.input else [args.value.strip()]
    check_email = args.email

    use_proxies = bool(args.proxyfile)
    proxies = load_proxies(args.proxyfile) if use_proxies else []
    proxy = None

    print(Fore.CYAN + f"\n[+] Starting Tellonym OSINT scan ({'email' if check_email else 'username'} mode)...\n")

    # progress bar wrapper
    for i, value in enumerate(tqdm(values, desc="Progress", unit="check"), 1):
        if use_proxies and (i == 1 or i % args.rotate == 0):
            proxy = get_proxy(proxies)
            print(Fore.YELLOW + f"\n🔁 Using new proxy: {proxy['http']}")

        result = check_availability(value, check_email, proxy=proxy)

        if result["status"] == "available":
            print(Fore.RED + f"🚫 {value} - User Not Found")
        elif result["status"] == "unavailable":
            print(Fore.GREEN + f"✅ {value} - User Found")
            if result.get("suggestion"):
                print(Fore.MAGENTA + "🎯 Target Found")
        else:
            print(Fore.LIGHTRED_EX + f"⚠️ Error checking {value}: {result.get('reason')}")

        if args.log:
            save_result_to_log(result, args.log)

        time.sleep(0.75)

if __name__ == "__main__":
    main()
