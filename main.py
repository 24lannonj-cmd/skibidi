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
    <title>Infinite Synced Space Sandbox 3D</title>
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
    </style>
    <!-- Three.js Library -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <!-- Simplex Noise Library -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/simplex-noise/2.4.0/simplex-noise.min.js"></script>
</head>
<body>
    <div id="ui">
        <h3 style="margin-top: 0; color: #00ffff; text-shadow: 0 0 8px #00ffff;">3D Infinite Warp Flight Deck</h3>
        <p>Position: X <span id="pos-x" class="stat">0</span> | Z <span id="pos-z" class="stat">0</span> | Alt <span id="pos-y" class="stat">0</span></p>
        <p>Speed: <span id="speed" class="stat">0</span> m/s</p>
        <p>Pilots Online: <span id="player-count" class="stat">0</span></p>
        <p>Active Planets: <span id="planet-count" class="stat">0</span></p>
        <p>Nearest Planet: <span id="nearest-dist" class="stat">N/A</span></p>
        <p>Controls: WASD (Forward/Turn), X/Z (Ascend/Descend)</p>
    </div>

    <div id="nav-arrow"></div>
    <div id="nav-text">TARGET</div>

    <script>
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.00005);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 250000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        document.body.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 2.5);
        sunLight.position.set(15000, 30000, 15000);
        scene.add(sunLight);

        const GLOBAL_SEED = 987654321;

        function seededRandom(seed) {
            let x = Math.sin(seed * 9999) * 10000;
            return x - Math.floor(x);
        }

        function lerp(start, end, amt) {
            return (1 - amt) * start + amt * end;
        }

        // Optimized Texture Cache
        const textureCache = {};

        function generatePlanetTextures(seed) {
            if (textureCache[seed]) return textureCache[seed];

            const simplex = new SimplexNoise(seed.toString());
            const width = 256;
            const height = 128;

            const canvasColor = document.createElement('canvas');
            canvasColor.width = width;
            canvasColor.height = height;
            const ctxColor = canvasColor.getContext('2d');
            const imgDataColor = ctxColor.createImageData(width, height);

            const temp = seededRandom(seed * 3.14159);

            let oceanR, oceanG, oceanB;
            let landR, landG, landB;

            if (temp < 0.25) {
                // Ice World
                const t = temp / 0.25;
                oceanR = lerp(10, 30, t); oceanG = lerp(60, 100, t); oceanB = lerp(120, 180, t);
                landR = lerp(200, 230, t); landG = lerp(220, 240, t); landB = lerp(245, 255, t);
            } else if (temp < 0.50) {
                // Terran World
                const t = (temp - 0.25) / 0.25;
                oceanR = lerp(5, 20, t); oceanG = lerp(35, 70, t); oceanB = lerp(120, 160, t);
                landR = lerp(30, 60, t); landG = lerp(110, 80, t); landB = lerp(30, 25, t);
            } else if (temp < 0.75) {
                // Scorched World (Darker Land)
                const t = (temp - 0.50) / 0.25;
                oceanR = lerp(80, 140, t); oceanG = lerp(140, 110, t); oceanB = lerp(20, 10, t);
                landR = lerp(40, 20, t); landG = lerp(30, 15, t); landB = lerp(25, 10, t);
            } else {
                // Lava World (Warmer = Dark Obsidian / Pitch Black Ash)
                const t = (temp - 0.75) / 0.25;
                oceanR = lerp(255, 200, t); oceanG = lerp(60, 15, t); oceanB = 0;
                landR = lerp(10, 2, t); landG = lerp(10, 2, t); landB = lerp(12, 2, t);
            }

            const seaLevel = 0.48;
            for (let y = 0; y < height; y++) {
                const v = y / height;
                const lat = (v - 0.5) * Math.PI;
                const sinLat = Math.sin(lat);
                const cosLat = Math.cos(lat);

                for (let x = 0; x < width; x++) {
                    const u = x / width;
                    const lon = u * Math.PI * 2;
                    const nx = cosLat * Math.cos(lon);
                    const ny = sinLat;
                    const nz = cosLat * Math.sin(lon);

                    let h = (simplex.noise3D(nx * 2, ny * 2, nz * 2) + 1) * 0.5;
                    const i = (y * width + x) * 4;

                    if (h < seaLevel) {
                        imgDataColor.data[i] = oceanR;
                        imgDataColor.data[i + 1] = oceanG;
                        imgDataColor.data[i + 2] = oceanB;
                    } else {
                        imgDataColor.data[i] = landR;
                        imgDataColor.data[i + 1] = landG;
                        imgDataColor.data[i + 2] = landB;
                    }
                    imgDataColor.data[i + 3] = 255;
                }
            }

            ctxColor.putImageData(imgDataColor, 0, 0);
            const colorTex = new THREE.CanvasTexture(canvasColor);
            
            const result = { colorTex, isLava: temp >= 0.75 };
            textureCache[seed] = result;
            return result;
        }

        // ==============================================================================
        // PLANETS MANAGER
        // ==============================================================================
        const PLANET_CHUNK_SIZE = 75000;
        const PLANET_DRAW_RADIUS = 1; 
        const UNLOAD_DISTANCE_THRESHOLD = 150000;
        const planetChunks = {};

        const sharedSphereGeom = new THREE.SphereGeometry(1, 32, 32);

        function createPlanetChunk(cx, cy, cz) {
            const key = `${cx},${cy},${cz}`;
            if (planetChunks[key] !== undefined) return;

            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791) ^ GLOBAL_SEED;

            if (seededRandom(seed) > 0.20) {
                planetChunks[key] = null;
                return;
            }

            seed += 100;
            const px = (cx + seededRandom(seed)) * PLANET_CHUNK_SIZE;
            seed += 200;
            const py = (cy + seededRandom(seed)) * PLANET_CHUNK_SIZE;
            seed += 300;
            const pz = (cz + seededRandom(seed)) * PLANET_CHUNK_SIZE;

            seed += 400;
            const radius = 8000 + seededRandom(seed) * 12000;
            
            const textures = generatePlanetTextures(seed);

            const mat = new THREE.MeshStandardMaterial({ 
                map: textures.colorTex,
                roughness: textures.isLava ? 0.3 : 0.8,
                metalness: textures.isLava ? 0.4 : 0.1,
                emissiveMap: textures.isLava ? textures.colorTex : null,
                emissive: textures.isLava ? 0xff2200 : 0x000000,
                emissiveIntensity: textures.isLava ? 0.6 : 0.0
            });

            const mesh = new THREE.Mesh(sharedSphereGeom, mat);
            mesh.scale.set(radius, radius, radius);
            mesh.position.set(px, pz, py);

            scene.add(mesh);

            planetChunks[key] = {
                mesh: mesh,
                x: px,
                y: py,
                z: pz,
                radius: radius
            };
        }

        function updatePlanetChunks(playerX, playerY, playerZ) {
            const currentChunkX = Math.floor(playerX / PLANET_CHUNK_SIZE);
            const currentChunkY = Math.floor(playerY / PLANET_CHUNK_SIZE);
            const currentChunkZ = Math.floor(playerZ / PLANET_CHUNK_SIZE);

            for (let x = -PLANET_DRAW_RADIUS; x <= PLANET_DRAW_RADIUS; x++) {
                for (let y = -PLANET_DRAW_RADIUS; y <= PLANET_DRAW_RADIUS; y++) {
                    for (let z = -PLANET_DRAW_RADIUS; z <= PLANET_DRAW_RADIUS; z++) {
                        createPlanetChunk(currentChunkX + x, currentChunkY + y, currentChunkZ + z);
                    }
                }
            }

            for (let key in planetChunks) {
                const planet = planetChunks[key];
                if (!planet) continue;

                const dx = planet.x - playerX;
                const dy = planet.z - playerY;
                const dz = planet.y - playerZ;
                const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

                if (dist > UNLOAD_DISTANCE_THRESHOLD) {
                    if (planet.mesh) {
                        scene.remove(planet.mesh);
                        planet.mesh.material.dispose();
                    }
                    delete planetChunks[key];
                }
            }

            let totalPlanets = 0;
            for (let key in planetChunks) {
                if (planetChunks[key]) totalPlanets++;
            }
            document.getElementById('planet-count').innerText = totalPlanets;
        }

        // ==============================================================================
        // NEAREST PLANET POINTER
        // ==============================================================================
        const arrowEl = document.getElementById('nav-arrow');
        const textEl = document.getElementById('nav-text');

        function updatePlanetPointer(playerX, playerY, playerZ) {
            let nearestPlanet = null;
            let minDistance = Infinity;

            for (let key in planetChunks) {
                const planet = planetChunks[key];
                if (!planet) continue;

                const dx = planet.x - playerX;
                const dy = planet.z - playerY; 
                const dz = planet.y - playerZ;
                const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) - planet.radius;

                if (dist < minDistance) {
                    minDistance = dist;
                    nearestPlanet = planet;
                }
            }

            if (!nearestPlanet) {
                arrowEl.style.display = 'none';
                textEl.style.display = 'none';
                document.getElementById('nearest-dist').innerText = 'None in range';
                return;
            }

            const formattedDist = Math.max(0, Math.round(minDistance));
            document.getElementById('nearest-dist').innerText = `${formattedDist} m`;

            const targetPos = new THREE.Vector3(nearestPlanet.x, nearestPlanet.z, nearestPlanet.y);
            const screenPos = targetPos.clone().project(camera);

            const widthHalf = window.innerWidth / 2;
            const heightHalf = window.innerHeight / 2;

            let screenX = (screenPos.x * widthHalf) + widthHalf;
            let screenY = -(screenPos.y * heightHalf) + heightHalf;

            const isBehind = screenPos.z > 1;
            const margin = 50;

            if (isBehind || screenX < margin || screenX > window.innerWidth - margin || screenY < margin || screenY > window.innerHeight - margin) {
                let edgeX = isBehind ? window.innerWidth - screenX : screenX;
                let edgeY = isBehind ? window.innerHeight - screenY : screenY;

                const dx = edgeX - widthHalf;
                const dy = edgeY - heightHalf;
                const angle = Math.atan2(dy, dx);

                const maxX = widthHalf - margin;
                const maxY = heightHalf - margin;

                const scale = Math.min(maxX / Math.abs(Math.cos(angle)), maxY / Math.abs(Math.sin(angle)));
                screenX = widthHalf + Math.cos(angle) * scale;
                screenY = heightHalf + Math.sin(angle) * scale;
            }

            arrowEl.style.display = 'block';
            arrowEl.style.left = `${screenX - 12}px`;
            arrowEl.style.top = `${screenY - 12}px`;

            textEl.style.display = 'block';
            textEl.style.left = `${screenX - 25}px`;
            textEl.style.top = `${screenY + 18}px`;
            textEl.innerText = `${formattedDist}m`;
        }

        // ==============================================================================
        // STARFIELD
        // ==============================================================================
        const TOTAL_STARS = 600;
        const STAR_FIELD_RADIUS = 5000;
        const starPositions = new Float32Array(TOTAL_STARS * 3);
        const starOrigins = [];

        for (let i = 0; i < TOTAL_STARS; i++) {
            const rx = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            const ry = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            const rz = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            
            starOrigins.push({ x: rx, y: ry, z: rz });
            const idx = i * 3;
            starPositions[idx] = rx;
            starPositions[idx + 1] = ry;
            starPositions[idx + 2] = rz;
        }

        const starGeo = new THREE.BufferGeometry();
        starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));

        const starMat = new THREE.PointsMaterial({
            size: 3,
            color: 0xffffff,
            transparent: true,
            opacity: 0.8
        });

        const starPoolMesh = new THREE.Points(starGeo, starMat);
        scene.add(starPoolMesh);

        function updateStarPool(px, py, pz) {
            const posArray = starGeo.attributes.position.array;
            for (let i = 0; i < TOTAL_STARS; i++) {
                const pt = starOrigins[i];
                let dx = pt.x - px;
                let dy = pt.y - py;
                let dz = pt.z - pz;

                if (dx * dx + dy * dy + dz * dz > STAR_FIELD_RADIUS * STAR_FIELD_RADIUS) {
                    pt.x = px + (Math.random() - 0.5) * STAR_FIELD_RADIUS * 1.8;
                    pt.y = py + (Math.random() - 0.5) * STAR_FIELD_RADIUS * 1.8;
                    pt.z = pz + (Math.random() - 0.5) * STAR_FIELD_RADIUS * 1.8;
                }

                const idx = i * 3;
                posArray[idx] = pt.x;
                posArray[idx + 1] = pt.y;
                posArray[idx + 2] = pt.z;
            }
            starGeo.attributes.position.needsUpdate = true;
        }

        // ==============================================================================
        // SHIP & CLIENT SETUP
        // ==============================================================================
        function createShipMesh(isLocal) {
            const group = new THREE.Group();
            const hullGeo = new THREE.ConeGeometry(8, 24, 4);
            hullGeo.rotateX(-Math.PI / 2);
            const hullMat = new THREE.MeshStandardMaterial({ color: isLocal ? 0x00ff88 : 0xff3344 });
            group.add(new THREE.Mesh(hullGeo, hullMat));
            return group;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

        let localPlayerId = null;
        let gameState = { players: {} };
        const shipMeshes = {};
        const keys = {};

        window.addEventListener('keydown', e => { keys[e.key] = true; });
        window.addEventListener('keyup', e => { keys[e.key] = false; });

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'init') {
                localPlayerId = data.id;
                gameState.players[localPlayerId] = { x: 200, y: 0, z: 0, angle: 0, vx: 0, vy: 0, vz: 0 };
            } else if (data.type === 'state') {
                for (let id in data.gameState.players) {
                    if (id !== localPlayerId) gameState.players[id] = data.gameState.players[id];
                }
                document.getElementById('player-count').innerText = Object.keys(data.gameState.players).length;
            }
        };

        function updateLocalPhysics() {
            if (!localPlayerId || !gameState.players[localPlayerId]) return;
            const me = gameState.players[localPlayerId];

            if (keys['a'] || keys['A']) me.angle -= 0.03;
            if (keys['d'] || keys['D']) me.angle += 0.03;

            if (keys['w'] || keys['W']) {
                me.vx += Math.sin(me.angle) * 0.4;
                me.vy -= Math.cos(me.angle) * 0.4;
            }

            if (keys['x'] || keys['X']) me.vz += 0.4;
            if (keys['z'] || keys['Z']) me.vz -= 0.4;

            me.vx *= 0.98; me.vy *= 0.98; me.vz *= 0.95;
            me.x += me.vx; me.y += me.vy; me.z += me.vz;

            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'sync', x: me.x, y: me.y, z: me.z, angle: me.angle, vx: me.vx, vy: me.vy, vz: me.vz }));
            }
        }

        function animate() {
            requestAnimationFrame(animate);
            updateLocalPhysics();

            const me = gameState.players[localPlayerId];
            if (me) {
                camera.position.set(me.x - Math.sin(me.angle) * 140, me.z + 50, me.y + Math.cos(me.angle) * 140);
                camera.lookAt(me.x, me.z, me.y);

                updateStarPool(me.x, me.z, me.y);
                updatePlanetChunks(me.x, me.z, me.y);
                updatePlanetPointer(me.x, me.z, me.y);

                document.getElementById('pos-x').innerText = Math.round(me.x);
                document.getElementById('pos-z').innerText = Math.round(me.y);
                document.getElementById('pos-y').innerText = Math.round(me.z);
            }

            for (let id in gameState.players) {
                if (!shipMeshes[id]) {
                    shipMeshes[id] = createShipMesh(id === localPlayerId);
                    scene.add(shipMeshes[id]);
                }
                const p = gameState.players[id];
                shipMeshes[id].position.set(p.x, p.z || 0, p.y);
                shipMeshes[id].rotation.y = -p.angle;
            }

            renderer.render(scene, camera);
        }

        animate();
    </script>
</body>
</html>
"""

# ==============================================================================
# BACKEND GAME STATE & FASTAPI SERVER
# ==============================================================================
game_state = {"players": {}}

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket
        game_state["players"][player_id] = {"x": 200, "y": 0, "z": 0, "angle": 0, "vx": 0, "vy": 0, "vz": 0}
        await websocket.send_text(json.dumps({"type": "init", "id": player_id}))

    def disconnect(self, player_id: str):
        self.active_connections.pop(player_id, None)
        game_state["players"].pop(player_id, None)

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
                p = game_state["players"].get(player_id)
                if p:
                    p.update({k: payload[k] for k in ["x", "y", "z", "angle", "vx", "vy", "vz"] if k in payload})
    except WebSocketDisconnect:
        manager.disconnect(player_id)

async def game_loop():
    while True:
        await manager.broadcast_state()
        await asyncio.sleep(1 / 30)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_loop())
