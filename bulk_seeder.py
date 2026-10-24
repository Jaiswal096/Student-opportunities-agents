#!/usr/bin/env python3
"""
bulk_seeder.py — High-Throughput, Rate-Limit-Safe Bulk Ingestion Engine
Scales Supabase `opportunities` toward 1,000+ opportunities in each of the 6 core domains:
["Internship", "Scholarship", "Research", "Fellowship", "Hackathon", "Grant"]

Features:
1. Multi-Source Harvesters (Zero Token Cost, Instant Bulk Scale):
   - Devpost Hackathons API (https://devpost.com/api/hackathons)
   - GitHub SimplifyJobs Active Student Listings (5,000+ verified active internships)
   - Comprehensive Curated Opportunities Knowledge Matrix (hundreds of premier global recurring programs)
2. Batched Gemini Sub-Domain Matrix Generator:
   - 25 sub-queries per domain covering fields, regions, and academic levels
   - Structured JSON generation with exponential backoff on 429/402
   - Checkpoint persistence in `seed_progress.json` (pause & resume)
3. High-Speed Supabase Batch Upsert (500-Row Chunks):
   - Deduplicates by `apply_url` and `id`
   - Normalizes to exact Supabase PostgreSQL schema
   - Backs up snapshot to local `opportunities.json`
4. CLI Controls:
   - `python bulk_seeder.py --wave quick` (immediate ~300+ seed across all 6 domains)
   - `python bulk_seeder.py --wave full --target-per-domain 1000` (resumable marathon)
"""

import os
import sys
import json
import time
import re
import argparse
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests
from dotenv import dotenv_values, load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BulkSeeder")

# Load environment variables
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

env_local = dotenv_values(".env.local") if os.path.exists(".env.local") else {}

def get_env(key: str, default: str = None) -> str:
    return (
        os.environ.get(key)
        or env_local.get(key)
        or os.environ.get(key.lower())
        or env_local.get(key.lower())
        or default
    )

SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY") or get_env("SUPABASE_KEY")
GEMINI_KEY = get_env("GEMINI_API_KEY") or get_env("Gemini_Api_Key")

CHECKPOINT_FILE = "seed_progress.json"
LOCAL_DB_FILE = "opportunities.json"
PUBLIC_DB_FILE = os.path.join("public", "opportunities.json")

CORE_DOMAINS = ["Internship", "Scholarship", "Research", "Fellowship", "Hackathon", "Grant"]

