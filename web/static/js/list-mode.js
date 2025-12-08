// ========================================
// LibreCrawl - List Mode Module
// ========================================

// List Mode Variables (globally accessible)
window.currentCrawlMode = 'standard';
window.currentListTab = 'paste';
window.validUrlList = [];
window.invalidUrlList = [];

// Switch between Standard and List Mode
function switchCrawlMode(mode) {
    console.log('Switching crawl mode to:', mode);
    window.currentCrawlMode = mode;
    const standardInput = document.getElementById('standardModeInput');
    const listInput = document.getElementById('listModeInput');

    if (mode === 'standard') {
        standardInput.style.display = 'block';
        listInput.style.display = 'none';
    } else {
        standardInput.style.display = 'none';
        listInput.style.display = 'block';
    }
}

// Switch between Paste and Upload tabs in List Mode
function switchListTab(tab) {
    console.log('Switching list tab to:', tab);
    window.currentListTab = tab;
    const pasteTab = document.getElementById('pasteTab');
    const uploadTab = document.getElementById('uploadTab');
    const pasteContent = document.getElementById('pasteUrlsContent');
    const uploadContent = document.getElementById('uploadFileContent');

    if (tab === 'paste') {
        pasteTab.classList.add('active');
        uploadTab.classList.remove('active');
        pasteContent.style.display = 'block';
        uploadContent.style.display = 'none';
    } else {
        pasteTab.classList.remove('active');
        uploadTab.classList.add('active');
        pasteContent.style.display = 'none';
        uploadContent.style.display = 'block';
    }
}

// Validate URL list from textarea
async function validateUrlList() {
    const textarea = document.getElementById('urlListText');
    const urlText = textarea.value.trim();

    if (!urlText) {
        document.getElementById('urlListStats').style.display = 'none';
        return;
    }

    try {
        const response = await fetch('/api/parse_url_list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ urlText: urlText })
        });

        const data = await response.json();

        if (data.success) {
            window.validUrlList = data.validUrls;
            window.invalidUrlList = data.invalidUrls;

            // Update stats display
            document.getElementById('validUrlCount').textContent = window.validUrlList.length;
            document.getElementById('invalidUrlCount').textContent = window.invalidUrlList.length;
            document.getElementById('uniqueDomainCount').textContent = data.stats.unique_domains;

            document.getElementById('urlListStats').style.display = 'flex';

            if (window.invalidUrlList.length > 0) {
                document.getElementById('invalidUrlBadge').style.display = 'inline-flex';
            } else {
                document.getElementById('invalidUrlBadge').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error validating URL list:', error);
    }
}

// Handle file upload
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload_url_list', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            window.validUrlList = data.validUrls;
            window.invalidUrlList = data.invalidUrls;

            // Show file info
            document.getElementById('fileName').textContent = file.name;
            document.getElementById('fileInfo').style.display = 'flex';

            // Update textarea with the content
            const textarea = document.getElementById('urlListText');
            textarea.value = window.validUrlList.join('\n');

            // Switch to paste tab to show results
            switchListTab('paste');

            // Validate to show stats
            await validateUrlList();

            if (typeof showNotification === 'function') {
                showNotification(`Loaded ${window.validUrlList.length} valid URLs from ${file.name}`, 'success');
            }
        } else {
            if (typeof showNotification === 'function') {
                showNotification(data.error || 'Failed to upload file', 'error');
            }
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        if (typeof showNotification === 'function') {
            showNotification('Error uploading file', 'error');
        }
    }
}

// Clear uploaded file
function clearFile() {
    document.getElementById('urlListFile').value = '';
    document.getElementById('fileInfo').style.display = 'none';
    window.validUrlList = [];
    window.invalidUrlList = [];
}

// Expose variables to global scope for use in main app.js
window.listMode = {
    currentCrawlMode: () => currentCrawlMode,
    validUrlList: () => validUrlList,
    invalidUrlList: () => invalidUrlList
};

console.log('List Mode module loaded successfully');
