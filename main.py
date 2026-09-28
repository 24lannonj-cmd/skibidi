import asyncio
import json
import random
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Infinite Synced Space Sandbox 3D</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        * { margin: 0; padding: 0; }
        body { 
            background: #000; 
            color: #fff; 
            font-family: monospace; 
            overflow: hidden; 
        }
        canvas { display: block; }
        #ui { 
            position: absolute; 
            top: 15px; 
            left: 15px; 
            background: rgba(10,15,30,0.9); 
            padding: 15px; 
            border: 1px solid #00ffff44; 
            border-radius: 8px; 
            box-shadow: 0 0 15px rgba(0,255,255,0.2);
            font-size: 13px;
            z-index: 10;
        }
        #ui h3 { margin-bottom: 10px; color: #00ffff; text-shadow: 0 0 8px #00ffff; }
        #ui p { margin: 4px 0; }
        .stat { color: #00ff88; font-weight: bold; }
        
        #nav-arrow {
            position: absolute;
            width: 0;
            height: 0;
            border-left: 12px solid transparent;
            border-right: 12px solid transparent;
            border-bottom: 24px solid #00ffff;
            filter: drop-shadow(0 0 8px #00ffff);
            pointer-events: none;
            z-index: 20;
            transform-origin: 50% 50%;
            display: none;
        }
        #nav-text {
            position: absolute;
            color: #00ffff;
            font-size: 11px;
            font-weight: bold;
            text-shadow: 0 0 5px #00ffff;
            pointer-events: none;
            z-index: 20;
            white-space: nowrap;
            display: none;
        }
        
        #debug-log {
            position: fixed;
            top: 10px;
            right: 10px;
            width: 350px;
            max-height: 100px;
            overflow-y: auto;
            background: rgba(0,0,0,0.9);
            color: #ff5555;
            font-size: 11px;
            padding: 8px;
            border-radius: 5px;
            z-index: 99999;
            pointer-events: none;
            border: 1px solid #ff5555;
        }
    </style>