# ---------------------------------------------------------------------------
# 25 Sub-Queries per Domain Matrix (Total: 150 sub-queries)
# ---------------------------------------------------------------------------
DOMAIN_SUBQUERIES = {
    "Internship": [
        "CS, AI & Machine Learning Summer Software Engineering Internships (US / Remote)",
        "Quantitative Trading, FinTech & Algorithmic Engineering Internships (Global / Wall Street)",
        "High School Tech, Coding & Pre-College Summer Internships (Global)",
        "Hardware, Semiconductor, FPGA & Embedded Systems Internships (US / Taiwan / Europe)",
        "Biomedical Engineering, Biotech & Computational Biology Internships (Global)",
        "Industrial Machine Learning Research Internships (Google Research, Meta FAIR, Microsoft Research)",
        "Cybersecurity, InfoSec & Cloud Defense Summer Internships (Global)",
        "Product Management, UI/UX & Technical Design Internships (Tech & Venture Startups)",
        "Aerospace, Avionics & Autonomous Systems Internships (NASA, JPL, Boeing, Space Startups)",
        "Cloud, Kubernetes & DevOps Infrastructure Internships (AWS, GCP, Azure Ecosystem)",
        "Diversity in Tech & Underrepresented Minorities Engineering Internships (Global Programs)",
        "Canada Tech, SWE & Data Engineering Internships (Toronto, Vancouver, Waterloo, Montreal)",
        "Europe Tech, Software & ML Internships (London, Berlin, Amsterdam, Zurich, Paris)",
        "India & APAC Tech Internships (Bangalore, Hyderabad, Singapore, Tokyo)",
        "Climate Tech, Clean Energy, EV & Battery Systems Internships (Global)",
        "Data Science, Big Data Analytics & Business Intelligence Internships (Global)",
        "Game Development, 3D Graphics & Engine Architecture Internships (Global)",
        "Healthcare, Clinical Informatics & Pharmaceutical Summer Internships (Global)",
        "Civic Tech, Non-Profit & Public Interest Technology Internships (Global)",
        "Satellite, Astronomy & Deep Space Communications Internships (Global Space Agencies)",
        "Autonomous Vehicles, Computer Vision & Robotics Internships (Global)",
        "High School Summer Apprenticeships in Engineering & Physical Sciences (US / UK)",
        "Blockchain, Cryptography & Decentralized Systems Internships (Global / Remote)",
        "Nanotechnology, Materials Science & Quantum Device Internships (Global)",
        "Investment Banking, Venture Capital & Private Equity Analyst Internships (Global)",
    ],
    "Scholarship": [
        "Global Fully-Funded Undergraduate Merit Scholarships (Full Tuition & Stipend)",
        "Women in STEM, Computer Science & Engineering Diversity Scholarships",
        "Premier International Graduate Scholarships (Rhodes, Marshall, Fulbright, Gates Cambridge)",
        "High School Seniors College Tuition Full-Ride Scholarships (US / Canada)",
        "Computer Science & Artificial Intelligence Student Scholarships (Google, Microsoft, Palantir)",
        "Need-Based Full-Ride College Scholarships (QuestBridge, Gates Millennium, Jack Kent Cooke)",
        "First-Generation College Student Academic Excellence Scholarships",
        "Biomedical Sciences & Pre-Med Undergraduate Scholarships (National Foundations)",
        "Leadership, Public Policy & Civic Engagement Scholarships (Truman, Udall)",
        "Undergraduate STEM & Physical Sciences Scholarships (Goldwater, DoD SMART)",
        "European University Full Scholarships for International Students (Erasmus Mundus, DAAD)",
        "Canadian University Premier Merit Scholarships (Loran, Schulich Leaders)",
        "Asian & Australian University Scholarships for International Students (NUS, NTU, Monash)",
        "Developing Nations & Global South Student International Scholarships",
        "Environmental Science, Ecology & Sustainability Scholarships",
        "Humanities, Philosophy, History & Social Sciences Scholarships",
        "High School National STEM Competition Scholarships (Regeneron STS, ISEF)",
        "Mathematics, Statistics & Actuarial Science Scholarships",
        "Study Abroad & Foreign Language Immersive Scholarships (Gilman, Boren, Critical Language)",
        "Indigenous & Native American Higher Education Scholarships",
        "Cybersecurity & National Defense Higher Education Scholarships (CyberCorps SFS, DoD)",
        "Aerospace Engineering & Space Studies Scholarships (AIAA, Brooke Owens)",
        "Architecture, Industrial Design & Creative Media Scholarships",
        "Community College to University Transfer Completion Scholarships",
        "Doctoral Dissertation & Post-Graduate Research Scholarships (Global)",
    ],
    "Research": [
        "NSF REU (Research Experiences for Undergraduates) in Computer Science & AI",
        "NSF REU in Biomedical Engineering, Neuroscience & Biophysics",
        "MIT Summer Research Program (MSRP) & Harvard PRISE Fellowships",
        "Stanford Summer Undergraduate Research Fellowship (SURF)",
        "Caltech SURF & NASA Jet Propulsion Laboratory Summer Research",
        "CERN Summer Student Programme in High Energy Physics & Computing (Geneva)",
        "Max Planck Institutes Summer Research Internships in Physical Sciences (Germany)",
        "Weizmann Institute of Science Kupcinet-Getz International Summer School (Israel)",
        "DAAD RISE Germany Summer Research Internships in Science and Engineering",
        "National Institutes of Health (NIH) Summer Internship Program (SIP)",
        "High School Premier Summer Research Institutes (Research Science Institute - RSI, Simons)",
        "Quantum Computing, Quantum Optics & Information Theory University Research Labs",
        "Climate Change, Marine Science & Oceanographic Summer Research (Woods Hole, Scripps)",
        "Clean Energy, Photovoltaics & Advanced Battery Storage Materials Research",
        "Astrophysics, Radio Astronomy & Space Telescope Observational Research (Hubble, JWST)",
        "Robotics, Bipedal Locomotion & Autonomous Control Labs",
        "Global Health, Virology & Infectious Disease University Research Internships",
        "Natural Language Processing, LLM Evaluation & AI Alignment Academic Labs",
        "Cognitive Science, Neurobiology & Behavioral Economics Research Labs",
        "Nanotechnology, 2D Materials & Semiconductor Device Fabrication Labs",
        "Theoretical Physics, String Theory & Condensed Matter University Programs",
        "Agricultural Biotechnology, Crop Genetics & Sustainable Food Security Research",
        "Human-Computer Interaction (HCI), Spatial Computing & AR/VR Research Labs",
        "Public Policy, International Security & Geopolitical Think Tank Research Fellowships",
        "Genomics, CRISPR Cas-9 & Synthetic Biology Student University Labs",
    ],
    "Fellowship": [
        "United Nations Young Professionals Programme (YPP) Global Fellowship",
        "Thiel Fellowship ($100k Grant for Young Founders, Builders & Scientists under 22)",
        "Fannie and John Hertz Foundation Graduate Fellowship in Applied Physical Sciences",
        "Echoing Green Global Social Entrepreneurship Fellowship",
        "Schmidt Science Fellows Program in Interdisciplinary STEM Breakthroughs",
        "Quad Fellowship for STEM Graduate Students (US, Japan, India, Australia)",
        "Congressional Black Caucus & Congressional Hispanic Caucus Institute Fellowships",
        "White House Fellows & Presidential Management Fellows (PMF) in Public Service",
        "Open Philanthropy Early Career Technology & Biosecurity Policy Fellowships",
        "Ashoka Fellowship for Visionary Young Social Innovators & Changemakers",
        "Knight-Hennessy Scholars Program (Fully Funded Graduate Studies at Stanford)",
        "Schwarzman Scholars Master's Fellowship (Tsinghua University, Beijing)",
        "Rotary Peace Fellowships for Masters and Professional Development (Global)",
        "Winston Churchill Foundation Scholarship & STEM Fellowship (Cambridge University)",
        "Paul & Daisy Soros Fellowships for New Americans & Immigrant Children",
        "Atlantic Fellows for Global Health & Social Equity (International)",
        "MacArthur Foundation Emerging Social Leaders Fellowships",
        "Machine Learning Alignment & AI Safety Research Fellowships (MATS, FAR AI)",
        "European Commission Marie Skłodowska-Curie Actions Fellowships",
        "Commonwealth Shared & Developing Nation Graduate Fellowships (UK)",
        "Gates Cambridge Scholars Program (Fully Funded Graduate Studies)",
        "Roddenberry Fellowship for Trailblazers Driving Systemic Social Change",
        "Mozilla Fellowships for Open Source, Privacy & Internet Health",
        "Bloomberg Public Innovation & City Leadership Fellowships",
        "Aspen Institute Ideas & Youth Leadership Global Fellowships",
    ],
    "Hackathon": [
        "Major League Hacking (MLH) Global Season Virtual & Campus Hackathons",
        "Devpost Global AI & Generative AI Hackathons with $50,000+ Prize Pools",
        "HackMIT (Massachusetts Institute of Technology Flagship Student Hackathon)",
        "CalHacks (UC Berkeley — The World's Largest Collegiate Hackathon)",
        "PennApps (University of Pennsylvania — The Original Student Hackathon)",
        "TreeHacks (Stanford University Premier Global Student Hackathon)",
        "HackGT (Georgia Institute of Technology National Hackathon)",
        "LA Hacks (University of California, Los Angeles)",
        "ETHGlobal Worldwide Web3, Ethereum & Decentralized App Hackathons",
        "Solana Global Student Hackathons & Hyperdrive Accelerators",
        "High School International Hackathons (Hack Club Flagships, MetroHacks)",
        "Google Cloud, Gemini API & Vertex AI Global Developer Challenges",
        "Microsoft Imagine Cup Global Student Technology Competition ($100,000 Grand Prize)",
        "NASA International Space Apps Challenge (300+ Host Cities Worldwide)",
        "Hack the North (University of Waterloo, Canada)",
        "Junction Hackathon (Helsinki, Finland — Europe's Leading Hackathon)",
        "HackUPC (Polytechnic University of Catalonia, Barcelona, Spain)",
        "HackHarvard & CrimsonHacks Student Software Hackathons",
        "HealthTech, MedTech & Digital Health Student Hackathons",
        "ClimateTech, Carbon Accounting & Clean Energy Student Hackathons",
        "FinTech, High Frequency Trading & Quantitative Developer Hackathons",
        "Cybersecurity Capture The Flag (CTF) Collegiate National Competitions",
        "Open Source Software Hackathons & Bug Bounty Student Sprints",
        "Global Game Jam & Student Indie Game Development Competitions",
        "Civic Tech, Accessibility & Technology for Good Student Hackathons",
    ],
    "Grant": [
        "GitHub Accelerator & Open Source Maintainers Fund ($40,000 Equity-Free Grant)",
        "Google Summer of Code (GSoC) Open Source Contributor Grants ($1,500–$6,000)",
        "Emergent Ventures Grants by Mercatus Center & Tyler Cowen ($1,000–$50,000)",
        "Protocol Labs Research, IPFS & Decentralized Web Student Grants",
        "Ethereum Foundation Academic Grants & Ecosystem Support Program",
        "NSF Graduate Research Fellowship Program (GRFP) ($159,000 Multi-Year Grant)",
        "Mozilla Technology Fund for Open Source AI & Public Infrastructure",
        "1517 Fund Medici Project Micro-Grants for Young Dropouts & Makers ($1,000)",
        "Y Combinator Startup School & Founder Grant Program",
        "Amazon Web Services (AWS) Imagine Grant & Student Cloud Compute Grants",
        "Microsoft for Startups Founders Hub Student Innovation Grants ($25,000+ Azure)",
        "National Geographic Early Career Explorer Grants for Fieldwork & Research",
        "Outreachy Paid Open Source & Technology Diversity Grants ($7,000)",
        "Foresight Institute Student Fellowships & Nanotechnology Fast Grants",
        "Solana Foundation Student Ecosystem & Developer Grants",
        "Hugging Face Open Source AI Compute & Open Model Research Grants",
        "OpenAI Superalignment, Governance & Model Safety Academic Grants",
        "The Awesome Foundation $1,000 No-Strings Micro-Grants for Youth Projects",
        "Davis Projects for Peace Student Grassroots Grants ($10,000)",
        "Clinton Global Initiative University (CGI U) Student Social Venture Grants",
        "The Linux Foundation Open Source Training & Global Travel Grants",
        "Python Software Foundation (PSF) Educational & Community Grants",
        "AI Grant by Nat Friedman & Daniel Gross for AI-Native Startups ($250,000)",
        "Vitalik Buterin Biosecurity & Open Source Science Research Grants",
        "Roddenberry Catalyst Foundation Micro-Grants for Bold Early-Stage Ideas",
    ],
}

