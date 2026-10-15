# Student Opportunities Agents

An automated daily pipeline powered by AI agents that scouts, vets, and curates the best student opportunities — scholarships, internships, research programs, fellowships, and hackathons.

## How It Works

The pipeline runs three sequential AI agents every day at 04:00 UTC via GitHub Actions:

| Agent | Role |
|-------|------|
| 🔍 **Scout** | Discovers newly posted, active opportunities using Google Search |
| 🛡️ **Gatekeeper** | Audits every lead — removes scams, expired deadlines, and unofficial sources |
| 📋 **Curator** | Structures vetted data into a normalized opportunities.json schema |

## Output

Results are stored and auto-updated in opportunities.json with fields:
- id, 	itle, host_organization, category, cademic_level
- location_type, location, compensation, deadline, pply_url
- 	ags, one_line_pitch

## Setup

1. Fork this repo
2. Add your GEMINI_API_KEY as a repository secret
3. The workflow runs automatically at 04:00 UTC daily (or trigger manually)