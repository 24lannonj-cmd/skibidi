const express = require('express');
const bcrypt = require('bcrypt');
const db = require('./db');

const app = express();
app.use(express.json());

// REGISTER
app.post('/api/register', async (req, res) => {
    const { username, password } = req.body;

    if (!username || !password) {
        return res.status(400).json({ error: 'Missing username or password' });
    }

    try {
        // Hash password before saving
        const hashedPassword = await bcrypt.hash(password, 10);

        // Insert new user
        db.run('INSERT INTO users (username, password) VALUES (?, ?)', [username, hashedPassword], function(err) {
            if (err) {
                return res.status(400).json({ error: 'Username already taken' });
            }

            const userId = this.lastID;

            // Create default save data for new user
            db.run('INSERT INTO player_data (user_id) VALUES (?)', [userId], (err) => {
                if (err) return res.status(500).json({ error: 'Failed to create player save' });
                
                res.json({ success: true, userId: userId });
            });
        });
    } catch (err) {
        res.status(500).json({ error: 'Server error during registration' });
    }
});

// LOGIN
app.post('/api/login', (req, res) => {
    const { username, password } = req.body;

    db.get('SELECT * FROM users WHERE username = ?', [username], async (err, user) => {
        if (err || !user) {
            return res.status(400).json({ error: 'User not found' });
        }

        // Compare hashed password
        const validPassword = await bcrypt.compare(password, user.password);
        if (!validPassword) {
            return res.status(401).json({ error: 'Invalid password' });
        }

        // Fetch saved player data
        db.get('SELECT * FROM player_data WHERE user_id = ?', [user.id], (err, playerData) => {
            if (err) return res.status(500).json({ error: 'Failed to load save data' });

            res.json({
                message: 'Login successful',
                userId: user.id,
                username: user.username,
                saveData: {
                    position: { x: playerData.x, y: playerData.y, z: playerData.z },
                    money: playerData.money,
                    inventory: JSON.parse(playerData.inventory)
                }
            });
        });
    });
});

// SAVE DATA
app.post('/api/save', (req, res) => {
    const { userId, position, money, inventory } = req.body;

    if (!userId) return res.status(400).json({ error: 'Missing userId' });

    const inventoryStr = JSON.stringify(inventory || {});

    const query = `
        UPDATE player_data 
        SET x = ?, y = ?, z = ?, money = ?, inventory = ? 
        WHERE user_id = ?
    `;

    db.run(query, [position.x, position.y, position.z, money, inventoryStr, userId], function(err) {
        if (err) {
            console.error('Error saving data:', err);
            return res.status(500).json({ error: 'Failed to save data' });
        }
        res.json({ success: true, message: 'Game saved successfully' });
    });
});

app.listen(3000, () => {
    console.log('Server running on http://localhost:3000');
});
