// Local cache of logged in player state
let currentUser = null;

// Auth functions
async function login(username, password) {
    const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    if (data.userId) {
        currentUser = data;
        console.log("Loaded save state:", currentUser.saveData);
        // Apply position, money, inventory to local game here
    }
    return data;
}

// Save function to call periodically or on logout
async function saveProgress(currentPos, currentMoney, currentInventory) {
    if (!currentUser) return;

    const saveData = {
        userId: currentUser.userId,
        position: currentPos,
        money: currentMoney,
        inventory: currentInventory
    };

    const response = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(saveData)
    });

    const result = await response.json();
    console.log("Save status:", result);
}

// Auto-save every 30 seconds
setInterval(() => {
    if (currentUser) {
        // Replace these with actual game variables
        saveProgress(
            { x: gameState.x, y: gameState.y, z: gameState.z },
            gameState.money,
            gameState.inventory
        );
    }
}, 30000);
