console.log("TV AI Sidecar Extension Loaded on TradingView.");

let currentTicker = "";

function extractTickerFromTitle(title) {
    // TradingView titles are usually format: "TCS 3500.00 — TradingView"
    // or sometimes just symbol name at the very start.
    if (!title) return null;
    const parts = title.split(' ');
    if (parts.length > 0) {
        // Ticker is usually the first word.
        return parts[0].trim();
    }
    return null;
}

function sendTickerToLocalAPI(ticker) {
    if (!ticker) return;
    console.log("TV AI Sidecar: Active Ticker Changed ->", ticker);
    
    // Attempt to hit the local FastAPI backend
    fetch(`http://localhost:8001/set_ticker?symbol=${encodeURIComponent(ticker)}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    }).then(response => {
        if (!response.ok) {
            console.warn("TV AI Sidecar: Failed to send ticker. Is backend running?");
        }
    }).catch(err => {
        console.error("TV AI Sidecar Error:", err);
    });
}

// Initial check
const initialTicker = extractTickerFromTitle(document.title);
if (initialTicker) {
    currentTicker = initialTicker;
    sendTickerToLocalAPI(currentTicker);
}

// Observe the title for changes, this is exactly what updates when a user changes symbols
const targetNode = document.querySelector('title');
if (targetNode) {
    const config = { childList: true, subtree: true, characterData: true };
    const callback = function(mutationsList, observer) {
        for(let mutation of mutationsList) {
            const newTicker = extractTickerFromTitle(document.title);
            // Ignore non-symbol title updates or unchanged symbols
            if (newTicker && newTicker !== currentTicker && newTicker !== "TradingView") {
                currentTicker = newTicker;
                sendTickerToLocalAPI(currentTicker);
            }
        }
    };
    const observer = new MutationObserver(callback);
    observer.observe(targetNode, config);
} else {
    // Fallback polling if title tag isn't immediately attached
    setInterval(() => {
        const newTicker = extractTickerFromTitle(document.title);
        if (newTicker && newTicker !== currentTicker && newTicker !== "TradingView") {
            currentTicker = newTicker;
            sendTickerToLocalAPI(currentTicker);
        }
    }, 2000);
}
