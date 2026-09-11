# Run Command:
# uvicorn main:app --host 0.0.0.0 --port $PORT

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# ==============================================================================
# 1. FRONTEND HTML & CSS LAYOUT
# ==============================================================================
HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Space Sandbox 3D</title>
    <style>
        body { 
            margin: 0; 
            background: #000; 
            color: #fff; 
            font-family: monospace; 
            overflow: hidden; 
        }
        #ui { 
            position: absolute; 
            top: 15px; 
            left: 15px; 
            background: rgba(10,15,30,0.85); 
            padding: 15px; 
            border: 1px solid #00ffff44; 
            border-radius: 8px; 
            box-shadow: 0 0 15px rgba(0,255,255,0.15);
            pointer-events: none;
            z-index: 10;
        }
        .stat { color: #00ffff; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="ui">
        <h3 style="margin-top: 0; color: #00ffff; text-shadow: 0 0 8px #00ffff;">3D Flight Deck</h3>
        <p>Position: X <span id="pos-x" class="stat">0</span> | Z <span id="pos-z" class="stat">0</span> | Alt <span id="pos-y" class="stat">0</span></p>
        <p>Speed: <span id="speed" class="stat">0</span> m/s</p>
        <p>Pilots Online: <span id="player-count" class="stat">0</span></p>
        <p>Controls: WASD (Forward/Turn), X/Z (Ascend/Descend)</p>
    </div>

    <script>
        // ==============================================================================
        // 2. THREE.JS SCENE SETUP & LIGHTING
        // ==============================================================================
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.0005);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 15000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        document.body.appendChild(renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x333355, 1.5);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 2.0);
        sunLight.position.set(500, 1000, 500);
        scene.add(sunLight);

        // Deterministic Pseudo-Random Generator (Ensures identical universe across all clients)
        function seededRandom(seed) {
            const x = Math.sin(seed) * 10000;
            return x - Math.floor(x);
        }

        // ==============================================================================
        // GRID-BASED STAR CHUNK MANAGER (SYNCED VIA SEED)
        // ==============================================================================
        const CHUNK_SIZE = 1500;
        const DRAW_RADIUS = 2;
        const STARS_PER_CHUNK = 250;
        const starChunks = {};

        function createStarChunk(cx, cy, cz) {
            const key = `${cx},${cy},${cz}`;
            if (starChunks[key]) return;

            const starGeo = new THREE.BufferGeometry();
            const starCoords = [];
            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791);

            for (let i = 0; i < STARS_PER_CHUNK; i++) {
                seed++;
                const rx = seededRandom(seed) * CHUNK_SIZE + cx * CHUNK_SIZE;
                seed++;
                const ry = seededRandom(seed) * CHUNK_SIZE + cy * CHUNK_SIZE;
                seed++;
                const rz = seededRandom(seed) * CHUNK_SIZE + cz * CHUNK_SIZE;
                starCoords.push(rx, ry, rz);
            }

            starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starCoords, 3));
            const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 1.2 });
            const chunkMesh = new THREE.Points(starGeo, starMat);
            
            scene.add(chunkMesh);
            starChunks[key] = chunkMesh;
        }

        function updateStarChunks(playerX, playerY, playerZ) {
            const currentChunkX = Math.floor(playerX / CHUNK_SIZE);
            const currentChunkY = Math.floor(playerY / CHUNK_SIZE);
            const currentChunkZ = Math.floor(playerZ / CHUNK_SIZE);

            const activeKeys = new Set();

            for (let x = -DRAW_RADIUS; x <= DRAW_RADIUS; x++) {
                for (let y = -DRAW_RADIUS; y <= DRAW_RADIUS; y++) {
                    for (let z = -DRAW_RADIUS; z <= DRAW_RADIUS; z++) {
                        const cx = currentChunkX + x;
                        const cy = currentChunkY + y;
                        const cz = currentChunkZ + z;
                        const key = `${cx},${cy},${cz}`;
                        
                        activeKeys.add(key);
                        createStarChunk(cx, cy, cz);
                    }
                }
            }

            for (let key in starChunks) {
                if (!activeKeys.has(key)) {
                    scene.remove(starChunks[key]);
                    starChunks[key].geometry.dispose();
                    starChunks[key].material.dispose();
                    delete starChunks[key];
                }
            }
        }

        // ==============================================================================
        // PLANETS (DETERMINISTICALLY SYNCED ACROSS MULTIPLAYER)
        // ==============================================================================
        const planetRadius = 500;
        const planetGeo = new THREE.SphereGeometry(planetRadius, 32, 32); 
        const planetMat = new THREE.MeshStandardMaterial({ color: 0xde071c, roughness: 0.8 });
        const planetCount = 10;
        const planetData = [];

        const planetMesh = new THREE.InstancedMesh(planetGeo, planetMat, planetCount);
        const dummy = new THREE.Object3D();

        let planetSeed = 12345; // Constant seed for global sync
        for (let i = 0; i < planetCount; i++) {
            planetSeed++;
            const px = (seededRandom(planetSeed) - 0.5) * 10000;
            planetSeed++;
            const py = (seededRandom(planetSeed) - 0.5) * 10000;
            planetSeed++;
            const pz = (seededRandom(planetSeed) - 0.5) * 10000;

            dummy.position.set(px, py, pz);
            dummy.updateMatrix();
            planetMesh.setMatrixAt(i, dummy.matrix);

            planetData.push({ x: px, y: py, z: pz, radius: planetRadius });
        }

        scene.add(planetMesh);

        // Dynamic Line Pointing to Origin (0,0,0)
        const lineGeo = new THREE.BufferGeometry();
        const linePositions = new Float32Array(6); 
        lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
        const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.8, transparent: true });
        const originLine = new THREE.Line(lineGeo, lineMat);
        originLine.frustumCulled = false;
        scene.add(originLine);

        // Particle System for Exhaust Trail
        const trailParticles = [];
        const particleGeo = new THREE.SphereGeometry(1.2, 6, 6);
        const particleMat = new THREE.MeshBasicMaterial({ color: 0xff6600, transparent: true, opacity: 0.8 });

        function spawnTrailParticle(x, y, z, angle) {
            const particle = new THREE.Mesh(particleGeo, particleMat.clone());
            particle.position.set(
                x - Math.sin(angle) * 12 + (Math.random() - 0.5) * 2,
                z + (Math.random() - 0.5) * 2,
                y + Math.cos(angle) * 12 + (Math.random() - 0.5) * 2
            );
            scene.add(particle);
            trailParticles.push({ mesh: particle, life: 1.0 });
        }

        function updateParticles() {
            for (let i = trailParticles.length - 1; i >= 0; i--) {
                const p = trailParticles[i];
                p.life -= 0.04;
                p.mesh.scale.multiplyScalar(0.96);
                p.mesh.material.opacity = p.life;

                if (p.life <= 0) {
                    scene.remove(p.mesh);
                    p.mesh.geometry.dispose();
                    p.mesh.material.dispose();
                    trailParticles.splice(i, 1);
                }
            }
        }

        // ==============================================================================
        // 3. 3D MODEL FACTORIES
        // ==============================================================================
        function createShipMesh(isLocal) {
            const group = new THREE.Group();

            const hullGeo = new THREE.ConeGeometry(8, 24, 4);
            hullGeo.rotateX(-Math.PI / 2);
            const hullMat = new THREE.MeshStandardMaterial({ 
                color: isLocal ? 0x00ff88 : 0xff3344, 
                roughness: 0.3, 
                metalness: 0.8 
            });
            const hull = new THREE.Mesh(hullGeo, hullMat);
            group.add(hull);

            const engineGeo = new THREE.CylinderGeometry(2.5, 0, 14, 8);
            engineGeo.rotateX(-Math.PI / 2);
            const engineMat = new THREE.MeshStandardMaterial({ 
                color: 0xff5500,
                emissive: 0xff4400,
                emissiveIntensity: 3.0
            });
            const engine = new THREE.Mesh(engineGeo, engineMat);
            engine.position.z = 12;
            group.add(engine);

            return group;
        }

        function createStationMesh() {
            const group = new THREE.Group();
            const ringGeo = new THREE.TorusGeometry(80, 6, 16, 64);
            const ringMat = new THREE.MeshStandardMaterial({ color: 0x00ffff, metalness: 0.9, roughness: 0.2 });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            group.add(ring);

            const coreGeo = new THREE.SphereGeometry(25, 32, 32);
            const coreMat = new THREE.MeshStandardMaterial({ color: 0x2244aa, metalness: 0.5 });
            const core = new THREE.Mesh(coreGeo, coreMat);
            group.add(core);

            return group;
        }

        const stationMesh = createStationMesh();
        scene.add(stationMesh);

        // ==============================================================================
        // 4. CLIENT STATE & WEBSOCKET HANDLING
        // ==============================================================================
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);

        let localPlayerId = null;
        let gameState = { players: {} };
        const shipMeshes = {};
        const keys = {};

        window.addEventListener('keydown', e => { keys[e.key] = true; });
        window.addEventListener('keyup', e => { keys[e.key] = false; });
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'init') {
                localPlayerId = data.id;
                if (!gameState.players[localPlayerId]) {
                    gameState.players[localPlayerId] = { x: 200, y: 0, z: 0, angle: 0, vx: 0, vy: 0, vz: 0 };
                }
                return;
            }
            if (data.type === 'state') {
                for (let id in data.gameState.players) {
                    if (id !== localPlayerId) {
                        gameState.players[id] = data.gameState.players[id];
                    } else if (!gameState.players[localPlayerId]) {
                        gameState.players[localPlayerId] = data.gameState.players[id];
                    }
                }
                for (let id in gameState.players) {
                    if (!data.gameState.players[id] && id !== localPlayerId) {
                        delete gameState.players[id];
                        if (shipMeshes[id]) {
                            scene.remove(shipMeshes[id]);
                            delete shipMeshes[id];
                        }
                    }
                }
                document.getElementById('player-count').innerText = Object.keys(data.gameState.players).length;
            }
        };

        // ==============================================================================
        // 5. MOVEMENT & SHIP PHYSICS
        // ==============================================================================
        function updateLocalPhysics() {
            if (localPlayerId && gameState.players[localPlayerId]) {
                const me = gameState.players[localPlayerId];
        
                if (me.z === undefined || isNaN(me.z)) me.z = 0;
                if (me.vz === undefined || isNaN(me.vz)) me.vz = 0;
                // TURNING
                if (keys['ArrowLeft'] || keys['a'] || keys['A']) me.angle -= 0.03;
                if (keys['ArrowRight'] || keys['d'] || keys['D']) me.angle += 0.03;
                
                const currentSpeed = Math.sqrt(me.vx * me.vx + me.vy * me.vy + me.vz * me.vz);
                const maxSpeed = 20;
                // THRUST
                if (keys['ArrowUp'] || keys['w'] || keys['W']) {
                    if (currentSpeed < maxSpeed) {
                        me.vx += Math.sin(me.angle) * 0.3;
                        me.vy -= Math.cos(me.angle) * 0.3;
                    }
                    spawnTrailParticle(me.x, me.y, me.z, me.angle);
                }
                // BRAKING
                if (keys['ArrowDown'] || keys['s'] || keys['S']) {
                    me.vx *= 0.95;
                    me.vy *= 0.95;
                    me.vz *= 0.95;
                }
                // ALTITUDE
                if (keys['x'] || keys['X']) me.vz += 0.3;
                if (keys['z'] || keys['Z']) me.vz -= 0.3;
        
                me.x += me.vx;
                me.y += me.vy;
                me.z += me.vz;
        
                me.vx *= 0.987;
                me.vy *= 0.987;
                me.vz *= 0.950;
        
                const shipRadius = 12;
                for (let i = 0; i < planetData.length; i++) {
                    const planet = planetData[i];
                    
                    const dx = me.x - planet.x;
                    const dy = me.z - planet.y; 
                    const dz = me.y - planet.z;
                    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
                    const minDist = planet.radius + shipRadius;
        
                    if (dist < minDist && dist > 0) {
                        const nx = dx / dist;
                        const ny = dy / dist;
                        const nz = dz / dist;
        
                        const overlap = minDist - dist;
                        me.x += nx * overlap;
                        me.z += ny * overlap;
                        me.y += nz * overlap;
        
                        const dotProduct = me.vx * nx + me.vz * ny + me.vy * nz;
        
                        if (dotProduct < 0) {
                            me.vx = (me.vx - 2 * dotProduct * nx) * 0.6;
                            me.vz = (me.vz - 2 * dotProduct * ny) * 0.6;
                            me.vy = (me.vy - 2 * dotProduct * nz) * 0.6;
                            me.angle = Math.atan2(me.vx, -me.vy);
                        }
                    }
                }
        
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ 
                        type: 'sync', x: me.x, y: me.y, z: me.z, angle: me.angle, vx: me.vx, vy: me.vy, vz: me.vz 
                    }));
                }
            }
        }

        // ==============================================================================
        // 6. CHASE CAMERA CONTROLS
        // ==============================================================================
        function updateCameraPosition(me) {
            const cameraDistance = 140; 
            const cameraHeight = 50;    

            const targetCamX = me.x - Math.sin(me.angle) * cameraDistance;
            const targetCamZ = me.y + Math.cos(me.angle) * cameraDistance;
            const targetCamY = me.z + cameraHeight;

            camera.position.x += (targetCamX - camera.position.x) * 0.1;
            camera.position.z += (targetCamZ - camera.position.z) * 0.1;
            camera.position.y += (targetCamY - camera.position.y) * 0.1;

            const lookTarget = new THREE.Vector3(
                me.x + Math.sin(me.angle) * 40,
                me.z,
                me.y - Math.cos(me.angle) * 40
            );
            camera.lookAt(lookTarget);
        }

        // ==============================================================================
        // 7. MAIN GAME LOOP WITH INTERPOLATED MULTIPLAYER MOVEMENT
        // ==============================================================================
        function animate() {
            requestAnimationFrame(animate);
            updateLocalPhysics();
            updateParticles();

            stationMesh.rotation.y += 0.005;

            // Render and smooth out remote ships via linear interpolation
            for (let id in gameState.players) {
                const p = gameState.players[id];
                if (!p) continue;

                if (!shipMeshes[id]) {
                    shipMeshes[id] = createShipMesh(id === localPlayerId);
                    scene.add(shipMeshes[id]);
                }

                if (id === localPlayerId) {
                    // Instant update for local player
                    shipMeshes[id].position.x = p.x;
                    shipMeshes[id].position.y = p.z || 0;
                    shipMeshes[id].position.z = p.y;
                    shipMeshes[id].rotation.y = -p.angle;
                } else {
                    // Smooth lerp interpolation for remote players (eliminates network lag jitter)
                    const targetX = p.x;
                    const targetY = p.z || 0;
                    const targetZ = p.y;

                    shipMeshes[id].position.x += (targetX - shipMeshes[id].position.x) * 0.25;
                    shipMeshes[id].position.y += (targetY - shipMeshes[id].position.y) * 0.25;
                    shipMeshes[id].position.z += (targetZ - shipMeshes[id].position.z) * 0.25;
                    shipMeshes[id].rotation.y += (-p.angle - shipMeshes[id].rotation.y) * 0.25;
                }
            }

            const me = gameState.players[localPlayerId];
            if (me && shipMeshes[localPlayerId]) {
                updateCameraPosition(me);

                updateStarChunks(me.x, me.z || 0, me.y);

                const posArr = originLine.geometry.attributes.position.array;
                posArr[0] = 0;     
                posArr[1] = 0;     
                posArr[2] = 0;     
                posArr[3] = me.x;  
                posArr[4] = me.z || 0; 
                posArr[5] = me.y;  
                originLine.geometry.attributes.position.needsUpdate = true;

                const spd = Math.sqrt(me.vx * me.vx + me.vy * me.vy + (me.vz || 0) * (me.vz || 0)).toFixed(1);
                document.getElementById('pos-x').innerText = Math.round(me.x);
                document.getElementById('pos-z').innerText = Math.round(me.y);
                document.getElementById('pos-y').innerText = Math.round(me.z || 0);
                document.getElementById('speed').innerText = spd;
            }

            renderer.render(scene, camera);
        }

        animate();
    </script>
</body>
</html>
"""

# ==============================================================================
# 8. BACKEND GAME STATE & FASTAPI SERVER
# ==============================================================================
game_state = {
    "station": {"x": 0, "y": 0, "radius": 80},
    "players": {}
}

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket
        game_state["players"][player_id] = {
            "x": 200, "y": 0, "z": 0, "angle": 0, "vx": 0, "vy": 0, "vz": 0
        }
        await websocket.send_text(json.dumps({"type": "init", "id": player_id}))

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        if player_id in game_state["players"]:
            del game_state["players"][player_id]

    async def broadcast_state(self):
        payload = json.dumps({"type": "state", "gameState": game_state})
        for connection in list(self.active_connections.values()):
            try:
                await connection.send_text(payload)
            except Exception:
                pass

manager = ConnectionManager()

@app.get("/")
async def get():
    return HTMLResponse(HTML_CLIENT)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_id = str(id(websocket))
    await manager.connect(websocket, player_id)
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
        await asyncio.sleep(1 / 30) # Increased broadcast rate to 30 FPS for lower latency

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_loop())
