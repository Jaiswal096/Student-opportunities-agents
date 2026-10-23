<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Opportunity Scout - Student Opportunities Portal</title>
  <meta name="description" content="Discover verified scholarships, internships, research programs, fellowships and hackathons curated daily by AI agents. Chat with your 24/7 student advisor." />

  <!-- Tailwind CSS CDN (with dark mode class strategy) -->
  <script>
    // Apply dark mode from localStorage before Tailwind loads to avoid FOUC
    (function() {
      const saved = localStorage.getItem('theme');
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (saved === 'light') {
        document.documentElement.classList.remove('dark');
      } else {
        document.documentElement.classList.add('dark');
      }
    })();
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { DEFAULT: '#6366f1', dark: '#4f46e5', light: '#818cf8' },
            violet: '#8b5cf6',
          },
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
          },
          animation: {
            'fade-up': 'fadeUp 0.4s ease both',
            'pulse-glow': 'pulseGlow 3s ease-in-out infinite',
            'blink': 'blink 2s ease-in-out infinite',
            'bounce-dot': 'bounceDot 1.2s ease-in-out infinite',
          },
          keyframes: {
            fadeUp: { from: { opacity: 0, transform: 'translateY(16px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
            pulseGlow: { '0%,100%': { boxShadow: '0 0 24px rgba(99,102,241,0.4)' }, '50%': { boxShadow: '0 0 48px rgba(99,102,241,0.7)' } },
            blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } },
            bounceDot: { '0%,80%,100%': { transform: 'translateY(0)' }, '40%': { transform: 'translateY(-6px)' } },
          },
        },
      },
    };
  </script>

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />

  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>

  <style>
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { font-family: 'Inter', system-ui, sans-serif; -webkit-font-smoothing: antialiased; }

    /* Animated background orbs */
    .bg-orb-1 {
      position: fixed; top: -20%; left: -10%; width: 60vw; height: 60vw;
      background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%);
      border-radius: 50%; pointer-events: none; z-index: 0;
      animation: orb1 12s ease-in-out infinite alternate;
    }
    .bg-orb-2 {
      position: fixed; bottom: -20%; right: -10%; width: 50vw; height: 50vw;
      background: radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 70%);
      border-radius: 50%; pointer-events: none; z-index: 0;
      animation: orb2 15s ease-in-out infinite alternate;
    }
    @keyframes orb1 { from { transform: translate(0,0) scale(1); } to { transform: translate(5%,5%) scale(1.1); } }
    @keyframes orb2 { from { transform: translate(0,0) scale(1); } to { transform: translate(-5%,-5%) scale(1.15); } }

    /* Glowing gradient text */
    .gradient-text {
      background: linear-gradient(135deg, #ffffff 0%, #c4b5fd 55%, #818cf8 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .gradient-text-brand {
      background: linear-gradient(90deg, #e0e7ff, #c4b5fd);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }

    /* Glassmorphism card */
    .glass-card {
      background: rgba(255,255,255,0.04);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255,255,255,0.08);
    }
    .light-glass-card {
      background: rgba(255,255,255,0.9);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(0,0,0,0.06);
    }

    /* Opportunity card hover glow */
    .opp-card {
      transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
      position: relative; overflow: hidden;
    }
    .opp-card::before {
      content: ''; position: absolute; inset: 0;
      background: linear-gradient(135deg, rgba(99,102,241,0.05) 0%, transparent 60%);
      opacity: 0; transition: opacity 0.25s ease; pointer-events: none;
    }
    .opp-card:hover { transform: translateY(-4px); box-shadow: 0 20px 60px rgba(0,0,0,0.4); }
    .opp-card:hover::before { opacity: 1; }
    .dark .opp-card:hover { border-color: rgba(99,102,241,0.5) !important; }
    .light .opp-card:hover { border-color: rgba(99,102,241,0.4) !important; }

    /* Skeleton loading animation */
    .skeleton {
      background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
    }
    .dark .skeleton {
      background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
      background-size: 200% 100%;
    }
    :root.light .skeleton, html:not(.dark) .skeleton {
      background: linear-gradient(90deg, rgba(0,0,0,0.04) 25%, rgba(0,0,0,0.08) 50%, rgba(0,0,0,0.04) 75%);
      background-size: 200% 100%;
    }
    @keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    .dark ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
    html:not(.dark) ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 3px; }

    /* Filter pill active */
    .pill-active {
      background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
      border-color: transparent !important;
      color: white !important;
    }

    /* Theme toggle transition */
    html { transition: background-color 0.3s ease, color 0.3s ease; }

    /* Kbd shortcut badge */
    kbd {
      display: inline-flex; align-items: center; justify-content: center;
      padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;
      border: 1px solid; font-family: inherit; line-height: 1.4;
    }
    .dark kbd { background: rgba(255,255,255,0.07); border-color: rgba(255,255,255,0.15); color: rgba(255,255,255,0.5); }
    html:not(.dark) kbd { background: rgba(0,0,0,0.05); border-color: rgba(0,0,0,0.15); color: rgba(0,0,0,0.4); }

    /* Deadline badge animations */
    @keyframes urgentPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.65; } }
    .deadline-urgent { animation: urgentPulse 1.5s ease-in-out infinite; }
  </style>
