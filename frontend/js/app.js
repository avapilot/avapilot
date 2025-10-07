document.addEventListener('DOMContentLoaded', function() {
    // --- CONSTANTS ---
    const FUJI_CHAIN_ID = '0xa869'; // 43113 in hex
    // --- UPDATE THIS LINE ---
    const API_GATEWAY_URL = 'https://avapilot-orchestrator-82975436299.europe-west2.run.app/chat';

    // --- ELEMENT SELECTORS ---
    const connectWalletBtn = document.getElementById('connectWalletBtn');
    const submitBtn = document.getElementById('submitBtn');
    const commandInput = document.getElementById('commandInput');
    const mainStatus = document.getElementById('mainStatus');
    const statusDot = document.getElementById('statusDot');

    // --- STATE ---
    let signer = null;

    // --- INITIALIZATION ---
    if (window.ethereum) {
        checkInitialConnection();
        window.ethereum.on('accountsChanged', () => window.location.reload());
        window.ethereum.on('chainChanged', () => window.location.reload());
    }

    // --- EVENT LISTENERS ---
    connectWalletBtn.addEventListener('click', handleConnect);
    submitBtn.addEventListener('click', handleCommand);

    // --- FUNCTIONS ---

    async function checkInitialConnection() {
        try {
            const accounts = await window.ethereum.request({ method: 'eth_accounts' });
            if (accounts.length > 0) {
                await handleConnect(true);
            }
        } catch (error) {
            console.error("Silent connection check failed:", error);
        }
    }

    async function handleConnect(isSilent = false) {
        if (!window.ethereum) {
            setStatus('Wallet not found. Please install a browser extension.');
            return;
        }

        try {
            const provider = new ethers.providers.Web3Provider(window.ethereum);
            await provider.send("eth_requestAccounts", []);
            const currentSigner = provider.getSigner();
            const address = await currentSigner.getAddress();
            const network = await provider.getNetwork();

            if (network.chainId !== parseInt(FUJI_CHAIN_ID, 16)) {
                if (!isSilent) setStatus('Wrong network. Please switch to Fuji Testnet.');
                updateUI(false);
                return;
            }

            signer = currentSigner;
            updateUI(true, address);

        } catch (error) {
            console.error("Connection failed:", error);
            if (!isSilent) setStatus('Connection rejected or failed.');
            updateUI(false);
        }
    }

    function updateUI(isConnected, address = '') {
        if (isConnected) {
            statusDot.className = 'dot green';
            connectWalletBtn.textContent = `${address.substring(0, 6)}...${address.substring(38)}`;
            connectWalletBtn.classList.add('connected');
            submitBtn.disabled = false;
            setStatus('Ready for your command.');
        } else {
            statusDot.className = 'dot red';
            connectWalletBtn.textContent = 'Connect Wallet';
            connectWalletBtn.classList.remove('connected');
            submitBtn.disabled = true;
            setStatus('Please connect your wallet to begin.');
        }
    }

    async function handleCommand() {
        if (!signer) {
            setStatus('Please connect your wallet first.');
            return;
        }

        const commandText = commandInput.value;
        if (!commandText) {
            setStatus('Please enter a command.');
            return;
        }

        setStatus('Sending command to agent...');

        try {
            // --- THIS IS THE NEW PART ---
            // 1. Call the live backend API
            const response = await fetch(API_GATEWAY_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: commandText,
                    context: { url: window.location.href } 
                })
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const apiResponse = await response.json();

            // 2. Check the response and trigger the wallet
            if (apiResponse.response_type === 'transaction') {
                setStatus('Transaction ready. Please sign in your wallet.');
                const tx = await signer.sendTransaction(apiResponse.payload.transaction);
                setStatus('Transaction sent. Waiting for confirmation...');
                await tx.wait();
                setStatus('Transaction sent successfully!');
            } else {
                // Handle text responses later
                setStatus(apiResponse.payload.message);
            }

        } catch (error) {
            console.error('Error:', error);
            if (error.code === 4001) {
                setStatus('Transaction rejected by user.');
            } else {
                setStatus(`Error: ${error.message}`);
            }
        }
    }

    function setStatus(message) {
        mainStatus.textContent = message;
    }
});