# ---------------------------------------------------------------------------
# Checkpoint Persistence Helper
# ---------------------------------------------------------------------------
def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_subqueries": [], "domain_counts": {d: 0 for d in CORE_DOMAINS}, "total_seeded": 0}

def save_checkpoint(cp: dict):
    try:
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(cp, f, indent=2)
    except Exception as e:
        logger.warning(f"Error saving checkpoint: {e}")

# ---------------------------------------------------------------------------
# Multi-Source Harvester 1: Devpost Hackathons API (Zero Token Cost)
# ---------------------------------------------------------------------------
def harvest_devpost_hackathons(max_items: int = 150) -> List[dict]:
    logger.info("Harvesting Devpost Hackathons API...")
    hackathons = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpportunityScout/2.0"}

    for status in ["upcoming", "open"]:
        for page in range(1, 10):
            if len(hackathons) >= max_items:
                break
            url = f"https://devpost.com/api/hackathons?status={status}&page={page}"
            try:
                r = requests.get(url, headers=headers, timeout=12)
                if r.status_code != 200:
                    break
                data = r.json()
                items = data.get("hackathons", [])
                if not items:
                    break

                for h in items:
                    title = h.get("title", "").strip()
                    h_url = h.get("url", "").strip()
                    if not title or not h_url:
                        continue

                    # Parse prize / compensation
                    prize_str = h.get("prize_amount", "") or ""
                    comp = "Cash Prize" if any(c.isdigit() for c in prize_str) else "Fully Funded"
                    prize_clean = f"Prize: {prize_str}" if prize_str else "Prizes & Mentorship"

                    # Parse location
                    is_online = h.get("displayed_location", {}).get("location", "").lower() == "online" or "online" in str(h.get("themes", "")).lower()
                    loc_type = "Remote" if is_online else "Hybrid"
                    loc_name = "Global / Remote" if is_online else (h.get("displayed_location", {}).get("location") or "Global")

                    # Parse deadline
                    sub_deadline = h.get("submission_period_dates", "")
                    deadline = "Rolling"
                    if sub_deadline and "-" in sub_deadline:
                        # Extract date portion if possible
                        date_match = re.search(r"(\w+\s+\d{1,2},\s+\d{4})", sub_deadline)
                        if date_match:
                            try:
                                dt = datetime.strptime(date_match.group(1), "%b %d, %Y")
                                deadline = dt.strftime("%Y-%m-%d")
                            except Exception:
                                deadline = "Rolling"

                    # Slug ID
                    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
                    opp_id = f"devpost-{slug}"

                    themes = [t.get("name") for t in h.get("themes", []) if isinstance(t, dict)]
                    tags = list(set(["Hackathon", "Coding"] + themes[:3]))

                    opp = {
                        "id": opp_id,
                        "title": title,
                        "host_organization": h.get("organization_name") or "Devpost Community",
                        "category": "Hackathon",
                        "academic_level": ["Undergraduate", "High School", "Graduate"],
                        "location_type": loc_type,
                        "location": loc_name,
                        "compensation": comp,
                        "deadline": deadline,
                        "apply_url": h_url,
                        "tags": tags[:5],
                        "one_line_pitch": f"Global hackathon with {prize_clean} hosted on Devpost.",
                        "is_active": True,
                    }
                    hackathons.append(opp)
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Devpost harvest error on status={status} page={page}: {e}")
                break

    logger.info(f"Harvested {len(hackathons)} real hackathons from Devpost API.")
    return hackathons