</head>

<body class="dark:bg-slate-950 dark:text-slate-100 bg-slate-50 text-slate-900 min-h-screen transition-colors duration-300">

  <!-- Background orbs -->
  <div class="bg-orb-1"></div>
  <div class="bg-orb-2"></div>

  <!-- ?????????????????? HEADER ?????????????????? -->
  <header class="sticky top-0 z-50 dark:bg-slate-950/85 bg-white/85 backdrop-blur-xl border-b dark:border-slate-800/60 border-slate-200/80 transition-colors duration-300">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 py-3">
      <div class="flex items-center gap-3">

        <!-- Logo -->
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 flex-shrink-0 text-white text-xl">??</div>

        <!-- Wordmark -->
        <div class="flex-1 min-w-0">
          <h1 class="text-lg font-extrabold gradient-text-brand leading-tight">Opportunity Scout</h1>
          <p class="text-xs dark:text-slate-400 text-slate-500 font-normal hidden sm:block">AI-curated student opportunities, updated daily</p>
        </div>

        <!-- Live badge -->
        <div class="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full dark:bg-indigo-500/10 bg-indigo-50 border dark:border-indigo-500/20 border-indigo-200 text-xs font-semibold dark:text-indigo-300 text-indigo-600 flex-shrink-0">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-[blink_2s_ease-in-out_infinite]"></span>
          <span id="header-count">Loading.</span>
        </div>

        <!-- Dark/Light Toggle -->
        <button
          id="theme-toggle"
          aria-label="Toggle dark/light mode"
          class="w-9 h-9 rounded-xl dark:bg-slate-800 bg-slate-100 dark:hover:bg-slate-700 hover:bg-slate-200 border dark:border-slate-700 border-slate-200 flex items-center justify-center transition-all duration-200 flex-shrink-0"
        >
          <i id="theme-icon-moon" data-lucide="moon" class="w-4 h-4 dark:text-slate-300 text-slate-600 block dark:block hidden"></i>
          <i id="theme-icon-sun" data-lucide="sun" class="w-4 h-4 dark:text-slate-300 text-slate-600 dark:hidden block"></i>
        </button>

      </div>
    </div>
  </header>

  <!-- ?????????????????? MAIN ?????????????????? -->
  <main class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6">

    <!-- ?? Hero ?? -->
    <section class="text-center pt-14 pb-10">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full dark:bg-indigo-500/10 bg-indigo-50 border dark:border-indigo-500/20 border-indigo-200 text-xs font-semibold dark:text-indigo-300 text-indigo-600 mb-5">
        <i data-lucide="bot" class="w-3.5 h-3.5"></i>
        Powered by AI Agents - Scout ? Gatekeeper ? Curator
      </div>
      <h2 class="text-4xl sm:text-5xl lg:text-6xl font-black gradient-text leading-tight mb-4">
        Find Your Next Big<br/>Student Opportunity
      </h2>
      <p class="text-base sm:text-lg dark:text-slate-400 text-slate-500 max-w-xl mx-auto mb-0 font-normal leading-relaxed">
        Verified scholarships, internships, research programs, fellowships &amp; hackathons - discovered and vetted by AI agents every day.
      </p>
    </section>

    <!-- ?? Stats Bar ?? -->
    <div class="flex flex-wrap gap-3 justify-center mb-10" id="stats-bar">
      <div class="stat-chip flex items-center gap-2.5 dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-xl px-4 py-2.5 text-sm shadow-sm">
        <span class="text-xl">??</span>
        <div><strong id="stat-total" class="font-bold text-lg dark:text-white text-slate-900">-</strong> <span class="dark:text-slate-400 text-slate-500">Total Active</span></div>
      </div>
      <div class="stat-chip flex items-center gap-2.5 dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-xl px-4 py-2.5 text-sm shadow-sm">
        <span class="text-xl">?</span>
        <div><strong id="stat-funded" class="font-bold text-lg dark:text-emerald-400 text-emerald-600">-</strong> <span class="dark:text-slate-400 text-slate-500">Fully Funded / Paid</span></div>
      </div>
      <div class="stat-chip flex items-center gap-2.5 dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-xl px-4 py-2.5 text-sm shadow-sm">
        <span class="text-xl">??</span>
        <div><strong id="stat-closing" class="font-bold text-lg dark:text-amber-400 text-amber-600">-</strong> <span class="dark:text-slate-400 text-slate-500">Closing Soon (14 days)</span></div>
      </div>
      <div class="stat-chip flex items-center gap-2.5 dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-xl px-4 py-2.5 text-sm shadow-sm">
        <span class="text-xl">??</span>
        <div><strong id="stat-scholarship" class="font-bold text-lg dark:text-amber-300 text-amber-600">-</strong> <span class="dark:text-slate-400 text-slate-500">Scholarships</span></div>
      </div>
      <div class="stat-chip flex items-center gap-2.5 dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-xl px-4 py-2.5 text-sm shadow-sm">
        <span class="text-xl">??</span>
        <div><strong id="stat-internship" class="font-bold text-lg dark:text-blue-400 text-blue-600">-</strong> <span class="dark:text-slate-400 text-slate-500">Internships</span></div>
      </div>
    </div>

    <!-- ?? Search & Filters ?? -->
    <div class="max-w-4xl mx-auto mb-8 space-y-4">

      <!-- Search bar -->
      <div class="relative">
        <i data-lucide="search" class="absolute left-4 top-1/2 -translate-y-1/2 w-4.5 h-4.5 dark:text-slate-500 text-slate-400 pointer-events-none"></i>
        <input
          type="search"
          id="search"
          placeholder="Search by title, organization, tag, or keyword."
          aria-label="Search opportunities"
          autocomplete="off"
          class="w-full pl-11 pr-24 py-3.5 dark:bg-slate-900/70 bg-white border dark:border-slate-800 border-slate-200 rounded-2xl dark:text-slate-100 text-slate-900 text-sm placeholder:dark:text-slate-600 placeholder:text-slate-400 outline-none focus:ring-2 dark:focus:ring-indigo-500/40 focus:ring-indigo-500/30 focus:border-indigo-500 transition-all duration-200 shadow-sm font-medium"
        />
        <span class="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1">
          <kbd>?</kbd><kbd>K</kbd>
        </span>
      </div>

      <!-- Category pills -->
      <div class="flex flex-wrap gap-2 items-center">
        <span class="text-xs font-semibold dark:text-slate-500 text-slate-400 uppercase tracking-widest mr-1">Category:</span>
        <button class="filter-btn pill-active px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="all">All</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Internship">?? Internship</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Research">?? Research</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Scholarship">?? Scholarship</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Fellowship">?? Fellowship</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Hackathon">? Hackathon</button>
        <button class="filter-btn px-4 py-1.5 rounded-full text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 hover:border-indigo-500 transition-all duration-150" data-filter="Grant">?? Grant</button>
      </div>

      <!-- Secondary dropdown filters -->
      <div class="flex flex-wrap gap-3 items-center">
        <span class="text-xs font-semibold dark:text-slate-500 text-slate-400 uppercase tracking-widest mr-1">Filter:</span>

        <select id="filter-level" aria-label="Filter by academic level" class="px-3 py-2 rounded-xl text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 outline-none cursor-pointer transition-all duration-150 focus:border-indigo-500">
          <option value="all">?? All Levels</option>
          <option value="High School">High School</option>
          <option value="Undergraduate">Undergraduate</option>
          <option value="Masters">Masters</option>
          <option value="PhD">PhD</option>
        </select>

        <select id="filter-location" aria-label="Filter by location type" class="px-3 py-2 rounded-xl text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 outline-none cursor-pointer transition-all duration-150 focus:border-indigo-500">
          <option value="all">?? All Locations</option>
          <option value="Remote">Remote</option>
          <option value="Hybrid">Hybrid</option>
          <option value="On-site">On-site</option>
        </select>

        <select id="filter-comp" aria-label="Filter by compensation" class="px-3 py-2 rounded-xl text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 outline-none cursor-pointer transition-all duration-150 focus:border-indigo-500">
          <option value="all">?? All Compensation</option>
          <option value="Fully Funded">? Fully Funded</option>
          <option value="Paid Stipend">?? Paid Stipend</option>
          <option value="Cash Prize">?? Cash Prize</option>
          <option value="Unpaid">Unpaid</option>
        </select>

        <select id="sort-select" aria-label="Sort opportunities" class="px-3 py-2 rounded-xl text-xs font-semibold dark:bg-slate-900 bg-white border dark:border-slate-700 border-slate-200 dark:text-slate-300 text-slate-600 outline-none cursor-pointer transition-all duration-150 focus:border-indigo-500 ml-auto">
          <option value="deadline">? Deadline (Soonest)</option>
          <option value="title">?? Title (A-Z)</option>
          <option value="compensation">?? Compensation</option>
        </select>
      </div>
    </div>

    <!-- ?? Results bar ?? -->
    <div class="flex items-center justify-between mb-5 flex-wrap gap-3 max-w-4xl mx-auto lg:max-w-none">
      <p class="text-sm dark:text-slate-400 text-slate-500 font-medium" id="results-count"></p>
      <button
        id="reset-btn"
        onclick="resetFilters()"
        class="hidden text-xs font-semibold px-3 py-1.5 rounded-lg dark:bg-slate-800 bg-slate-100 dark:text-slate-300 text-slate-600 hover:dark:bg-slate-700 hover:bg-slate-200 transition-colors border dark:border-slate-700 border-slate-200"
      >
        ? Clear Filters
      </button>
    </div>

    <!-- ?? Cards Grid ?? -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-24" id="cards-grid">
      <!-- Skeleton loaders -->
      <div class="skeleton h-72 rounded-2xl"></div>
      <div class="skeleton h-72 rounded-2xl"></div>
      <div class="skeleton h-72 rounded-2xl"></div>
      <div class="skeleton h-72 rounded-2xl hidden md:block"></div>
      <div class="skeleton h-72 rounded-2xl hidden lg:block"></div>
      <div class="skeleton h-72 rounded-2xl hidden lg:block"></div>
    </div>

  </main>

  <!-- ?????????????????? CHAT WIDGET ?????????????????? -->
  <script src="/widget.js" data-api-url="/api/chat"></script>

  <!-- ?????????????????? PORTAL LOGIC ?????????????????? -->
  <script>
    // ?? Dark Mode Toggle ?????????????????????????????????????????????????????
    const themeToggle = document.getElementById('theme-toggle');
    themeToggle.addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
      lucide.createIcons();
    });

    // ?? Keyboard shortcut: Cmd/Ctrl+K ? focus search ?????????????????????????
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('search').focus();
        document.getElementById('search').select();
      }
    });

    // ?? Config ???????????????????????????????????????????????????????????????
    const OPPORTUNITIES_URL = '/opportunities.json';

    const CAT_EMOJI   = { Scholarship:'??', Internship:'??', Research:'??', Hackathon:'?', Fellowship:'??', Grant:'??' };
    const CAT_COLORS  = {
      Scholarship: { bg: 'rgba(245,158,11,0.12)', badge: 'bg-amber-500/10 text-amber-400 border border-amber-500/20' },
      Internship:  { bg: 'rgba(59,130,246,0.12)',  badge: 'bg-blue-500/10 text-blue-400 border border-blue-500/20' },
      Research:    { bg: 'rgba(139,92,246,0.12)',  badge: 'bg-violet-500/10 text-violet-400 border border-violet-500/20' },
      Hackathon:   { bg: 'rgba(16,185,129,0.12)',  badge: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' },
      Fellowship:  { bg: 'rgba(249,115,22,0.12)',  badge: 'bg-orange-500/10 text-orange-400 border border-orange-500/20' },
      Grant:       { bg: 'rgba(236,72,153,0.12)',  badge: 'bg-pink-500/10 text-pink-400 border border-pink-500/20' },
    };
    const COMP_BADGE  = {
      'Fully Funded': 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      'Paid Stipend': 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      'Cash Prize':   'bg-amber-500/10 text-amber-400 border border-amber-500/20',
      'Unpaid':       'dark:bg-slate-700/50 bg-slate-100 dark:text-slate-400 text-slate-500 border dark:border-slate-600 border-slate-200',
      'N/A':          'dark:bg-slate-700/50 bg-slate-100 dark:text-slate-400 text-slate-500 border dark:border-slate-600 border-slate-200',
    };
    const LOC_BADGE = {
      'Remote':  'bg-sky-500/10 text-sky-400 border border-sky-500/20',
      'Hybrid':  'bg-purple-500/10 text-purple-400 border border-purple-500/20',
      'On-site': 'dark:bg-slate-700/50 bg-slate-100 dark:text-slate-400 text-slate-500 border dark:border-slate-600 border-slate-200',
    };

    // ?? State ????????????????????????????????????????????????????????????????
    let allOpportunities = [];
    let activeCategory   = 'all';
    let activeLevel      = 'all';
    let activeLocation   = 'all';
    let activeComp       = 'all';
    let searchQuery      = '';
    let sortBy           = 'deadline';

    // ?? Helpers ??????????????????????????????????????????????????????????????
    function daysUntil(dateStr) {
      if (!dateStr || dateStr === 'Rolling') return null;
      return Math.ceil((new Date(dateStr) - new Date()) / 86400000);
    }

    function deadlineInfo(dateStr) {
      if (!dateStr || dateStr === 'Rolling')
        return { text: 'Rolling', cls: 'dark:text-slate-400 text-slate-500', icon: 'refresh-cw', urgent: false };
      const d = daysUntil(dateStr);
      if (d < 0)   return { text: 'Deadline passed', cls: 'text-slate-500 line-through', icon: 'x-circle', urgent: false };
      if (d === 0) return { text: 'Closes TODAY!', cls: 'text-red-400 deadline-urgent font-bold', icon: 'alert-circle', urgent: true };
      if (d <= 7)  return { text: `${d}d left`, cls: 'text-red-400 deadline-urgent font-semibold', icon: 'alert-triangle', urgent: true };
      if (d <= 14) return { text: `${d}d left`, cls: 'text-amber-400 font-semibold', icon: 'clock', urgent: true };
      if (d <= 30) return { text: `${d} days left`, cls: 'dark:text-slate-300 text-slate-600', icon: 'clock', urgent: false };
      return { text: dateStr, cls: 'dark:text-slate-400 text-slate-500', icon: 'calendar', urgent: false };
    }

    function esc(s) {
      return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ?? Render card ??????????????????????????????????????????????????????????
    function renderCard(opp, idx) {
      const cat     = opp.category || 'Other';
      const emoji   = CAT_EMOJI[cat] || '??';
      const catInfo = CAT_COLORS[cat] || { bg: 'rgba(255,255,255,0.06)', badge: 'dark:bg-slate-700 bg-slate-100 dark:text-slate-300 text-slate-500' };
      const comp    = opp.compensation || 'N/A';
      const compBadge = COMP_BADGE[comp] || COMP_BADGE['N/A'];
      const locBadge  = opp.location_type ? (LOC_BADGE[opp.location_type] || LOC_BADGE['On-site']) : '';
      const dl      = deadlineInfo(opp.deadline);
      const tags    = (opp.tags || []).slice(0, 4);
      const delay   = Math.min(idx * 0.05, 0.4);
      const compIcon = comp === 'Fully Funded' ? '? ' : comp === 'Paid Stipend' ? '?? ' : comp === 'Cash Prize' ? '?? ' : '';
      const locIcon  = opp.location_type === 'Remote' ? '??' : opp.location_type === 'Hybrid' ? '??' : '??';

      return `
        <article class="opp-card dark:bg-slate-900/60 bg-white border dark:border-slate-800 border-slate-200 rounded-2xl p-5 flex flex-col gap-3.5 shadow-sm" style="animation: fadeUp 0.4s ease ${delay}s both" aria-label="${esc(opp.title)}">

          <!-- Top: icon + org + title -->
          <div class="flex items-start gap-3">
            <div class="w-11 h-11 rounded-xl flex items-center justify-center text-2xl flex-shrink-0" style="background:${catInfo.bg}">${emoji}</div>
            <div class="flex-1 min-w-0">
              <div class="text-xs dark:text-slate-500 text-slate-400 font-medium truncate mb-0.5">${esc(opp.host_organization)}</div>
              <div class="text-sm font-bold dark:text-white text-slate-900 leading-snug line-clamp-2">${esc(opp.title)}</div>
            </div>
          </div>

          <!-- Badges row -->
          <div class="flex flex-wrap gap-1.5">
            <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${catInfo.badge}">${emoji} ${esc(cat)}</span>
            <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${compBadge}">${compIcon}${esc(comp)}</span>
            ${opp.location_type ? `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${locBadge}">${locIcon} ${esc(opp.location_type)}</span>` : ''}
          </div>

          <!-- Pitch -->
          ${opp.one_line_pitch ? `<p class="text-xs dark:text-slate-400 text-slate-500 leading-relaxed line-clamp-2">${esc(opp.one_line_pitch)}</p>` : ''}

          <!-- Tags -->
          ${tags.length ? `<div class="flex flex-wrap gap-1">${tags.map(t => `<span class="text-xs px-2 py-0.5 rounded-md dark:bg-slate-800 bg-slate-100 dark:text-slate-400 text-slate-500 border dark:border-slate-700 border-slate-200 font-medium">${esc(t)}</span>`).join('')}</div>` : ''}

          <!-- Footer: deadline + actions -->
          <div class="mt-auto pt-3.5 border-t dark:border-slate-800 border-slate-100 flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-1.5 text-xs ${dl.cls}">
              <i data-lucide="${dl.icon}" class="w-3.5 h-3.5 flex-shrink-0"></i>
              <span>${dl.text}</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                class="ask-advisor-btn text-xs font-semibold px-3 py-1.5 rounded-lg dark:bg-indigo-500/10 bg-indigo-50 dark:text-indigo-400 text-indigo-600 border dark:border-indigo-500/20 border-indigo-200 hover:dark:bg-indigo-500/20 hover:bg-indigo-100 transition-colors"
                data-title="${esc(opp.title)}"
                data-org="${esc(opp.host_organization)}"
                aria-label="Ask advisor about ${esc(opp.title)}"
              >?? Ask Advisor</button>
              <a
                href="${esc(opp.apply_url)}"
                target="_blank"
                rel="noopener"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90 hover:-translate-y-px transition-all"
                id="apply-${esc(opp.id)}"
              >Apply Now <i data-lucide="arrow-up-right" class="w-3 h-3"></i></a>
            </div>
          </div>

        </article>`;
    }

    // ?? Filter & sort ????????????????????????????????????????????????????????
    function getFiltered() {
      let data = [...allOpportunities];
      if (activeCategory !== 'all')
        data = data.filter(o => (o.category||'').toLowerCase() === activeCategory.toLowerCase());
      if (activeLevel !== 'all')
        data = data.filter(o => Array.isArray(o.academic_level) && o.academic_level.includes(activeLevel));
      if (activeLocation !== 'all')
        data = data.filter(o => o.location_type === activeLocation);
      if (activeComp !== 'all')
        data = data.filter(o => o.compensation === activeComp);
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        data = data.filter(o =>
          (o.title||'').toLowerCase().includes(q) ||
          (o.host_organization||'').toLowerCase().includes(q) ||
          (o.one_line_pitch||'').toLowerCase().includes(q) ||
          (o.tags||[]).some(t => t.toLowerCase().includes(q))
        );
      }
      if (sortBy === 'deadline') {
        data.sort((a,b) => {
          const da = a.deadline === 'Rolling' ? 9999 : daysUntil(a.deadline) ?? 9999;
          const db = b.deadline === 'Rolling' ? 9999 : daysUntil(b.deadline) ?? 9999;
          return da - db;
        });
      } else if (sortBy === 'title') {
        data.sort((a,b) => (a.title||'').localeCompare(b.title||''));
      } else if (sortBy === 'compensation') {
        const order = { 'Fully Funded':0, 'Paid Stipend':1, 'Cash Prize':2, 'Unpaid':3, 'N/A':4 };
        data.sort((a,b) => (order[a.compensation]??5) - (order[b.compensation]??5));
      }
      return data;
    }

    function hasActiveFilters() {
      return activeCategory !== 'all' || activeLevel !== 'all' || activeLocation !== 'all' || activeComp !== 'all' || searchQuery !== '';
    }

    // ?? Render grid ??????????????????????????????????????????????????????????
    function render() {
      const grid    = document.getElementById('cards-grid');
      const countEl = document.getElementById('results-count');
      const resetBtn = document.getElementById('reset-btn');
      const data    = getFiltered();

      resetBtn.classList.toggle('hidden', !hasActiveFilters());

      countEl.innerHTML = data.length
        ? `Showing <strong class="dark:text-white text-slate-900">${data.length}</strong> of <strong class="dark:text-white text-slate-900">${allOpportunities.length}</strong> opportunities`
        : '';

      if (!data.length) {
        grid.innerHTML = `
          <div class="col-span-full text-center py-20 px-6">
            <div class="text-6xl mb-5">??</div>
            <div class="text-xl font-bold dark:text-white text-slate-900 mb-3">No opportunities found</div>
            <div class="text-sm dark:text-slate-400 text-slate-500 max-w-sm mx-auto mb-6">Try adjusting your filters or search term - or ask the Advisor chat for personalized recommendations.</div>
            <button onclick="resetFilters()" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90 transition-opacity">
              ? Clear all filters
            </button>
          </div>`;
        return;
      }

      grid.innerHTML = data.map((opp, i) => renderCard(opp, i)).join('');
      lucide.createIcons();

      // Attach Ask Advisor listeners
      grid.querySelectorAll('.ask-advisor-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const title = btn.dataset.title;
          const org   = btn.dataset.org;
          const prompt = `Tell me how to make my application stand out for ${title} at ${org}.`;
          if (window.askAdvisor) {
            window.askAdvisor(prompt);
          }
        });
      });
    }

    // ?? Stats ????????????????????????????????????????????????????????????????
    function updateStats() {
      const d = allOpportunities;
      document.getElementById('stat-total').textContent        = d.length;
      document.getElementById('stat-funded').textContent       = d.filter(o => o.compensation === 'Fully Funded' || o.compensation === 'Paid Stipend').length;
      document.getElementById('stat-closing').textContent      = d.filter(o => { const days = daysUntil(o.deadline); return days !== null && days >= 0 && days <= 14; }).length;
      document.getElementById('stat-scholarship').textContent  = d.filter(o => o.category === 'Scholarship').length;
      document.getElementById('stat-internship').textContent   = d.filter(o => o.category === 'Internship').length;
      document.getElementById('header-count').textContent = `${d.length} live opportunities`;
    }

    // ?? Reset ????????????????????????????????????????????????????????????????
    function resetFilters() {
      activeCategory = 'all'; activeLevel = 'all'; activeLocation = 'all'; activeComp = 'all'; searchQuery = '';
      document.getElementById('search').value = '';
      document.getElementById('filter-level').value = 'all';
      document.getElementById('filter-location').value = 'all';
      document.getElementById('filter-comp').value = 'all';
      document.querySelectorAll('[data-filter]').forEach(b => b.classList.toggle('pill-active', b.dataset.filter === 'all'));
      render();
    }

    // ?? Event listeners ??????????????????????????????????????????????????????
    document.addEventListener('DOMContentLoaded', () => {
      // Lucide icons first pass
      lucide.createIcons();

      // Search
      document.getElementById('search').addEventListener('input', e => {
        searchQuery = e.target.value.trim();
        render();
      });

      // Category pills
      document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', () => {
          activeCategory = btn.dataset.filter;
          document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('pill-active'));
          btn.classList.add('pill-active');
          render();
        });
      });

      // Dropdown filters
      document.getElementById('filter-level').addEventListener('change', e => { activeLevel = e.target.value; render(); });
      document.getElementById('filter-location').addEventListener('change', e => { activeLocation = e.target.value; render(); });
      document.getElementById('filter-comp').addEventListener('change', e => { activeComp = e.target.value; render(); });
      document.getElementById('sort-select').addEventListener('change', e => { sortBy = e.target.value; render(); });

      // Fetch opportunities from local JSON
      fetch(OPPORTUNITIES_URL)
        .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(data => {
          if (!Array.isArray(data) || data.length === 0) throw new Error('empty');
          allOpportunities = data.filter(o => o.is_active !== false);
          updateStats();
          render();
        })
        .catch(() => {
          // Fallback: try /api/opportunities
          return fetch('/api/opportunities')
            .then(r => r.json())
            .then(data => {
              if (!Array.isArray(data) || data.length === 0) throw new Error('empty');
              allOpportunities = data.filter(o => o.is_active !== false);
              updateStats();
              render();
            });
        })
        .catch(() => {
          document.getElementById('header-count').textContent = 'Pipeline pending';
          document.getElementById('cards-grid').innerHTML = `
            <div class="col-span-full text-center py-20 px-6">
              <div class="text-6xl mb-5">??</div>
              <div class="text-xl font-bold dark:text-white text-slate-900 mb-3">Pipeline hasn't run yet</div>
              <div class="text-sm dark:text-slate-400 text-slate-500 max-w-md mx-auto mb-6">
                The AI agents run daily at 04:00 UTC to discover and verify new opportunities.
                Check back tomorrow - or ask <strong>Opportunity Scout</strong> chat (bottom-right) for advice right now!
              </div>
              <button onclick="if(window.askAdvisor) window.askAdvisor('What are some good opportunities for students right now?')" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:opacity-90 transition-opacity">
                ?? Ask the Advisor
              </button>
            </div>`;
          document.querySelectorAll('.stat-chip strong').forEach(el => el.textContent = '0');
          lucide.createIcons();
        });
    });
  </script>

</body>
</html>
