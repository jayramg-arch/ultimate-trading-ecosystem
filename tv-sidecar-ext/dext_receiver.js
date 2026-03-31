console.log("TV AI Sidecar: Dext T3 Receiver Loaded.");

let lastTicker = "";

function injectTickerToSearchBox(searchInput, ticker) {
    if (!searchInput) return;
    
    ticker = ticker.replace("NSE:", "").replace("BSE:", "");
    console.log("Dext Receiver: Injecting ticker into search box ->", ticker);
    
    // 1. Force value
    searchInput.focus();
    searchInput.value = ticker;
    
    // 2. Dispatch React/Vue events
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    searchInput.dispatchEvent(new Event('change', { bubbles: true }));
    
    // 3. Wait for the broker backend to return predictive search results
    setTimeout(() => {
        // 4. Hit Enter
        searchInput.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
        }));
        
        // 5. Hardcode a click on the first match if Enter fails
        setTimeout(() => {
            const items = Array.from(document.querySelectorAll('div[data-role="list-item"], .list-item, [role="option"], li'));
            const exactMatch = items.find(el => el.textContent && el.textContent.toUpperCase().includes(ticker.toUpperCase()) && el.clientHeight > 0);
            if (exactMatch) {
                exactMatch.click();
            }
        }, 500);
        
    }, 400);
}

function syncDextUI(ticker) {
    if (!ticker) return;

    // Search for the explicit TradingView search box using the user's provided metadata
    let searchInput = document.querySelector('input[data-role="search"]');
    
    if (searchInput && searchInput.clientHeight > 0) {
        // The search box is already open and visible, inject immediately
        injectTickerToSearchBox(searchInput, ticker);
    } else {
        // The search box is closed. In TradingView charting, typing any letter instantly opens it.
        console.log("Dext Receiver: Triggering search box open...");
        
        // Send a dummy keydown ('A') to the document body to force the Symbol Search popup
        const event = new KeyboardEvent('keydown', {
            key: 'a', code: 'KeyA', keyCode: 65, which: 65, bubbles: true, cancelable: true
        });
        document.body.dispatchEvent(event);
        
        // Give the popup 200ms to mount to the DOM
        setTimeout(() => {
            searchInput = document.querySelector('input[data-role="search"]');
            if (searchInput) {
                injectTickerToSearchBox(searchInput, ticker);
            } else {
                console.warn("Dext Receiver: Force-open failed. Search box still not in DOM.");
            }
        }, 200);
    }
}

// Polling Loop against Local API
setInterval(() => {
    fetch("http://localhost:8001/ticker")
        .then(response => response.json())
        .then(data => {
            const activeSymbol = data.active_symbol;
            if (activeSymbol && activeSymbol !== lastTicker) {
                lastTicker = activeSymbol;
                syncDextUI(lastTicker);
            }
        })
        .catch(err => {
            // backend offline, skip
        });
}, 1000);
