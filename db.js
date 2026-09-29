const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database('./game.db');

// Set up database tables if they don't exist yet
db.serialize(() => {
    // Accounts table
    db.run(`
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    `);

    // Player data table
    db.run(`
        CREATE TABLE IF NOT EXISTS player_data (
            user_id INTEGER PRIMARY KEY,
            x REAL DEFAULT 0,
            y REAL DEFAULT 0,
            z REAL DEFAULT 0,
            money INTEGER DEFAULT 100,
            inventory TEXT DEFAULT '{"iron": 0, "copper": 0}',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    `);
});

module.exports = db;