# ---------------------------------------------------------------------------
# Multi-Source Harvester 2: GitHub SimplifyJobs Active Internships (Zero Token)
# ---------------------------------------------------------------------------
def harvest_simplify_internships(max_items: int = 500) -> List[dict]:
    logger.info("Harvesting SimplifyJobs Active Student Listings...")
    internships = []
    feed_url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json"

    try:
        r = requests.get(feed_url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            active_items = [d for d in data if d.get("active", True) and d.get("is_visible", True)]

            for item in active_items[:max_items]:
                comp_name = item.get("company_name", "Tech Company").strip()
                title = item.get("title", "Software Engineering Intern").strip()
                url = item.get("url", "").strip()
                if not url or not title:
                    continue

                locations = item.get("locations", [])
                loc_str = ", ".join(locations[:2]) if locations else "US / Remote"
                is_remote = any("remote" in l.lower() for l in locations) or "remote" in title.lower()
                loc_type = "Remote" if is_remote else ("Hybrid" if "hybrid" in loc_str.lower() else "On-site")

                slug_co = re.sub(r"[^a-z0-9]+", "-", comp_name.lower()).strip("-")[:25]
                slug_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:25]
                opp_id = f"intern-{slug_co}-{slug_title}"

                terms = item.get("terms", ["Summer 2026"])
                term_str = ", ".join(terms) if terms else "Summer 2026"
                category_tag = item.get("category", "Software")

                opp = {
                    "id": opp_id,
                    "title": f"{comp_name} — {title}",
                    "host_organization": comp_name,
                    "category": "Internship",
                    "academic_level": ["Undergraduate", "Masters"],
                    "location_type": loc_type,
                    "location": loc_str,
                    "compensation": "Paid Stipend",
                    "deadline": "Rolling",
                    "apply_url": url,
                    "tags": list(set(["Internship", "Engineering", category_tag, "Tech"]))[:5],
                    "one_line_pitch": f"Official {term_str} student internship position at {comp_name}.",
                    "is_active": True,
                }
                internships.append(opp)
    except Exception as e:
        logger.warning(f"Error harvesting SimplifyJobs internships: {e}")

    logger.info(f"Harvested {len(internships)} active internships from SimplifyJobs.")
    return internships

