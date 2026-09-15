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
        <p>Controls: WASD (Forward/Turn), X/Z (Ascend/Descend)</p>
    </div>

    <script>
        // ==============================================================================
        // 2. THREE.JS SCENE SETUP & LIGHTING
        // ==============================================================================
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.00005);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 250000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        document.body.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 2.5);
        sunLight.position.set(15000, 30000, 15000);
        scene.add(sunLight);

        const GLOBAL_SEED = 987654321;

        function seededRandom(seed) {
            const x = Math.sin(seed) * 10000;
            return x - Math.floor(x);
        }

        // Shared helper function for multi-octave spherical noise calculation
        function getPlanetNoise(simplex, nx, ny, nz) {
            // Higher base scale ensures multiple continents wrap all around the sphere
            let n1 = (simplex.noise3D(nx * 2.5, ny * 2.5, nz * 2.5) + 1) * 0.5 * 0.65;
            let n2 = (simplex.noise3D(nx * 6.0, ny * 6.0, nz * 6.0) + 1) * 0.5 * 0.25;
            let n3 = (simplex.noise3D(nx * 14.0, ny * 14.0, nz * 14.0) + 1) * 0.5 * 0.10;
            return n1 + n2 + n3;
        }

        // ==============================================================================
        // SEAMLESS 3D SPHERICAL PLANET TEXTURE GENERATOR
        // ==============================================================================
        function generatePlanetTexture(seed) {
            const simplex = new SimplexNoise(seed.toString());
            
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');
            const imgData = ctx.createImageData(canvas.width, canvas.height);

            const oceanR = Math.floor(seededRandom(seed) * 20);
            const oceanG = Math.floor(seededRandom(seed + 1) * 80 + 30);
            const oceanB = Math.floor(seededRandom(seed + 2) * 150 + 100);

            const landR = Math.floor(seededRandom(seed + 3) * 150 + 50);
            const landG = Math.floor(seededRandom(seed + 4) * 180 + 70);
            const landB = Math.floor(seededRandom(seed + 5) * 60 + 20);

            const seaLevel = 0.48;

            for (let y = 0; y < canvas.height; y++) {
                const v = y / canvas.height;
                const lat = (v - 0.5) * Math.PI;
                const sinLat = Math.sin(lat);
                const cosLat = Math.cos(lat);

                for (let x = 0; x < canvas.width; x++) {
                    const u = x / canvas.width;
                    const lon = u * Math.PI * 2;

                    const nx = cosLat * Math.cos(lon);
                    const ny = sinLat;
                    const nz = cosLat * Math.sin(lon);

                    let totalHeight = getPlanetNoise(simplex, nx, ny, nz);

                    const i = (y * canvas.width + x) * 4;

                    if (totalHeight < seaLevel) {
                        const oceanDepth = Math.max(0.2, totalHeight / seaLevel);
                        imgData.data[i]     = Math.floor(oceanR * oceanDepth);
                        imgData.data[i + 1] = Math.floor(oceanG * oceanDepth);
                        imgData.data[i + 2] = Math.floor(oceanB * oceanDepth);
                    } else {
                        const landElev = (totalHeight - seaLevel) / (1 - seaLevel);
                        imgData.data[i]     = Math.min(255, Math.floor(landR + landElev * 80));
                        imgData.data[i + 1] = Math.min(255, Math.floor(landG + landElev * 80));
                        imgData.data[i + 2] = Math.min(255, Math.floor(landB + landElev * 40));
                    }
                    imgData.data[i + 3] = 255;
                }
            }

            ctx.putImageData(imgData, 0, 0);

            const colorTex = new THREE.CanvasTexture(canvas);
            colorTex.minFilter = THREE.LinearFilter;
            colorTex.magFilter = THREE.LinearFilter;
            colorTex.needsUpdate = true;

            return colorTex;
        }

        // ==============================================================================
        // PLANETS MANAGER WITH MATCHED 3D TERRAIN DISPLACEMENT
        // ==============================================================================
        const PLANET_CHUNK_SIZE = 60000;
        const PLANET_DRAW_RADIUS = 1;
        const planetChunks = {};

        function createPlanetChunk(cx, cy, cz) {
            const key = `${cx},${cy},${cz}`;
            if (planetChunks[key]) return;

            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791) ^ GLOBAL_SEED;

            seed++;
            if (seededRandom(seed) > 0.25) {
                planetChunks[key] = null;
                return;
            }

            seed++;
            const px = (cx + seededRandom(seed)) * PLANET_CHUNK_SIZE;
            seed++;
            const py = (cy + seededRandom(seed)) * PLANET_CHUNK_SIZE;
            seed++;
            const pz = (cz + seededRandom(seed)) * PLANET_CHUNK_SIZE;

            seed++;
            const radius = 8000 + seededRandom(seed) * 12000;
            
            const colorTexture = generatePlanetTexture(seed);

            const geom = new THREE.SphereGeometry(radius, 128, 128);
            const posAttr = geom.attributes.position;
            const vertex = new THREE.Vector3();
            const simplex = new SimplexNoise(seed.toString());

            const seaLevel = 0.48;
            const maxMountainHeight = radius * 0.08; 

            for (let i = 0; i < posAttr.count; i++) {
                vertex.fromBufferAttribute(posAttr, i);
                const dir = vertex.clone().normalize();

                let totalHeight = getPlanetNoise(simplex, dir.x, dir.y, dir.z);

                if (totalHeight > seaLevel) {
                    const landElev = (totalHeight - seaLevel) / (1 - seaLevel);
                    const displacement = landElev * maxMountainHeight;
                    vertex.addScaledVector(dir, displacement);
                }

                posAttr.setXYZ(i, vertex.x, vertex.y, vertex.z);
            }

            geom.computeVertexNormals();

            const mat = new THREE.MeshStandardMaterial({ 
                map: colorTexture,
                roughness: 0.8,
                metalness: 0.1,
                flatShading: false
            });

            const mesh = new THREE.Mesh(geom, mat);
            mesh.position.set(px, pz, py);

            scene.add(mesh);

            planetChunks[key] = {
                mesh: mesh,
                x: px,
                y: py,
                z: pz,
                radius: radius,
                seed: seed,
                maxMountainHeight: maxMountainHeight
            };
        }

        function updatePlanetChunks(playerX, playerY, playerZ) {
            const currentChunkX = Math.floor(playerX / PLANET_CHUNK_SIZE);
            const currentChunkY = Math.floor(playerY / PLANET_CHUNK_SIZE);
            const currentChunkZ = Math.floor(playerZ / PLANET_CHUNK_SIZE);

            const activeKeys = new Set();

            for (let x = -PLANET_DRAW_RADIUS; x <= PLANET_DRAW_RADIUS; x++) {
                for (let y = -PLANET_DRAW_RADIUS; y <= PLANET_DRAW_RADIUS; y++) {
                    for (let z = -PLANET_DRAW_RADIUS; z <= PLANET_DRAW_RADIUS; z++) {
                        const cx = currentChunkX + x;
                        const cy = currentChunkY + y;
                        const cz = currentChunkZ + z;
                        const key = `${cx},${cy},${cz}`;
                        
                        activeKeys.add(key);
                        createPlanetChunk(cx, cy, cz);
                    }
                }
            }

            for (let key in planetChunks) {
                if (!activeKeys.has(key)) {
                    if (planetChunks[key] && planetChunks[key].mesh) {
                        scene.remove(planetChunks[key].mesh);
                        if (planetChunks[key].mesh.material.map) planetChunks[key].mesh.material.map.dispose();
                        planetChunks[key].mesh.geometry.dispose();
                        planetChunks[key].mesh.material.dispose();
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
        // UNIFORM 360-DEGREE SPHERICAL STAR POOL
        // ==============================================================================
        function createStarGlowTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 64;
            canvas.height = 64;
            const ctx = canvas.getContext('2d');

            const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
            gradient.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)'); 
            gradient.addColorStop(0.2, 'rgba(250, 250, 250, 0.9)'); 
            gradient.addColorStop(0.5, 'rgba(245, 245, 245, 0.3)');  
            gradient.addColorStop(1.0, 'rgba(0, 0, 0, 0)');        

            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, 64, 64);

            const tex = new THREE.CanvasTexture(canvas);
            tex.needsUpdate = true;
            return tex;
        }

        const TOTAL_STARS = 1000;
        const STAR_FIELD_RADIUS = 6000;
        const starPositions = new Float32Array(TOTAL_STARS * 3);
        const starOrigins = [];

        for (let i = 0; i < TOTAL_STARS; i++) {
            const rx = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            const ry = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            const rz = (Math.random() - 0.5) * STAR_FIELD_RADIUS * 2;
            
            starOrigins.push({ x: rx, y: ry, z: rz });

            const idx = i * 3;
            starPositions[idx]     = rx;
            starPositions[idx + 1] = ry;
            starPositions[idx + 2] = rz;
        }

        const starGeo = new THREE.BufferGeometry();
        starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));

        const starGlowTexture = createStarGlowTexture();
        const starMat = new THREE.PointsMaterial({
            size: 65,
            map: starGlowTexture,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        const starPoolMesh = new THREE.Points(starGeo, starMat);
        starPoolMesh.frustumCulled = false;
        scene.add(starPoolMesh);

        function updateStarPool(px, py, pz, vx, vy, vz, angle) {
            const posAttr = starGeo.attributes.position;
            const posArray = posAttr.array;

            for (let i = 0; i < TOTAL_STARS; i++) {
                const pt = starOrigins[i];
                
                let dx = pt.x - px;
                let dy = pt.y - py;
                let dz = pt.z - pz;
                let distSq = dx * dx + dy * dy + dz * dz;

                if (distSq > STAR_FIELD_RADIUS * STAR_FIELD_RADIUS) {
                    const u = Math.random();
                    const v = Math.random();
                    const theta = u * 2.0 * Math.PI; 
                    const phi = Math.acos(2.0 * v - 1.0); 
                    const radius = STAR_FIELD_RADIUS * 0.95; 

                    pt.x = px + radius * Math.sin(phi) * Math.cos(theta);
                    pt.y = py + radius * Math.sin(phi) * Math.sin(theta);
                    pt.z = pz + radius * Math.cos(phi);
                }

                const idx = i * 3;
                posArray[idx]     = pt.x;
                posArray[idx + 1] = pt.y;
                posArray[idx + 2] = pt.z;
            }

            posAttr.needsUpdate = true;
        }

        // ==============================================================================
        // DYNAMIC ORIGIN LINE & EXHAUST PARTICLES
        // ==============================================================================
        const lineGeo = new THREE.BufferGeometry();
        const linePositions = new Float32Array(6); 
        lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
        const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.8, transparent: true });
        const originLine = new THREE.Line(lineGeo, lineMat);
        originLine.frustumCulled = false;
        scene.add(originLine);

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
        // 3D MODEL FACTORIES
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
        // CLIENT STATE & WEBSOCKET HANDLING
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
        // MOVEMENT & PHYSICS
        // ==============================================================================
        function updateLocalPhysics() {
            if (localPlayerId && gameState.players[localPlayerId]) {
                const me = gameState.players[localPlayerId];

                if (me.z === undefined || isNaN(me.z)) me.z = 0;
                if (me.vz === undefined || isNaN(me.vz)) me.vz = 0;

                const maxSpeed = 35;
                const currentSpeed = Math.sqrt(me.vx * me.vx + me.vy * me.vy + me.vz * me.vz);

                if (keys['ArrowLeft'] || keys['a'] || keys['A']) me.angle -= 0.03;
                if (keys['ArrowRight'] || keys['d'] || keys['D']) me.angle += 0.03;

                if (keys['ArrowUp'] || keys['w'] || keys['W']) {
                    const baseAccel = 0.35;
                    const dragFactor = 0.013;
                    const effectiveThrust = baseAccel + (currentSpeed * dragFactor);

                    me.vx += Math.sin(me.angle) * effectiveThrust;
                    me.vy -= Math.cos(me.angle) * effectiveThrust;

                    spawnTrailParticle(me.x, me.y, me.z, me.angle);
                }

                if (keys['ArrowDown'] || keys['s'] || keys['S']) {
                    me.vx *= 0.90;
                    me.vy *= 0.90;
                    me.vz *= 0.90;
                }

                if (keys['x'] || keys['X']) me.vz += 0.45;
                if (keys['z'] || keys['Z']) me.vz -= 0.45;

                // Apply drag
                me.vx *= 0.987;
                me.vy *= 0.987;
                me.vz *= 0.950;

                // Clamp velocity
                const newSpeed = Math.sqrt(me.vx * me.vx + me.vy * me.vy + me.vz * me.vz);
                if (newSpeed > maxSpeed) {
                    const scale = maxSpeed / newSpeed;
                    me.vx *= scale;
                    me.vy *= scale;
                    me.vz *= scale;
                }

                me.x += me.vx;
                me.y += me.vy;
                me.z += me.vz;

                // Smooth Terrain Collision Check
                const shipRadius = 12;
                for (let key in planetChunks) {
                    const planet = planetChunks[key];
                    if (!planet) continue;

                    const dx = me.x - planet.x;
                    const dy = me.z - planet.z; 
                    const dz = me.y - planet.y;
                    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

                    const maxPossibleRadius = planet.radius + planet.maxMountainHeight + shipRadius;
                    if (dist > maxPossibleRadius) continue;

                    const nx = dx / dist;
                    const ny = dz / dist; 
                    const nz = dy / dist;

                    const simplex = new SimplexNoise(planet.seed.toString());
                    let totalHeight = getPlanetNoise(simplex, nx, ny, nz);

                    const seaLevel = 0.48;
                    let surfaceRadius = planet.radius;
                    if (totalHeight > seaLevel) {
                        const landElev = (totalHeight - seaLevel) / (1 - seaLevel);
                        surfaceRadius += landElev * planet.maxMountainHeight;
                    }

                    const minDist = surfaceRadius + shipRadius;

                    if (dist < minDist && dist > 0) {
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
        // CHASE CAMERA CONTROLS
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
        // MAIN GAME LOOP
        // ==============================================================================
        function animate() {
            requestAnimationFrame(animate);
            updateLocalPhysics();
            updateParticles();

            stationMesh.rotation.y += 0.005;

            for (let id in gameState.players) {
                const p = gameState.players[id];
                if (!p) continue;

                if (!shipMeshes[id]) {
                    shipMeshes[id] = createShipMesh(id === localPlayerId);
                    scene.add(shipMeshes[id]);
                }

                if (id === localPlayerId) {
                    shipMeshes[id].position.x = p.x;
                    shipMeshes[id].position.y = p.z || 0;
                    shipMeshes[id].position.z = p.y;
                    shipMeshes[id].rotation.y = -p.angle;
                } else {
                    shipMeshes[id].position.x += (p.x - shipMeshes[id].position.x) * 0.25;
                    shipMeshes[id].position.y += ((p.z || 0) - shipMeshes[id].position.y) * 0.25;
                    shipMeshes[id].position.z += (p.y - shipMeshes[id].position.z) * 0.25;
                    shipMeshes[id].rotation.y += (-p.angle - shipMeshes[id].rotation.y) * 0.25;
                }
            }

            const me = gameState.players[localPlayerId];
            if (me && shipMeshes[localPlayerId]) {
                updateCameraPosition(me);

                updateStarPool(me.x, me.z || 0, me.y, me.vx, me.vy, me.vz || 0, me.angle);
                updatePlanetChunks(me.x, me.z || 0, me.y);

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
# BACKEND GAME STATE & FASTAPI SERVER
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
        await asyncio.sleep(1 / 30)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_loop())
