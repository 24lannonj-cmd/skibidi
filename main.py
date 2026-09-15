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

        function getPlanetNoise(simplex, nx, ny, nz) {
            let n1 = (simplex.noise3D(nx * 2.5, ny * 2.5, nz * 2.5) + 1) * 0.5 * 0.65;
            let n2 = (simplex.noise3D(nx * 6.0, ny * 6.0, nz * 6.0) + 1) * 0.5 * 0.25;
            let n3 = (simplex.noise3D(nx * 14.0, ny * 14.0, nz * 14.0) + 1) * 0.5 * 0.10;
            return n1 + n2 + n3;
        }

        const planetTextureCache = {};

        function generatePlanetTextures(seed) {
            if (planetTextureCache[seed]) {
                return planetTextureCache[seed];
            }

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
            let shoreR, shoreG, shoreB;

            if (temp < 0.25) {
                // Ice World: Deep Cyan Oceans vs Bright Snow
                oceanR = 0;   oceanG = 90;  oceanB = 160;
                shoreR = 120; shoreG = 200; shoreB = 235;
                landR  = 240; landG  = 248; landB  = 255;
            } else if (temp < 0.50) {
                // Earthlike Terran: Deep Blue Ocean, Beach Shore, Bright Green Land
                oceanR = 0;   oceanG = 40;  oceanB = 180;
                shoreR = 210; shoreG = 190; shoreB = 130;
                landR  = 20;  landG  = 160; landB  = 40;
            } else if (temp < 0.75) {
                // Desert/Arid World: Dark Blue Water, Golden Sand Land
                oceanR = 10;  oceanG = 30;  oceanB = 120;
                shoreR = 230; shoreG = 170; shoreB = 90;
                landR  = 220; landG  = 140; landB  = 40;
            } else {
                // Crimson Lava World: Glowing Lava Oceans vs Dark Basalt Land
                oceanR = 255; oceanG = 50;  oceanB = 0;
                shoreR = 200; shoreG = 100; shoreB = 0;
                landR  = 45;  landG  = 40;  landB  = 42;
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

                    let h = getPlanetNoise(simplex, nx, ny, nz);
                    const i = (y * width + x) * 4;

                    if (h < seaLevel) {
                        // Deep Water
                        imgDataColor.data[i]     = oceanR;
                        imgDataColor.data[i + 1] = oceanG;
                        imgDataColor.data[i + 2] = oceanB;
                    } else if (h < seaLevel + 0.04) {
                        // Shoreline / Beach Transition
                        imgDataColor.data[i]     = shoreR;
                        imgDataColor.data[i + 1] = shoreG;
                        imgDataColor.data[i + 2] = shoreB;
                    } else {
                        // Land
                        imgDataColor.data[i]     = landR;
                        imgDataColor.data[i + 1] = landG;
                        imgDataColor.data[i + 2] = landB;
                    }
                    imgDataColor.data[i + 3] = 255;
                }
            }

            ctxColor.putImageData(imgDataColor, 0, 0);

            const colorTex = new THREE.CanvasTexture(canvasColor);
            colorTex.needsUpdate = true;

            const res = { colorTex, isLava: temp >= 0.75 };
            planetTextureCache[seed] = res;
            return res;
        }

        // ==============================================================================
        // PLANETS MANAGER
        // ==============================================================================
        const PLANET_CHUNK_SIZE = 60000;
        const PLANET_DRAW_RADIUS = 2;
        const UNLOAD_DISTANCE_THRESHOLD = 180000;
        const planetChunks = {};

        const sharedSphereGeom = new THREE.SphereGeometry(1, 32, 32);

        function createPlanetChunk(cx, cy, cz) {
            const key = `${cx},${cy},${cz}`;
            if (planetChunks[key] !== undefined) return;

            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791) ^ GLOBAL_SEED;

            if (seededRandom(seed) > 0.25) {
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
                roughness: textures.isLava ? 0.3 : 0.65,
                metalness: textures.isLava ? 0.4 : 0.1,
                emissiveMap: textures.isLava ? textures.colorTex : null,
                emissive: textures.isLava ? 0xff2200 : 0x000000,
                emissiveIntensity: textures.isLava ? 0.8 : 0.0
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
                radius: radius,
                seed: seed
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
        // NEAREST PLANET POINTER LOGIC
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
            let edgeX = screenX;
            let edgeY = screenY;

            if (isBehind || screenX < margin || screenX > window.innerWidth - margin || screenY < margin || screenY > window.innerHeight - margin) {
                if (isBehind) {
                    edgeX = window.innerWidth - screenX;
                    edgeY = window.innerHeight - screenY;
                }
                const dx = edgeX - widthHalf;
                const dy = edgeY - heightHalf;
                const angle = Math.atan2(dy, dx);

                const maxX = widthHalf - margin;
                const maxY = heightHalf - margin;

                const cos = Math.cos(angle);
                const sin = Math.sin(angle);

                const scaleX = maxX / Math.abs(cos);
                const scaleY = maxY / Math.abs(sin);
                const scale = Math.min(scaleX, scaleY);

                edgeX = widthHalf + cos * scale;
                edgeY = heightHalf + sin * scale;
            }

            const dx = screenX - edgeX;
            const dy = screenY - edgeY;
            let rotationAngle = Math.atan2(dy, dx) + Math.PI / 2;
            if (isBehind) rotationAngle += Math.PI;

            arrowEl.style.display = 'block';
            arrowEl.style.left = `${edgeX - 12}px`;
            arrowEl.style.top = `${edgeY - 12}px`;
            arrowEl.style.transform = `rotate(${rotationAngle}rad)`;

            textEl.style.display = 'block';
            textEl.style.left = `${edgeX - 25}px`;
            textEl.style.top = `${edgeY + 18}px`;
            textEl.innerText = `${formattedDist}m`;
        }

        // ==============================================================================
        // UNIFORM SPHERICAL STAR POOL
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

        const TOTAL_STARS = 800;
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
            size: 50,
            map: starGlowTexture,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        const starPoolMesh = new THREE.Points(starGeo, starMat);
        starPoolMesh.frustumCulled = false;
        scene.add(starPoolMesh);

        function updateStarPool(px, py, pz) {
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
            if (trailParticles.length > 25) return;
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
                p.life -= 0.05;
                p.mesh.scale.multiplyScalar(0.95);
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

                me.vx *= 0.987;
                me.vy *= 0.987;
                me.vz *= 0.950;

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

                const shipRadius = 12;
                for (let key in planetChunks) {
                    const planet = planetChunks[key];
                    if (!planet) continue;

                    const dx = me.x - planet.x;
                    const dy = me.z - planet.z; 
                    const dz = me.y - planet.y;
                    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

                    const minDist = planet.radius + shipRadius;

                    if (dist < minDist && dist > 0) {
                        const nx = dx / dist;
                        const ny = dz / dist; 
                        const nz = dy / dist;

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

                updateStarPool(me.x, me.z || 0, me.y);
                updatePlanetChunks(me.x, me.z || 0, me.y);
                updatePlanetPointer(me.x, me.z || 0, me.y);

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
