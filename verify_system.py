#!/usr/bin/env python3
"""
verify_system.py — End-to-End Diagnostic & Audit Tool
Tests:
1. Supabase Direct Read/Write (using SUPABASE_URL & SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY)
2. Live Vercel Audit (Root, /api/health, /api/opportunities, /api/chat)
3. Storage source validation (Supabase live vs local JSON fallback)
"""

import os
import sys
import json
import time
import requests
from dotenv import dotenv_values, load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load local environment
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

env_local = dotenv_values(".env.local") if os.path.exists(".env.local") else {}

def get_env_var(key: str, default: str = None) -> str:
    return (
        os.environ.get(key)
        or env_local.get(key)
        or os.environ.get(key.lower())
        or env_local.get(key.lower())
        or default
    )

SUPABASE_URL = get_env_var("SUPABASE_URL")
SUPABASE_KEY = (
    get_env_var("SUPABASE_SERVICE_ROLE_KEY")
    or get_env_var("SUPABASE_KEY")
)
VERCEL_BASE_URL = get_env_var("VERCEL_URL", "https://student-opportunities-agents.vercel.app").rstrip("/")
if not VERCEL_BASE_URL.startswith("http"):
    VERCEL_BASE_URL = f"https://{VERCEL_BASE_URL}"

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_supabase_direct() -> dict:
    print_header("TEST 1: Supabase Direct Read/Write Diagnostic")
    results = {"pass": False, "total_rows": 0, "details": []}

    if not SUPABASE_URL or not SUPABASE_KEY:
        results["details"].append("FAIL: SUPABASE_URL or SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY missing.")
        print("❌ Missing Supabase credentials in environment or .env.local")
        return results

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    test_id = f"diagnostic-test-{int(time.time())}"
    rest_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/opportunities"

    try:
        # Step A: Insert a test opportunity row
        print(f"[*] Inserting test opportunity row (id={test_id})...")
        payload = [{
            "id": test_id,
            "title": "System Diagnostic Test Opportunity",
            "host_organization": "YouthHub QA Agent",
            "category": "Internship",
            "academic_level": ["Undergraduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Funded",
            "deadline": "2027-12-31",
            "apply_url": "https://student-opportunities-agents.vercel.app",
            "tags": ["QA", "Diagnostic", "Test"],
            "one_line_pitch": "Automated verification test row for Supabase PostgreSQL.",
            "is_active": True
        }]

        r_insert = requests.post(rest_url, headers=headers, json=payload, timeout=10)
        if r_insert.status_code not in (200, 201):
            results["details"].append(f"FAIL: Insert returned HTTP {r_insert.status_code}: {r_insert.text}")
            print(f"❌ Insert failed: {r_insert.status_code} - {r_insert.text}")
            return results
        print(f"✅ Test row inserted successfully (HTTP {r_insert.status_code}).")

        # Step B: Read back from public.opportunities
        print(f"[*] Reading back test row from Supabase...")
        r_read = requests.get(f"{rest_url}?id=eq.{test_id}", headers=headers, timeout=10)
        if r_read.status_code != 200 or not r_read.json():
            results["details"].append(f"FAIL: Read back returned HTTP {r_read.status_code}: {r_read.text}")
            print(f"❌ Read back failed: {r_read.status_code}")
            return results
        read_row = r_read.json()[0]
        print(f"✅ Read back verified: '{read_row.get('title')}' by {read_row.get('host_organization')}.")

        # Step C: Delete the test row
        print(f"[*] Cleaning up test row...")
        r_delete = requests.delete(f"{rest_url}?id=eq.{test_id}", headers=headers, timeout=10)
        if r_delete.status_code in (200, 204):
            print("✅ Test row deleted successfully.")
        else:
            print(f"⚠️ Warning: Cleanup returned HTTP {r_delete.status_code}")

        # Step D: Count total rows in Supabase
        r_count = requests.get(f"{rest_url}?select=id", headers=headers, timeout=10)
        total_rows = len(r_count.json()) if r_count.status_code == 200 else 0
        results["total_rows"] = total_rows
        results["pass"] = True
        print(f"✅ Current total active opportunities in Supabase: {total_rows}")
        results["details"].append(f"PASS: Read/Write/Delete verified. Current Supabase count: {total_rows}")

    except Exception as e:
        results["details"].append(f"FAIL: Exception during Supabase test: {str(e)}")
        print(f"❌ Exception: {e}")

    return results

def test_live_vercel() -> dict:
    print_header("TEST 2: Live Vercel Audit")
    results = {
        "pass": False,
        "endpoints": {},
        "storage_source": "unknown",
        "supabase_connected": False,
        "total_opportunities": 0
    }

    # 1. Root /
    try:
        url_root = f"{VERCEL_BASE_URL}/"
        print(f"[*] Testing GET {url_root}...")
        r_root = requests.get(url_root, timeout=15)
        is_ok = r_root.status_code == 200 and "Opportunity Scout" in r_root.text
        results["endpoints"]["/"] = {
            "status": r_root.status_code,
            "pass": is_ok,
            "latency_ms": int(r_root.elapsed.total_seconds() * 1000)
        }
        print(f"    Status: {r_root.status_code} ({results['endpoints']['/']['latency_ms']}ms) — {'PASS' if is_ok else 'FAIL'}")
    except Exception as e:
        results["endpoints"]["/"] = {"status": "ERR", "pass": False, "error": str(e)}
        print(f"    Error: {e}")

    # 2. /api/health
    try:
        url_health = f"{VERCEL_BASE_URL}/api/health?t={int(time.time())}"
        print(f"[*] Testing GET {url_health}...")
        r_health = requests.get(url_health, headers={"Cache-Control": "no-cache"}, timeout=15)
        h_json = r_health.json() if r_health.status_code == 200 else {}
        is_ok = r_health.status_code == 200 and h_json.get("status") == "ok"
        results["storage_source"] = h_json.get("storage_source", "unknown")
        results["supabase_connected"] = h_json.get("supabase_connected", False)
        results["total_opportunities"] = h_json.get("total_opportunities", 0)

        results["endpoints"]["/api/health"] = {
            "status": r_health.status_code,
            "pass": is_ok,
            "data": h_json,
            "latency_ms": int(r_health.elapsed.total_seconds() * 1000)
        }
        print(f"    Status: {r_health.status_code} ({results['endpoints']['/api/health']['latency_ms']}ms) — {'PASS' if is_ok else 'FAIL'}")
        print(f"    Storage Source: {results['storage_source']}")
        print(f"    Supabase Connected: {results['supabase_connected']}")
        print(f"    Total Opportunities: {results['total_opportunities']}")
    except Exception as e:
        results["endpoints"]["/api/health"] = {"status": "ERR", "pass": False, "error": str(e)}
        print(f"    Error: {e}")

    # 3. /api/opportunities
    try:
        url_opps = f"{VERCEL_BASE_URL}/api/opportunities?limit=1000&t={int(time.time())}"
        print(f"[*] Testing GET {url_opps}...")
        r_opps = requests.get(url_opps, headers={"Cache-Control": "no-cache"}, timeout=15)
        opps_data = r_opps.json() if r_opps.status_code == 200 else []
        items = opps_data.get("data", []) if isinstance(opps_data, dict) else (opps_data if isinstance(opps_data, list) else [])
        total_found = opps_data.get("total", len(items)) if isinstance(opps_data, dict) else len(items)
        is_ok = r_opps.status_code == 200 and len(items) > 0
        results["endpoints"]["/api/opportunities"] = {
            "status": r_opps.status_code,
            "pass": is_ok,
            "count": len(items),
            "total_in_db": total_found,
            "cache_control": r_opps.headers.get("Cache-Control", ""),
            "latency_ms": int(r_opps.elapsed.total_seconds() * 1000)
        }
        print(f"    Status: {r_opps.status_code} ({results['endpoints']['/api/opportunities']['latency_ms']}ms) — {'PASS' if is_ok else 'FAIL'}")
        print(f"    Items Returned: {results['endpoints']['/api/opportunities']['count']} (Total DB: {total_found})")
        print(f"    Cache-Control: {results['endpoints']['/api/opportunities']['cache_control']}")
    except Exception as e:
        results["endpoints"]["/api/opportunities"] = {"status": "ERR", "pass": False, "error": str(e)}
        print(f"    Error: {e}")

    # 4. /api/chat (POST test message)
    try:
        url_chat = f"{VERCEL_BASE_URL}/api/chat"
        print(f"[*] Testing POST {url_chat} (Agent 4 Student Advisor)...")
        chat_payload = {
            "message": "Hello! What scholarships or internships are available for CS students?",
            "history": []
        }
        r_chat = requests.post(url_chat, json=chat_payload, timeout=25)
        chat_json = r_chat.json() if r_chat.status_code == 200 else {}
        is_ok = r_chat.status_code == 200 and bool(chat_json.get("reply"))
        results["endpoints"]["/api/chat"] = {
            "status": r_chat.status_code,
            "pass": is_ok,
            "latency_ms": int(r_chat.elapsed.total_seconds() * 1000),
            "reply_snippet": (chat_json.get("reply", "")[:120] + "...") if chat_json.get("reply") else ""
        }
        print(f"    Status: {r_chat.status_code} ({results['endpoints']['/api/chat']['latency_ms']}ms) — {'PASS' if is_ok else 'FAIL'}")
        if is_ok:
            print(f"    Reply preview: {results['endpoints']['/api/chat']['reply_snippet']}")
    except Exception as e:
        results["endpoints"]["/api/chat"] = {"status": "ERR", "pass": False, "error": str(e)}
        print(f"    Error: {e}")

    # Overall Live Vercel Audit Pass
    all_endpoints_pass = all(ep.get("pass", False) for ep in results["endpoints"].values())
    results["pass"] = all_endpoints_pass
    return results

def main():
    print("=" * 70)
    print("  🚀 OPPORTUNITY SCOUT — END-TO-END SYSTEM DIAGNOSTIC & AUDIT")
    print("=" * 70)
    print(f"Target Vercel URL : {VERCEL_BASE_URL}")
    print(f"Target Supabase   : {SUPABASE_URL}")

    supabase_res = test_supabase_direct()
    vercel_res = test_live_vercel()

    print_header("FINAL VERIFICATION REPORT")
    print(f"1. Supabase Direct Read/Write  : {'[ PASS ]' if supabase_res['pass'] else '[ FAIL ]'}")
    print(f"   -> Total Rows in DB         : {supabase_res['total_rows']}")
    print(f"2. Live Vercel Deployment      : {'[ PASS ]' if vercel_res['pass'] else '[ FAIL ]'}")
    print(f"   -> Root HTML (/)            : {'PASS' if vercel_res['endpoints'].get('/', {}).get('pass') else 'FAIL'}")
    print(f"   -> Health API (/api/health) : {'PASS' if vercel_res['endpoints'].get('/api/health', {}).get('pass') else 'FAIL'}")
    print(f"   -> Opps API (/api/opps)     : {'PASS' if vercel_res['endpoints'].get('/api/opportunities', {}).get('pass') else 'FAIL'}")
    print(f"   -> Chat API (/api/chat)     : {'PASS' if vercel_res['endpoints'].get('/api/chat', {}).get('pass') else 'FAIL'}")
    print(f"3. Active Storage Source       : {vercel_res['storage_source'].upper()}")
    print(f"   -> Supabase Active Live?    : {'YES ✅' if vercel_res['supabase_connected'] else 'NO (Local JSON Fallback) ⚠️'}")

    success = supabase_res["pass"] and vercel_res["pass"]
    print("=" * 70)
    if success:
        print("  🎉 ALL SYSTEMS OPERATIONAL AND PASSING AUDIT!")
    else:
        print("  ⚠️ SOME CHECKS REQUIRE ATTENTION. Review details above.")
    print("=" * 70)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