</head>
<body>
    <div id="debug-log"><strong>Status:</strong> Initializing...</div>
    
    <div id="ui">
        <h3>⚡ Flight Deck</h3>
        <p>Pos: <span class="stat" id="pos-x">0</span> / <span class="stat" id="pos-y">0</span> / <span class="stat" id="pos-z">0</span></p>
        <p>Speed: <span class="stat" id="speed">0</span> m/s</p>
        <p>Players: <span class="stat" id="player-count">0</span></p>
        <p>Planets: <span class="stat" id="planet-count">0</span></p>
        <p>Target: <span class="stat" id="nearest-dist">None</span></p>
        <p style="margin-top: 10px; color: #aaa; font-size: 11px;">
            WASD/Arrows: Pitch/Yaw | Q/E: Roll<br>
            Shift: Boost | S: Brake / Reverse
        </p>
    </div>

    <div id="nav-arrow"></div>
    <div id="nav-text">TARGET</div>

    <script>
        // Logging Utility
        const debugLog = document.getElementById('debug-log');
        function log(msg) {
            debugLog.innerHTML += `<br>${msg}`;
            debugLog.scrollTop = debugLog.scrollHeight;
        }

        window.onerror = (msg, url, line) => {
            log(`❌ Err: ${msg}`);
            console.error(msg, url, line);
        };

        // ==========================================================================
        // THREE.JS SCENE SETUP
        // ==========================================================================
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.000002);
        scene.background = new THREE.Color(0x010105);
        
        const camera = new THREE.PerspectiveCamera(
            60, 
            window.innerWidth / window.innerHeight, 
            0.1, 
            2000000
        );
        
        const renderer = new THREE.WebGLRenderer({ 
            antialias: true, 
            powerPreference: "high-performance"
        });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        document.body.appendChild(renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);
        
        const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
        sunLight.position.set(100000, 100000, 100000);
        scene.add(sunLight);

        // Starfield Background
        const starsGeo = new THREE.BufferGeometry();
        const starCount = 5000;
        const starPos = new Float32Array(starCount * 3);
        for(let i=0; i<starCount*3; i+=3) {
            starPos[i] = (Math.random() - 0.5) * 1000000;
            starPos[i+1] = (Math.random() - 0.5) * 1000000;
            starPos[i+2] = (Math.random() - 0.5) * 1000000;
        }
        starsGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
        const starsMat = new THREE.PointsMaterial({color: 0xffffff, size: 2, sizeAttenuation: false});
        const starField = new THREE.Points(starsGeo, starsMat);
        scene.add(starField);

        // ==========================================================================
        // CONSTANTS & STATE
        // ==========================================================================
        const GLOBAL_SEED = 987654321;
        const CLUSTER_GRID_SIZE = 200000;
        const MIN_SPAWN_DIST = 100000; // 100k units away from 0,0,0
        const planetObjects = {};
        const shipMeshes = {};
        const keys = {};
        
        let localPlayerId = null;
        let gameState = { players: {} };

        // Physics State
        let localPos = new THREE.Vector3(0, 0, 0);
        let localVel = new THREE.Vector3(0, 0, 0);
        let localRot = new THREE.Quaternion();
        
        // ==========================================================================
        // PROCEDURAL GENERATION (SEEDED RNG)
        // ==========================================================================
        function seededRandom(seed) {
            let x = Math.sin(seed++) * 10000;
            return x - Math.floor(x);
        }

        function createPlanetCluster(cx, cy, cz) {
            const key = `${cx}_${cy}_${cz}`;
            if (planetObjects[key]) return;

            // Enforce minimum 100k distance check from origin in all 3 directions or overall length
            const distFromOrigin = Math.sqrt(cx*cx + cy*cy + cz*cz);
            if (distFromOrigin < MIN_SPAWN_DIST && Math.abs(cx) < MIN_SPAWN_DIST && Math.abs(cy) < MIN_SPAWN_DIST && Math.abs(cz) < MIN_SPAWN_DIST) {
                return; 
            }

            let seed = GLOBAL_SEED + cx * 73856093 ^ cy * 19349663 ^ cz * 83492791;
            const group = new THREE.Group();
            
            // Generate deterministic planets within this cell
            const count = Math.floor(seededRandom(seed++) * 3) + 2;
            const planetGeom = new THREE.SphereGeometry(1, 32, 32);

            for(let i = 0; i < count; i++) {
                const px = cx + (seededRandom(seed++) - 0.5) * CLUSTER_GRID_SIZE * 0.8;
                const py = cy + (seededRandom(seed++) - 0.5) * CLUSTER_GRID_SIZE * 0.8;
                const pz = cz + (seededRandom(seed++) - 0.5) * CLUSTER_GRID_SIZE * 0.8;
                const radius = seededRandom(seed++) * 3000 + 1000;

                const color = new THREE.Color().setHSL(seededRandom(seed++), 0.7, 0.5);
                const mat = new THREE.MeshStandardMaterial({ 
                    color: color, 
                    roughness: 0.8,
                    metalness: 0.2
                });

                const planet = new THREE.Mesh(planetGeom, mat);
                planet.position.set(px, py, pz);
                planet.scale.setScalar(radius);
                group.add(planet);
            }

            scene.add(group);
            planetObjects[key] = group;
        }

        function updateProceduralUniverse() {
            const currentCellX = Math.floor(localPos.x / CLUSTER_GRID_SIZE) * CLUSTER_GRID_SIZE;
            const currentCellY = Math.floor(localPos.y / CLUSTER_GRID_SIZE) * CLUSTER_GRID_SIZE;
            const currentCellZ = Math.floor(localPos.z / CLUSTER_GRID_SIZE) * CLUSTER_GRID_SIZE;

            const radius = 1;
            for(let x = -radius; x <= radius; x++) {
                for(let y = -radius; y <= radius; y++) {
                    for(let z = -radius; z <= radius; z++) {
                        createPlanetCluster(
                            currentCellX + x * CLUSTER_GRID_SIZE,
                            currentCellY + y * CLUSTER_GRID_SIZE,
                            currentCellZ + z * CLUSTER_GRID_SIZE
                        );
                    }
                }
            }
        }

        // ==========================================================================
        // SHIP CREATION (PURE PROCEDURAL CONE)
        // ==========================================================================
        function createConeShipMesh(colorHex = 0x00ffff) {
            const shipGroup = new THREE.Group();

            // Main Cone Body pointing along local -Z
            const geom = new THREE.ConeGeometry(8, 25, 16);
            geom.rotateX(-Math.PI / 2); // Align point forward to -Z
            
            const mat = new THREE.MeshStandardMaterial({
                color: colorHex,
                metalness: 0.8,
                roughness: 0.2,
                emissive: 0x002244
            });

            const cone = new THREE.Mesh(geom, mat);
            shipGroup.add(cone);

            // Engine Thruster Glow
            const engineGeom = new THREE.CylinderGeometry(3, 1, 4, 12);
            engineGeom.rotateX(-Math.PI / 2);
            const engineMat = new THREE.MeshBasicMaterial({ color: 0x00ffff });
            const engine = new THREE.Mesh(engineGeom, engineMat);
            engine.position.set(0, 0, 12);
            shipGroup.add(engine);

            return shipGroup;
        }

        const localShipMesh = createConeShipMesh(0x00ff88);
        scene.add(localShipMesh);

        // ==========================================================================
        // INPUT & PHYSICS CONTROLS
        // ==========================================================================
        window.addEventListener('keydown', (e) => { keys[e.code] = true; });
        window.addEventListener('keyup', (e) => { keys[e.code] = false; });

        function processPhysics(dt) {
            const turnSpeed = 1.5 * dt;
            const moveSpeed = keys['ShiftLeft'] || keys['ShiftRight'] ? 2500 : 800;

            // Rotation vectors
            const rotDelta = new THREE.Quaternion();
            let pitch = 0, yaw = 0, roll = 0;

            if (keys['KeyW'] || keys['ArrowUp']) pitch -= turnSpeed;
            if (keys['KeyS'] || keys['ArrowDown']) pitch += turnSpeed;
            if (keys['KeyA'] || keys['ArrowLeft']) yaw += turnSpeed;
            if (keys['KeyD'] || keys['ArrowRight']) yaw -= turnSpeed;
            if (keys['KeyQ']) roll += turnSpeed;
            if (keys['KeyE']) roll -= turnSpeed;

            const euler = new THREE.Euler(pitch, yaw, roll, 'YXZ');
            rotDelta.setFromEuler(euler);
            localRot.multiply(rotDelta);
            localShipMesh.quaternion.copy(localRot);

            // Forward Direction
            const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(localRot);
            
            // Propulsion
            if (keys['KeyW'] || keys['ArrowUp'] || keys['ShiftLeft']) {
                localVel.addScaledVector(forward, moveSpeed * dt);
            }
            if (keys['KeyS'] || keys['ArrowDown']) {
                localVel.addScaledVector(forward, -moveSpeed * 0.5 * dt);
            }

            // Apply Friction / Drag
            localVel.multiplyScalar(0.985);
            localPos.addScaledVector(localVel, dt);

            localShipMesh.position.copy(localPos);

            // Dynamic Third-Person Camera Tracking
            const camOffset = new THREE.Vector3(0, 12, 45).applyQuaternion(localRot);
            camera.position.copy(localPos).add(camOffset);
            camera.quaternion.copy(localRot);
        }

        // ==========================================================================
        // WEBSOCKET MULTIPLAYER & SYNC
        // ==========================================================================
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onopen = () => {
            log("🟢 Connected to Server");
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'init') {
                localPlayerId = data.id;
                log(`⚡ Player ID Assigned: ${localPlayerId}`);
            } else if (data.type === 'state') {
                gameState = data.state;
                updateOtherPlayers();
            }
        };

        ws.onclose = () => log("🔴 Connection Closed");
        ws.onerror = (err) => log("❌ WS Error");

        function updateOtherPlayers() {
            const activeIds = new Set();

            for (const id in gameState.players) {
                if (id === localPlayerId) continue;
                activeIds.add(id);

                const pData = gameState.players[id];
                if (!shipMeshes[id]) {
                    const otherMesh = createConeShipMesh(0xff0055);
                    scene.add(otherMesh);
                    shipMeshes[id] = otherMesh;
                }

                shipMeshes[id].position.set(pData.pos.x, pData.pos.y, pData.pos.z);
                shipMeshes[id].quaternion.set(pData.rot.x, pData.rot.y, pData.rot.z, pData.rot.w);
            }

            // Clean up disconnected players
            for (const id in shipMeshes) {
                if (!activeIds.has(id)) {
                    scene.remove(shipMeshes[id]);
                    delete shipMeshes[id];
                }
            }
        }

        function sendNetworkState() {
            if (ws.readyState === WebSocket.OPEN && localPlayerId) {
                ws.send(JSON.stringify({
                    pos: { x: localPos.x, y: localPos.y, z: localPos.z },
                    rot: { x: localRot.x, y: localRot.y, z: localRot.z, w: localRot.w }
                }));
            }
        }

        // Update UI
        function updateUI() {
            document.getElementById('pos-x').innerText = Math.round(localPos.x);
            document.getElementById('pos-y').innerText = Math.round(localPos.y);
            document.getElementById('pos-z').innerText = Math.round(localPos.z);
            document.getElementById('speed').innerText = Math.round(localVel.length());
            document.getElementById('player-count').innerText = Object.keys(gameState.players).length || 1;
            document.getElementById('planet-count').innerText = Object.keys(planetObjects).length * 3;
        }

        // ==========================================================================
        // GAME LOOP
        // ==========================================================================
        let lastTime = performance.now();
        let netTimer = 0;

        function animate() {
            requestAnimationFrame(animate);

            const now = performance.now();
            const dt = Math.min((now - lastTime) / 1000, 0.1);
            lastTime = now;

            processPhysics(dt);
            updateProceduralUniverse();
            updateUI();

            netTimer += dt;
            if (netTimer >= 0.05) { // 20 Hz sync rate
                sendNetworkState();
                netTimer = 0;
            }

            renderer.render(scene, camera);
        }

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        animate();
    </script>
