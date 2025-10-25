/**
 * AvaPilot Widget Loader
 * Embeds chat bubble and iframe into any website
 */
(function() {
  'use strict';
  
  // Get configuration from script tag
  const scriptTag = document.currentScript;
  const allowedContract = scriptTag.getAttribute('data-contract');
  const apiKey = scriptTag.getAttribute('data-api-key') || 'avapilot_free_alpha';  // ← Default to free tier
  const primaryColor = scriptTag.getAttribute('data-color') || '#667eea';
  const position = scriptTag.getAttribute('data-position') || 'bottom-right';
  
  // Auto-detect base URL
  const WIDGET_BASE_URL = scriptTag.src.includes('localhost') 
    ? 'http://localhost:8080'
    : 'https://avapilot-orchestrator-82975436299.us-central1.run.app';
  
  console.log('[AvaPilot] Base URL:', WIDGET_BASE_URL);
  
  // Validate required attributes
  if (!allowedContract) {
    console.error('[AvaPilot] ERROR: data-contract attribute is required');
    return;
  }
  
  if (!apiKey || apiKey === 'avapilot_free_alpha') {
    console.log('[AvaPilot] Using free tier (20 req/min, 500 req/day)');
  } else {
    console.log('[AvaPilot] API Key:', '***' + apiKey.slice(-4));
  }
  
  // Create chat bubble
  const bubble = document.createElement('div');
  bubble.id = 'avapilot-bubble';
  bubble.innerHTML = '💬';
  bubble.style.cssText = `
    position: fixed;
    ${position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
    ${position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${primaryColor} 0%, #764ba2 100%);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 999999;
    transition: transform 0.2s;
  `;
  
  bubble.onmouseenter = () => bubble.style.transform = 'scale(1.1)';
  bubble.onmouseleave = () => bubble.style.transform = 'scale(1)';
  
  // Create iframe container
  const iframe = document.createElement('iframe');
  iframe.id = 'avapilot-widget';
  
  // Build iframe URL with parameters
  const WIDGET_CDN_URL = scriptTag.src.includes('localhost')
    ? 'http://localhost:8080'
    : 'https://storage.googleapis.com/avapilot-cdn';

  const iframeUrl = new URL(`${WIDGET_CDN_URL}/widget-chat.html`);
  iframeUrl.searchParams.set('contract', allowedContract);
  iframeUrl.searchParams.set('apiKey', apiKey || '');
  iframeUrl.searchParams.set('color', primaryColor);
  iframe.src = iframeUrl.toString();
  
  console.log('[AvaPilot] Iframe URL:', iframe.src);
  
  iframe.style.cssText = `
    position: fixed;
    ${position.includes('bottom') ? 'bottom: 90px;' : 'top: 90px;'}
    ${position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
    width: 400px;
    height: 600px;
    border: none;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    z-index: 999998;
    display: none;
  `;
  
  // Toggle chat visibility
  let isOpen = false;
  bubble.onclick = () => {
    isOpen = !isOpen;
    iframe.style.display = isOpen ? 'block' : 'none';
    bubble.innerHTML = isOpen ? '✕' : '💬';
  };
  
  // Handle messages from iframe
  window.addEventListener('message', (event) => {
    // Only accept messages from our iframe
    if (event.source !== iframe.contentWindow) return;
    
    if (event.data.type === 'AVAPILOT_WALLET_REQUEST') {
      // ✅ FIX: Check if parent page has wallet connection
      if (typeof window.ethereum !== 'undefined') {
        // First check if parent page already has connection
        window.ethereum.request({ method: 'eth_accounts' })
          .then(accounts => {
            if (accounts && accounts.length > 0) {
              // Parent has connection, send to iframe
              console.log('[AvaPilot] Found existing wallet connection:', accounts[0]);
              iframe.contentWindow.postMessage({
                type: 'AVAPILOT_WALLET_CONNECTED',
                address: accounts[0]
              }, '*');
            } else {
              // No connection yet - prompt user to connect
              console.log('[AvaPilot] No wallet connected, requesting connection...');
              return window.ethereum.request({ method: 'eth_requestAccounts' });
            }
          })
          .then(accounts => {
            if (accounts && accounts.length > 0) {
              console.log('[AvaPilot] Wallet connected:', accounts[0]);
              iframe.contentWindow.postMessage({
                type: 'AVAPILOT_WALLET_CONNECTED',
                address: accounts[0]
              }, '*');
            }
          })
          .catch(err => {
            if (err.code === 4001) {
              // User rejected
              console.log('[AvaPilot] User rejected wallet connection');
              iframe.contentWindow.postMessage({
                type: 'AVAPILOT_WALLET_NOT_CONNECTED',
                error: 'Please connect your wallet to continue'
              }, '*');
            } else {
              console.error('[AvaPilot] Wallet error:', err);
              iframe.contentWindow.postMessage({
                type: 'AVAPILOT_WALLET_ERROR',
                error: err.message || 'Failed to detect wallet'
              }, '*');
            }
          });
      } else {
        iframe.contentWindow.postMessage({
          type: 'AVAPILOT_WALLET_ERROR',
          error: 'No wallet detected'
        }, '*');
      }
    }

    // Handle transaction execution request
    if (event.data.type === 'AVAPILOT_EXECUTE_TX') {
      const tx = event.data.transaction;
      
      // CRITICAL: Validate transaction target matches allowed contract
      if (tx.to.toLowerCase() !== allowedContract.toLowerCase()) {
        alert(`🚨 Security Alert: Transaction blocked!\n\nTarget: ${tx.to}\nAllowed: ${allowedContract}\n\nThis widget is restricted to specific contracts.`);
        iframe.contentWindow.postMessage({
          type: 'AVAPILOT_TX_BLOCKED',
          reason: 'Contract not allowed'
        }, '*');
        return;
      }
      
      // ✅ FIX: Get user's address and add to transaction
      if (typeof window.ethereum !== 'undefined') {
        window.ethereum.request({ method: 'eth_accounts' })
          .then(accounts => {
            if (!accounts || accounts.length === 0) {
              throw new Error('No wallet connected');
            }
            
            // Add 'from' field if not present
            if (!tx.from) {
              tx.from = accounts[0];
              console.log('[AvaPilot] Added from field:', accounts[0]);
            }
            
            // Now send transaction with 'from' field
            return window.ethereum.request({
              method: 'eth_sendTransaction',
              params: [tx]
            });
          })
          .then(txHash => {
            iframe.contentWindow.postMessage({
              type: 'AVAPILOT_TX_SUCCESS',
              txHash: txHash
            }, '*');
          })
          .catch(err => {
            console.error('[AvaPilot] Transaction error:', err);
            iframe.contentWindow.postMessage({
              type: 'AVAPILOT_TX_ERROR',
              error: err.message
            }, '*');
          });
      }
    }
  });
  
  // Inject into page
  document.body.appendChild(bubble);
  document.body.appendChild(iframe);
  
  console.log(`✅ AvaPilot widget loaded`);
  console.log(`   Scoped to: ${allowedContract}`);
  console.log(`   API Key: ${apiKey ? '***' + apiKey.slice(-4) : 'none'}`);
})();