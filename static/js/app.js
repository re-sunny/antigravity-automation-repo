/**
 * TECH TRENDS - Client-side engine
 * Handles news rendering, local bookmarking storage, real-time search,
 * keyword frequency analysis, and interactive analytics visualization via Chart.js
 */

// Global State
let allNews = [];
let bookmarks = [];
let ratioChartInstance = null;
let frequencyChartInstance = null;

// Target elements
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

/**
 * Initializes the application: loads tabs, bookmarks, and fetches news.
 */
async function initApp() {
    loadBookmarks();
    setupTabNavigation();
    setupEventListeners();
    await fetchNews();
}

/**
 * Loads bookmarks from secure localStorage.
 */
function loadBookmarks() {
    try {
        const stored = localStorage.getItem("tech_news_bookmarks");
        bookmarks = stored ? JSON.parse(stored) : [];
    } catch (e) {
        console.error("북마크 데이터 로딩 실패:", e);
        bookmarks = [];
    }
}

/**
 * Restores bookmarks state to secure localStorage.
 */
function saveBookmarks() {
    try {
        localStorage.setItem("tech_news_bookmarks", JSON.stringify(bookmarks));
    } catch (e) {
        console.error("북마크 데이터 저장 실패:", e);
    }
}

/**
 * Sets up custom tab switching functionality with animation hooks.
 */
function setupTabNavigation() {
    const tabs = document.querySelectorAll(".nav-tab");
    const contents = document.querySelectorAll(".tab-content");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            // Remove active classes
            tabs.forEach(t => t.classList.remove("active"));
            contents.forEach(c => c.classList.remove("active"));

            // Add active classes
            tab.classList.add("active");
            const targetId = tab.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");

            // Custom handle for tab rendering
            if (targetId === "bookmarks-tab") {
                renderBookmarksGrid();
            } else if (targetId === "insights-tab") {
                renderInsightsDashboard();
            }
        });
    });
}

/**
 * Binds input and button events.
 */
function setupEventListeners() {
    // Live Search
    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", () => {
        filterAndRenderNews();
    });

    // Source Filter
    const sourceFilter = document.getElementById("source-filter");
    sourceFilter.addEventListener("change", () => {
        filterAndRenderNews();
    });

    // Date Filter
    const dateFilter = document.getElementById("date-filter");
    if (dateFilter) {
        dateFilter.addEventListener("change", () => {
            filterAndRenderNews();
        });
    }

    // Close Modals
    document.getElementById("btn-close-details").addEventListener("click", () => {
        closeModal("modal-details");
    });
    document.getElementById("btn-modal-close").addEventListener("click", () => {
        closeModal("modal-details");
    });

    // Backdrop Click Close
    document.getElementById("modal-details").addEventListener("click", (e) => {
        if (e.target.id === "modal-details") {
            closeModal("modal-details");
        }
    });
}

/**
 * Fetches news from FastAPI backend proxy leading to Supabase.
 */
async function fetchNews() {
    const loader = document.getElementById("loader");
    const grid = document.getElementById("news-grid");

    loader.style.display = "block";
    grid.innerHTML = "";

    try {
        const response = await fetch("/api/news");
        if (response.ok) {
            allNews = await response.json();
            filterAndRenderNews();
        } else {
            console.error("뉴스 데이터를 불러오지 못했습니다.");
            grid.innerHTML = `<div class="no-data">Supabase DB 가동 상태 및 .env 의 키를 확인하십시오.</div>`;
        }
    } catch (e) {
        console.error("API 요청 중 에러 발생:", e);
        grid.innerHTML = `<div class="no-data">백엔드 서버 API 호출에 실패하였습니다.</div>`;
    } finally {
        loader.style.display = "none";
    }
}

/**
 * Formats timestamps to customized readable Korean relative presentation format.
 */
