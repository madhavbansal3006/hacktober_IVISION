'use client'

import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { MwsGeoJsonCollection, MwsGeoJsonFeature, WatershedDetail } from '../lib/types'
import { useLanguage } from '../lib/i18n/LanguageContext'

interface Gis3DTerrainProps {
  selectedMws?: string
  selectedId?: string
  gisBoundaries: MwsGeoJsonCollection | null
  onSelectMws?: (mwsId: string) => void
  selectedProfile?: WatershedDetail | null
  className?: string
  onSwitchTo2D?: () => void
}

interface DemTerrainData {
  source: string
  crs: string
  bounds: [number, number, number, number] // [west, south, east, north]
  grid_shape: [number, number]
  min_elevation: number
  max_elevation: number
  mean_elevation: number
  elevations: number[][]
  mws_elevation_stats: Record<
    string,
    {
      id: string
      MWS: string
      min: number
      max: number
      mean: number
      range: number
      slope_min?: number
      slope_max?: number
      slope_mean?: number
    }
  >
  total_mws: number
}

interface TerrainProbeState {
  interpolatedElevation: number
  clickedLng: number
  clickedLat: number
  mws?: string
  gisId?: string
}

// Point in polygon (Ray casting)
function pointInPolygon(point: [number, number], polygon: number[][][]): boolean {
  const [x, y] = point
  let inside = false

  for (const ring of polygon) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0]
      const yi = ring[i][1]
      const xj = ring[j][0]
      const yj = ring[j][1]

      const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
      if (intersect) inside = !inside
    }
  }
  return inside
}

function getFeatureCoordinates(feature: MwsGeoJsonFeature): number[][][][] {
  if (feature.geometry.type === 'Polygon') {
    return [feature.geometry.coordinates as number[][][]]
  } else if (feature.geometry.type === 'MultiPolygon') {
    return feature.geometry.coordinates as number[][][][]
  }
  return []
}