</body>
</html>
"""

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        if player_id in game_state["players"]:
            del game_state["players"][player_id]

    async def broadcast_state(self):
        payload = json.dumps({"type": "state", "players": game_state["players"]})
        for connection in list(self.active_connections.values()):
            try:
                await connection.send_text(payload)
            except Exception:
                pass

manager = ConnectionManager()
game_state = {"players": {}}

@app.get("/")
async def get():
    return HTMLResponse(HTML_CLIENT)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    import random
    player_id = f"player_{random.randint(1000, 9999)}"
    await manager.connect(websocket, player_id)
    
    game_state["players"][player_id] = {
        "x": 0, "y": 0, "z": 0, "angle": 0, "vx": 0, "vy": 0, "vz": 0
    }
    
    await websocket.send_text(json.dumps({
        "type": "init",
        "id": player_id,
        "state": game_state
    }))
    
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("type") == "sync":
                player = game_state["players"].get(player_id)
                if player:
                    player["x"] = payload.get("x", player["x"])
                    player["y"] = payload.get("y", player["y"])
                    player["z"] = payload.get("z", player["z"])
                    player["angle"] = payload.get("angle", player["angle"])
                    player["vx"] = payload.get("vx", player["vx"])
                    player["vy"] = payload.get("vy", player["vy"])
                    player["vz"] = payload.get("vz", player.get("vz", 0))
    except WebSocketDisconnect:
        manager.disconnect(player_id)

async def game_loop():
    while True:
        await manager.broadcast_state()
        await asyncio.sleep(1 / 30)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_loop())