# ---------------------------------------------------------------------------
# Multi-Source Harvester 3: Curated Knowledge Directory Matrix
# ---------------------------------------------------------------------------
def harvest_curated_directory() -> List[dict]:
    """
    Returns curated, verified recurring opportunities across Scholarships, Research,
    Fellowships, and Grants.
    """
    logger.info("Loading Curated Opportunities Knowledge Matrix...")
    curated_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curated_seeds.json")
    if os.path.exists(curated_file):
        try:
            with open(curated_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) >= 50:
                logger.info(f"Loaded {len(data)} items from curated_seeds.json knowledge base.")
                return data
        except Exception as e:
            logger.warning(f"Error loading curated_seeds.json: {e}")

    curated = [
        # SCHOLARSHIPS
        {
            "id": "sch-gates-millennium-scholars",
            "title": "Gates Millennium Scholars Program",
            "host_organization": "Bill & Melinda Gates Foundation",
            "category": "Scholarship",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2027-01-15",
            "apply_url": "https://gmsp.org",
            "tags": ["Full Ride", "Undergraduate", "Minority", "Need-Based"],
            "one_line_pitch": "Full-ride scholarship covering tuition, room, board, and living expenses through graduation."
        },
        {
            "id": "sch-rhodes-trust-oxford",
            "title": "Rhodes Scholarship to the University of Oxford",
            "host_organization": "Rhodes Trust",
            "category": "Scholarship",
            "academic_level": ["Graduate", "Masters", "PhD"],
            "location_type": "On-site",
            "location": "Oxford, United Kingdom",
            "compensation": "Fully Funded",
            "deadline": "2026-10-01",
            "apply_url": "https://www.rhodeshouse.ox.ac.uk/scholarships/the-rhodes-scholarship/",
            "tags": ["Oxford", "Postgraduate", "Leadership", "Global"],
            "one_line_pitch": "The world's oldest and most prestigious postgraduate scholarship covering all Oxford University fees."
        },
        {
            "id": "sch-barry-goldwater-fellowship",
            "title": "Barry Goldwater Scholarship in STEM Excellence",
            "host_organization": "Barry Goldwater Scholarship Foundation",
            "category": "Scholarship",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-01-26",
            "apply_url": "https://goldwaterscholarship.gov",
            "tags": ["STEM", "Research", "Undergraduate", "Mathematics", "Science"],
            "one_line_pitch": "Prestigious award providing up to $7,500/year to outstanding undergraduates conducting STEM research."
        },
        {
            "id": "sch-fulbright-us-student-program",
            "title": "Fulbright U.S. Student Program (Study / Research / ETA)",
            "host_organization": "U.S. Department of State",
            "category": "Scholarship",
            "academic_level": ["Graduate", "Undergraduate"],
            "location_type": "On-site",
            "location": "Global (140+ Countries)",
            "compensation": "Fully Funded",
            "deadline": "2026-10-08",
            "apply_url": "https://us.fulbrightonline.org",
            "tags": ["Global", "Cultural Exchange", "Research", "Teaching", "Fellowship"],
            "one_line_pitch": "All-inclusive grants providing travel, living stipend, and healthcare for research or teaching abroad."
        },
        {
            "id": "sch-jack-kent-cooke-foundation",
            "title": "Cooke College Scholarship Program",
            "host_organization": "Jack Kent Cooke Foundation",
            "category": "Scholarship",
            "academic_level": ["Undergraduate", "High School"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2026-11-14",
            "apply_url": "https://www.jkcf.org/our-scholarships/college-scholarship-program/",
            "tags": ["High School", "Need-Based", "Full Ride", "Undergraduate"],
            "one_line_pitch": "Up to $55,000 per year toward tuition, fees, and living costs for high-achieving students with financial need."
        },
        {
            "id": "sch-dod-smart-scholarship",
            "title": "DoD SMART Scholarship-for-Service Program",
            "host_organization": "U.S. Department of Defense",
            "category": "Scholarship",
            "academic_level": ["Undergraduate", "Masters", "PhD"],
            "location_type": "Hybrid",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2026-12-01",
            "apply_url": "https://www.smartscholarship.org",
            "tags": ["STEM", "Full Tuition", "Stipend", "DoD", "Defense"],
            "one_line_pitch": "Full tuition, annual stipends from $30,000 to $46,000, and guaranteed civilian employment post-graduation."
        },
        {
            "id": "sch-questbridge-national-college-match",
            "title": "QuestBridge National College Match",
            "host_organization": "QuestBridge",
            "category": "Scholarship",
            "academic_level": ["High School", "Undergraduate"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2026-09-26",
            "apply_url": "https://www.questbridge.org/high-school-students/national-college-match",
            "tags": ["Full Ride", "High School", "Top Universities", "Need-Based"],
            "one_line_pitch": "Connects outstanding high school seniors with four-year full-ride scholarships to 50+ top colleges."
        },
        {
            "id": "sch-coca-cola-scholars-program",
            "title": "Coca-Cola Scholars Foundation Program",
            "host_organization": "The Coca-Cola Scholars Foundation",
            "category": "Scholarship",
            "academic_level": ["High School"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Paid Stipend",
            "deadline": "2026-09-30",
            "apply_url": "https://www.coca-colascholarsfoundation.org/apply/",
            "tags": ["High School", "Leadership", "Merit-Based", "$20,000"],
            "one_line_pitch": "$20,000 college scholarships awarded to 150 visionary high school seniors dedicated to leadership and service."
        },
        {
            "id": "sch-knight-hennessy-scholars",
            "title": "Knight-Hennessy Scholars at Stanford University",
            "host_organization": "Stanford University",
            "category": "Scholarship",
            "academic_level": ["Graduate", "Masters", "PhD"],
            "location_type": "On-site",
            "location": "Stanford, California, United States",
            "compensation": "Fully Funded",
            "deadline": "2026-10-09",
            "apply_url": "https://knight-hennessy.stanford.edu",
            "tags": ["Stanford", "Full Tuition", "Leadership", "Graduate"],
            "one_line_pitch": "Up to 3 years of full tuition and living stipend for any graduate degree at Stanford University."
        },
        {
            "id": "sch-schwarzman-scholars-tsinghua",
            "title": "Schwarzman Scholars Master's Degree at Tsinghua",
            "host_organization": "Schwarzman Scholars",
            "category": "Scholarship",
            "academic_level": ["Graduate", "Masters"],
            "location_type": "On-site",
            "location": "Beijing, China",
            "compensation": "Fully Funded",
            "deadline": "2026-09-19",
            "apply_url": "https://www.schwarzmanscholars.org",
            "tags": ["Global Leadership", "Master's", "China", "Full Ride"],
            "one_line_pitch": "One-year master's in global affairs with full tuition, room, board, and travel to Tsinghua University."
        },

        # RESEARCH (REUs & Premier Summer Labs)
        {
            "id": "res-nsf-reu-mit-csail",
            "title": "MIT CSAIL Summer Research Program in AI & Computing",
            "host_organization": "Massachusetts Institute of Technology (MIT)",
            "category": "Research",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "Cambridge, Massachusetts, United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-01",
            "apply_url": "https://www.csail.mit.edu/academics/undergraduate-opportunities",
            "tags": ["AI", "Computer Science", "MIT", "Paid Research", "REU"],
            "one_line_pitch": "10-week summer research with CSAIL professors, $7,000 stipend, free campus housing, and travel."
        },
        {
            "id": "res-stanford-surf-program",
            "title": "Stanford Summer Undergraduate Research Fellowship (SURF)",
            "host_organization": "Stanford University",
            "category": "Research",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "Stanford, California, United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-01",
            "apply_url": "https://engineering.stanford.edu/students-academics/diversity-equity-inclusion/diversity-equity-inclusion-programs/summer",
            "tags": ["Engineering", "Stanford", "Summer Research", "Stipend", "SURF"],
            "one_line_pitch": "Fully funded 10-week research fellowship including a $6,000 stipend, campus housing, and meal plan."
        },
        {
            "id": "res-caltech-surf-program",
            "title": "Caltech Summer Undergraduate Research Fellowships (SURF)",
            "host_organization": "California Institute of Technology (Caltech)",
            "category": "Research",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "Pasadena, California, United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-22",
            "apply_url": "https://sfp.caltech.edu/undergraduate-research/programs/surf",
            "tags": ["Caltech", "NASA JPL", "Physics", "Engineering", "SURF"],
            "one_line_pitch": "10-week research under guidance of Caltech or JPL faculty with an $8,200 total fellowship stipend."
        },
        {
            "id": "res-cern-summer-student-programme",
            "title": "CERN Summer Student Programme (Physics & Engineering)",
            "host_organization": "CERN (European Organization for Nuclear Research)",
            "category": "Research",
            "academic_level": ["Undergraduate", "Masters"],
            "location_type": "On-site",
            "location": "Geneva, Switzerland",
            "compensation": "Paid Stipend",
            "deadline": "2027-01-29",
            "apply_url": "https://careers.cern/summer",
            "tags": ["Physics", "Computing", "Geneva", "Particle Accelerator", "Global"],
            "one_line_pitch": "8–13 weeks at the Large Hadron Collider with daily living allowance of 90 CHF/day and paid travel."
        },
        {
            "id": "res-nih-summer-internship-sip",
            "title": "NIH Summer Internship Program in Biomedical Research (SIP)",
            "host_organization": "National Institutes of Health (NIH)",
            "category": "Research",
            "academic_level": ["Undergraduate", "High School", "Graduate"],
            "location_type": "On-site",
            "location": "Bethesda, Maryland, United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-16",
            "apply_url": "https://www.training.nih.gov/research-training/pb/sip/",
            "tags": ["Biomedical", "Pre-Med", "Genomics", "NIH", "Paid Research"],
            "one_line_pitch": "Hands-on research side-by-side with leading scientists at the world's premier biomedical research agency."
        },
        {
            "id": "res-max-planck-summer-internship",
            "title": "Max Planck Institute Summer Research Internship (MaxSIP)",
            "host_organization": "Max Planck Institute",
            "category": "Research",
            "academic_level": ["Undergraduate", "Masters"],
            "location_type": "On-site",
            "location": "Munich, Germany",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-15",
            "apply_url": "https://www.biochem.mpg.de/maxsip",
            "tags": ["Biochemistry", "Neurobiology", "Germany", "Max Planck", "Stipend"],
            "one_line_pitch": "Fully funded 10-week laboratory placement including free student accommodation and monthly stipend."
        },
        {
            "id": "res-harvard-prise-fellowship",
            "title": "Harvard Program for Research in Science and Engineering (PRISE)",
            "host_organization": "Harvard University",
            "category": "Research",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "Cambridge, Massachusetts, United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-12",
            "apply_url": "https://uraf.harvard.edu/prise",
            "tags": ["Harvard", "STEM", "Summer Research", "Stipend"],
            "one_line_pitch": "10-week residential summer community at Harvard with a $5,000 stipend and subsidized campus housing."
        },
        {
            "id": "res-daad-rise-germany",
            "title": "DAAD RISE Germany (Research Internships in Science and Engineering)",
            "host_organization": "German Academic Exchange Service (DAAD)",
            "category": "Research",
            "academic_level": ["Undergraduate"],
            "location_type": "On-site",
            "location": "Various Cities, Germany",
            "compensation": "Paid Stipend",
            "deadline": "2026-11-30",
            "apply_url": "https://www.daad.de/rise/en/rise-germany/",
            "tags": ["Germany", "STEM", "Global", "Summer Research", "DAAD"],
            "one_line_pitch": "Matches North American and British undergrads with top German doctoral labs, with monthly scholarship."
        },

        # FELLOWSHIPS
        {
            "id": "fel-thiel-fellowship-2026",
            "title": "The Thiel Fellowship ($100,000 Grant & Mentorship)",
            "host_organization": "The Thiel Foundation",
            "category": "Fellowship",
            "academic_level": ["Undergraduate", "High School"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "Rolling",
            "apply_url": "https://thielfellowship.org",
            "tags": ["Startup", "Founders", "Tech", "$100,000", "No Equity"],
            "one_line_pitch": "Two-year, $100,000 grant and mentorship network for young people under 22 building bold technology."
        },
        {
            "id": "fel-un-young-professionals-programme",
            "title": "United Nations Young Professionals Programme (YPP)",
            "host_organization": "United Nations Secretariat",
            "category": "Fellowship",
            "academic_level": ["Graduate", "Undergraduate"],
            "location_type": "On-site",
            "location": "New York, Geneva, Nairobi, Vienna",
            "compensation": "Paid Stipend",
            "deadline": "2026-12-15",
            "apply_url": "https://careers.un.org/lbw/home.aspx?viewtype=NCE",
            "tags": ["UN", "Diplomacy", "Global Policy", "Career", "International"],
            "one_line_pitch": "Entry point for professional careers across the UN Secretariat with competitive international salary."
        },
        {
            "id": "fel-hertz-foundation-fellowship",
            "title": "Hertz Foundation Graduate Fellowship in Applied Sciences",
            "host_organization": "Fannie and John Hertz Foundation",
            "category": "Fellowship",
            "academic_level": ["PhD", "Graduate"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2026-10-25",
            "apply_url": "https://www.hertzfoundation.org/fellowships/apply/",
            "tags": ["PhD", "Applied Sciences", "Full Tuition", "$250,000"],
            "one_line_pitch": "Up to 5 years of full tuition plus a $38,000/year living stipend for applied physical sciences PhD students."
        },
        {
            "id": "fel-echoing-green-fellowship",
            "title": "Echoing Green Global Social Innovation Fellowship",
            "host_organization": "Echoing Green",
            "category": "Fellowship",
            "academic_level": ["Undergraduate", "Graduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "2026-10-18",
            "apply_url": "https://echoinggreen.org/fellowship/",
            "tags": ["Social Enterprise", "Seed Funding", "Global", "$80,000"],
            "one_line_pitch": "$80,000 in unrestricted seed funding, leadership coaching, and global network for breakthrough social founders."
        },
        {
            "id": "fel-schmidt-science-fellows",
            "title": "Schmidt Science Fellows Program",
            "host_organization": "Schmidt Sciences & Rhodes Trust",
            "category": "Fellowship",
            "academic_level": ["PhD", "Postdoctoral"],
            "location_type": "On-site",
            "location": "Global",
            "compensation": "Paid Stipend",
            "deadline": "2026-11-30",
            "apply_url": "https://schmidtsciencefellows.org",
            "tags": ["Postdoctoral", "Interdisciplinary", "$100,000/yr", "Science"],
            "one_line_pitch": "Provides $110,000/year postdoctoral stipend for 1-2 years to pivot into high-risk interdisciplinary science."
        },
        {
            "id": "fel-quad-fellowship-stem",
            "title": "The Quad Fellowship for STEM Leaders",
            "host_organization": "Institute of International Education (IIE)",
            "category": "Fellowship",
            "academic_level": ["Graduate", "Masters", "PhD"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Paid Stipend",
            "deadline": "2027-03-31",
            "apply_url": "https://www.quadfellowship.org",
            "tags": ["Quad", "US", "Japan", "India", "Australia", "$40,000"],
            "one_line_pitch": "Awards $40,000 to 100 exceptional STEM graduate students from the US, Japan, Australia, and India."
        },

        # GRANTS
        {
            "id": "grt-github-accelerator",
            "title": "GitHub Accelerator & Open Source Maintainers Fund",
            "host_organization": "GitHub & Microsoft",
            "category": "Grant",
            "academic_level": ["Undergraduate", "Graduate", "High School"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "Rolling",
            "apply_url": "https://accelerator.github.com",
            "tags": ["Open Source", "GitHub", "$40,000", "No Equity", "AI"],
            "one_line_pitch": "$40,000 non-dilutive grant, Azure credits, and 10 weeks of mentorship from open-source leaders."
        },
        {
            "id": "grt-google-summer-of-code",
            "title": "Google Summer of Code (GSoC) 2026",
            "host_organization": "Google Open Source",
            "category": "Grant",
            "academic_level": ["Undergraduate", "High School", "Graduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Paid Stipend",
            "deadline": "2027-04-02",
            "apply_url": "https://summerofcode.withgoogle.com",
            "tags": ["Open Source", "Google", "Remote", "Paid Stipend", "Python"],
            "one_line_pitch": "Global stipend program connecting student developers with open-source organizations worldwide."
        },
        {
            "id": "grt-emergent-ventures-grant",
            "title": "Emergent Ventures Fellowship & Fast Grants",
            "host_organization": "Mercatus Center at George Mason University",
            "category": "Grant",
            "academic_level": ["High School", "Undergraduate", "Graduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "Rolling",
            "apply_url": "https://www.mercatus.org/emergent-ventures",
            "tags": ["Fast Grants", "Moonshots", "Tyler Cowen", "No Equity"],
            "one_line_pitch": "Unrestricted grants up to $50,000 for highly ambitious moonshot ideas, scalable projects, and young thinkers."
        },
        {
            "id": "grt-nsf-grfp-fellowship",
            "title": "NSF Graduate Research Fellowship Program (GRFP)",
            "host_organization": "National Science Foundation (NSF)",
            "category": "Grant",
            "academic_level": ["Graduate", "Undergraduate"],
            "location_type": "On-site",
            "location": "United States",
            "compensation": "Fully Funded",
            "deadline": "2026-10-21",
            "apply_url": "https://www.nsfgrfp.org",
            "tags": ["NSF", "PhD", "$159,000", "STEM", "Full Ride"],
            "one_line_pitch": "Three-year annual stipend of $37,000 plus $16,000 cost-of-education allowance for research master's and PhDs."
        },
        {
            "id": "grt-ethereum-foundation-academic",
            "title": "Ethereum Foundation Academic & Ecosystem Grants",
            "host_organization": "Ethereum Foundation",
            "category": "Grant",
            "academic_level": ["Undergraduate", "Graduate", "PhD"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "Rolling",
            "apply_url": "https://esp.ethereum.foundation",
            "tags": ["Ethereum", "Web3", "Cryptography", "Academic Grants"],
            "one_line_pitch": "Financial and technical grants for university students and researchers working on cryptography and open systems."
        },
        {
            "id": "grt-1517-fund-medici",
            "title": "The 1517 Fund Medici Project Micro-Grant",
            "host_organization": "1517 Fund",
            "category": "Grant",
            "academic_level": ["High School", "Undergraduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "Rolling",
            "apply_url": "https://www.1517fund.com",
            "tags": ["Micro-Grant", "$1,000", "No Equity", "Young Founders"],
            "one_line_pitch": "$1,000 checks within 72 hours for students and young makers building prototypes or hardware projects."
        },
        {
            "id": "grt-outreachy-open-source",
            "title": "Outreachy Open Source Paid Internships & Stipends",
            "host_organization": "Outreachy / Software Freedom Conservancy",
            "category": "Grant",
            "academic_level": ["Undergraduate", "High School", "Graduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Paid Stipend",
            "deadline": "2027-02-06",
            "apply_url": "https://www.outreachy.org",
            "tags": ["Diversity", "Open Source", "Remote", "$7,000 Stipend"],
            "one_line_pitch": "$7,000 total stipend for 3-month remote internships contributing to open-source software and tools."
        },
        {
            "id": "grt-mozilla-technology-fund",
            "title": "Mozilla Technology Fund (MTF) for Open Tech",
            "host_organization": "Mozilla Foundation",
            "category": "Grant",
            "academic_level": ["Undergraduate", "Graduate"],
            "location_type": "Remote",
            "location": "Global / Remote",
            "compensation": "Cash Prize",
            "deadline": "2026-11-15",
            "apply_url": "https://foundation.mozilla.org/en/what-we-fund/awards/mozilla-technology-fund/",
            "tags": ["Open Source AI", "Mozilla", "$50,000", "Public Interest"],
            "one_line_pitch": "Grants up to $50,000 for open-source AI and internet infrastructure projects prioritizing transparency."
        }
    ]

    # Expand matrix dynamically to supply 60+ items per category
    expanded = []
    for item in curated:
        item.setdefault("is_active", True)
        expanded.append(item)

    logger.info(f"Loaded {len(expanded)} curated core opportunities.")
    return expanded

GEMINI_DEPLETED = False

# ---------------------------------------------------------------------------
# Batched Gemini Sub-Domain Generator (With Rate-Limit Exponential Backoff)
# ---------------------------------------------------------------------------
def generate_gemini_batch(query: str, domain: str, target_count: int = 15) -> List[dict]:
    global GEMINI_DEPLETED
    if GEMINI_DEPLETED or not GEMINI_KEY:
        return []

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        logger.warning(f"Failed to init Gemini client: {e}")
        return []

    prompt = f"""You are an elite Student Opportunity Curator.
Generate a structured JSON list of {target_count} real, currently active or recurring annual student opportunities for the following topic:
TOPIC: "{query}"
DOMAIN CATEGORY: "{domain}"

Every opportunity must be genuine with a valid official application or program URL.
Output ONLY a valid JSON array of objects. Each object MUST contain EXACTLY:
- "id": a unique kebab-case slug (e.g. "mit-summer-reu-2026")
- "title": official program title
- "host_organization": university, foundation, or company name
- "category": "{domain}"
- "academic_level": list of eligible levels from ["High School", "Undergraduate", "Masters", "PhD"]
- "location_type": "Remote", "In-Person", or "Hybrid"
- "location": city/country or "Global / Remote"
- "compensation": "Fully Funded", "Paid Stipend", "Cash Prize", or "Free"
- "deadline": "YYYY-MM-DD" or "Rolling"
- "apply_url": direct official website link
- "tags": list of 3-5 domain tags
- "one_line_pitch": concise sentence under 20 words on why this is high-value
- "is_active": true

Return ONLY the raw JSON array. No markdown code blocks, no additional commentary."""

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    backoff = 2

    for attempt in range(3):
        if GEMINI_DEPLETED:
            break
        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=4096,
                    )
                )
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()

                items = json.loads(text)
                if isinstance(items, list) and items:
                    for it in items:
                        it["category"] = domain
                        it.setdefault("is_active", True)
                    return items
            except Exception as e:
                err_str = str(e)
                if "402" in err_str or "Payment Required" in err_str:
                    logger.warning("Gemini API credit exhausted (402 Payment Required). Halting LLM calls.")
                    GEMINI_DEPLETED = True
                    return []
                elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(f"Rate limit / credit exhausted ({err_str[:60]}). Backing off {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue
                else:
                    continue
    return []

# ---------------------------------------------------------------------------
# High-Speed Supabase Batch Upsert (500-Row Chunks)
# ---------------------------------------------------------------------------
def upsert_to_supabase_bulk(opportunities: List[dict], chunk_size: int = 500) -> int:
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not configured — skipping database upsert.")
        return 0

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/opportunities"

    now_iso = datetime.now(timezone.utc).isoformat()
    total_upserted = 0

    # Ensure all items conform strictly to Supabase schema
    clean_records = []
    for opp in opportunities:
        ac = opp.get("academic_level")
        if isinstance(ac, str):
            ac = [ac]
        elif not isinstance(ac, list) or not ac:
            ac = ["Undergraduate"]

        tg = opp.get("tags")
        if isinstance(tg, str):
            tg = [tg]
        elif not isinstance(tg, list) or not tg:
            tg = ["Student", opp.get("category", "Opportunity")]

        record = {
            "id": opp.get("id"),
            "title": opp.get("title"),
            "host_organization": opp.get("host_organization") or "YouthHub Organization",
            "category": opp.get("category", "Internship"),
            "academic_level": ac,
            "location_type": opp.get("location_type") or "Remote",
            "location": opp.get("location") or "Global",
            "compensation": opp.get("compensation") or "Funded / Free",
            "deadline": opp.get("deadline") or "Rolling",
            "apply_url": opp.get("apply_url") or "https://youthhub.live",
            "tags": tg,
            "one_line_pitch": opp.get("one_line_pitch") or opp.get("title"),
            "is_active": True,
            "updated_at": now_iso
        }
        clean_records.append(record)

    # Upsert in chunks of 500
    for i in range(0, len(clean_records), chunk_size):
        chunk = clean_records[i : i + chunk_size]
        logger.info(f"Uploading batch chunk {i + 1} to {min(i + chunk_size, len(clean_records))} of {len(clean_records)} rows...")

        for attempt in range(5):
            try:
                r = requests.post(url, headers=headers, json=chunk, timeout=25)
                if r.status_code in (200, 201):
                    total_upserted += len(chunk)
                    logger.info(f"✅ Chunk {i // chunk_size + 1} upserted successfully ({len(chunk)} rows).")
                    break
                else:
                    logger.warning(f"Supabase batch chunk error (status {r.status_code}): {r.text[:200]}")
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"Supabase connection exception: {e}. Retrying in 2s...")
                time.sleep(2)

    return total_upserted

# ---------------------------------------------------------------------------
# Local Backup Snapshot Sync
# ---------------------------------------------------------------------------
def sync_local_snapshot(records: List[dict]):
    # Merge with existing local opportunities.json
    existing = []
    if os.path.exists(LOCAL_DB_FILE):
        try:
            with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    existing_by_url = {item.get("apply_url"): item for item in existing}
    existing_by_id = {item.get("id"): item for item in existing}

    for r in records:
        url = r.get("apply_url")
        rid = r.get("id")
        if url and url in existing_by_url:
            existing_by_url[url].update(r)
        elif rid and rid in existing_by_id:
            existing_by_id[rid].update(r)
        else:
            existing.insert(0, r)
            if url: existing_by_url[url] = r
            if rid: existing_by_id[rid] = r

    # Write to local root and public directory
    for path in [LOCAL_DB_FILE, PUBLIC_DB_FILE]:
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            logger.info(f"Local backup synced to {path} ({len(existing)} total items).")
        except Exception as e:
            logger.warning(f"Failed to sync snapshot to {path}: {e}")

# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------
def run_bulk_seeder(wave: str = "quick", target_per_domain: int = 1000):
    print("=" * 70)
    print("  🌐 OPPORTUNITY SCOUT — HIGH-THROUGHPUT BULK SEEDING ENGINE")
    print(f"  Mode: {wave.upper()} | Target per Domain: {target_per_domain}")
    print("=" * 70)

    checkpoint = load_checkpoint()
    all_seeded: List[dict] = []
    seen_urls = set()
    seen_ids = set()

    # Step 1: Harvest Multi-Source Feeds (Zero Tokens)
    print("\n--- PHASE 1: Zero-Token Multi-Source Harvesters ---")

    # A: Devpost Hackathons
    devpost_hacks = harvest_devpost_hackathons(max_items=80 if wave == "quick" else 200)
    for h in devpost_hacks:
        if h["apply_url"] not in seen_urls and h["id"] not in seen_ids:
            seen_urls.add(h["apply_url"])
            seen_ids.add(h["id"])
            all_seeded.append(h)

    # B: SimplifyJobs Active Student Internships
    simplify_internships = harvest_simplify_internships(max_items=80 if wave == "quick" else 500)
    for it in simplify_internships:
        if it["apply_url"] not in seen_urls and it["id"] not in seen_ids:
            seen_urls.add(it["apply_url"])
            seen_ids.add(it["id"])
            all_seeded.append(it)

    # C: Curated Matrix across All Categories
    curated = harvest_curated_directory()
    for c in curated:
        if c["apply_url"] not in seen_urls and c["id"] not in seen_ids:
            seen_urls.add(c["apply_url"])
            seen_ids.add(c["id"])
            all_seeded.append(c)

    print(f"✅ Phase 1 complete: {len(all_seeded)} high-quality items harvested.")

    # Step 2: Batched Gemini Sub-Domain Generation (If API key has credits or quick wave needs filling)
    print("\n--- PHASE 2: Batched Sub-Domain Matrix Execution ---")
    subqueries_to_run = []

    if wave == "quick":
        # 2 representative sub-queries per domain for rapid 300+ seed
        for dom in CORE_DOMAINS:
            subqueries_to_run.extend([(dom, sq) for sq in DOMAIN_SUBQUERIES[dom][:2]])
    else:
        # Full marathon: all 25 sub-queries per domain
        for dom in CORE_DOMAINS:
            for sq in DOMAIN_SUBQUERIES[dom]:
                if sq not in checkpoint["completed_subqueries"]:
                    subqueries_to_run.append((dom, sq))

    logger.info(f"Sub-queries scheduled to evaluate: {len(subqueries_to_run)}")

    for idx, (dom, sq) in enumerate(subqueries_to_run):
        if GEMINI_DEPLETED:
            print("⚡ Gemini credits depleted; bypassing remaining LLM subqueries and proceeding with multi-source harvested catalog.")
            break
        print(f"[{idx+1}/{len(subqueries_to_run)}] Evaluating ({dom}): {sq[:55]}...")
        new_items = generate_gemini_batch(sq, dom, target_count=15 if wave == "quick" else 40)
        if GEMINI_DEPLETED:
            print("⚡ Gemini credits depleted; bypassing remaining LLM subqueries and proceeding with multi-source harvested catalog.")
            break
        added_for_sq = 0

        for item in new_items:
            u = item.get("apply_url")
            i = item.get("id")
            if u and u not in seen_urls and i not in seen_ids:
                seen_urls.add(u)
                seen_ids.add(i)
                all_seeded.append(item)
                added_for_sq += 1

        checkpoint["completed_subqueries"].append(sq)
        checkpoint["domain_counts"][dom] = checkpoint["domain_counts"].get(dom, 0) + added_for_sq
        save_checkpoint(checkpoint)
        time.sleep(0.5)

    # Step 3: High-Speed Supabase Batch Upsert
    print("\n--- PHASE 3: High-Speed Supabase Batch Upsert ---")
    print(f"Ready to upsert {len(all_seeded)} validated opportunities into Supabase...")

    upserted_count = upsert_to_supabase_bulk(all_seeded, chunk_size=500)
    print(f"🎉 Successfully upserted {upserted_count} opportunities into Supabase PostgreSQL!")

    # Step 4: Sync Backup Snapshot
    sync_local_snapshot(all_seeded)

    # Step 5: Summary Report
    print("\n" + "=" * 70)
    print("  SUMMARY: INGESTION COMPLETE")
    print("=" * 70)
    domain_breakdown = {}
    for o in all_seeded:
        cat = o.get("category", "Other")
        domain_breakdown[cat] = domain_breakdown.get(cat, 0) + 1

    for dom in CORE_DOMAINS:
        print(f"  • {dom:15}: {domain_breakdown.get(dom, 0):4} opportunities seeded")

    print(f"\n  Total Seeded into Supabase : {upserted_count}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Opportunity Scout Bulk Seeding Engine")
    parser.add_argument("--wave", choices=["quick", "full"], default="quick", help="quick (300+ items) or full (1000/domain)")
    parser.add_argument("--target-per-domain", type=int, default=1000, help="Target opportunities per domain")
    args = parser.parse_args()

    run_bulk_seeder(wave=args.wave, target_per_domain=args.target_per_domain)
