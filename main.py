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
    <!-- Three.js Core -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    
    <!-- OBJLoader extension -->
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/OBJLoader.js"></script>
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
</head>
<body>

    <!-- On-Screen Debug Box -->
    <div id="debug-log" style="position: fixed; top: 10px; left: 10px; width: 90%; max-height: 150px; overflow-y: auto; background: rgba(0,0,0,0.85); color: #ff5555; font-family: monospace; font-size: 12px; padding: 10px; border-radius: 5px; z-index: 99999; pointer-events: none;">
        <strong>Debug Log:</strong>
    </div>

    <script>
        // Catch every single JavaScript error and show it on screen
        window.onerror = function(msg, url, lineNo, columnNo, error) {
            const logBox = document.getElementById('debug-log');
            if (logBox) {
                logBox.innerHTML += `<br>❌ Error: ${msg} (Line ${lineNo})`;
            }
            return false;
        };
    </script>
    <div id="ui">
        <h3 style="margin-top: 0; color: #00ffff; text-shadow: 0 0 8px #00ffff;">3D Infinite Warp Flight Deck</h3>
        <p>Position: X <span id="pos-x" class="stat">0</span> | Z <span id="pos-z" class="stat">0</span> | Alt <span id="pos-y" class="stat">0</span></p>
        <p>Speed: <span id="speed" class="stat">0</span> m/s</p>
        <p>Pilots Online: <span id="player-count" class="stat">0</span></p>
        <p>Active Planets: <span id="planet-count" class="stat">0</span></p>
        <p>Nearest Planet: <span id="nearest-dist" class="stat">N/A</span></p>
        <p>Controls: WASD (Forward/Turn), X/Z (Ascend/Descend)</p>
        <p>Shift to boost</p>
    </div>

    <div id="nav-arrow"></div>
    <div id="nav-text">TARGET</div>

    <script>
        // Core Setup
        
        // Screen Logger Fallback
        window.onerror = function(msg, url, line) {
            let errDiv = document.getElementById('screen-log');
            if (!errDiv) {
                errDiv = document.createElement('div');
                errDiv.id = 'screen-log';
                errDiv.style.cssText = 'position:fixed; bottom:10px; left:10px; background:rgba(255,0,0,0.85); color:#fff; padding:10px; z-index:9999; font-size:12px; max-width:80%; word-break:break-all; border-radius:5px;';
                document.body.appendChild(errDiv);
            }
            errDiv.innerHTML += `<p style="margin:2px 0;">ERROR: ${msg} (Line ${line})</p>`;
        };
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020208, 0.00002);
        
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25));
        document.body.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 2.5);
        sunLight.position.set(50000, 100000, 50000);
        scene.add(sunLight);
        

        
        
        let loadedShipModel = null;

        function loadShipAssets() {
            if (typeof THREE === 'undefined') {
                document.getElementById('debug-log').innerHTML += `<br>❌ Three.js not loaded yet!`;
                return;
            }
        
            if (typeof THREE.OBJLoader === 'undefined') {
                document.getElementById('debug-log').innerHTML += `<br>❌ OBJLoader library missing! Make sure the script tag is in <head>`;
                return;
            }
        
            const objLoader = new THREE.OBJLoader();
            const cdnUrl = 'https://cdn.jsdelivr.net/gh/24lannonj-cmd/skibidi@main/ship.obj';
        
            // No Man's Sky Color Palette
            const redHullMat = new THREE.MeshStandardMaterial({ color: 0xd62222, roughness: 0.3, metalness: 0.1 });
            const whiteHullMat = new THREE.MeshStandardMaterial({ color: 0xf0f0f0, roughness: 0.3, metalness: 0.1 });
            const darkMetalMat = new THREE.MeshStandardMaterial({ color: 0x222225, roughness: 0.2, metalness: 0.9 });
            const glassMat = new THREE.MeshStandardMaterial({ color: 0x111115, roughness: 0.1, metalness: 0.9 });
        
            objLoader.load(
                cdnUrl, 
                function (obj) {
                    let meshCount = 0;
        
                    obj.traverse((child) => {
                        if (child && child.isMesh) {
                            const name = (child.name || '').toLowerCase();
                            if (name.includes('glass') || name.includes('cockpit')) {
                                child.material = glassMat;
                            } else if (name.includes('engine') || name.includes('metal')) {
                                child.material = darkMetalMat;
                            } else if (meshCount % 2 === 0) {
                                child.material = redHullMat;
                            } else {
                                child.material = whiteHullMat;
                            }
        
                            if (child.geometry) {
                                child.geometry.computeBoundingBox();
                                child.geometry.center();
                            }
                            meshCount++;
                        }
                    });
        
                    loadedShipModel = obj;
                    // Requested scale: (50, 50, 100)
                    loadedShipModel.scale.set(50, 50, 100); 
                    loadedShipModel.rotation.y = Math.PI;
        
                    document.getElementById('debug-log').innerHTML += `<br>✅ Ship model successfully loaded!`;
        
                    // Hot-swap fallback cones
                    if (typeof shipMeshes !== 'undefined') {
                        for (let id in shipMeshes) {
                            if (shipMeshes[id] && shipMeshes[id].children) {
                                while (shipMeshes[id].children.length > 0) { 
                                    shipMeshes[id].remove(shipMeshes[id].children[0]); 
                                }
                                shipMeshes[id].add(loadedShipModel.clone());
                            }
                        }
                    }
                },
                undefined,
                function (error) {
                    document.getElementById('debug-log').innerHTML += `<br>❌ Failed to fetch/parse ship.obj from CDN`;
                }
            );
        }
        // Trigger load
        loadShipAssets();
        function createShipMesh(isLocal) {
            const group = new THREE.Group();
            
            // 1. Temporary placeholder geometry
            const tempGeo = new THREE.ConeGeometry(5, 15, 8);
            const tempMat = new THREE.MeshBasicMaterial({ color: isLocal ? 0x00ff00 : 0xff0000 });
            const tempMesh = new THREE.Mesh(tempGeo, tempMat);
            tempMesh.rotation.x = Math.PI / 2;
            group.add(tempMesh);
            
            // 2. Load OBJ / GLTF model cleanly without forcing solid red
            if (typeof loadedShipModel !== 'undefined' && loadedShipModel) {
                group.remove(tempMesh);
                tempGeo.dispose();
                tempMat.dispose();

                const model = loadedShipModel.clone();
                // Ensure no global red material override is applied
                model.traverse((child) => {
                    if (child.isMesh) {
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });
                group.add(model);
            }

            return group;
        }
        const GLOBAL_SEED = 987654321;
        
        function seededRandom(seed) {
            let x = Math.sin(seed * 9999) * 10000;
            return x - Math.floor(x);
        }
        
        const planetTextureCache = {};
        // ==============================================================================
        // GLOBAL PLANET TEMPERATURE SYSTEM
        // ==============================================================================
        function generatePlanetTextures(seed) {
            if (planetTextureCache[seed]) {
                return planetTextureCache[seed];
            }

            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');

            let s = seed;
            const rand = () => { s += 1; return seededRandom(s); };

            // Determine planet temperature category (0.0 to 1.0)
            const globalTemp = rand(); 

            let baseColor, continentColor, detailColor, capColor, isLava = false;

            if (globalTemp > 0.82) {
                // EXTREME HOT: Volcanic Lava World
                baseColor = '#1a0b0b';       // Dark Basalt Crust
                continentColor = '#e63900';  // Molten Rivers
                detailColor = '#ffaa00';     // Glowing Magma Fissures
                capColor = null;             // No ice caps
                isLava = true;
            } else if (globalTemp > 0.62) {
                // HOT: Arid Desert Planet
                baseColor = '#8c593b';       // Dry Dunes
                continentColor = '#d99b00';  // Sand Basins
                detailColor = '#ffcc66';     // Salt Flats / Light Sand
                capColor = null;             // No ice caps
            } else if (globalTemp > 0.38) {
                // TEMPERATE: Earth-like Planet
                baseColor = '#0b3d91';       // Oceans
                continentColor = '#3a7d44';  // Foliage
                detailColor = '#24522c';     // Mountain ranges
                capColor = '#ffffff';        // Polar Caps
            } else if (globalTemp > 0.18) {
                // COLD: Tundra & Glacial World
                baseColor = '#2b4450';       // Frozen Deep Waters
                continentColor = '#607d8b';  // Rocky Tundra Lands
                detailColor = '#8ca3ad';     // Snow-dusted Peaks
                capColor = '#e0f7fa';        // Expanded Ice Caps
            } else {
                // EXTREME COLD: Frozen Ice World
                baseColor = '#b2ebf2';       // Glacial Ice Base
                continentColor = '#e0f7fa';  // Deep Snowfields
                detailColor = '#ffffff';     // Pure White Glaciers
                capColor = '#ffffff';        // Entirely Ice Capped
            }

            // 1. Draw Global Base Layer
            ctx.fillStyle = baseColor;
            ctx.fillRect(0, 0, 512, 256);

            // 2. Draw Temperature-Specific Surface Formations
            const continentCount = 4 + Math.floor(rand() * 5);

            for (let c = 0; c < continentCount; c++) {
                const cx = rand() * 512;
                const cy = rand() * 256;
                const radiusX = 40 + rand() * 80;
                const radiusY = 30 + rand() * 60;

                ctx.beginPath();
                const points = 12;
                for (let i = 0; i < points; i++) {
                    const angle = (i / points) * Math.PI * 2;
                    const rX = radiusX * (0.6 + rand() * 0.8);
                    const rY = radiusY * (0.6 + rand() * 0.8);
                    const px = cx + Math.cos(angle) * rX;
                    const py = cy + Math.sin(angle) * rY;

                    if (i === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                }
                ctx.closePath();
                ctx.fillStyle = continentColor;
                ctx.fill();

                // Detail Layer (Mountain Chains / Magma Veins)
                ctx.beginPath();
                for (let i = 0; i < points; i++) {
                    const angle = (i / points) * Math.PI * 2;
                    const rX = (radiusX * 0.4) * (0.6 + rand() * 0.6);
                    const rY = (radiusY * 0.4) * (0.6 + rand() * 0.6);
                    const px = cx + Math.cos(angle) * rX;
                    const py = cy + Math.sin(angle) * rY;

                    if (i === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                }
                ctx.closePath();
                ctx.fillStyle = detailColor;
                ctx.fill();
            }

            // 3. Ice Caps (Only apply if the temperature permits)
            if (capColor) {
                ctx.fillStyle = capColor;
                const capRadius = globalTemp < 0.18 ? 90 : 45 + rand() * 15;

                // North Cap
                ctx.beginPath();
                ctx.arc(256, 0, capRadius, 0, Math.PI * 2);
                ctx.fill();

                // South Cap
                ctx.beginPath();
                ctx.arc(256, 256, capRadius, 0, Math.PI * 2);
                ctx.fill();
            }

            const colorTex = new THREE.CanvasTexture(canvas);
            colorTex.wrapS = THREE.RepeatWrapping;
            colorTex.needsUpdate = true;

            const res = { colorTex, isLava };
            planetTextureCache[seed] = res;
            return res;
        }

        // ==============================================================================
        // PLANET CLUSTER SYSTEM MANAGER
        // ==============================================================================
        const CLUSTER_GRID_SIZE = 200000;
        const CLUSTER_DRAW_RADIUS = 1; 
        const UNLOAD_DISTANCE_THRESHOLD = 350000; 
        const planetObjects = {};

        const sharedSphereGeom = new THREE.SphereGeometry(1, 32, 32);

        function createSystemCluster(cx, cy, cz) {
            const clusterKey = `${cx},${cy},${cz}`;
            let seed = (cx * 73856093) ^ (cy * 19349663) ^ (cz * 83492791) ^ GLOBAL_SEED;

            if (seededRandom(seed) > 0.50) return;

            seed += 10;
            const systemCenterX = (cx + 0.2 + seededRandom(seed) * 0.6) * CLUSTER_GRID_SIZE;
            seed += 20;
            const systemCenterY = (cy + 0.2 + seededRandom(seed) * 0.6) * CLUSTER_GRID_SIZE;
            seed += 30;
            const systemCenterZ = (cz + 0.2 + seededRandom(seed) * 0.6) * CLUSTER_GRID_SIZE;

            seed += 40;
            const planetCount = 2 + Math.floor(seededRandom(seed) * 2);

            for (let p = 0; p < planetCount; p++) {
                const pKey = `${clusterKey}_p${p}`;
                if (planetObjects[pKey] !== undefined) continue;

                seed += 100 + p * 50;
                const angle = seededRandom(seed) * Math.PI * 2;
                
                seed += 101 + p * 50;
                const clusterOffsetDist = 40000 + seededRandom(seed) * 40000;
                
                seed += 102 + p * 50;
                const altOffset = (seededRandom(seed) - 0.5) * 20000;

                const px = systemCenterX + Math.cos(angle) * clusterOffsetDist;
                const py = systemCenterY + Math.sin(angle) * clusterOffsetDist;
                const pz = systemCenterZ + altOffset;

                seed += 103 + p * 50;
                const radius = 6000 + seededRandom(seed) * 9000;

                const textures = generatePlanetTextures(seed);

                const mat = new THREE.MeshStandardMaterial({ 
                    map: textures.colorTex,
                    roughness: textures.isLava ? 0.4 : 0.7,
                    metalness: textures.isLava ? 0.3 : 0.1,
                    emissiveMap: textures.isLava ? textures.colorTex : null,
                    emissive: textures.isLava ? 0xff4400 : 0x000000,
                    emissiveIntensity: textures.isLava ? 0.8 : 0.0
                });

                const mesh = new THREE.Mesh(sharedSphereGeom, mat);
                mesh.scale.set(radius, radius, radius);
                mesh.position.set(px, pz, py);

                scene.add(mesh);

                planetObjects[pKey] = {
                    mesh: mesh,
                    x: px,
                    y: py,
                    z: pz,
                    radius: radius,
                    clusterKey: clusterKey,
                    seed: seed
                };
            }
        }

        function updatePlanetClusters(playerX, playerY, playerZ) {
            const currentChunkX = Math.floor(playerX / CLUSTER_GRID_SIZE);
            const currentChunkY = Math.floor(playerY / CLUSTER_GRID_SIZE);
            const currentChunkZ = Math.floor(playerZ / CLUSTER_GRID_SIZE);

            for (let x = -CLUSTER_DRAW_RADIUS; x <= CLUSTER_DRAW_RADIUS; x++) {
                for (let y = -CLUSTER_DRAW_RADIUS; y <= CLUSTER_DRAW_RADIUS; y++) {
                    for (let z = -CLUSTER_DRAW_RADIUS; z <= CLUSTER_DRAW_RADIUS; z++) {
                        createSystemCluster(currentChunkX + x, currentChunkY + y, currentChunkZ + z);
                    }
                }
            }

            for (let key in planetObjects) {
                const planet = planetObjects[key];
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
                    delete planetObjects[key];
                }
            }

            let totalPlanets = 0;
            for (let key in planetObjects) {
                if (planetObjects[key]) totalPlanets++;
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

            for (let key in planetObjects) {
                const planet = planetObjects[key];
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
            canvas.width = 32;
            canvas.height = 32;
            const ctx = canvas.getContext('2d');

            const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
            gradient.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)'); 
            gradient.addColorStop(0.5, 'rgba(245, 245, 245, 0.3)');  
            gradient.addColorStop(1.0, 'rgba(0, 0, 0, 0)');        

            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, 32, 32);

            const tex = new THREE.CanvasTexture(canvas);
            tex.needsUpdate = true;
            return tex;
        }

        const TOTAL_STARS = 400;
        const STAR_FIELD_RADIUS = 12000;
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
            size: 60,
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
        const particleGeo = new THREE.SphereGeometry(1.2, 4, 4);
        const particleMat = new THREE.MeshBasicMaterial({ color: 0xff6600, transparent: true, opacity: 0.8 });

        function spawnTrailParticle(x, y, z, angle) {
            if (trailParticles.length > 12) return;
            const particle = new THREE.Mesh(particleGeo, particleMat.clone());
            particle.position.set(
                x - Math.sin(angle) * 12 + (Math.random() - 0.5) * 2,
                z + (Math.random() - 0.5) * 2,
                y + Math.cos(angle) * 12 + (Math.random() - 0.5) * 2
            );
            scene.add(particle);
            trailParticles.push({ mesh: particle, life: 1.0 });
        }

        // ==============================================================================
        // 3D MODEL FACTORIES
        // ==============================================================================
        
        function updateParticles() {
            for (let i = trailParticles.length - 1; i >= 0; i--) {
                const p = trailParticles[i];
                p.life -= 0.1;
                p.mesh.scale.multiplyScalar(0.92);
                p.mesh.material.opacity = p.life;

                if (p.life <= 0) {
                    scene.remove(p.mesh);
                    p.mesh.geometry.dispose();
                    p.mesh.material.dispose();
                    trailParticles.splice(i, 1);
                }
            }
        }

        // Helper to recursively dispose of group meshes when player disconnects
        function removeAndDisposeGroup(group) {
            scene.remove(group);
            group.traverse((child) => {
                if (child.isMesh) {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(m => m.dispose());
                        } else {
                            child.material.dispose();
                        }
                    }
                }
            });
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

            const engineGeo = new THREE.CylinderGeometry(2.5, 0, 14, 6);
            engineGeo.rotateX(-Math.PI / 2);
            const engineMat = new THREE.MeshStandardMaterial({ 
                color: 0xff5500,
                emissive: 0xff4400,
                emissiveIntensity: 2.0
            });
            const engine = new THREE.Mesh(engineGeo, engineMat);
            engine.position.z = 12;
            group.add(engine);

            return group;
        }

        function createStationMesh() {
            const group = new THREE.Group();
            const ringGeo = new THREE.TorusGeometry(80, 6, 8, 32);
            const ringMat = new THREE.MeshStandardMaterial({ color: 0x00ffff, metalness: 0.9, roughness: 0.2 });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            group.add(ring);

            const coreGeo = new THREE.SphereGeometry(25, 16, 16);
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
                // Ensure local player state exists immediately upon connection
                if (!gameState.players[localPlayerId]) {
                    gameState.players[localPlayerId] = { x: 200, y: 0, z: 0, angle: 0, vx: 0, vy: 0, vz: 0 };
                }
                return;
            }
        
            if (data.type === 'state') {
                const serverPlayers = data.gameState ? data.gameState.players : {};
        
                for (let id in serverPlayers) {
                    if (id !== localPlayerId) {
                        gameState.players[id] = serverPlayers[id];
                    } else if (!gameState.players[localPlayerId]) {
                        gameState.players[localPlayerId] = serverPlayers[id];
                    }
                }
        
                for (let id in gameState.players) {
                    if (!serverPlayers[id] && id !== localPlayerId) {
                        delete gameState.players[id];
                        if (shipMeshes[id]) {
                            scene.remove(shipMeshes[id]);
                            delete shipMeshes[id];
                        }
                    }
                }
        
                const playerCountEl = document.getElementById('player-count');
                if (playerCountEl) {
                    playerCountEl.innerText = Object.keys(serverPlayers).length;
                }
            }
        };
        // ========================================
        // PHYSICS
        // ========================================
        function updateLocalPhysics() {
            if (localPlayerId && gameState.players[localPlayerId]) {
                const me = gameState.players[localPlayerId];
                
                // 1. Sanitize velocity vectors
                if (!me.vx || isNaN(me.vx)) me.vx = 0;
                if (!me.vy || isNaN(me.vy)) me.vy = 0;
                if (!me.vz || isNaN(me.vz)) me.vz = 0;
                
                // 2. Read inputs
                const isThrusting = keys['ArrowUp'] || keys['w'] || keys['W'];
                const isBoosting = keys['Shift'];
                
                // Steering
                if (keys['ArrowLeft'] || keys['a'] || keys['A']) me.angle -= 0.03;
                if (keys['ArrowRight'] || keys['d'] || keys['D']) me.angle += 0.03;
                
                // Vertical movement controls (Z-axis)
                if (keys['x'] || keys['X']) me.vz += 0.85;
                if (keys['z'] || keys['Z']) me.vz -= 0.85;
                
                // Reverse / Braking key (S)
                if (keys['ArrowDown'] || keys['s'] || keys['S']) {
                    me.vx *= 0.90;
                    me.vy *= 0.90;
                    me.vz *= 0.90;
                }
        
                // 3. Speed Caps & Dynamic Acceleration
                const maxSpeed = isBoosting ? 100 : 50;
                let currentSpeed = Math.sqrt(me.vx * me.vx + me.vy * me.vy + me.vz * me.vz);
        
                // Apply forward engine thrust
                if (isThrusting) {
                    if (currentSpeed < maxSpeed) {
                        const baseAccel = isBoosting ? 1.0 : 0.3;
                        const dragFactor = 0.013;
                        const effectiveThrust = baseAccel + (currentSpeed * dragFactor);
        
                        // --- GRADUAL / SMOOTH VELOCITY BLENDING ---
                        const targetVx = Math.sin(me.angle) * (currentSpeed + effectiveThrust);
                        const targetVy = -Math.cos(me.angle) * (currentSpeed + effectiveThrust);
                        
                        const turnGrip = 0.035; 
                        me.vx += (targetVx - me.vx) * turnGrip;
                        me.vy += (targetVy - me.vy) * turnGrip;
                        
                        // --- DUAL JET ENGINE PARTICLE OFFSETS ---
                        const rearOffset = 38;
                        const jetWidth = 14.0; 
        
                        const backX = -Math.sin(me.angle) * rearOffset;
                        const backY = Math.cos(me.angle) * rearOffset;
        
                        const perpX = Math.cos(me.angle) * jetWidth;
                        const perpY = Math.sin(me.angle) * jetWidth;
        
                        const leftX = me.x + backX - perpX;
                        const leftY = me.y + backY - perpY;
        
                        const rightX = me.x + backX + perpX;
                        const rightY = me.y + backY + perpY;
        
                        if (typeof spawnTrailParticle === 'function') {
                            spawnTrailParticle(leftX, leftY, me.z, me.angle);
                            spawnTrailParticle(rightX, rightY, me.z, me.angle);
                        }
                    }
                    
                    currentSpeed = Math.sqrt(me.vx * me.vx + me.vy * me.vy + me.vz * me.vz);
                }
        
                // 4. Clamping & Decay Management
                if (currentSpeed > maxSpeed) {
                    if (isBoosting) {
                        const scale = maxSpeed / currentSpeed;
                        me.vx *= scale;
                        me.vy *= scale;
                        me.vz *= scale;
                    } else {
                        const decayRate = 0.99;
                        me.vx *= decayRate;
                        me.vy *= decayRate;
                        me.vz *= decayRate;
                    }
                } else if (isThrusting && !isBoosting && currentSpeed > 49.0) {
                    const scale = 50 / currentSpeed;
                    me.vx *= scale;
                    me.vy *= scale;
                    me.vz *= scale;
                } else if (!isThrusting) {
                    me.vx *= 0.987;
                    me.vy *= 0.987;
                    me.vz *= 0.950;
                }
        
                // 5. Update Position
                me.x += me.vx;
                me.y += me.vy;
                me.z += me.vz;
        
                // 6. Planetary Collision Resolution
                const shipRadius = 12;
                for (let key in planetObjects) {
                    const planet = planetObjects[key];
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
        
                // 7. Sync over WebSocket
                if (typeof ws !== 'undefined' && ws.readyState === WebSocket.OPEN) {
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

            // 1. Run local movement & physics
            if (typeof updateLocalPhysics === 'function') {
                updateLocalPhysics();
            }

            // 2. Update particles & station rotation
            if (typeof updateParticles === 'function') {
                updateParticles();
            }
            if (typeof stationMesh !== 'undefined' && stationMesh) {
                stationMesh.rotation.y += 0.005;
            }

            // 3. Update player ship meshes in 3D scene
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

            // 4. Update HUD, Camera, and Infinite World Clusters
            const me = gameState.players[localPlayerId];
            if (me) {
                if (typeof updateCameraPosition === 'function') updateCameraPosition(me);
                if (typeof updateStarPool === 'function') updateStarPool(me.x, me.z || 0, me.y);
                if (typeof updatePlanetClusters === 'function') updatePlanetClusters(me.x, me.z || 0, me.y);
                if (typeof updatePlanetPointer === 'function') updatePlanetPointer(me.x, me.z || 0, me.y);

                // Safe UI Updates
                const spd = Math.sqrt((me.vx||0)*(me.vx||0) + (me.vy||0)*(me.vy||0) + (me.vz||0)*(me.vz||0)).toFixed(1);
                const elX = document.getElementById('pos-x');
                const elZ = document.getElementById('pos-z');
                const elY = document.getElementById('pos-y');
                const elSpeed = document.getElementById('speed');

                if (elX) elX.innerText = Math.round(me.x);
                if (elZ) elZ.innerText = Math.round(me.y);
                if (elY) elY.innerText = Math.round(me.z || 0);
                if (elSpeed) elSpeed.innerText = spd;
            }

            // 5. Render Scene
            if (renderer && scene && camera) {
                renderer.render(scene, camera);
            }
        }

        // KICK OFF THE ANIMATION LOOP IMMEDIATELY
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
