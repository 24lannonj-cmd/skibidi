HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Infinite Synced Space Sandbox 3D</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/OBJLoader.js"></script>
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
    <div id="debug-log"><strong>Status:</strong></div>
    
    <div id="ui">
        <h3>⚡ Flight Deck</h3>
        <p>Pos: <span class="stat" id="pos-x">0</span> / <span class="stat" id="pos-y">0</span> / <span class="stat" id="pos-z">0</span></p>
        <p>Speed: <span class="stat" id="speed">0</span> m/s</p>
        <p>Players: <span class="stat" id="player-count">0</span></p>
        <p>Planets: <span class="stat" id="planet-count">0</span></p>
        <p>Target: <span class="stat" id="nearest-dist">None</span></p>
        <p style="margin-top: 10px; color: #aaa; font-size: 11px;">
            WASD/Arrows: Steer | X/Z: Up/Down<br>
            Shift: Boost | S: Brake
        </p>
    </div>

    <div id="nav-arrow"></div>
    <div id="nav-text">TARGET</div>

    <script>
        // ==========================================================================
        // GLOBAL ERROR HANDLING
        // ==========================================================================
        const debugLog = document.getElementById('debug-log');
        window.onerror = (msg, url, line) => {
            debugLog.innerHTML += `<br>❌ ${msg.substring(0, 60)}`;
            console.error(msg, url, line);
        };

        // ==========================================================================
        // THREE.JS SCENE SETUP
        // ==========================================================================
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.00002);
        scene.background = new THREE.Color(0x000000);
        
        const camera = new THREE.PerspectiveCamera(
            60, 
            window.innerWidth / window.innerHeight, 
            0.1, 
            1000000
        );
        
        const renderer = new THREE.WebGLRenderer({ 
            antialias: true, 
            powerPreference: "high-performance",
            precision: "mediump"
        });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFShadowShadowMap;
        document.body.appendChild(renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        
        const sunLight = new THREE.DirectionalLight(0xffffff, 2.0);
        sunLight.position.set(50000, 80000, 50000);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 2048;
        sunLight.shadow.mapSize.height = 2048;
        scene.add(sunLight);

        // ==========================================================================
        // CONSTANTS & STATE
        // ==========================================================================
        const GLOBAL_SEED = 987654321;
        const CLUSTER_GRID_SIZE = 200000;
        const CLUSTER_DRAW_RADIUS = 1;
        const UNLOAD_DISTANCE_THRESHOLD = 350000;
        
        const planetObjects = {};
        const shipMeshes = {};
        const keys = {};
        const trailParticles = [];
        
        let localPlayerId = null;
        let gameState = { players: {} };
        let loadedShipModel = null;

        // ==========================================================================
        // SEEDED RNG
        // ==========================================================================
        function seededRandom(seed) {
            const x = Math.sin(seed * 12.9898) * 43758.5453;
            return x - Math.floor(x);
        }

        // ==========================================================================
        // PLANET GENERATION
        // ==========================================================================
        const planetTextureCache = {};

        function generatePlanetTextures(seed) {
            if (planetTextureCache[seed]) return planetTextureCache[seed];

            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');

            let s = seed;
            const rand = () => { s = (s * 73856093) ^ GLOBAL_SEED; return seededRandom(s); };
            const globalTemp = rand();

            let baseColor, continentColor, detailColor, capColor, isLava = false;

            if (globalTemp > 0.82) {
                baseColor = '#1a0b0b';
                continentColor = '#e63900';
                detailColor = '#ffaa00';
                isLava = true;
            } else if (globalTemp > 0.62) {
                baseColor = '#8c593b';
                continentColor = '#d99b00';
                detailColor = '#ffcc66';
            } else if (globalTemp > 0.38) {
                baseColor = '#0b3d91';
                continentColor = '#3a7d44';
                detailColor = '#24522c';
                capColor = '#ffffff';
            } else if (globalTemp > 0.18) {
                baseColor = '#2b4450';
                continentColor = '#607d8b';
                detailColor = '#8ca3ad';
                capColor = '#e0f7fa';
            } else {
                baseColor = '#b2ebf2';
                continentColor = '#e0f7fa';
                detailColor = '#ffffff';
                capColor = '#ffffff';
            }

            ctx.fillStyle = baseColor;
            ctx.fillRect(0, 0, 512, 256);

            const continentCount = 4 + Math.floor(rand() * 5);
            for (let c = 0; c < continentCount; c++) {
                const cx = rand() * 512;
                const cy = rand() * 256;
                const radiusX = 40 + rand() * 80;
                const radiusY = 30 + rand() * 60;

                // Main continent
                ctx.beginPath();
                for (let i = 0; i < 12; i++) {
                    const angle = (i / 12) * Math.PI * 2;
                    const rX = radiusX * (0.6 + rand() * 0.8);
                    const rY = radiusY * (0.6 + rand() * 0.8);
                    const px = cx + Math.cos(angle) * rX;
                    const py = cy + Math.sin(angle) * rY;
                    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
                }
                ctx.closePath();
                ctx.fillStyle = continentColor;
                ctx.fill();

                // Detail
                ctx.beginPath();
                for (let i = 0; i < 12; i++) {
                    const angle = (i / 12) * Math.PI * 2;
                    const rX = (radiusX * 0.4) * (0.6 + rand() * 0.6);
                    const rY = (radiusY * 0.4) * (0.6 + rand() * 0.6);
                    const px = cx + Math.cos(angle) * rX;
                    const py = cy + Math.sin(angle) * rY;
                    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
                }
                ctx.closePath();
                ctx.fillStyle = detailColor;
                ctx.fill();
            }

            // Ice caps
            if (capColor) {
                ctx.fillStyle = capColor;
                const capRadius = globalTemp < 0.18 ? 90 : 45 + rand() * 15;
                ctx.beginPath();
                ctx.arc(256, 0, capRadius, 0, Math.PI * 2);
                ctx.fill();
                ctx.beginPath();
                ctx.arc(256, 256, capRadius, 0, Math.PI * 2);
                ctx.fill();
            }

            const colorTex = new THREE.CanvasTexture(canvas);
            colorTex.wrapS = THREE.RepeatWrapping;

            const res = { colorTex, isLava };
            planetTextureCache[seed] = res;
            return res;
        }

        // ==========================================================================
        // PLANET CLUSTERS
        // ==========================================================================
        const sharedSphereGeom = new THREE.SphereGeometry(1, 24, 24);

        function createSystemCluster(cx, cy, cz) {
            const clusterKey = `${cx},${cy},${cz}`;
            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791) ^ GLOBAL_SEED;

            if (seededRandom(seed) > 0.50) return;

            const systemCenterX = (cx + 0.2 + seededRandom(seed + 10) * 0.6) * CLUSTER_GRID_SIZE;
            const systemCenterY = (cy + 0.2 + seededRandom(seed + 20) * 0.6) * CLUSTER_GRID_SIZE;
            const systemCenterZ = (cz + 0.2 + seededRandom(seed + 30) * 0.6) * CLUSTER_GRID_SIZE;

            const planetCount = 2 + Math.floor(seededRandom(seed + 40) * 2);

            for (let p = 0; p < planetCount; p++) {
                const pKey = `${clusterKey}_p${p}`;
                if (planetObjects[pKey]) continue;

                seed += 100;
                const angle = seededRandom(seed) * Math.PI * 2;
                const clusterOffsetDist = 40000 + seededRandom(seed + 1) * 40000;
                const altOffset = (seededRandom(seed + 2) - 0.5) * 20000;

                const px = systemCenterX + Math.cos(angle) * clusterOffsetDist;
                const py = systemCenterY + Math.sin(angle) * clusterOffsetDist;
                const pz = systemCenterZ + altOffset;
                const radius = 6000 + seededRandom(seed + 3) * 9000;

                const textures = generatePlanetTextures(seed);

                const mat = new THREE.MeshStandardMaterial({
                    map: textures.colorTex,
                    roughness: textures.isLava ? 0.4 : 0.7,
                    metalness: textures.isLava ? 0.3 : 0.1,
                    emissive: textures.isLava ? 0xff4400 : 0x000000,
                    emissiveIntensity: textures.isLava ? 0.8 : 0.0
                });

                const mesh = new THREE.Mesh(sharedSphereGeom, mat);
                mesh.scale.set(radius, radius, radius);
                mesh.position.set(px, pz, py);
                mesh.castShadow = true;

                scene.add(mesh);

                planetObjects[pKey] = {
                    mesh, x: px, y: py, z: pz, radius,
                    clusterKey, seed
                };
            }
        }

        function updatePlanetClusters(playerX, playerY, playerZ) {
            const chunkX = Math.floor(playerX / CLUSTER_GRID_SIZE);
            const chunkY = Math.floor(playerY / CLUSTER_GRID_SIZE);
            const chunkZ = Math.floor(playerZ / CLUSTER_GRID_SIZE);

            // Create visible clusters
            for (let x = -CLUSTER_DRAW_RADIUS; x <= CLUSTER_DRAW_RADIUS; x++) {
                for (let y = -CLUSTER_DRAW_RADIUS; y <= CLUSTER_DRAW_RADIUS; y++) {
                    for (let z = -CLUSTER_DRAW_RADIUS; z <= CLUSTER_DRAW_RADIUS; z++) {
                        createSystemCluster(chunkX + x, chunkY + y, chunkZ + z);
                    }
                }
            }

            // Unload far planets
            for (let key in planetObjects) {
                const planet = planetObjects[key];
                const dx = planet.x - playerX;
                const dy = planet.z - playerY;
                const dz = planet.y - playerZ;
                const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

                if (dist > UNLOAD_DISTANCE_THRESHOLD) {
                    scene.remove(planet.mesh);
                    planet.mesh.material.dispose();
                    delete planetObjects[key];
                }
            }

            document.getElementById('planet-count').innerText = Object.keys(planetObjects).length;
        }

        // ==========================================================================
        // NEAREST PLANET POINTER
        // ==========================================================================
        const arrowEl = document.getElementById('nav-arrow');
        const textEl = document.getElementById('nav-text');

        function updatePlanetPointer(playerX, playerY, playerZ) {
            let nearest = null;
            let minDist = Infinity;

            for (let key in planetObjects) {
                const p = planetObjects[key];
                const dx = p.x - playerX;
                const dy = p.z - playerY;
                const dz = p.y - playerZ;
                const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) - p.radius;

                if (dist < minDist) {
                    minDist = dist;
                    nearest = p;
                }
            }

            if (!nearest) {
                arrowEl.style.display = 'none';
                textEl.style.display = 'none';
                document.getElementById('nearest-dist').innerText = 'None';
                return;
            }

            document.getElementById('nearest-dist').innerText = Math.max(0, Math.round(minDist)) + 'm';

            const screenPos = new THREE.Vector3(nearest.x, nearest.z, nearest.y).project(camera);
            const w2 = window.innerWidth / 2;
            const h2 = window.innerHeight / 2;
            
            let sx = screenPos.x * w2 + w2;
            let sy = -screenPos.y * h2 + h2;

            const margin = 50;
            let edgeX = sx, edgeY = sy;

            if (screenPos.z > 1 || sx < margin || sx > window.innerWidth - margin || sy < margin || sy > window.innerHeight - margin) {
                const dx = (sx - w2) || 1;
                const dy = (sy - h2) || 1;
                const angle = Math.atan2(dy, dx);
                const scale = Math.min(Math.abs((w2 - margin) / Math.cos(angle)), Math.abs((h2 - margin) / Math.sin(angle)));
                edgeX = w2 + Math.cos(angle) * scale;
                edgeY = h2 + Math.sin(angle) * scale;
            }

            const angle = Math.atan2(sy - edgeY, sx - edgeX) + Math.PI / 2;
            arrowEl.style.display = 'block';
            arrowEl.style.left = (edgeX - 12) + 'px';
            arrowEl.style.top = (edgeY - 12) + 'px';
            arrowEl.style.transform = `rotate(${angle}rad)`;

            textEl.style.display = 'block';
            textEl.style.left = (edgeX - 20) + 'px';
            textEl.style.top = (edgeY + 15) + 'px';
        }

        // ==========================================================================
        // STARS
        // ==========================================================================
        function createStarField() {
            const STAR_COUNT = 400;
            const STAR_RADIUS = 12000;
            const positions = new Float32Array(STAR_COUNT * 3);
            const colors = new Float32Array(STAR_COUNT * 3);

            for (let i = 0; i < STAR_COUNT; i++) {
                const idx = i * 3;
                positions[idx] = (Math.random() - 0.5) * STAR_RADIUS * 2;
                positions[idx + 1] = (Math.random() - 0.5) * STAR_RADIUS * 2;
                positions[idx + 2] = (Math.random() - 0.5) * STAR_RADIUS * 2;

                const hue = Math.random();
                colors[idx] = 0.8 + Math.random() * 0.2;
                colors[idx + 1] = 0.8 + Math.random() * 0.2;
                colors[idx + 2] = 0.8 + Math.random() * 0.2;
            }

            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

            const mat = new THREE.PointsMaterial({
                size: 40,
                sizeAttenuation: true,
                transparent: true,
                vertexColors: true
            });

            const stars = new THREE.Points(geo, mat);
            stars.frustumCulled = false;
            return stars;
        }

        const starField = createStarField();
        scene.add(starField);

        // ==========================================================================
        // PARTICLES (TRAIL)
        // ==========================================================================
        const particleGeo = new THREE.SphereGeometry(0.8, 4, 4);

        function spawnTrailParticle(x, y, z) {
            if (trailParticles.length > 20) return;

            const mat = new THREE.MeshBasicMaterial({
                color: new THREE.Color().setHSL(Math.random() * 0.1 + 0.08, 1, 0.5),
                transparent: true
            });

            const particle = new THREE.Mesh(particleGeo, mat);
            particle.position.set(x, z, y);
            particle.scale.set(1, 1, 1);
            scene.add(particle);

            trailParticles.push({
                mesh: particle,
                life: 1.0,
                vx: (Math.random() - 0.5) * 2,
                vy: (Math.random() - 0.5) * 2,
                vz: (Math.random() - 0.5) * 2
            });
        }

        function updateParticles() {
            for (let i = trailParticles.length - 1; i >= 0; i--) {
                const p = trailParticles[i];
                p.life -= 0.08;
                p.mesh.scale.multiplyScalar(0.94);
                p.mesh.material.opacity = p.life;
                p.mesh.position.x += p.vx;
                p.mesh.position.y += p.vy;
                p.mesh.position.z += p.vz;

                if (p.life <= 0) {
                    scene.remove(p.mesh);
                    p.mesh.geometry.dispose();
                    p.mesh.material.dispose();
                    trailParticles.splice(i, 1);
                }
            }
        }

        // ==========================================================================
        // SHIP MODELS
        // ==========================================================================
        function createShipMesh(isLocal) {
            const group = new THREE.Group();

            const hullGeo = new THREE.ConeGeometry(8, 24, 6);
            const hullMat = new THREE.MeshStandardMaterial({
                color: isLocal ? 0x00ff88 : 0xff3344,
                roughness: 0.3,
                metalness: 0.7,
                emissive: isLocal ? 0x00aa44 : 0x552222,
                emissiveIntensity: 0.3
            });
            const hull = new THREE.Mesh(hullGeo, hullMat);
            hull.rotation.x = -Math.PI / 2;
            group.add(hull);

            // Engine glow
            const engineGeo = new THREE.CylinderGeometry(2.5, 0, 12, 8);
            const engineMat = new THREE.MeshBasicMaterial({
                color: 0xff5500,
                transparent: true,
                opacity: 0.8
            });
            const engine = new THREE.Mesh(engineGeo, engineMat);
            engine.rotation.x = -Math.PI / 2;
            engine.position.z = 14;
            group.add(engine);

            return group;
        }

        // ==========================================================================
        // STATION
        // ==========================================================================
        function createStation() {
            const group = new THREE.Group();

            const ringGeo = new THREE.TorusGeometry(80, 6, 16, 100);
            const ringMat = new THREE.MeshStandardMaterial({
                color: 0x00ffff,
                metalness: 0.9,
                roughness: 0.2,
                emissive: 0x0099ff,
                emissiveIntensity: 0.5
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            group.add(ring);

            const coreGeo = new THREE.SphereGeometry(25, 20, 20);
            const coreMat = new THREE.MeshStandardMaterial({
                color: 0x2244aa,
                metalness: 0.5,
                emissive: 0x114488,
                emissiveIntensity: 0.6
            });
            const core = new THREE.Mesh(coreGeo, coreMat);
            group.add(core);

            return group;
        }

        const stationMesh = createStation();
        scene.add(stationMesh);

        // ==========================================================================
        // INPUT HANDLING
        // ==========================================================================
        window.addEventListener('keydown', (e) => { keys[e.key.toLowerCase()] = true; });
        window.addEventListener('keyup', (e) => { keys[e.key.toLowerCase()] = false; });

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // ==========================================================================
        // WEBSOCKET
        // ==========================================================================
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'init') {
                localPlayerId = data.id;
                gameState.players[localPlayerId] = {
                    x: 200, y: 0, z: 0, angle: 0, vx: 0, vy: 0, vz: 0
                };
                return;
            }

            if (data.type === 'state') {
                const serverPlayers = data.gameState?.players || {};

                // Update/sync player states
                for (let id in serverPlayers) {
                    if (id !== localPlayerId) {
                        gameState.players[id] = serverPlayers[id];
                    } else if (!gameState.players[localPlayerId]) {
                        gameState.players[localPlayerId] = serverPlayers[id];
                    }
                }

                // Remove disconnected players
                for (let id in gameState.players) {
                    if (!serverPlayers[id] && id !== localPlayerId) {
                        delete gameState.players[id];
                        if (shipMeshes[id]) {
                            scene.remove(shipMeshes[id]);
                            delete shipMeshes[id];
                        }
                    }
                }

                document.getElementById('player-count').innerText = Object.keys(serverPlayers).length;
            }
        };

        // ==========================================================================
        // PHYSICS (CLIENT-SIDE)
        // ==========================================================================
        function updateLocalPhysics() {
            if (!localPlayerId || !gameState.players[localPlayerId]) return;

            const me = gameState.players[localPlayerId];
            me.vx ??= 0;
            me.vy ??= 0;
            me.vz ??= 0;

            const thrust = keys['w'] || keys['arrowup'];
            const boost = keys['shift'];
            const brake = keys['s'] || keys['arrowdown'];

            // Steering
            if (keys['a'] || keys['arrowleft']) me.angle -= 0.03;
            if (keys['d'] || keys['arrowright']) me.angle += 0.03;

            // Vertical
            if (keys['x']) me.vz += 0.85;
            if (keys['z']) me.vz -= 0.85;

            // Braking
            if (brake) {
                me.vx *= 0.92;
                me.vy *= 0.92;
                me.vz *= 0.92;
            }

            // Acceleration
            const maxSpeed = boost ? 100 : 50;
            let speed = Math.hypot(me.vx, me.vy, me.vz);

            if (thrust && speed < maxSpeed) {
                const accel = boost ? 1.0 : 0.3;
                const targetVx = Math.sin(me.angle) * (speed + accel);
                const targetVy = -Math.cos(me.angle) * (speed + accel);

                const grip = 0.04;
                me.vx += (targetVx - me.vx) * grip;
                me.vy += (targetVy - me.vy) * grip;

                // ===== CORRECTED PARTICLE OFFSETS =====
                // Engine is at position Z=14, so particles spawn BEHIND
                // Left jet offset: -sin(angle) * 40 for rear, -cos(angle) * 16 for left
                // Right jet offset: -sin(angle) * 40 for rear, +cos(angle) * 16 for right

                const rearDist = 40;
                const jetWidth = 18;

                const backX = -Math.sin(me.angle) * rearDist;
                const backY = Math.cos(me.angle) * rearDist;

                const sideX = Math.cos(me.angle) * jetWidth;
                const sideY = Math.sin(me.angle) * jetWidth;

                const leftX = me.x + backX - sideX;
                const leftY = me.y + backY - sideY;

                const rightX = me.x + backX + sideX;
                const rightY = me.y + backY + sideY;

                spawnTrailParticle(leftX, leftY, me.z - 3);
                spawnTrailParticle(rightX, rightY, me.z - 3);
            }

            speed = Math.hypot(me.vx, me.vy, me.vz);

            // Velocity clamping
            if (speed > maxSpeed) {
                const scale = maxSpeed / speed;
                me.vx *= scale;
                me.vy *= scale;
                me.vz *= scale;
            }

            // Natural decay
            if (!thrust) {
                me.vx *= 0.988;
                me.vy *= 0.988;
                me.vz *= 0.950;
            }

            // Position update
            me.x += me.vx;
            me.y += me.vy;
            me.z += me.vz;

            // Collision with planets
            for (let key in planetObjects) {
                const planet = planetObjects[key];
                const dx = me.x - planet.x;
                const dy = me.z - planet.z;
                const dz = me.y - planet.y;
                const dist = Math.hypot(dx, dy, dz);
                const minDist = planet.radius + 12;

                if (dist < minDist && dist > 0.1) {
                    const nx = dx / dist;
                    const ny = dy / dist;
                    const nz = dz / dist;

                    me.x += nx * (minDist - dist);
                    me.z += ny * (minDist - dist);
                    me.y += nz * (minDist - dist);

                    const dot = me.vx * nx + me.vz * ny + me.vy * nz;
                    if (dot < 0) {
                        me.vx = (me.vx - 2 * dot * nx) * 0.6;
                        me.vz = (me.vz - 2 * dot * ny) * 0.6;
                        me.vy = (me.vy - 2 * dot * nz) * 0.6;
                    }
                }
            }

            // Sync to server
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'sync',
                    x: me.x, y: me.y, z: me.z,
                    angle: me.angle,
                    vx: me.vx, vy: me.vy, vz: me.vz
                }));
            }
        }

        // ==========================================================================
        // CAMERA
        // ==========================================================================
        function updateCamera(me) {
            const dist = 140;
            const height = 50;

            const targetX = me.x - Math.sin(me.angle) * dist;
            const targetZ = me.y + Math.cos(me.angle) * dist;
            const targetY = me.z + height;

            camera.position.x += (targetX - camera.position.x) * 0.12;
            camera.position.z += (targetZ - camera.position.z) * 0.12;
            camera.position.y += (targetY - camera.position.y) * 0.12;

            const lookTarget = new THREE.Vector3(
                me.x + Math.sin(me.angle) * 40,
                me.z,
                me.y - Math.cos(me.angle) * 40
            );
            camera.lookAt(lookTarget);
        }

        // ==========================================================================
        // ANIMATION LOOP
        // ==========================================================================
        function animate() {
            requestAnimationFrame(animate);

            // Physics & input
            updateLocalPhysics();
            updateParticles();

            // Station rotation
            stationMesh.rotation.y += 0.003;

            // Player visuals
            for (let id in gameState.players) {
                const p = gameState.players[id];
                if (!p) continue;

                if (!shipMeshes[id]) {
                    shipMeshes[id] = createShipMesh(id === localPlayerId);
                    scene.add(shipMeshes[id]);
                }

                if (id === localPlayerId) {
                    shipMeshes[id].position.set(p.x, p.z || 0, p.y);
                    shipMeshes[id].rotation.y = -p.angle;
                } else {
                    const mesh = shipMeshes[id];
                    mesh.position.x += (p.x - mesh.position.x) * 0.2;
                    mesh.position.y += ((p.z || 0) - mesh.position.y) * 0.2;
                    mesh.position.z += (p.y - mesh.position.z) * 0.2;
                    mesh.rotation.y += (-p.angle - mesh.rotation.y) * 0.2;
                }
            }

            // World updates
            const me = gameState.players[localPlayerId];
            if (me) {
                updateCamera(me);
                updatePlanetClusters(me.x, me.z || 0, me.y);
                updatePlanetPointer(me.x, me.z || 0, me.y);

                const speed = Math.hypot(me.vx || 0, me.vy || 0, me.vz || 0).toFixed(1);
                document.getElementById('pos-x').innerText = Math.round(me.x);
                document.getElementById('pos-y').innerText = Math.round(me.y);
                document.getElementById('pos-z').innerText = Math.round(me.z || 0);
                document.getElementById('speed').innerText = speed;
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