function formatKoreanDate(dateStr) {
    if (!dateStr) return "미상";

    try {
        // Handle ISO and RSS date variations
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;

        const ampm = date.getHours() < 12 ? "오전" : "오후";
        const rawHour = date.getHours();
        let hour = rawHour > 12 ? rawHour - 12 : rawHour;
        if (hour === 0) hour = 12;

        return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${ampm} ${hour}시 ${String(date.getMinutes()).padStart(2, "0")}분`;
    } catch (e) {
        return dateStr;
    }
}

/**
 * Performs local grid rendering based on selected filters (live search & source selectors).
 */
function filterAndRenderNews() {
    const query = document.getElementById("search-input").value.toLowerCase().trim();
    const source = document.getElementById("source-filter").value;
    const dateQuery = document.getElementById("date-filter").value;
    const grid = document.getElementById("news-grid");

    const filtered = allNews.filter(item => {
        // Query filter
        const matchesQuery = !query ||
            (item.title && item.title.toLowerCase().includes(query)) ||
            (item.description && item.description.toLowerCase().includes(query));

        // Source filter
        const matchesSource = source === "all" || item.source === source;

        // Date filter
        let matchesDate = true;
        if (dateQuery) {
            try {
                const articleDate = new Date(item.published_at || item.created_at);
                if (!isNaN(articleDate.getTime())) {
                    const yyyy = articleDate.getFullYear();
                    const mm = String(articleDate.getMonth() + 1).padStart(2, "0");
                    const dd = String(articleDate.getDate()).padStart(2, "0");
                    const articleYMD = `${yyyy}-${mm}-${dd}`;
                    matchesDate = (articleYMD === dateQuery);
                } else {
                    matchesDate = false;
                }
            } catch (e) {
                matchesDate = false;
            }
        }

        return matchesQuery && matchesSource && matchesDate;
    });

    // Update count labels
    document.getElementById("results-count").innerText = `조회 결과: ${filtered.length}개 기사`;

    renderGrid(filtered, grid);
}

/**
 * Renders bookmarks grid tab content.
 */
function renderBookmarksGrid() {
    const grid = document.getElementById("bookmarks-grid");
    const countLabel = document.getElementById("bookmarks-count");

    countLabel.innerText = `북마크: ${bookmarks.length}개`;

    // Filter bookmarks out from allNews to guarantee updated DB records
    const bookmarkedNews = allNews.filter(n => bookmarks.some(b => b.link === n.link));

    // Add additional locally accumulated bookmark items if they aren't in allNews
    const uniqueLocal = bookmarks.filter(b => !allNews.some(n => n.link === b.link));
    const merged = [...bookmarkedNews, ...uniqueLocal];

    renderGrid(merged, grid);
}

/**
 * General helper function to output news card structures into target DOM nodes.
 */
function renderGrid(articlesList, targetContainer) {
    targetContainer.innerHTML = "";

    if (articlesList.length === 0) {
        targetContainer.innerHTML = `<div class="no-data" style="grid-column: 1 / -1;">조건에 상응하는 수집 뉴스가 존재하지 않습니다.</div>`;
        return;
    }

    articlesList.forEach(item => {
        const isFav = bookmarks.some(b => b.link === item.link);
        const card = document.createElement("div");
        card.className = "news-card";

        const sourceClass = (item.source || "unknown").toLowerCase();

        card.innerHTML = `
            <div class="card-header">
                <span class="source-badge ${sourceClass}">${item.source || "기타"}</span>
                <button class="btn-bookmark ${isFav ? 'bookmarked' : ''}" onclick="toggleBookmark(event, ${JSON.stringify(item).replace(/"/g, '&quot;')})">
                    ${isFav ? '★' : '☆'}
                </button>
            </div>
            <div class="card-body">
                <a href="#" class="article-title" onclick="openDetails(event, ${JSON.stringify(item).replace(/"/g, '&quot;')})">
                    ${item.title || "제목 없음"}
                </a>
                <div class="pub-date">
                    <span>📅</span>
                    <span>${formatKoreanDate(item.published_at)}</span>
                </div>
                <p class="article-desc">${item.description || "이 요약문은 수집 도구에서 자동 생성되었습니다."}</p>
            </div>
            <div class="card-footer">
                <button class="btn-more" onclick="openDetails(event, ${JSON.stringify(item).replace(/"/g, '&quot;')})">
                    자세히 보기
                </button>
            </div>
        `;
        targetContainer.appendChild(card);
    });
}

/**
 * Toggles the favorited status of a news item.
 */
function toggleBookmark(event, item) {
    event.stopPropagation();
    event.preventDefault();

    const idx = bookmarks.findIndex(b => b.link === item.link);
    if (idx === -1) {
        bookmarks.push(item);
    } else {
        bookmarks.splice(idx, 1);
    }

    saveBookmarks();

    // Re-render currently active views
    const activeTab = document.querySelector(".nav-tab.active").getAttribute("data-tab");
    if (activeTab === "feed-tab") {
        filterAndRenderNews();
    } else if (activeTab === "bookmarks-tab") {
        renderBookmarksGrid();
    }
}

/**
 * Opens detailed view in an elegant modal card.
 */
function openDetails(event, item) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const modal = document.getElementById("modal-details");

    // Set content details
    document.getElementById("detail-title").innerText = item.title || "제목 정보 없음";

    const badge = document.getElementById("detail-source-badge");
    badge.innerText = item.source || "기타";
    badge.className = `source-badge ${(item.source || "unknown").toLowerCase()}`;

    document.getElementById("detail-pub-date").innerText = formatKoreanDate(item.published_at);

    const descEl = document.getElementById("detail-desc");
    const isLinkOnly = !item.description || item.description.trim() === item.title.trim() || item.description.trim().length < 80;

    // Link original
    const linkBtn = document.getElementById("detail-link-btn");
    if (item.link) {
        linkBtn.style.display = "inline-flex";
        linkBtn.href = item.link;
    } else {
        linkBtn.style.display = "none";
    }

    // Modal favorite toggle setup
    const favBtn = document.getElementById("detail-bookmark-btn");
    const isFav = bookmarks.some(b => b.link === item.link);
    favBtn.className = `btn-bookmark ${isFav ? 'bookmarked' : ''}`;
    favBtn.innerText = isFav ? '★' : '☆';

    favBtn.onclick = (e) => {
        toggleBookmark(e, item);
        const nextIsFav = bookmarks.some(b => b.link === item.link);
        favBtn.className = `btn-bookmark ${nextIsFav ? 'bookmarked' : ''}`;
        favBtn.innerText = nextIsFav ? '★' : '☆';
    };

    // AI 3줄 요약 영역 초기화 및 버튼 노출 조정
    const summarySection = document.getElementById("modal-summary-section");
    const summaryList = document.getElementById("modal-summary-list");
    summarySection.style.display = "none";
    summaryList.innerHTML = "";

    const summaryBtn = document.getElementById("btn-modal-summary");

    if (isLinkOnly) {
        descEl.innerHTML = `💡 이 기사는 등록된 요약 본문 없이 <strong>외부 원본 링크</strong>로만 구성된 글입니다.<br><br>우측 하단의 <strong>'원문 보기 ↗'</strong> 버튼을 클릭해 원본 사이트에서 전체 내용을 감상하실 수 있습니다.`;
        summaryBtn.style.display = "none";
    } else {
        descEl.innerText = item.description;
        summaryBtn.style.display = "inline-flex";
        summaryBtn.innerText = "⚡ AI 3줄 요약";
        summaryBtn.disabled = false;
        summaryBtn.style.opacity = "1";
    }

    summaryBtn.onclick = async (e) => {
        if (!item.description) return;

        summaryBtn.innerText = "요약 분석 중...";
        summaryBtn.disabled = true;
        summaryBtn.style.opacity = "0.7";

        try {
            const response = await fetch("/api/news/summarize", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ text: item.description })
            });

            if (!response.ok) {
                throw new Error("요약 API 요청에 실패했습니다.");
            }

            const data = await response.json();
            summaryList.innerHTML = "";

            if (data.summary && data.summary.length > 0) {
                data.summary.forEach(sentence => {
                    const li = document.createElement("li");
                    li.innerText = sentence;
                    summaryList.appendChild(li);
                });

                summarySection.style.display = "block";
                summaryBtn.innerText = "⚡ 요약 완료";

                // 모달 내에서 부드럽게 요약 내용 영역으로 스크롤 이동
                summarySection.scrollIntoView({ behavior: "smooth", block: "nearest" });
            } else {
                summaryBtn.innerText = "요약 분석 불가";
                summaryBtn.disabled = false;
                summaryBtn.style.opacity = "1";
            }
        } catch (err) {
            console.error("Summarization error:", err);
            summaryBtn.innerText = "분석 실패 (오류)";
            summaryBtn.disabled = false;
            summaryBtn.style.opacity = "1";
        }
    };

    modal.classList.add("active");
}

/**
 * Closes modal helper.
 */
function closeModal(id) {
    document.getElementById(id).classList.remove("active");
}

/**
 * Renders statistical dashboard metrics values and loads Chart.js charts.
 */
function renderInsightsDashboard() {
    // 1. Calculate general numbers
    const totalCount = allNews.length;
    const geekCount = allNews.filter(n => n.source === "GeekNews").length;
    const tcCount = allNews.filter(n => n.source === "TechCrunch").length;

    document.getElementById("stat-total-news").innerText = totalCount;
    document.getElementById("stat-geek-news").innerText = geekCount;
    document.getElementById("stat-tc-news").innerText = tcCount;
    document.getElementById("stat-bookmarks").innerText = bookmarks.length;

    // 2. Generate and render source ratio distribution
    renderRatioChart(geekCount, tcCount, totalCount - geekCount - tcCount);

    // 3. Generate and render date collection trends
    renderFrequencyChart();

    // 4. Generate Hot Keywords list
    renderHotKeywords();
}

/**
 * Renders source distribution doughnut chart.
 */
function renderRatioChart(geek, tc, other) {
    const ctx = document.getElementById("ratioChart").getContext("2d");

    if (ratioChartInstance) {
        ratioChartInstance.destroy();
    }

    ratioChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['GeekNews', 'TechCrunch', '기타 출처'],
            datasets: [{
                data: [geek, tc, other],
                backgroundColor: [
                    'rgba(249, 115, 22, 0.7)',  // Orange
                    'rgba(16, 185, 129, 0.7)',  // Emerald
                    'rgba(100, 116, 139, 0.7)'  // Slate
                ],
                borderColor: [
                    '#f97316',
                    '#10b981',
                    '#64748b'
                ],
                borderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Inter', size: 11 }
                    }
                }
            }
        }
    });
}

/**
 * Gathers aggregate daily quantities and renders frequency trends.
 */
function renderFrequencyChart() {
    const ctx = document.getElementById("frequencyChart").getContext("2d");

    if (frequencyChartInstance) {
        frequencyChartInstance.destroy();
    }

    // Tally up items by date
    const dateCounts = {};
    allNews.forEach(item => {
        if (!item.created_at) return;

        // Grab date portion (YYYY-MM-DD)
        const dateStr = item.created_at.substring(0, 10);
        dateCounts[dateStr] = (dateCounts[dateStr] || 0) + 1;
    });

    // Resolve sorted array of days (up to 7 latest recorded)
    const sortedDates = Object.keys(dateCounts).sort().slice(-7);
    const frequencies = sortedDates.map(date => dateCounts[date]);

    // Fallback if empty datasets
    const labels = sortedDates.length ? sortedDates : ['수집 기록 없음'];
    const dataPoints = frequencies.length ? frequencies : [0];

    frequencyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '뉴스 수집 건수',
                data: dataPoints,
                backgroundColor: 'rgba(99, 102, 241, 0.5)',
                borderColor: '#6366f1',
                borderWidth: 1.5,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', stepSize: 1 }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

/**
 * Dynamic keyword extraction engine: splits titles, filters common stopwords,
 * counts occurrence densities and generates keyword tags on the statistical board.
 */
function renderHotKeywords() {
    const container = document.getElementById("keywords-container");
    container.innerHTML = "";

    if (allNews.length === 0) {
        container.innerHTML = `<span class="text-muted">수집된 뉴스가 발생해야 키워드 집계가 가능합니다.</span>`;
        return;
    }

    const wordCounts = {};

    // Core stop words to filter out (general Korean particles, conjunctions and helper particles)
    const stopwords = new Set([
        "이", "그", "저", "은", "는", "을", "를", "에", "의", "와", "과", "도", "로", "으로", "에서",
        "해서", "그리고", "하지만", "에서", "합니다", "하는", "할", "한", "있습니다", "있는",
        "show", "gn:", "hn:", "게시판", "새로운", "출시", "공개", "기반", "기반의", "도구", "프로젝트",
        "the", "a", "of", "and", "in", "to", "for", "with", "is", "on", "an", "at", "by", "from", "how", "why"
    ]);

    allNews.forEach(n => {
        if (!n.title) return;

        // Clean characters and parse lower case tokens
        const cleanedStr = n.title.toLowerCase()
            .replace(/[^\w\sㄱ-ㅎㅏ-ㅣ가-힣]/g, ' ') // Only letters, numbers, spaces
            .replace(/\s+/g, ' ');

        const words = cleanedStr.split(' ');
        words.forEach(word => {
            const trimmed = word.trim();
            if (trimmed.length > 1 && !stopwords.has(trimmed) && isNaN(trimmed)) {
                wordCounts[trimmed] = (wordCounts[trimmed] || 0) + 1;
            }
        });
    });

    // Sort keywords by frequency values
    const sortedKeywords = Object.entries(wordCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15); // Show top 15 words

    if (sortedKeywords.length === 0) {
        container.innerHTML = `<span class="text-muted">분석에 충분한 단어 데이터가 추출되지 못했습니다.</span>`;
        return;
    }

    sortedKeywords.forEach(([word, count]) => {
        const pill = document.createElement("span");
        pill.className = "keyword-pill";
        pill.innerHTML = `
            <span>${word}</span>
            <span class="keyword-count">${count}</span>
        `;

        // Custom feature: Click keyword to trigger search on news feed tab
        pill.onclick = () => {
            // Put word in search
            document.getElementById("search-input").value = word;

            // Switch tabs
            document.querySelector('.nav-tab[data-tab="feed-tab"]').click();

            // Perform filter
            filterAndRenderNews();
        };

        container.appendChild(pill);
    });
}
