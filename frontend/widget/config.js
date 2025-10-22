// Optional: Global configuration
window.AvaPilotConfig = {
  // Multi-contract support
  contracts: ['0xRouter', '0xStaking'],  // Array of allowed contracts
  
  // Styling
  primaryColor: '#FF6B6B',
  position: 'bottom-left',  // bottom-right, top-left, top-right
  
  // Behavior
  greeting: 'Need help with swaps?',
  autoOpen: false,  // Open widget on page load
  
  // Security
  allowedOrigins: ['traderjoe.xyz', 'pangolin.exchange']
};