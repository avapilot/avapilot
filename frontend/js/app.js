document.addEventListener('DOMContentLoaded', function() {
    // Wait for both DOM and ethers to be ready
    window.addEventListener('load', function() {
        // Check if ethers is available
        if (typeof ethers === 'undefined') {
            console.error('Ethers.js failed to load');
            document.getElementById('statusContainer').textContent = 'Error: Wallet library failed to load';
            return;
        }

        // --- CONSTANTS & SELECTORS ---
        const FUJI_CHAIN_ID = '0xa869';
        const API_URL = 'https://avapilot-orchestrator-82975436299.europe-west2.run.app/chat';

        const connectWalletBtn = document.getElementById('connectWalletBtn');
        const submitBtn = document.getElementById('submitBtn');
        const commandInput = document.getElementById('commandInput');
        const chatHistory = document.getElementById('chatHistory');
        const chatForm = document.getElementById('chatForm');
        const statusContainer = document.getElementById('statusContainer');
        const statusDot = document.getElementById('statusDot');

        let signer = null;

        // --- INITIALIZATION ---
        if (window.ethereum) {
            checkInitialConnection();
            window.ethereum.on('accountsChanged', () => window.location.reload());
            window.ethereum.on('chainChanged', () => window.location.reload());
        } else {
            updateUI(false);
            addMessageToHistory('agent', 'No wallet detected. Please install MetaMask or Core wallet.');
        }

        // --- EVENT LISTENERS ---
        connectWalletBtn.addEventListener('click', handleConnect);
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            handleCommand();
        });

        // --- CORE FUNCTIONS ---
        async function handleCommand() {
            if (!signer) {
                setStatus('Please connect your wallet first.');
                return;
            }
            const commandText = commandInput.value.trim();
            if (!commandText) return;

            addMessageToHistory('user', commandText);
            commandInput.value = '';
            setStatus('Agent is thinking...');
            submitBtn.disabled = true;

            try {
                const response = await fetch(API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: commandText, 
                        context: { url: window.location.href } 
                    })
                });

                if (!response.ok) throw new Error(`API Error: ${response.statusText}`);

                const apiResponse = await response.json();

                if (apiResponse.response_type === 'transaction') {
                    addMessageToHistory('agent', 'Transaction ready. Please check your wallet to sign.');
                    setStatus('Waiting for wallet signature...');
                    await initiateTransaction(apiResponse.payload.transaction);
                    addMessageToHistory('agent', 'Transaction sent successfully!');
                } else {
                    addMessageToHistory('agent', apiResponse.payload.message);
                }

            } catch (error) {
                console.error('Error:', error);
                const errorMessage = (error.code === 4001) ? 'Action rejected by user.' : `Error: ${error.message}`;
                addMessageToHistory('agent', `Sorry, an error occurred: ${errorMessage}`);
            } finally {
                setStatus('');
                submitBtn.disabled = false;
            }
        }

        // --- HELPER FUNCTIONS ---
        function addMessageToHistory(sender, text) {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message', `${sender}-message`);
            messageDiv.textContent = text;
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        function setStatus(message) {
            statusContainer.textContent = message;
        }

        // --- WALLET FUNCTIONS ---
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
                if (!isSilent) addMessageToHistory('agent', 'Wallet not found. Please install MetaMask or Core wallet.');
                return;
            }

            try {
                const provider = new ethers.providers.Web3Provider(window.ethereum);
                await provider.send("eth_requestAccounts", []);
                const currentSigner = provider.getSigner();
                const address = await currentSigner.getAddress();
                const network = await provider.getNetwork();

                if (network.chainId !== parseInt(FUJI_CHAIN_ID, 16)) {
                    if (!isSilent) {
                        addMessageToHistory('agent', 'Wrong network. Please switch to Avalanche Fuji Testnet.');
                        setStatus('Please switch to Fuji Testnet');
                    }
                    updateUI(false);
                    return;
                }

                signer = currentSigner;
                updateUI(true, address);
                if (!isSilent) {
                    addMessageToHistory('agent', `Connected! Welcome to AvaPilot. How can I help you today?`);
                }

            } catch (error) {
                console.error("Connection failed:", error);
                if (!isSilent) {
                    addMessageToHistory('agent', 'Connection rejected or failed.');
                    setStatus('Connection failed');
                }
                updateUI(false);
            }
        }

        function updateUI(isConnected, address = '') {
            if (isConnected) {
                statusDot.className = 'dot green';
                connectWalletBtn.textContent = `${address.substring(0, 6)}...${address.substring(38)}`;
                connectWalletBtn.classList.add('connected');
                submitBtn.disabled = false;
                setStatus('');
            } else {
                statusDot.className = 'dot red';
                connectWalletBtn.textContent = 'Connect Wallet';
                connectWalletBtn.classList.remove('connected');
                submitBtn.disabled = true;
                setStatus('Please connect your wallet to begin.');
            }
        }

        async function initiateTransaction(txObject) {
            setStatus('Sending transaction...');
            const tx = await signer.sendTransaction(txObject);
            setStatus('Transaction sent. Waiting for confirmation...');
            await tx.wait();
            setStatus('Transaction confirmed!');
        }
    });
});