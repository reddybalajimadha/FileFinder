// FileFinder web UI client logic
(function () {
    "use strict";

    const API = {
        health: "/api/health",
        index: "/api/index",
        search: "/api/search",
        stats: "/api/stats",
        byType: "/api/by-type",
        open: "/api/open",
        reveal: "/api/reveal",
    };

    const el = {
        searchInput: document.getElementById("search-input"),
        semanticToggle: document.getElementById("semantic-toggle"),
        pickFolderBtn: document.getElementById("pick-folder-btn"),
        statsBtn: document.getElementById("stats-btn"),
        currentFolder: document.getElementById("current-folder"),
        statusBar: document.getElementById("status-bar"),
        results: document.getElementById("results"),
        statsSection: document.getElementById("stats-section"),
        statsContent: document.getElementById("stats-content"),
        toast: document.getElementById("toast"),
        typeFilters: document.querySelectorAll(".type-filter"),
    };

    let debounceTimer = null;
    let statsRefreshInterval = null;
    let currentDirectory = null;

    // --- API helpers ---

    async function apiGet(url) {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Request failed");
        }
        return res.json();
    }

    async function apiPost(url, body) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Request failed");
        }
        return res.json();
    }

    // --- UI helpers ---

    function showToast(message, type = "info") {
        el.toast.textContent = message;
        el.toast.className = "toast show " + type;
        setTimeout(() => {
            el.toast.className = "toast";
        }, 3000);
    }

    function setStatus(text, loading = false) {
        el.statusBar.textContent = text;
        el.statusBar.className = loading ? "status-bar loading" : "status-bar";
    }

    function formatSize(bytes) {
        if (!bytes) return "";
        const units = ["B", "KB", "MB", "GB"];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return bytes.toFixed(bytes < 10 && i > 0 ? 1 : 0) + units[i];
    }

    function extLabel(ext) {
        if (!ext) return "FILE";
        return ext.replace(".", "").toUpperCase().slice(0, 4);
    }

    // --- Folder selection ---

    async function pickFolder() {
        let folder = null;

        // If running inside PyWebView, use its native dialog
        if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_folder) {
            try {
                folder = await window.pywebview.api.pick_folder();
            } catch (e) {
                console.error("PyWebView picker failed:", e);
            }
        }

        // Fallback: prompt the user to type a path
        if (!folder) {
            folder = prompt("Enter folder path to index:", currentDirectory || "");
        }

        if (!folder) return;

        await indexFolder(folder);
    }

    async function indexFolder(directory) {
        setStatus(`Indexing ${directory}...`, true);
        el.searchInput.disabled = true;
        el.pickFolderBtn.disabled = true;

        try {
            const result = await apiPost(API.index, { directory });
            currentDirectory = result.directory;
            el.currentFolder.textContent = result.directory;
            el.currentFolder.classList.add("active");
            setStatus(`Indexed ${result.file_count} files. ${result.message}`);
            showToast(`Indexed ${result.file_count} files`, "success");
            el.searchInput.disabled = false;
            el.searchInput.focus();
            el.typeFilters.forEach((btn) => (btn.disabled = false));
            refreshStats();
            // Start periodic stats refresh while content indexing runs
            if (statsRefreshInterval) clearInterval(statsRefreshInterval);
            statsRefreshInterval = setInterval(refreshStats, 3000);
            showEmptyState("Type to search your files", "");
        } catch (e) {
            setStatus("Indexing failed: " + e.message);
            showToast(e.message, "error");
        } finally {
            el.pickFolderBtn.disabled = false;
        }
    }

    // --- Search ---

    async function doSearch(query) {
        if (!query || query.length < 2) {
            showEmptyState("Type to search your files", "");
            return;
        }

        const semantic = el.semanticToggle.checked;
        setStatus(`Searching for "${query}"${semantic ? " (AI mode)" : ""}...`, true);

        try {
            const url = `${API.search}?q=${encodeURIComponent(query)}&limit=30&semantic=${semantic}`;
            const data = await apiGet(url);
            setStatus(`${data.count} results for "${query}"`);
            renderResults(data.results);
        } catch (e) {
            setStatus("Search failed: " + e.message);
            showToast(e.message, "error");
        }
    }

    async function searchByType(extension) {
        setStatus(`Finding .${extension} files...`, true);
        try {
            const url = `${API.byType}?extension=${encodeURIComponent(extension)}&limit=100`;
            const data = await apiGet(url);
            setStatus(`${data.count} .${extension} files`);
            renderResults(data.results.map((r) => ({
                ...r,
                extension: "." + extension,
                match_type: "type",
            })));
        } catch (e) {
            setStatus("Failed: " + e.message);
        }
    }

    // --- Rendering ---

    function renderResults(results) {
        if (!results || results.length === 0) {
            showEmptyState("No results found", "Try different search terms or enable AI Search");
            return;
        }

        el.results.innerHTML = "";
        for (const r of results) {
            const item = document.createElement("div");
            item.className = "result-item";

            const icon = document.createElement("div");
            icon.className = "result-icon";
            icon.textContent = extLabel(r.extension);

            const details = document.createElement("div");
            details.className = "result-details";

            const name = document.createElement("div");
            name.className = "result-name";
            name.textContent = r.name || r.path.split(/[/\\]/).pop();

            const path = document.createElement("div");
            path.className = "result-path";
            path.textContent = r.path;

            details.appendChild(name);
            details.appendChild(path);

            const meta = document.createElement("div");
            meta.className = "result-meta";

            if (r.size_bytes) {
                const size = document.createElement("span");
                size.textContent = formatSize(r.size_bytes);
                meta.appendChild(size);
            }

            if (r.match_type) {
                const tag = document.createElement("span");
                tag.className = "result-tag";
                tag.textContent = r.match_type;
                meta.appendChild(tag);
            }

            const actions = document.createElement("div");
            actions.className = "result-actions";

            const openBtn = document.createElement("button");
            openBtn.className = "result-action";
            openBtn.textContent = "Open";
            openBtn.onclick = (e) => {
                e.stopPropagation();
                openFile(r.path);
            };

            const revealBtn = document.createElement("button");
            revealBtn.className = "result-action";
            revealBtn.textContent = "Reveal";
            revealBtn.onclick = (e) => {
                e.stopPropagation();
                revealFile(r.path);
            };

            actions.appendChild(openBtn);
            actions.appendChild(revealBtn);

            item.appendChild(icon);
            item.appendChild(details);
            item.appendChild(meta);
            item.appendChild(actions);

            item.onclick = () => openFile(r.path);

            el.results.appendChild(item);
        }
    }

    function showEmptyState(title, hint) {
        el.results.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">[?]</div>
                <h2>${title}</h2>
                <p>${hint || ""}</p>
            </div>
        `;
    }

    // --- File actions ---

    async function openFile(path) {
        try {
            await apiPost(API.open, { path });
            showToast("Opened: " + path.split(/[/\\]/).pop(), "success");
        } catch (e) {
            showToast("Failed to open: " + e.message, "error");
        }
    }

    async function revealFile(path) {
        try {
            await apiPost(API.reveal, { path });
            showToast("Revealed in file manager", "success");
        } catch (e) {
            showToast("Failed to reveal: " + e.message, "error");
        }
    }

    // --- Stats ---

    async function refreshStats() {
        try {
            const stats = await apiGet(API.stats);
            if (!stats.indexed) {
                el.statsSection.style.display = "none";
                return;
            }

            el.statsSection.style.display = "block";
            el.statsContent.innerHTML = `
                <div><span>Total files</span><span class="stat-value">${stats.total_files || 0}</span></div>
                <div><span>Content indexed</span><span class="stat-value">${stats.content_indexed || 0}</span></div>
                <div><span>Content pending</span><span class="stat-value">${stats.content_pending || 0}</span></div>
                <div><span>File types</span><span class="stat-value">${stats.unique_extensions || 0}</span></div>
                <div><span>Total size</span><span class="stat-value">${formatSize(stats.total_size_bytes)}</span></div>
            `;

            // Stop refreshing when content indexing is complete
            if (stats.content_pending === 0 && statsRefreshInterval) {
                clearInterval(statsRefreshInterval);
                statsRefreshInterval = null;
            }
        } catch (e) {
            console.debug("Stats refresh failed:", e);
        }
    }

    // --- Event wiring ---

    el.pickFolderBtn.addEventListener("click", pickFolder);

    el.statsBtn.addEventListener("click", () => {
        el.statsSection.style.display =
            el.statsSection.style.display === "none" ? "block" : "none";
        if (el.statsSection.style.display === "block") refreshStats();
    });

    el.searchInput.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => doSearch(e.target.value.trim()), 200);
    });

    el.searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            clearTimeout(debounceTimer);
            doSearch(e.target.value.trim());
        }
    });

    el.typeFilters.forEach((btn) => {
        btn.disabled = true;
        btn.addEventListener("click", () => searchByType(btn.dataset.ext));
    });

    // Auto-index if a default directory was passed via URL (useful for PyWebView)
    const params = new URLSearchParams(window.location.search);
    const initialDir = params.get("dir");
    if (initialDir) {
        indexFolder(initialDir);
    }
})();