export function Gis3DTerrain({
  selectedMws,
  selectedId,
  gisBoundaries,
  onSelectMws,
  selectedProfile,
  className = '',
  onSwitchTo2D,
}: Gis3DTerrainProps) {
  const { dict, t } = useLanguage()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // State
  const [demData, setDemData] = useState<DemTerrainData | null>(null)
  const [talukGeoJson, setTalukGeoJson] = useState<any | null>(null)
  const [riversGeoJson, setRiversGeoJson] = useState<any | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // 3D Sub-Mode: 'terrain' | 'slope' | 'flood'
  const [subMode, setSubMode] = useState<'terrain' | 'slope' | 'flood'>('terrain')

  // Flood Scenario Controls
  const [waterLevel, setWaterLevel] = useState<number>(570.0) // Derived from GLO-30 DEM range (540m-650m)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [isFloodPanelCollapsed, setIsFloodPanelCollapsed] = useState<boolean>(false)

  // Terrain Probe State (Interactive Click-to-Inspect)
  const [probe, setProbe] = useState<TerrainProbeState | null>(null)
  const mouseDownPosRef = useRef<{ x: number; y: number } | null>(null)

  // Lightweight Scenario A/B Comparison State
  const [isCompareOpen, setIsCompareOpen] = useState<boolean>(false)
  const [scenarioALevel, setScenarioALevel] = useState<number>(570.0) // Existing preset default
  const [scenarioBLevel, setScenarioBLevel] = useState<number>(600.0) // Existing preset default

  // View Controls & Layers
  const [exaggeration, setExaggeration] = useState<number>(1.2)
  const [layerMws, setLayerMws] = useState<boolean>(true)
  const [layerStreams, setLayerStreams] = useState<boolean>(true)
  const [layerTaluk, setLayerTaluk] = useState<boolean>(true)
  const [layerPanelOpen, setLayerPanelOpen] = useState<boolean>(false)

  // Three.js internal handles stored in ref to avoid re-renders
  const sceneRef = useRef<{
    scene: THREE.Scene
    camera: THREE.PerspectiveCamera
    renderer: THREE.WebGLRenderer
    mesh: THREE.Mesh | null
    waterMesh: THREE.Mesh | null
    planeGeom: THREE.PlaneGeometry | null
    texture: THREE.CanvasTexture | null
    waterTexture: THREE.CanvasTexture | null
    wireframeMesh?: THREE.Mesh | null
    animId: number | null
    target: THREE.Vector3
    radius: number
    theta: number // Azimuth angle (horizontal)
    phi: number // Polar angle (vertical, 0 = top, PI/2 = ground)
  } | null>(null)

  // Load datasets on mount
  useEffect(() => {
    let active = true

    async function loadData() {
      try {
        setLoading(true)
        const [demRes, talukRes, riversRes] = await Promise.all([
          fetch('/data/shiggaon_dem_terrain.json'),
          fetch('/data/shiggaon_taluk_boundary.geojson').catch(() => null),
          fetch('/data/shiggaon_rivers.geojson').catch(() => null),
        ])

        if (!demRes.ok) {
          throw new Error(`Failed to load DEM dataset (${demRes.status})`)
        }

        const demJson = (await demRes.json()) as DemTerrainData
        const talukJson = talukRes && talukRes.ok ? await talukRes.json() : null
        const riversJson = riversRes && riversRes.ok ? await riversRes.json() : null

        if (active) {
          setDemData(demJson)
          if (talukJson) setTalukGeoJson(talukJson)
          if (riversJson) setRiversGeoJson(riversJson)
          setLoading(false)
        }
      } catch (err: any) {
        if (active) {
          console.error('3D Terrain load error:', err)
          setError(err.message || 'Error loading 3D elevation data')
          setLoading(false)
        }
      }
    }

    loadData()
    return () => {
      active = false
    }
  }, [])

  // Animation Loop for Flood Scenario Run
  useEffect(() => {
    if (!isPlaying || subMode !== 'flood') return

    const interval = setInterval(() => {
      setWaterLevel((prev) => {
        if (prev >= 640.0) {
          setIsPlaying(false)
          return 640.0
        }
        return Math.round((prev + 0.8) * 10) / 10
      })
    }, 120)

    return () => clearInterval(interval)
  }, [isPlaying, subMode])

  // Helper: Generate realistic DEM-conforming 3D water texture strictly masked to terrain-elevation flood extent
  const generateWaterTexture = useCallback((dem: DemTerrainData, floodLevel: number) => {
    const [rows, cols] = dem.grid_shape
    const canvas = document.createElement('canvas')
    canvas.width = cols
    canvas.height = rows
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    const imgData = ctx.createImageData(cols, rows)
    const data = imgData.data
    const grid = dem.elevations
    const minE = dem.min_elevation

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const elev = grid[r][c]
        const idx = (r * cols + c) * 4

        // Elevation-threshold scenario: only terrain within basin below scenario flood level
        if (elev >= minE - 1 && elev <= floodLevel) {
          const depth = floodLevel - elev
          // Subtle realistic water coloration graduated with depth
          let rC = 2
          let gC = 132
          let bC = 199
          let alpha = 160 // ~0.63 opacity

          if (depth <= 1.5) {
            // SHALLOW fringe (0–1.5 m)
            rC = 125
            gC = 211
            bC = 252
            alpha = 135
          } else if (depth <= 6.0) {
            // MODERATE (1.5–6 m)
            rC = 2
            gC = 132
            bC = 199
            alpha = 165
          } else {
            // DEEP depression (> 6 m) - visually stronger than shallow areas
            rC = 7
            gC = 89
            bC = 133
            alpha = 205
          }

          data[idx] = rC
          data[idx + 1] = gC
          data[idx + 2] = bC
          data[idx + 3] = alpha
        } else {
          // DRY upland or outside basin: 100% transparent (no floating water on dry ridges)
          data[idx] = 0
          data[idx + 1] = 0
          data[idx + 2] = 0
          data[idx + 3] = 0
        }
      }
    }
    ctx.putImageData(imgData, 0, 0)
    return canvas
  }, [])

  // Helper: Draw draped 2D texture containing hypsometric gradient, slope gradient, flood extent, streams, and boundaries
  const generateTexture = useCallback(
    (
      dem: DemTerrainData,
      activeMws?: string,
      activeId?: string,
      mode: 'terrain' | 'slope' | 'flood' = 'terrain',
      floodLevel?: number
    ) => {
      const canvas = document.createElement('canvas')
      const size = 1024
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')
      if (!ctx) return null

      const [west, south, east, north] = dem.bounds
      const dLng = east - west
      const dLat = north - south

      const lngToX = (lng: number) => ((lng - west) / dLng) * size
      const latToY = (lat: number) => (1 - (lat - south) / dLat) * size

      // 1. Draw base hypsometric or slope color ramp from DEM grid, with flood overlay if active
      const grid = dem.elevations
      const rows = grid.length
      const cols = grid[0].length
      const cellW = size / cols
      const cellH = size / rows

      const minE = dem.min_elevation
      const maxE = dem.max_elevation
      const rangeE = Math.max(1, maxE - minE)

      const isFlood = mode === 'flood'
      const isSlope = mode === 'slope'
      const targetFloodLevel = isFlood && floodLevel !== undefined ? floodLevel : -9999

      // Metric cell spacing for slope calculation
      const meanLat = ((north + south) / 2.0) * (Math.PI / 180)
      const cellDx = ((east - west) / cols) * 111320 * Math.cos(meanLat)
      const cellDy = ((north - south) / rows) * 110600

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const elev = grid[r][c]

          // Check slope condition: compute gradient in degrees
          if (isSlope) {
            const zL = grid[r][Math.max(0, c - 1)]
            const zR = grid[r][Math.min(cols - 1, c + 1)]
            const zT = grid[Math.max(0, r - 1)][c]
            const zB = grid[Math.min(rows - 1, r + 1)][c]

            const dz_dx = (zR - zL) / (c === 0 || c === cols - 1 ? cellDx : 2 * cellDx)
            const dz_dy = (zB - zT) / (r === 0 || r === rows - 1 ? cellDy : 2 * cellDy)
            const slopeDeg = Math.atan(Math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy)) * (180 / Math.PI)

            let rC = 0
            let gC = 0
            let bC = 0

            if (slopeDeg < 15.0) {
              const t = Math.max(0, Math.min(1, slopeDeg / 15.0))
              if (t < 0.5) {
                // 0° to 7.5°: #10b981 (16, 185, 129) -> #84cc16 (132, 204, 22)
                const k = t / 0.5
                rC = Math.round(16 + k * (132 - 16))
                gC = Math.round(185 + k * (204 - 185))
                bC = Math.round(129 + k * (22 - 129))
              } else {
                // 7.5° to 15°: #84cc16 (132, 204, 22) -> #eab308 (234, 179, 8)
                const k = (t - 0.5) / 0.5
                rC = Math.round(132 + k * (234 - 132))
                gC = Math.round(204 + k * (179 - 204))
                bC = Math.round(22 + k * (8 - 22))
              }
            } else if (slopeDeg < 30.0) {
              // 15° to 30°: #eab308 (234, 179, 8) -> #f97316 (249, 115, 22)
              const t = (slopeDeg - 15.0) / 15.0
              rC = Math.round(234 + t * (249 - 234))
              gC = Math.round(179 + t * (115 - 179))
              bC = Math.round(8 + t * (22 - 8))
            } else {
              // 30°+: #ef4444 (239, 68, 68) -> #991b1b (153, 27, 27)
              const t = Math.min(1.0, (slopeDeg - 30.0) / 15.0)
              rC = Math.round(239 + t * (153 - 239))
              gC = Math.round(68 + t * (27 - 68))
              bC = Math.round(68 + t * (27 - 68))
            }

            ctx.fillStyle = `rgb(${rC},${gC},${bC})`
            ctx.fillRect(c * cellW, r * cellH, cellW + 1, cellH + 1)
            continue
          }

          // Check flood condition: terrain elevation <= scenario water level
          if (isFlood && elev <= targetFloodLevel && elev >= minE - 2) {
            // DEM-derived scenario inundation depth = max(0, scenario_flood_level - DEM_elevation)
            const depth = Math.max(0, targetFloodLevel - elev)
            if (depth <= 1.5) {
              // SHALLOW (0–1.5 m) - light cyan shoreline fringe
              ctx.fillStyle = '#7dd3fc'
            } else if (depth <= 6.0) {
              // MODERATE (1.5–6 m) - vibrant azure
              ctx.fillStyle = '#0284c7'
            } else {
              // DEEP (> 6 m) - deep depression navy
              ctx.fillStyle = '#075985'
            }
            ctx.fillRect(c * cellW, r * cellH, cellW + 1, cellH + 1)
            continue
          }

          // Unflooded authentic hypsometric topography
          const t = Math.max(0, Math.min(1, (elev - minE) / rangeE))

          let rC = 0
          let gC = 0
          let bC = 0

          if (t < 0.25) {
            // Low valleys (540m - 590m) - valley green
            const k = t / 0.25
            rC = Math.round(42 + k * (76 - 42))
            gC = Math.round(92 + k * (128 - 92))
            bC = Math.round(62 + k * (84 - 62))
          } else if (t < 0.55) {
            // Mid plateaus (590m - 650m) - olive ochre
            const k = (t - 0.25) / 0.3
            rC = Math.round(76 + k * (145 - 76))
            gC = Math.round(128 + k * (132 - 128))
            bC = Math.round(84 + k * (72 - 84))
          } else if (t < 0.8) {
            // Rolling hills & ridges (650m - 695m) - warm amber / terracotta
            const k = (t - 0.55) / 0.25
            rC = Math.round(145 + k * (182 - 145))
            gC = Math.round(132 + k * (108 - 132))
            bC = Math.round(72 + k * (64 - 72))
          } else {
            // Highest ridges (695m - 738m) - stony umber
            const k = (t - 0.8) / 0.2
            rC = Math.round(182 + k * (198 - 182))
            gC = Math.round(108 + k * (82 - 108))
            bC = Math.round(64 + k * (68 - 64))
          }

          // In flood mode, slightly dim dry upland terrain so flood inundation pops
          if (isFlood) {
            rC = Math.round(rC * 0.88)
            gC = Math.round(gC * 0.88)
            bC = Math.round(bC * 0.88)
          }

          ctx.fillStyle = `rgb(${rC},${gC},${bC})`
          ctx.fillRect(c * cellW, r * cellH, cellW + 1, cellH + 1)
        }
      }

      // 2. Overlay 66 Micro-Watershed Boundaries & Highlight Selected MWS
      if (layerMws && gisBoundaries?.features) {
        for (const feature of gisBoundaries.features) {
          const isSelected =
            feature.properties.MWS === activeMws || feature.properties.id === activeId

          const multiPolys = getFeatureCoordinates(feature)
          for (const poly of multiPolys) {
            for (const ring of poly) {
              if (ring.length < 3) continue

              ctx.beginPath()
              const startX = lngToX(ring[0][0])
              const startY = latToY(ring[0][1])
              ctx.moveTo(startX, startY)

              for (let i = 1; i < ring.length; i++) {
                ctx.lineTo(lngToX(ring[i][0]), latToY(ring[i][1]))
              }
              ctx.closePath()

              if (isSelected) {
                ctx.fillStyle = 'rgba(59, 130, 246, 0.38)'
                ctx.fill()
                ctx.lineWidth = 4
                ctx.strokeStyle = '#60a5fa'
                ctx.stroke()
              } else {
                ctx.lineWidth = 1
                ctx.strokeStyle = isFlood
                  ? 'rgba(255, 255, 255, 0.45)'
                  : 'rgba(255, 255, 255, 0.38)'
                ctx.stroke()
              }
            }
          }
        }
      }

      // 3. Overlay Streams Network
      if (layerStreams && riversGeoJson?.features) {
        ctx.strokeStyle = isFlood ? '#67e8f9' : '#38bdf8'
        ctx.lineWidth = 2.4
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'

        for (const feature of riversGeoJson.features) {
          const geom = feature.geometry
          if (!geom) continue

          const lines =
            geom.type === 'LineString'
              ? [geom.coordinates]
              : geom.type === 'MultiLineString'
              ? geom.coordinates
              : []

          for (const coords of lines) {
            if (coords.length < 2) continue
            ctx.beginPath()
            ctx.moveTo(lngToX(coords[0][0]), latToY(coords[0][1]))
            for (let i = 1; i < coords.length; i++) {
              ctx.lineTo(lngToX(coords[i][0]), latToY(coords[i][1]))
            }
            ctx.stroke()
          }
        }
      }

      // 4. Overlay Taluk Administrative Boundary
      if (layerTaluk && talukGeoJson) {
        ctx.strokeStyle = '#f8fafc'
        ctx.lineWidth = 3.5
        ctx.setLineDash([8, 4])

        const features = talukGeoJson.features || [talukGeoJson]
        for (const feat of features) {
          const geom = feat.geometry
          if (!geom) continue
          const polys =
            geom.type === 'Polygon'
              ? [geom.coordinates]
              : geom.type === 'MultiPolygon'
              ? geom.coordinates
              : []

          for (const poly of polys) {
            for (const ring of poly) {
              if (ring.length < 3) continue
              ctx.beginPath()
              ctx.moveTo(lngToX(ring[0][0]), latToY(ring[0][1]))
              for (let i = 1; i < ring.length; i++) {
                ctx.lineTo(lngToX(ring[i][0]), latToY(ring[i][1]))
              }
              ctx.closePath()
              ctx.stroke()
            }
          }
        }
        ctx.setLineDash([])
      }

      return canvas
    },
    [layerMws, layerStreams, layerTaluk, gisBoundaries, riversGeoJson, talukGeoJson]
  )

  // Initialize and update Three.js canvas
  useEffect(() => {
    if (!canvasRef.current || !demData || loading) return

    const canvas = canvasRef.current
    const container = containerRef.current
    if (!container) return

    let width = container.clientWidth || 800
    let height = container.clientHeight || 560

    // 1. Scene & Camera
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0a0f18)

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000)

    // 2. Renderer
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        powerPreference: 'high-performance',
      })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(width, height)
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      renderer.toneMappingExposure = 1.05
    } catch (e) {
      console.error('WebGL initialization failed:', e)
      setError('WebGL is not available in your browser.')
      return
    }

    // 3. Lights (Sunlight for authentic hillshade)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.72)
    scene.add(ambientLight)

    const sunLight = new THREE.DirectionalLight(0xfffaed, 1.25)
    sunLight.position.set(-60, 90, 80)
    scene.add(sunLight)

    const fillLight = new THREE.DirectionalLight(0x90b0e0, 0.45)
    fillLight.position.set(60, -40, 40)
    scene.add(fillLight)

    // 4. Build 3D Terrain Mesh from DEM Grid
    const [west, south, east, north] = demData.bounds
    const dLng = east - west
    const dLat = north - south
    const meanLat = (south + north) / 2
    const aspect = (dLng * Math.cos((meanLat * Math.PI) / 180)) / dLat

    const meshWidth = 90 * aspect
    const meshHeight = 90
    const [rows, cols] = demData.grid_shape

    const planeGeom = new THREE.PlaneGeometry(meshWidth, meshHeight, cols - 1, rows - 1)

    // Displace vertices by elevation
    const pos = planeGeom.attributes.position
    const minE = demData.min_elevation
    const maxE = demData.max_elevation
    const rangeE = Math.max(1, maxE - minE)
    const elevGrid = demData.elevations

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const index = r * cols + c
        const elev = elevGrid[r][c]
        const normalizedZ = ((elev - minE) / rangeE) * 12 * exaggeration
        pos.setZ(index, normalizedZ)
      }
    }
    planeGeom.computeVertexNormals()

    // 5. Generate and drape texture
    const textureCanvas = generateTexture(
      demData,
      selectedMws,
      selectedId,
      subMode,
      waterLevel
    )
    const texture = textureCanvas ? new THREE.CanvasTexture(textureCanvas) : null
    if (texture) {
      texture.wrapS = THREE.ClampToEdgeWrapping
      texture.wrapT = THREE.ClampToEdgeWrapping
      texture.anisotropy = 4
      texture.needsUpdate = true
    }

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      roughness: 0.85,
      metalness: 0.08,
      flatShading: false,
    })

    const mesh = new THREE.Mesh(planeGeom, material)
    mesh.rotation.x = -Math.PI / 2
    scene.add(mesh)

    // 6. Realistic DEM-conforming 3D Water Surface for Flood Mode
    const waterGeom = new THREE.PlaneGeometry(meshWidth, meshHeight, 1, 1)
    const initialWaterCanvas = generateWaterTexture(demData, waterLevel)
    const initialWaterTex = initialWaterCanvas ? new THREE.CanvasTexture(initialWaterCanvas) : null
    if (initialWaterTex) {
      initialWaterTex.wrapS = THREE.ClampToEdgeWrapping
      initialWaterTex.wrapT = THREE.ClampToEdgeWrapping
      initialWaterTex.magFilter = THREE.LinearFilter
      initialWaterTex.minFilter = THREE.LinearFilter
      initialWaterTex.needsUpdate = true
    }

    const waterMat = new THREE.MeshStandardMaterial({
      map: initialWaterTex,
      transparent: true,
      roughness: 0.15,
      metalness: 0.12,
      depthWrite: false,
    })
    const waterMesh = new THREE.Mesh(waterGeom, waterMat)
    waterMesh.rotation.x = -Math.PI / 2
    const waterElevationZ = ((waterLevel - minE) / rangeE) * 12 * exaggeration
    waterMesh.position.y = waterElevationZ
    waterMesh.visible = subMode === 'flood' && waterLevel > minE
    scene.add(waterMesh)

    // 7. Camera Orbit Parameters
    const target = new THREE.Vector3(0, 2, 0)
    let radius = 120
    let theta = 0.2
    let phi = Math.PI / 3.4

    const updateCamera = () => {
      camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
      camera.position.y = target.y + radius * Math.cos(phi)
      camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
      camera.lookAt(target)
    }
    updateCamera()

    // Render loop
    let animId: number
    const animate = () => {
      animId = requestAnimationFrame(animate)
      renderer.render(scene, camera)
    }
    animId = requestAnimationFrame(animate)

    // Store handles
    sceneRef.current = {
      scene,
      camera,
      renderer,
      mesh,
      waterMesh,
      wireframeMesh: null,
      planeGeom,
      texture,
      waterTexture: initialWaterTex,
      animId,
      target,
      radius,
      theta,
      phi,
    }

    // Resize Observer
    const handleResize = () => {
      if (!container) return
      const w = container.clientWidth
      const h = container.clientHeight
      if (w > 0 && h > 0) {
        camera.aspect = w / h
        camera.updateProjectionMatrix()
        renderer.setSize(w, h)
      }
    }
    const observer = new ResizeObserver(handleResize)
    observer.observe(container)

    return () => {
      cancelAnimationFrame(animId)
      observer.disconnect()
      planeGeom.dispose()
      waterGeom.dispose()
      material.dispose()
      waterMat.dispose()
      if (texture) texture.dispose()
      if (initialWaterTex) initialWaterTex.dispose()
      renderer.dispose()
      sceneRef.current = null
    }
  }, [demData, loading, exaggeration, generateTexture, generateWaterTexture, selectedMws, selectedId, subMode])

  // Update texture & water mesh height when flood level, selection, or layers change
  useEffect(() => {
    if (!sceneRef.current || !demData) return
    const { mesh, waterMesh } = sceneRef.current
    if (!mesh) return

    const isFlood = subMode === 'flood'
    const newCanvas = generateTexture(
      demData,
      selectedMws,
      selectedId,
      subMode,
      waterLevel
    )
    if (!newCanvas) return

    const newTexture = new THREE.CanvasTexture(newCanvas)
    newTexture.wrapS = THREE.ClampToEdgeWrapping
    newTexture.wrapT = THREE.ClampToEdgeWrapping
    newTexture.anisotropy = 4
    newTexture.needsUpdate = true

    const oldMat = mesh.material as THREE.MeshStandardMaterial
    if (oldMat.map) oldMat.map.dispose()
    oldMat.map = newTexture
    oldMat.needsUpdate = true

    if (waterMesh) {
      const minE = demData.min_elevation
      const maxE = demData.max_elevation
      const rangeE = Math.max(1, maxE - minE)
      const waterElevationZ = ((waterLevel - minE) / rangeE) * 12 * exaggeration
      waterMesh.position.y = waterElevationZ
      waterMesh.visible = isFlood && waterLevel > minE

      if (isFlood) {
        const newWaterCanvas = generateWaterTexture(demData, waterLevel)
        if (newWaterCanvas) {
          const newWaterTex = new THREE.CanvasTexture(newWaterCanvas)
          newWaterTex.wrapS = THREE.ClampToEdgeWrapping
          newWaterTex.wrapT = THREE.ClampToEdgeWrapping
          newWaterTex.magFilter = THREE.LinearFilter
          newWaterTex.minFilter = THREE.LinearFilter
          newWaterTex.needsUpdate = true

          const oldWaterMat = waterMesh.material as THREE.MeshStandardMaterial
          if (oldWaterMat.map) oldWaterMat.map.dispose()
          oldWaterMat.map = newWaterTex
          oldWaterMat.needsUpdate = true
          sceneRef.current.waterTexture = newWaterTex
        }
      }
    }
  }, [generateTexture, generateWaterTexture, demData, selectedMws, selectedId, subMode, waterLevel, exaggeration])

  // Mouse Interaction (Orbit, Pan, Zoom)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let isDragging = false
    let isPanning = false
    let prevMouseX = 0
    let prevMouseY = 0

    const onMouseDown = (e: MouseEvent) => {
      mouseDownPosRef.current = { x: e.clientX, y: e.clientY }
      if (e.button === 0 && !e.shiftKey) {
        isDragging = true
      } else if (e.button === 2 || (e.button === 0 && e.shiftKey)) {
        isPanning = true
      }
      prevMouseX = e.clientX
      prevMouseY = e.clientY
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!sceneRef.current) return
      const deltaX = e.clientX - prevMouseX
      const deltaY = e.clientY - prevMouseY
      prevMouseX = e.clientX
      prevMouseY = e.clientY

      if (isDragging) {
        sceneRef.current.theta -= deltaX * 0.007
        sceneRef.current.phi = Math.max(
          0.15,
          Math.min(Math.PI / 2 - 0.05, sceneRef.current.phi - deltaY * 0.007)
        )

        const { camera, target, radius, theta, phi } = sceneRef.current
        camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
        camera.position.y = target.y + radius * Math.cos(phi)
        camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
        camera.lookAt(target)
      } else if (isPanning) {
        const { camera, target } = sceneRef.current
        const factor = 0.12
        const forward = new THREE.Vector3()
        camera.getWorldDirection(forward)
        forward.y = 0
        forward.normalize()

        const right = new THREE.Vector3()
        right.crossVectors(camera.up, forward).normalize()

        target.addScaledVector(right, deltaX * factor)
        target.addScaledVector(forward, deltaY * factor)

        const { radius, theta, phi } = sceneRef.current
        camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
        camera.position.y = target.y + radius * Math.cos(phi)
        camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
        camera.lookAt(target)
      }
    }

    const onMouseUp = () => {
      isDragging = false
      isPanning = false
    }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      if (!sceneRef.current) return
      const zoomFactor = e.deltaY > 0 ? 1.08 : 0.92
      sceneRef.current.radius = Math.max(30, Math.min(260, sceneRef.current.radius * zoomFactor))

      const { camera, target, radius, theta, phi } = sceneRef.current
      camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
      camera.position.y = target.y + radius * Math.cos(phi)
      camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
      camera.lookAt(target)
    }

    const onContextMenu = (e: MouseEvent) => {
      e.preventDefault()
    }

    canvas.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('contextmenu', onContextMenu)

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('contextmenu', onContextMenu)
    }
  }, [])

  // Raycasting for Click-to-Inspect Terrain Probe & MWS Selection in 3D
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!sceneRef.current || !demData) return
    const canvas = canvasRef.current
    if (!canvas) return

    // Drag-distance threshold: prevent orbit/pan from triggering probe
    if (mouseDownPosRef.current) {
      const dist = Math.hypot(
        e.clientX - mouseDownPosRef.current.x,
        e.clientY - mouseDownPosRef.current.y
      )
      if (dist > 5) return // Ignore click after drag
    }

    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1

    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera(new THREE.Vector2(x, y), sceneRef.current.camera)

    const intersects = raycaster.intersectObject(sceneRef.current.mesh!)
    if (intersects.length > 0 && intersects[0].uv) {
      const uv = intersects[0].uv
      const [west, south, east, north] = demData.bounds
      const clickedLng = west + uv.x * (east - west)
      const clickedLat = south + uv.y * (north - south)

      // Bilinear interpolation on DEM grid elevations
      const [rows, cols] = demData.grid_shape
      const gridR = (1 - uv.y) * (rows - 1)
      const gridC = uv.x * (cols - 1)
      const r0 = Math.max(0, Math.min(rows - 1, Math.floor(gridR)))
      const r1 = Math.max(0, Math.min(rows - 1, Math.ceil(gridR)))
      const c0 = Math.max(0, Math.min(cols - 1, Math.floor(gridC)))
      const c1 = Math.max(0, Math.min(cols - 1, Math.ceil(gridC)))
      const dr = gridR - r0
      const dc = gridC - c0

      const elevTop = (1 - dc) * demData.elevations[r0][c0] + dc * demData.elevations[r0][c1]
      const elevBottom = (1 - dc) * demData.elevations[r1][c0] + dc * demData.elevations[r1][c1]
      const interpolatedElev = (1 - dr) * elevTop + dr * elevBottom
      const roundedElevation = Math.round(interpolatedElev * 10) / 10

      let matchedMws: string | undefined = undefined
      let matchedGisId: string | undefined = undefined

      if (gisBoundaries?.features) {
        for (const feature of gisBoundaries.features) {
          const multiPolys = getFeatureCoordinates(feature)
          for (const poly of multiPolys) {
            if (pointInPolygon([clickedLng, clickedLat], poly)) {
              matchedMws = feature.properties.MWS
              matchedGisId = feature.properties.id
              const canonicalId = feature.properties.id || feature.properties.MWS
              if (onSelectMws) {
                onSelectMws(canonicalId)
              }
              break
            }
          }
          if (matchedMws) break
        }
      }

      setProbe({
        interpolatedElevation: roundedElevation,
        clickedLng,
        clickedLat,
        mws: matchedMws,
        gisId: matchedGisId,
      })
    }
  }

  // Camera Zoom In / Out / Reset
  const handleZoom = (direction: 'in' | 'out') => {
    if (!sceneRef.current) return
    const factor = direction === 'in' ? 0.85 : 1.15
    sceneRef.current.radius = Math.max(30, Math.min(260, sceneRef.current.radius * factor))
    const { camera, target, radius, theta, phi } = sceneRef.current
    camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
    camera.position.y = target.y + radius * Math.cos(phi)
    camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
    camera.lookAt(target)
  }

  const handleResetCamera = () => {
    if (!sceneRef.current) return
    sceneRef.current.target.set(0, 2, 0)
    sceneRef.current.radius = 120
    sceneRef.current.theta = 0.2
    sceneRef.current.phi = Math.PI / 3.4

    const { camera, target, radius, theta, phi } = sceneRef.current
    camera.position.x = target.x + radius * Math.sin(phi) * Math.sin(theta)
    camera.position.y = target.y + radius * Math.cos(phi)
    camera.position.z = target.z + radius * Math.sin(phi) * Math.cos(theta)
    camera.lookAt(target)
  }

  // Authoritative elevation statistics for currently selected MWS
  const selectedMwsStats =
    (selectedMws && demData?.mws_elevation_stats
      ? demData.mws_elevation_stats[selectedMws] ||
        (selectedId ? demData.mws_elevation_stats[selectedId] : null)
      : null) ||
    (selectedId && demData?.mws_elevation_stats
      ? demData.mws_elevation_stats[selectedId]
      : null)

  // Helper calculations for flood extent and depth screening
  const computeAffectedMws = useCallback(
    (level: number) => {
      if (!demData?.mws_elevation_stats) return 0
      let count = 0
      const seen = new Set<string>()
      for (const stats of Object.values(demData.mws_elevation_stats)) {
        if (stats.MWS && !seen.has(stats.MWS)) {
          seen.add(stats.MWS)
          if (stats.min <= level) {
            count++
          }
        }
      }
      return count
    },
    [demData]
  )

  const computeInundationPct = useCallback(
    (level: number) => {
      if (!demData) return 0
      const elevs = demData.elevations
      const minE = demData.min_elevation
      let totalTalukCells = 0
      let floodedCells = 0
      const rows = elevs.length
      const cols = elevs[0].length

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const e = elevs[r][c]
          if (e >= minE) {
            totalTalukCells++
            if (e <= level) {
              floodedCells++
            }
          }
        }
      }
      return totalTalukCells > 0 ? (floodedCells / totalTalukCells) * 100 : 0
    },
    [demData]
  )

  const computeMaxDepth = useCallback(
    (level: number) => {
      if (!demData) return 0
      return Math.max(0, level - demData.min_elevation)
    },
    [demData]
  )

  // Calculate potentially affected MWS count based on authentic DEM min elevation
  const affectedMwsCount = React.useMemo(() => {
    if (subMode !== 'flood') return 0
    return computeAffectedMws(waterLevel)
  }, [computeAffectedMws, subMode, waterLevel])

  // Calculate basin-wide terrain area below scenario flood level
  const basinInundationPct = React.useMemo(() => {
    if (subMode !== 'flood') return 0
    return computeInundationPct(waterLevel)
  }, [computeInundationPct, subMode, waterLevel])

  const isSelectedMwsAffected = Boolean(
    selectedMwsStats && selectedMwsStats.min <= waterLevel
  )

  const estimatedMaxDepth =
    isSelectedMwsAffected && selectedMwsStats
      ? Math.max(0, waterLevel - selectedMwsStats.min)
      : 0

  // Dynamic Terrain Probe calculations
  const probeDepth = probe ? Math.max(0, waterLevel - probe.interpolatedElevation) : 0
  const probeStatus = probe
    ? waterLevel > probe.interpolatedElevation
      ? 'INUNDATED'
      : 'DRY'
    : 'DRY'

  // Memoized Scenario A/B Comparison Metrics
  const statsA = React.useMemo(() => {
    return {
      affectedMws: computeAffectedMws(scenarioALevel),
      inundatedPct: computeInundationPct(scenarioALevel),
      maxDepth: computeMaxDepth(scenarioALevel),
      mwsMaxDepth: selectedMwsStats ? Math.max(0, scenarioALevel - selectedMwsStats.min) : null,
    }
  }, [computeAffectedMws, computeInundationPct, computeMaxDepth, scenarioALevel, selectedMwsStats])

  const statsB = React.useMemo(() => {
    return {
      affectedMws: computeAffectedMws(scenarioBLevel),
      inundatedPct: computeInundationPct(scenarioBLevel),
      maxDepth: computeMaxDepth(scenarioBLevel),
      mwsMaxDepth: selectedMwsStats ? Math.max(0, scenarioBLevel - selectedMwsStats.min) : null,
    }
  }, [computeAffectedMws, computeInundationPct, computeMaxDepth, scenarioBLevel, selectedMwsStats])

  // Risk-scaled scenario level (User Requirement 2)
  // formula: flood_level = selected_MWS_min_elevation + (flood_risk_score / 100) * 4.5
  const riskScaledScenarioLevel = React.useMemo(() => {
    if (!selectedMwsStats) return null
    const riskScore =
      selectedProfile?.risk?.flood_risk_score ??
      selectedProfile?.risk?.final_risk_score ??
      50.0
    const scaledLevel = selectedMwsStats.min + (riskScore / 100.0) * 4.5
    return Math.round(scaledLevel * 10) / 10
  }, [selectedMwsStats, selectedProfile])

  // Illustrative DEM-based scenario presets (User Requirement 1)
  const SCENARIO_PRESETS = [
    { label: '540m', full: '540m (Baseline)', level: 540.0, desc: 'Outlet threshold' },
    { label: '550m', full: '550m (Minor)', level: 550.0, desc: '6 MWS affected' },
    { label: '570m', full: '570m (Moderate)', level: 570.0, desc: 'Default scenario' },
    { label: '600m', full: '600m (High)', level: 600.0, desc: '29 MWS affected' },
    { label: '620m', full: '620m (Severe)', level: 620.0, desc: '43 MWS affected' },
    { label: '640m', full: '640m (Extreme)', level: 640.0, desc: '56 MWS affected' },
  ]

  // Fallback View if Error or WebGL unavailable (Requirement 11)
  if (error) {
    return (
      <div
        className={`gis-container relative flex flex-col items-center justify-center p-8 text-center ${className}`}
        style={{ height: '560px', background: 'var(--panel)' }}
      >
        <div style={{ maxWidth: '480px' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🌊</div>
          <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
            {dict.gis3d.demUnavailable}
          </h3>
          <p style={{ color: 'var(--muted)', fontSize: '13px', marginBottom: '20px' }}>
            {error}. {dict.gis3d.demUnavailableDesc}
          </p>
          {onSwitchTo2D && (
            <button className="primary-button" onClick={onSwitchTo2D}>
              {dict.gis3d.switchTo2d}
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      className={`gis-container relative overflow-hidden select-none ${className}`}
      style={{
        height: '560px',
        background: '#0a0f18',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'row',
      }}
    >
      {/* 3D Viewport Area (Main Focus) */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          height: '100%',
          position: 'relative',
          overflow: 'hidden',
          minWidth: 0,
        }}
      >
        {/* 3D WebGL Canvas */}
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
            cursor: 'grab',
          }}
        />

      {/* Loading Overlay */}
      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(10, 15, 24, 0.85)',
            zIndex: 30,
            backdropFilter: 'blur(4px)',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                display: 'inline-block',
                width: '28px',
                height: '28px',
                border: '3px solid rgba(255,255,255,0.2)',
                borderTopColor: 'var(--accent)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
                marginBottom: '10px',
              }}
            />
            <div style={{ fontSize: '13px', color: '#e2e8f0', fontWeight: 500 }}>
              {dict.gis3d.loadingDem}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
              {dict.gis3d.loadingDemSub}
            </div>
          </div>
        </div>
      )}

      {/* Top Left: Sub-Mode Switch & 3D Status Badges */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 20,
        }}
      >
        {/* [ Terrain ] [ Slope ] [ Flood Scenario ] Mode Switch */}
        <div
          className="mode-control"
          role="group"
          aria-label="3D View Sub-mode"
          style={{ border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(15, 23, 42, 0.88)' }}
        >
          <button
            aria-pressed={subMode === 'terrain'}
            className={subMode === 'terrain' ? 'selected' : ''}
            onClick={() => {
              setSubMode('terrain')
              setIsPlaying(false)
            }}
          >
            {dict.gis3d.modeTerrain}
          </button>
          <button
            aria-pressed={subMode === 'slope'}
            className={subMode === 'slope' ? 'selected' : ''}
            onClick={() => {
              setSubMode('slope')
              setIsPlaying(false)
            }}
          >
            {dict.gis3d.modeSlope}
          </button>
          <button
            aria-pressed={subMode === 'flood'}
            className={subMode === 'flood' ? 'selected' : ''}
            onClick={() => setSubMode('flood')}
          >
            {dict.gis3d.modeFlood}
          </button>
        </div>

        {/* Status Indicator */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            backdropFilter: 'blur(8px)',
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '10.5px',
            fontWeight: 600,
            color: '#f8fafc',
            letterSpacing: '0.04em',
            width: 'fit-content',
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: loading
                ? '#f59e0b'
                : subMode === 'flood'
                ? '#38bdf8'
                : subMode === 'slope'
                ? '#eab308'
                : '#10b981',
              boxShadow: loading
                ? '0 0 8px #f59e0b'
                : subMode === 'flood'
                ? '0 0 8px #38bdf8'
                : subMode === 'slope'
                ? '0 0 8px #eab308'
                : '0 0 8px #10b981',
            }}
          />
          {loading
            ? dict.gis3d.statusDemLoading
            : subMode === 'flood'
            ? dict.gis3d.statusFloodActive
            : subMode === 'slope'
            ? dict.gis3d.statusSlopeActive
            : dict.gis3d.statusTerrainActive}
        </div>

        {subMode === 'terrain' && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(15, 23, 42, 0.75)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              backdropFilter: 'blur(6px)',
              borderRadius: '6px',
              padding: '3px 8px',
              fontSize: '9.5px',
              fontWeight: 500,
              color: 'var(--muted)',
              width: 'fit-content',
            }}
          >
            <span>{dict.gis3d.terrainSourceBadge}</span>
          </div>
        )}

        {subMode === 'flood' && isFloodPanelCollapsed && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '7px',
              background: 'rgba(15, 23, 42, 0.92)',
              border: '1px solid rgba(56, 189, 248, 0.45)',
              backdropFilter: 'blur(10px)',
              borderRadius: '6px',
              padding: '4px 8px',
              fontSize: '10.5px',
              color: '#f8fafc',
              boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
              width: 'fit-content',
            }}
          >
            <span style={{ color: '#38bdf8', fontWeight: 600 }}>🌊 {waterLevel.toFixed(1)}m</span>
            <span style={{ color: 'var(--muted)', fontSize: '9.5px' }}>
              {dict.gis3d.mwsAffected.replace('{count}', String(affectedMwsCount))}
            </span>
            {isCompareOpen && (
              <span style={{ display: 'inline-flex', gap: '3px' }}>
                <button
                  onClick={() => {
                    setWaterLevel(scenarioALevel)
                    setIsPlaying(false)
                  }}
                  title="Render Scenario A in 3D"
                  style={{
                    padding: '2px 5px',
                    borderRadius: '3px',
                    background:
                      Math.abs(waterLevel - scenarioALevel) < 0.2
                        ? 'rgba(56, 189, 248, 0.4)'
                        : 'rgba(56, 189, 248, 0.12)',
                    border: '1px solid #38bdf8',
                    color: '#38bdf8',
                    fontSize: '9px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  A: {scenarioALevel}m
                </button>
                <button
                  onClick={() => {
                    setWaterLevel(scenarioBLevel)
                    setIsPlaying(false)
                  }}
                  title="Render Scenario B in 3D"
                  style={{
                    padding: '2px 5px',
                    borderRadius: '3px',
                    background:
                      Math.abs(waterLevel - scenarioBLevel) < 0.2
                        ? 'rgba(251, 191, 36, 0.4)'
                        : 'rgba(251, 191, 36, 0.12)',
                    border: '1px solid #fbbf24',
                    color: '#fbbf24',
                    fontSize: '9px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  B: {scenarioBLevel}m
                </button>
              </span>
            )}
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              style={{
                padding: '2px 7px',
                borderRadius: '3px',
                background: isPlaying ? 'var(--amber)' : '#0284c7',
                border: 'none',
                color: '#fff',
                fontSize: '9px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {isPlaying ? dict.gis3d.btnPause : dict.gis3d.btnRun}
            </button>
            <button
              onClick={() => setIsFloodPanelCollapsed(false)}
              title={dict.gis3d.showFloodControls}
              style={{
                padding: '2px 8px',
                borderRadius: '3px',
                background: 'rgba(56, 189, 248, 0.16)',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                color: '#38bdf8',
                fontSize: '9.5px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ⚙ Controls ◀
            </button>
          </div>
        )}
      </div>

      {/* Top Right: Camera & Layer Controls */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: '8px',
          zIndex: 20,
        }}
      >
        {/* Camera Action Buttons */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            backdropFilter: 'blur(8px)',
            borderRadius: '6px',
            padding: '4px',
          }}
        >
          <button
            onClick={() => handleZoom('in')}
            title="Zoom In"
            style={{
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              color: '#f8fafc',
              fontSize: '15px',
              fontWeight: 600,
              cursor: 'pointer',
              borderRadius: '4px',
            }}
          >
            +
          </button>
          <button
            onClick={() => handleZoom('out')}
            title="Zoom Out"
            style={{
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              color: '#f8fafc',
              fontSize: '15px',
              fontWeight: 600,
              cursor: 'pointer',
              borderRadius: '4px',
            }}
          >
            −
          </button>
          <button
            onClick={handleResetCamera}
            title="Reset Perspective"
            style={{
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              color: '#f8fafc',
              fontSize: '13px',
              cursor: 'pointer',
              borderRadius: '4px',
            }}
          >
            ⟳
          </button>
          <button
            onClick={() => setLayerPanelOpen(!layerPanelOpen)}
            title="Toggle Map Layers & Terrain Exaggeration"
            style={{
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: layerPanelOpen ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
              border: 'none',
              color: layerPanelOpen ? '#38bdf8' : '#f8fafc',
              fontSize: '13px',
              cursor: 'pointer',
              borderRadius: '4px',
            }}
          >
            🗺
          </button>
        </div>

        {/* Exaggeration & Layer Toggles Panel (Toggled via 🗺 button) */}
        {layerPanelOpen && (
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.92)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              backdropFilter: 'blur(10px)',
              borderRadius: '6px',
              padding: '8px 10px',
              fontSize: '11px',
              color: '#e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              minWidth: '160px',
              boxShadow: '0 6px 16px rgba(0,0,0,0.4)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontWeight: 600,
                fontSize: '10.5px',
                color: 'var(--muted)',
                marginBottom: '2px',
              }}
            >
              <span>{dict.gis3d.terrainExaggeration}</span>
              <span style={{ color: '#60a5fa' }}>{exaggeration.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="1.0"
              max="2.0"
              step="0.1"
              value={exaggeration}
              onChange={(e) => setExaggeration(parseFloat(e.target.value))}
              style={{ width: '100%', cursor: 'pointer', height: '4px', accentColor: '#3b82f6' }}
            />

            <div
              style={{
                borderTop: '1px solid rgba(255,255,255,0.1)',
                marginTop: '4px',
                paddingTop: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  fontSize: '10.5px',
                }}
              >
                <input
                  type="checkbox"
                  checked={layerMws}
                  onChange={(e) => setLayerMws(e.target.checked)}
                  style={{ accentColor: '#3b82f6' }}
                />
                <span>{dict.gis3d.boundaries66}</span>
              </label>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  fontSize: '10.5px',
                }}
              >
                <input
                  type="checkbox"
                  checked={layerStreams}
                  onChange={(e) => setLayerStreams(e.target.checked)}
                  style={{ accentColor: '#38bdf8' }}
                />
                <span>{dict.gis3d.streamsDrainage}</span>
              </label>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  fontSize: '10.5px',
                }}
              >
                <input
                  type="checkbox"
                  checked={layerTaluk}
                  onChange={(e) => setLayerTaluk(e.target.checked)}
                  style={{ accentColor: '#f8fafc' }}
                />
                <span>{dict.gis3d.talukBoundary}</span>
              </label>
            </div>
          </div>
        )}
      </div>



      {/* Floating Panel: Slope Analysis Controls & HUD (When Slope Mode Active) */}
      {subMode === 'slope' && (
        <div
          style={{
            position: 'absolute',
            top: '76px',
            left: '12px',
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(234, 179, 8, 0.35)',
            backdropFilter: 'blur(10px)',
            borderRadius: '6px',
            padding: '7px 9px',
            zIndex: 20,
            width: '240px',
            boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '2px',
            }}
          >
            <span
              style={{
                fontSize: '9.5px',
                fontWeight: 700,
                color: '#facc15',
                letterSpacing: '0.04em',
              }}
            >
              {dict.gis3d.slopeHeatmapTitle}
            </span>
            <span
              style={{
                fontSize: '7.5px',
                fontWeight: 700,
                padding: '1px 4px',
                borderRadius: '3px',
                background: 'rgba(234, 179, 8, 0.18)',
                color: '#facc15',
              }}
            >
              DEM-DERIVED
            </span>
          </div>

          <p
            style={{
              fontSize: '8.5px',
              color: 'var(--muted)',
              margin: '1px 0 5px 0',
              lineHeight: 1.25,
            }}
          >
            Topographic gradient in degrees derived from Copernicus GLO-30 DEM.
          </p>

          {/* Legend showing degrees */}
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '4px',
              padding: '4px 6px',
              border: '1px solid rgba(255,255,255,0.06)',
              marginBottom: '5px',
              display: 'flex',
              flexDirection: 'column',
              gap: '3px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '8px',
                color: 'var(--muted)',
                marginBottom: '1px',
              }}
            >
              <span style={{ fontWeight: 600 }}>SLOPE GRADIENT</span>
              <span>DEGREES (°)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '8px', color: '#e2e8f0' }}>
                <span style={{ width: '7px', height: '7px', background: '#10b981', borderRadius: '2px' }} />
                <span>0°–5° → {dict.risk.low}</span>
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '8px', color: '#e2e8f0' }}>
                <span style={{ width: '7px', height: '7px', background: '#eab308', borderRadius: '2px' }} />
                <span>5°–30° → {dict.risk.moderate}</span>
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '8px', color: '#e2e8f0' }}>
                <span style={{ width: '7px', height: '7px', background: '#ef4444', borderRadius: '2px' }} />
                <span>30°+ → {dict.gis3d.slopeSteep}</span>
              </span>
            </div>
          </div>

          {/* Selected MWS Slope Stats */}
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '4px',
              padding: '5px 7px',
              border: '1px solid rgba(255,255,255,0.06)',
              marginBottom: '5px',
              fontSize: '9px',
            }}
          >
            {selectedMwsStats ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                  <span style={{ color: 'var(--muted)' }}>Selected MWS:</span>
                  <strong style={{ color: '#38bdf8' }}>{selectedMws || selectedProfile?.MWS}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '8.5px' }}>
                  <span style={{ color: 'var(--muted)' }}>GIS ID:</span>
                  <span style={{ color: '#cbd5e1' }}>{selectedId || selectedProfile?.id}</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 1fr',
                    gap: '4px',
                    paddingTop: '3px',
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '2px', borderRadius: '3px' }}>
                    <div style={{ color: 'var(--muted)', fontSize: '8px' }}>Min Slope</div>
                    <div style={{ color: '#34d399', fontWeight: 600, fontSize: '9.5px', fontFamily: 'var(--font-mono, monospace)' }}>
                      {(selectedMwsStats.slope_min ?? 0.0).toFixed(1)}°
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '2px', borderRadius: '3px' }}>
                    <div style={{ color: 'var(--muted)', fontSize: '8px' }}>Mean Slope</div>
                    <div style={{ color: '#fbbf24', fontWeight: 600, fontSize: '9.5px', fontFamily: 'var(--font-mono, monospace)' }}>
                      {(selectedMwsStats.slope_mean ?? 0.0).toFixed(1)}°
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '2px', borderRadius: '3px' }}>
                    <div style={{ color: 'var(--muted)', fontSize: '8px' }}>Max Slope</div>
                    <div
                      style={{
                        color: (selectedMwsStats.slope_max ?? 0) >= 30 ? '#f87171' : (selectedMwsStats.slope_max ?? 0) >= 15 ? '#fbbf24' : '#34d399',
                        fontWeight: 600,
                        fontSize: '9.5px',
                        fontFamily: 'var(--font-mono, monospace)',
                      }}
                    >
                      {(selectedMwsStats.slope_max ?? 0.0).toFixed(1)}°
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: '3px', paddingTop: '3px', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)', fontSize: '8px' }}>Classification:</span>
                  <span
                    style={{
                      fontSize: '8px',
                      fontWeight: 600,
                      color:
                        (selectedMwsStats.slope_max ?? 0) >= 30
                          ? '#f87171'
                          : (selectedMwsStats.slope_mean ?? 0) >= 5
                          ? '#fbbf24'
                          : '#34d399',
                    }}
                  >
                    {(selectedMwsStats.slope_max ?? 0) >= 30
                      ? 'Steep (>30°)'
                      : (selectedMwsStats.slope_mean ?? 0) >= 5
                      ? 'Moderate (5°–30°)'
                      : 'Low (<5°)'}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--muted)', padding: '3px 0' }}>
                <div>Click any micro-watershed to view slope statistics</div>
                <div style={{ fontSize: '8px', color: '#94a3b8', marginTop: '2px' }}>
                  Basin Relief: {demData?.min_elevation}m – {demData?.max_elevation}m
                </div>
              </div>
            )}
          </div>

          {/* Footer note */}
          <div
            style={{
              borderTop: '1px solid rgba(255,255,255,0.08)',
              paddingTop: '4px',
              fontSize: '8px',
              color: 'var(--muted)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>Copernicus GLO-30 DEM (30m)</span>
            <span>Mode: <strong style={{ color: '#facc15' }}>SLOPE</strong></span>
          </div>
        </div>
      )}

      {/* Bottom Left: Selected Catchment Info HUD (When Flood Mode Inactive) */}
      {subMode === 'terrain' && selectedMws && (
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            background: 'rgba(15, 23, 42, 0.88)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            backdropFilter: 'blur(10px)',
            borderRadius: '8px',
            padding: '10px 14px',
            zIndex: 20,
            maxWidth: '320px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '4px',
            }}
          >
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc', letterSpacing: '0.02em' }}>
                Selected MWS: <span style={{ color: '#38bdf8' }}>{selectedMws || selectedProfile?.MWS}</span>
              </div>
              <div style={{ fontSize: '10.5px', color: 'var(--muted)', marginTop: '2px' }}>
                GIS ID: {selectedId || selectedProfile?.id}
              </div>
            </div>

            <span
              style={{
                fontSize: '9.5px',
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: '4px',
                letterSpacing: '0.04em',
                backgroundColor:
                  selectedProfile?.risk?.risk_category === 'CRITICAL'
                    ? 'rgba(239, 68, 68, 0.25)'
                    : selectedProfile?.risk?.risk_category === 'HIGH'
                    ? 'rgba(245, 158, 11, 0.25)'
                    : 'rgba(16, 185, 129, 0.25)',
                color:
                  selectedProfile?.risk?.risk_category === 'CRITICAL'
                    ? '#f87171'
                    : selectedProfile?.risk?.risk_category === 'HIGH'
                    ? '#fbbf24'
                    : '#34d399',
                border:
                  selectedProfile?.risk?.risk_category === 'CRITICAL'
                    ? '1px solid rgba(239, 68, 68, 0.4)'
                    : selectedProfile?.risk?.risk_category === 'HIGH'
                    ? '1px solid rgba(245, 158, 11, 0.4)'
                    : '1px solid rgba(16, 185, 129, 0.4)',
              }}
            >
              {selectedProfile?.risk?.risk_category || 'HIGH'}
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '6px 12px',
              fontSize: '10.5px',
              color: '#cbd5e1',
              marginTop: '6px',
              paddingTop: '6px',
              borderTop: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <div>
              <span style={{ color: 'var(--muted)' }}>Risk Score: </span>
              <strong style={{ color: '#f8fafc' }}>
                {selectedProfile?.risk?.final_risk_score ?? '55.27'}
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--muted)' }}>Area: </span>
              <strong style={{ color: '#f8fafc' }}>
                {selectedProfile?.area_km2 ?? '14.24'} km²
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--muted)' }}>Stream: </span>
              <strong style={{ color: '#f8fafc' }}>
                {selectedProfile?.stream_length_km ?? '2.62'} km
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--muted)' }}>Driver: </span>
              <strong style={{ color: '#f8fafc' }}>
                {selectedProfile?.risk?.primary_risk_driver ?? 'Water Stress'}
              </strong>
            </div>
          </div>

          {/* Real Copernicus DEM Elevation Statistics */}
          <div
            style={{
              marginTop: '8px',
              paddingTop: '6px',
              borderTop: '1px solid rgba(255,255,255,0.1)',
              fontSize: '10px',
            }}
          >
            <div
              style={{
                color: 'var(--muted)',
                fontWeight: 600,
                letterSpacing: '0.04em',
                marginBottom: '3px',
              }}
            >
              ELEVATION (COPERNICUS GLO-30)
            </div>
            {selectedMwsStats ? (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  color: '#e2e8f0',
                  fontFamily: 'var(--font-mono, monospace)',
                }}
              >
                <span>
                  Min: <strong style={{ color: '#38bdf8' }}>{selectedMwsStats.min}m</strong>
                </span>
                <span>
                  Mean: <strong style={{ color: '#34d399' }}>{selectedMwsStats.mean}m</strong>
                </span>
                <span>
                  Max: <strong style={{ color: '#f59e0b' }}>{selectedMwsStats.max}m</strong>
                </span>
              </div>
            ) : (
              <div style={{ color: 'var(--muted)' }}>Elevation data loading...</div>
            )}
          </div>
        </div>
      )}

      {/* Terrain Probe Interactive Card (Feature 2) */}
      {probe && (
        <div
          role="region"
          aria-label="Terrain Probe Inspector"
          style={{
            position: 'absolute',
            bottom: subMode === 'terrain' && selectedMws ? '182px' : '14px',
            left: '12px',
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(56, 189, 248, 0.4)',
            backdropFilter: 'blur(12px)',
            borderRadius: '8px',
            padding: '9px 12px',
            zIndex: 25,
            width: '200px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
            fontSize: '9.5px',
            color: '#e2e8f0',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '6px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              paddingBottom: '4px',
            }}
          >
            <span
              style={{
                fontWeight: 700,
                color: '#38bdf8',
                letterSpacing: '0.04em',
                fontSize: '10px',
              }}
            >
              {dict.gis3d.probeTitle}
            </span>
            <button
              onClick={() => setProbe(null)}
              title={dict.gis3d.probeDismiss}
              style={{
                background: 'none',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 700,
                padding: '0 2px',
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            <div>
              <div style={{ fontSize: '7.5px', color: 'var(--muted)' }}>
                {dict.gis3d.probeElevation}
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontWeight: 700,
                  color: '#f8fafc',
                  fontSize: '11px',
                }}
              >
                {probe.interpolatedElevation.toFixed(1)} m
              </div>
            </div>

            <div>
              <div style={{ fontSize: '7.5px', color: 'var(--muted)' }}>
                Scenario Level
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontWeight: 700,
                  color: '#38bdf8',
                  fontSize: '11px',
                }}
              >
                {waterLevel.toFixed(1)} m
              </div>
            </div>

            <div>
              <div style={{ fontSize: '7.5px', color: 'var(--muted)' }}>
                Scenario-Estimated Depth
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-mono, monospace)',
                  fontWeight: 700,
                  color: probeDepth > 0 ? '#38bdf8' : '#34d399',
                  fontSize: '11px',
                }}
              >
                {probeDepth.toFixed(1)} m
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '1px',
              }}
            >
              <span style={{ fontSize: '8px', color: 'var(--muted)' }}>Status</span>
              <span
                style={{
                  fontSize: '7.5px',
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: '3px',
                  backgroundColor:
                    probeStatus === 'INUNDATED'
                      ? 'rgba(56, 189, 248, 0.22)'
                      : 'rgba(16, 185, 129, 0.22)',
                  color: probeStatus === 'INUNDATED' ? '#38bdf8' : '#34d399',
                  border:
                    probeStatus === 'INUNDATED'
                      ? '1px solid rgba(56, 189, 248, 0.4)'
                      : '1px solid rgba(16, 185, 129, 0.4)',
                }}
              >
                {probeStatus}
              </span>
            </div>

            {(probe.mws || probe.gisId) && (
              <div
                style={{
                  borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                  paddingTop: '4px',
                  marginTop: '1px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px',
                }}
              >
                {probe.mws && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '7.5px', color: 'var(--muted)' }}>MWS:</span>
                    <strong
                      style={{
                        color: '#38bdf8',
                        fontFamily: 'var(--font-mono, monospace)',
                      }}
                    >
                      {probe.mws}
                    </strong>
                  </div>
                )}
                {probe.gisId && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '7.5px', color: 'var(--muted)' }}>GIS ID:</span>
                    <span
                      style={{
                        color: '#cbd5e1',
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: '7.5px',
                      }}
                    >
                      {probe.gisId}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating Flood Depth Legend for Maximized 3D View (Visible in Maximized Mode) */}
      {subMode === 'flood' && isFloodPanelCollapsed && (
        <div
          role="complementary"
          aria-label="Flood Depth Legend"
          style={{
            position: 'absolute',
            bottom: '12px',
            right: '12px',
            background: 'rgba(15, 23, 42, 0.92)',
            border: '1px solid rgba(56, 189, 248, 0.35)',
            backdropFilter: 'blur(10px)',
            borderRadius: '6px',
            padding: '5px 8px',
            zIndex: 20,
            fontSize: '7.5px',
            color: '#cbd5e1',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.55)',
          }}
        >
          <div
            style={{
              fontWeight: 700,
              color: '#38bdf8',
              marginBottom: '3px',
              letterSpacing: '0.04em',
              fontSize: '8px',
            }}
          >
            FLOOD DEPTH (SCENARIO-ESTIMATED)
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  background: '#5a7844',
                  borderRadius: '1px',
                }}
              />
              <span>0 m Dry</span>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  background: '#7dd3fc',
                  borderRadius: '1px',
                }}
              />
              <span>0–1.5 m Shallow</span>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  background: '#0284c7',
                  borderRadius: '1px',
                }}
              />
              <span>1.5–6 m Moderate</span>
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  background: '#075985',
                  borderRadius: '1px',
                }}
              />
              <span>&gt;6 m Deep</span>
            </span>
          </div>
        </div>
      )}

      {/* Bottom Center: Navigation Hint */}
      <div
        style={{
          position: 'absolute',
          bottom: '8px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(6px)',
          borderRadius: '20px',
          padding: '3px 12px',
          fontSize: '9.5px',
          color: 'var(--muted)',
          pointerEvents: 'none',
          zIndex: 15,
        }}
      >
        Left drag: Rotate/Tilt · Right/Shift drag: Pan · Scroll: Zoom · Click: Inspect Terrain Probe
      </div>
    </div>

    {/* Docked Sidebar: 3D Flood Scenario Controls & HUD (When Flood Mode Active and not collapsed) */}
    {subMode === 'flood' && !isFloodPanelCollapsed && (
      <aside
        className="gis-flood-sidebar"
        aria-label="3D Flood Scenario Controls"
        style={{
          width: '300px',
          minWidth: '300px',
          maxWidth: '320px',
          height: '100%',
          background: 'rgba(10, 15, 24, 0.96)',
          borderLeft: '1px solid rgba(56, 189, 248, 0.28)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 25,
          boxShadow: '-6px 0 24px rgba(0, 0, 0, 0.55)',
          flexShrink: 0,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '10px 12px 8px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(15, 23, 42, 0.7)',
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  fontSize: '10.5px',
                  fontWeight: 700,
                  color: '#38bdf8',
                  letterSpacing: '0.04em',
                }}
              >
                {dict.gis3d.modeFlood}
              </span>
              <span
                style={{
                  fontSize: '7.5px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '3px',
                  background: 'rgba(56, 189, 248, 0.16)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                DEM-BASED
              </span>
            </div>
            <div style={{ fontSize: '8.5px', color: '#94a3b8', fontWeight: 500, marginTop: '2px' }}>
              DEM-Based Scenario Inundation
            </div>
          </div>

          <button
            onClick={() => setIsFloodPanelCollapsed(true)}
            title={dict.gis3d.maximizeView}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 7px',
              borderRadius: '4px',
              background: 'rgba(56, 189, 248, 0.12)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#38bdf8',
              fontSize: '9.5px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <span>{dict.gis3d.maximizeView}</span>
            <span style={{ fontSize: '11px' }}>⤢</span>
          </button>
        </div>

        {/* Scrollable controls body */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '10px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '7px',
          }}
        >
          {/* Mandatory Disclaimers (Scientific Integrity) */}
          <div
            style={{
              background: 'rgba(56, 189, 248, 0.05)',
              border: '1px solid rgba(56, 189, 248, 0.18)',
              borderRadius: '4px',
              padding: '5px 7px',
              fontSize: '8px',
              lineHeight: 1.3,
              color: '#cbd5e1',
            }}
          >
            <div style={{ color: '#7dd3fc', fontWeight: 600, marginBottom: '2px' }}>
              SCENARIO ANALYSIS NOTICE
            </div>
            <div>
              Terrain-based scenario visualization using DEM elevation and project flood inputs.
              Flood extent and depth are estimates for scenario analysis, not observed flood
              measurements.
            </div>
            <div
              style={{
                marginTop: '3px',
                color: 'var(--muted)',
                borderTop: '1px solid rgba(255,255,255,0.06)',
                paddingTop: '3px',
              }}
            >
              Limitation: DEM elevation-threshold screening based on Copernicus GLO-30 DEM.
              Hydraulic connectivity is not explicitly simulated.
            </div>
          </div>

          {/* Water Level Slider & Readout */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              fontSize: '10px',
              fontWeight: 600,
              marginTop: '1px',
            }}
          >
            <div>
              <span style={{ color: '#cbd5e1' }}>Scenario Flood Level:</span>
              <div style={{ fontSize: '7.5px', color: 'var(--muted)', fontWeight: 400 }}>
                Illustrative DEM-based scenario
              </div>
            </div>
            <span
              style={{
                color: '#38bdf8',
                fontFamily: 'var(--font-mono, monospace)',
                fontSize: '11.5px',
                fontWeight: 700,
              }}
            >
              {waterLevel.toFixed(1)} m
            </span>
          </div>

          <input
            type="range"
            min={540}
            max={650}
            step={0.5}
            value={waterLevel}
            onChange={(e) => {
              setWaterLevel(parseFloat(e.target.value))
              setIsPlaying(false)
            }}
            style={{
              width: '100%',
              cursor: 'pointer',
              height: '3px',
              accentColor: '#38bdf8',
            }}
          />

          {/* Scenario Presets (Illustrative DEM-based scenario) */}
          <div>
            <div
              style={{
                fontSize: '8px',
                color: 'var(--muted)',
                fontWeight: 600,
                marginBottom: '3px',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span>{dict.gis3d.presetScenarios}</span>
              <span>ELEVATION</span>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '3px',
              }}
            >
              {SCENARIO_PRESETS.map((preset) => {
                const isCurrent = Math.abs(waterLevel - preset.level) < 0.4
                return (
                  <button
                    key={preset.label}
                    onClick={() => {
                      setWaterLevel(preset.level)
                      setIsPlaying(false)
                    }}
                    title={`${preset.full}: ${preset.desc}`}
                    style={{
                      padding: '3px 2px',
                      fontSize: '8px',
                      fontWeight: isCurrent ? 700 : 500,
                      borderRadius: '3px',
                      border: isCurrent
                        ? '1px solid #38bdf8'
                        : '1px solid rgba(255,255,255,0.1)',
                      background: isCurrent
                        ? 'rgba(56, 189, 248, 0.22)'
                        : 'rgba(255,255,255,0.04)',
                      color: isCurrent ? '#38bdf8' : '#cbd5e1',
                      cursor: 'pointer',
                      textAlign: 'center',
                    }}
                  >
                    {preset.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Risk-Scaled Scenario Level Button (When MWS Selected) */}
          {selectedMwsStats && riskScaledScenarioLevel !== null && (
            <div
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '4px',
                padding: '4px 6px',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '2px',
                }}
              >
                <span style={{ fontSize: '8px', color: '#cbd5e1', fontWeight: 600 }}>
                  Risk-scaled scenario level:
                </span>
                <span
                  style={{
                    fontSize: '9px',
                    color: '#fbbf24',
                    fontFamily: 'var(--font-mono, monospace)',
                    fontWeight: 700,
                  }}
                >
                  {riskScaledScenarioLevel.toFixed(1)} m
                </span>
              </div>
              <button
                onClick={() => {
                  setWaterLevel(riskScaledScenarioLevel)
                  setIsPlaying(false)
                }}
                style={{
                  width: '100%',
                  padding: '3px',
                  fontSize: '8px',
                  fontWeight: 600,
                  borderRadius: '3px',
                  border: '1px solid rgba(251, 191, 36, 0.4)',
                  background: 'rgba(251, 191, 36, 0.12)',
                  color: '#fbbf24',
                  cursor: 'pointer',
                  marginBottom: '3px',
                }}
              >
                ⚡ Apply Risk-Scaled Level ({riskScaledScenarioLevel.toFixed(1)}m)
              </button>
              <div style={{ fontSize: '7.5px', color: 'var(--muted)', lineHeight: 1.2 }}>
                Risk-scaled scenario level for visualization; not a measured or hydraulically
                calibrated flood elevation.
              </div>
            </div>
          )}

          {/* Animation & Reset Controls */}
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              style={{
                flex: 1,
                padding: '4px 6px',
                fontSize: '9px',
                fontWeight: 600,
                borderRadius: '4px',
                border: 'none',
                background: isPlaying ? 'var(--amber)' : '#0284c7',
                color: '#ffffff',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {isPlaying ? dict.gis3d.btnPause : dict.gis3d.btnRun}
            </button>
            <button
              onClick={() => {
                setWaterLevel(540.0)
                setIsPlaying(false)
              }}
              style={{
                padding: '4px 8px',
                fontSize: '9px',
                fontWeight: 600,
                borderRadius: '4px',
                border: '1px solid rgba(255,255,255,0.15)',
                background: 'rgba(255,255,255,0.06)',
                color: '#cbd5e1',
                cursor: 'pointer',
              }}
            >
              ⟳ {dict.gis3d.btnReset}
            </button>
          </div>

          {/* Feature 3: Lightweight Scenario A/B Comparison */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '4px',
              padding: '6px 8px',
              border: '1px solid rgba(56, 189, 248, 0.22)',
              fontSize: '8.5px',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span
                  style={{
                    fontSize: '8.5px',
                    fontWeight: 700,
                    color: '#38bdf8',
                    letterSpacing: '0.04em',
                  }}
                >
                  {dict.gis3d.scenarioCompare}
                </span>
                <span
                  style={{
                    fontSize: '7px',
                    fontWeight: 600,
                    padding: '1px 4px',
                    borderRadius: '2px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    color: '#7dd3fc',
                  }}
                >
                  A vs B
                </span>
              </div>
              <button
                onClick={() => setIsCompareOpen(!isCompareOpen)}
                style={{
                  padding: '2px 6px',
                  fontSize: '8px',
                  fontWeight: 600,
                  borderRadius: '3px',
                  background: isCompareOpen ? 'rgba(56, 189, 248, 0.22)' : 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  color: isCompareOpen ? '#38bdf8' : '#cbd5e1',
                  cursor: 'pointer',
                }}
              >
                {isCompareOpen ? 'Collapse ▲' : 'Compare Scenarios ▼'}
              </button>
            </div>

            {isCompareOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', marginTop: '1px' }}>
                {/* Scenario Selectors from existing presets */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '5px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    padding: '4px 6px',
                    borderRadius: '4px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '7.5px', color: '#94a3b8', marginBottom: '2px', fontWeight: 600 }}>
                      Scenario A
                    </div>
                    <select
                      value={scenarioALevel}
                      onChange={(e) => setScenarioALevel(parseFloat(e.target.value))}
                      style={{
                        width: '100%',
                        background: 'rgba(15, 23, 42, 0.95)',
                        border: '1px solid rgba(56, 189, 248, 0.45)',
                        borderRadius: '3px',
                        color: '#38bdf8',
                        fontSize: '8px',
                        padding: '2px 3px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {SCENARIO_PRESETS.map((p) => (
                        <option key={`a-${p.level}`} value={p.level}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div style={{ fontSize: '7.5px', color: '#94a3b8', marginBottom: '2px', fontWeight: 600 }}>
                      Scenario B
                    </div>
                    <select
                      value={scenarioBLevel}
                      onChange={(e) => setScenarioBLevel(parseFloat(e.target.value))}
                      style={{
                        width: '100%',
                        background: 'rgba(15, 23, 42, 0.95)',
                        border: '1px solid rgba(251, 191, 36, 0.45)',
                        borderRadius: '3px',
                        color: '#fbbf24',
                        fontSize: '8px',
                        padding: '2px 3px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {SCENARIO_PRESETS.map((p) => (
                        <option key={`b-${p.level}`} value={p.level}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Comparison Table */}
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '8px',
                    lineHeight: 1.4,
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: 'var(--muted)' }}>
                      <th style={{ textAlign: 'left', padding: '2px 0', fontWeight: 600 }}>METRIC</th>
                      <th style={{ textAlign: 'right', padding: '2px 4px', color: '#38bdf8', fontWeight: 700 }}>A</th>
                      <th style={{ textAlign: 'right', padding: '2px 0', color: '#fbbf24', fontWeight: 700 }}>B</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ color: '#cbd5e1', padding: '2px 0' }}>Level</td>
                      <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'var(--font-mono, monospace)', color: '#38bdf8' }}>
                        {scenarioALevel.toFixed(1)} m
                      </td>
                      <td style={{ textAlign: 'right', padding: '2px 0', fontFamily: 'var(--font-mono, monospace)', color: '#fbbf24' }}>
                        {scenarioBLevel.toFixed(1)} m
                      </td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ color: '#cbd5e1', padding: '2px 0' }}>Affected MWS</td>
                      <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsA.affectedMws}
                      </td>
                      <td style={{ textAlign: 'right', padding: '2px 0', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsB.affectedMws}
                      </td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ color: '#cbd5e1', padding: '2px 0' }}>Inundated</td>
                      <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsA.inundatedPct.toFixed(1)}%
                      </td>
                      <td style={{ textAlign: 'right', padding: '2px 0', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsB.inundatedPct.toFixed(1)}%
                      </td>
                    </tr>
                    <tr>
                      <td style={{ color: '#cbd5e1', padding: '2px 0' }}>Max Depth</td>
                      <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsA.maxDepth.toFixed(1)} m
                      </td>
                      <td style={{ textAlign: 'right', padding: '2px 0', fontFamily: 'var(--font-mono, monospace)' }}>
                        {statsB.maxDepth.toFixed(1)} m
                      </td>
                    </tr>
                    {statsA.mwsMaxDepth !== null && statsB.mwsMaxDepth !== null && (
                      <tr style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                        <td style={{ color: 'var(--muted)', padding: '2px 0' }}>Selected MWS Max Depth</td>
                        <td style={{ textAlign: 'right', padding: '2px 4px', fontFamily: 'var(--font-mono, monospace)', color: '#38bdf8' }}>
                          {statsA.mwsMaxDepth.toFixed(1)} m
                        </td>
                        <td style={{ textAlign: 'right', padding: '2px 0', fontFamily: 'var(--font-mono, monospace)', color: '#fbbf24' }}>
                          {statsB.mwsMaxDepth.toFixed(1)} m
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {/* Show A / Show B controls */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', marginTop: '2px' }}>
                  <button
                    onClick={() => {
                      setWaterLevel(scenarioALevel)
                      setIsPlaying(false)
                    }}
                    style={{
                      padding: '3px 4px',
                      fontSize: '8px',
                      fontWeight: 700,
                      borderRadius: '3px',
                      border:
                        Math.abs(waterLevel - scenarioALevel) < 0.2
                          ? '1px solid #38bdf8'
                          : '1px solid rgba(56, 189, 248, 0.3)',
                      background:
                        Math.abs(waterLevel - scenarioALevel) < 0.2
                          ? 'rgba(56, 189, 248, 0.25)'
                          : 'rgba(56, 189, 248, 0.08)',
                      color: '#38bdf8',
                      cursor: 'pointer',
                    }}
                  >
                    {Math.abs(waterLevel - scenarioALevel) < 0.2 ? '● Showing A' : 'Show A'}
                  </button>

                  <button
                    onClick={() => {
                      setWaterLevel(scenarioBLevel)
                      setIsPlaying(false)
                    }}
                    style={{
                      padding: '3px 4px',
                      fontSize: '8px',
                      fontWeight: 700,
                      borderRadius: '3px',
                      border:
                        Math.abs(waterLevel - scenarioBLevel) < 0.2
                          ? '1px solid #fbbf24'
                          : '1px solid rgba(251, 191, 36, 0.3)',
                      background:
                        Math.abs(waterLevel - scenarioBLevel) < 0.2
                          ? 'rgba(251, 191, 36, 0.25)'
                          : 'rgba(251, 191, 36, 0.08)',
                      color: '#fbbf24',
                      cursor: 'pointer',
                    }}
                  >
                    {Math.abs(waterLevel - scenarioBLevel) < 0.2 ? '● Showing B' : 'Show B'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Scenario-Estimated Flood Extent Summary Card */}
          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '4px',
              padding: '5px 7px',
              border: '1px solid rgba(255,255,255,0.07)',
              fontSize: '8.5px',
              display: 'flex',
              flexDirection: 'column',
              gap: '2px',
            }}
          >
            <div
              style={{
                fontSize: '8px',
                fontWeight: 700,
                color: '#94a3b8',
                letterSpacing: '0.04em',
                marginBottom: '1px',
              }}
            >
              {dict.gis3d.inundationArea}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--muted)' }}>{dict.gis3d.affectedCatchments}:</span>
              <strong style={{ color: affectedMwsCount > 0 ? '#fbbf24' : '#34d399' }}>
                {affectedMwsCount} / 66 Units
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--muted)' }}>Inundated Basin Terrain:</span>
              <strong style={{ color: '#38bdf8', fontFamily: 'var(--font-mono, monospace)' }}>
                {basinInundationPct.toFixed(1)}% of area
              </strong>
            </div>

            {/* Selected MWS HUD (Requirement 7) */}
            {(selectedMws || selectedProfile?.MWS || selectedId || selectedProfile?.id) && (
              <div
                style={{
                  borderTop: '1px solid rgba(56, 189, 248, 0.2)',
                  paddingTop: '4px',
                  marginTop: '4px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)' }}>Selected MWS:</span>
                  <strong style={{ color: '#38bdf8', fontFamily: 'var(--font-mono, monospace)' }}>
                    {selectedMwsStats?.MWS || selectedMws || selectedProfile?.MWS || '—'}
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)' }}>GIS ID:</span>
                  <span style={{ color: '#e2e8f0', fontFamily: 'var(--font-mono, monospace)', fontSize: '8px' }}>
                    {selectedMwsStats?.id || selectedId || selectedProfile?.id || '—'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)' }}>Terrain Elevation:</span>
                  <span style={{ color: '#cbd5e1', fontFamily: 'var(--font-mono, monospace)', fontSize: '8px' }}>
                    {selectedMwsStats
                      ? `${selectedMwsStats.min.toFixed(1)}m – ${selectedMwsStats.max.toFixed(1)}m`
                      : '—'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)' }}>Scenario Flood Level:</span>
                  <strong style={{ color: '#38bdf8', fontFamily: 'var(--font-mono, monospace)' }}>
                    {waterLevel.toFixed(1)} m
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)' }}>Estimated Flood Depth:</span>
                  <strong
                    style={{
                      color: isSelectedMwsAffected ? '#f87171' : '#34d399',
                      fontFamily: 'var(--font-mono, monospace)',
                    }}
                  >
                    {isSelectedMwsAffected
                      ? `${estimatedMaxDepth.toFixed(1)} m (valley floor)`
                      : '0.0 m (Dry)'}
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1px' }}>
                  <span style={{ color: 'var(--muted)' }}>Flood Status:</span>
                  <span
                    style={{
                      fontSize: '7.5px',
                      fontWeight: 700,
                      padding: '1px 5px',
                      borderRadius: '3px',
                      letterSpacing: '0.04em',
                      backgroundColor: isSelectedMwsAffected
                        ? 'rgba(239, 68, 68, 0.22)'
                        : 'rgba(16, 185, 129, 0.22)',
                      color: isSelectedMwsAffected ? '#f87171' : '#34d399',
                      border: isSelectedMwsAffected
                        ? '1px solid rgba(239, 68, 68, 0.4)'
                        : '1px solid rgba(16, 185, 129, 0.4)',
                    }}
                  >
                    {isSelectedMwsAffected ? 'AFFECTED' : 'NOT AFFECTED'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Model 2 Context */}
          <div
            style={{
              borderTop: '1px solid rgba(255,255,255,0.08)',
              paddingTop: '4px',
              fontSize: '8px',
              color: 'var(--muted)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>
              M2 Risk: <strong style={{ color: '#f8fafc' }}>{selectedProfile?.risk?.final_risk_score ?? '55.27'}</strong> ({selectedProfile?.risk?.risk_category ?? 'HIGH'})
            </span>
            <span>
              M2 Flood Score: <strong style={{ color: '#38bdf8' }}>{selectedProfile?.risk?.flood_risk_score ?? '62.0'}</strong>
            </span>
          </div>

          {/* Scenario-Estimated Flood Depth Legend */}
          <div
            style={{
              borderTop: '1px solid rgba(255,255,255,0.08)',
              paddingTop: '4px',
              display: 'flex',
              flexDirection: 'column',
              gap: '3px',
            }}
          >
            <div
              style={{
                fontSize: '8px',
                fontWeight: 700,
                color: '#94a3b8',
                letterSpacing: '0.03em',
              }}
            >
              SCENARIO-ESTIMATED FLOOD DEPTH
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '3px 6px',
                fontSize: '7.5px',
                color: '#cbd5e1',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '7px', background: '#5a7844', borderRadius: '1px' }} />
                <span>0 m Dry</span>
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '7px', background: '#7dd3fc', borderRadius: '1px' }} />
                <span>0–1.5 m Shallow</span>
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '7px', background: '#0284c7', borderRadius: '1px' }} />
                <span>1.5–6 m Moderate</span>
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '7px', background: '#075985', borderRadius: '1px' }} />
                <span>&gt;6 m Deep</span>
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                gap: '8px',
                fontSize: '7.5px',
                color: 'var(--muted)',
                marginTop: '1px',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '2px', background: '#38bdf8' }} /> Streams
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '7px', height: '2px', background: 'rgba(255,255,255,0.55)' }} /> 66 MWS
              </span>
            </div>
          </div>
        </div>
      </aside>
    )}
  </div>
)
}
