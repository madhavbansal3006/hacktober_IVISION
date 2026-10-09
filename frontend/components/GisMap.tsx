'use client'

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  MwsGeoJsonCollection,
  MwsGeoJsonFeature,
  DataStatus,
  Screen,
  ObservationMarkerData,
} from '../lib/types'
import { useLanguage } from '../lib/i18n/LanguageContext'

// Authoritative Risk Theme
export const RISK_THEME: Record<string, { fill: string; stroke: string; label: string }> = {
  CRITICAL: { fill: '#ba1a1a', stroke: '#7a0000', label: 'Critical' },
  HIGH: { fill: '#ed6c02', stroke: '#994400', label: 'High' },
  MODERATE: { fill: '#c8961e', stroke: '#8c6812', label: 'Moderate' },
  LOW: { fill: '#1b5e20', stroke: '#0d3810', label: 'Low' },
}

// LULC Color Palette
export const LULC_THEME: Record<string, string> = {
  Agriculture: '#ca8a04',
  Forest: '#15803d',
  Water: '#0284c7',
  'Built-up': '#dc2626',
  Barren: '#a16207',
}

// Bounding box of the 66 micro-watersheds in WGS84 EPSG:4326
export const SHIGGAON_BBOX = {
  minLng: 75.034813,
  maxLng: 75.379239,
  minLat: 14.835313,
  maxLat: 15.19076,
  centerLng: 75.2070,
  centerLat: 15.0130,
}

const TILE_SIZE = 256

export type BasemapType = 'satellite' | 'terrain'

interface BasemapConfig {
  id: BasemapType
  name: string
  label: string
  subtext: string
  getTileUrl: (z: number, x: number, y: number) => string
  attribution: string
  maxZoom: number
}

const BASEMAPS: Record<BasemapType, BasemapConfig> = {
  satellite: {
    id: 'satellite',
    name: 'Satellite Imagery',
    label: 'Satellite',
    subtext: 'ESRI World Imagery',
    getTileUrl: (z, x, y) =>
      `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,
    attribution: 'Esri, Maxar, Earthstar',
    maxZoom: 18,
  },
  terrain: {
    id: 'terrain',
    name: 'Topographic Terrain',
    label: 'Terrain',
    subtext: 'ESRI World Topo',
    getTileUrl: (z, x, y) =>
      `https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/${z}/${y}/${x}`,
    attribution: 'Esri, HERE, Garmin',
    maxZoom: 17,
  },
}

// Web Mercator (EPSG:3857) Math
export function lngLatToWorldPixels(lng: number, lat: number, zoom: number): [number, number] {
  const scale = TILE_SIZE * Math.pow(2, zoom)
  const x = ((lng + 180) / 360) * scale
  const sinLat = Math.sin((lat * Math.PI) / 180)
  const clampedSin = Math.max(-0.9999, Math.min(0.9999, sinLat))
  const y = (0.5 - Math.log((1 + clampedSin) / (1 - clampedSin)) / (4 * Math.PI)) * scale
  return [x, y]
}

export function worldPixelsToLngLat(x: number, y: number, zoom: number): [number, number] {
  const scale = TILE_SIZE * Math.pow(2, zoom)
  const lng = (x / scale) * 360 - 180
  const n = Math.PI - (2 * Math.PI * y) / scale
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))
  return [lng, lat]
}

export function projectToScreen(
  lng: number,
  lat: number,
  center: [number, number],
  zoom: number,
  width: number,
  height: number
): [number, number] {
  const [wx, wy] = lngLatToWorldPixels(lng, lat, zoom)
  const [cx, cy] = lngLatToWorldPixels(center[0], center[1], zoom)
  return [
    Math.round((wx - cx + width / 2) * 10) / 10,
    Math.round((wy - cy + height / 2) * 10) / 10,
  ]
}

// Compute polygon centroid
function computeFeatureCentroid(geom: MwsGeoJsonFeature['geometry']): [number, number] {
  if (!geom || !geom.coordinates) return [SHIGGAON_BBOX.centerLng, SHIGGAON_BBOX.centerLat]
  let sumLng = 0
  let sumLat = 0
  let count = 0

  const addRing = (ring: number[][]) => {
    for (const pt of ring) {
      sumLng += pt[0]
      sumLat += pt[1]
      count++
    }
  }

  if (geom.type === 'Polygon') {
    for (const ring of geom.coordinates as number[][][]) {
      addRing(ring)
    }
  } else if (geom.type === 'MultiPolygon') {
    for (const poly of geom.coordinates as number[][][][]) {
      for (const ring of poly) {
        addRing(ring)
      }
    }
  }

  if (count === 0) return [SHIGGAON_BBOX.centerLng, SHIGGAON_BBOX.centerLat]
  return [sumLng / count, sumLat / count]
}

export interface GisMapProps {
  variant?: Screen | 'overview'
  selectedMws?: string
  selectedId?: string
  gisBoundaries?: MwsGeoJsonCollection | null
  gisStatus?: DataStatus
  gisError?: string | null
  onSelectMws?: (mwsId: string) => void
  observationMarker?: ObservationMarkerData | null
  onClearObservationMarker?: () => void
  hoveredId?: string | null
  className?: string
  height?: number | string
}

export function GisMap({
  variant = 'overview',
  selectedMws,
  selectedId,
  hoveredId,
  gisBoundaries,
  gisStatus,
  gisError,
  onSelectMws,
  observationMarker,
  onClearObservationMarker,
  className = '',
  height = '100%',
}: GisMapProps) {
  const { dict, t } = useLanguage()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 800,
    height: 520,
  })

  // Map Navigation State
  const [center, setCenter] = useState<[number, number]>([
    SHIGGAON_BBOX.centerLng,
    SHIGGAON_BBOX.centerLat,
  ])
  const [zoom, setZoom] = useState<number>(11.2)
  const [basemap, setBasemap] = useState<BasemapType>('satellite')
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)

  // Layers Toggles
  const [layers, setLayers] = useState({
    mws: true,
    risk: true,
    streams: true,
    taluk: true,
    lulc: false,
  })
  const [layerDrawerOpen, setLayerDrawerOpen] = useState<boolean>(false)

  // Contextual Data
  const [talukGeoJson, setTalukGeoJson] = useState<any | null>(null)
  const [riversGeoJson, setRiversGeoJson] = useState<any | null>(null)

  // Interaction State
  const [hoveredFeature, setHoveredFeature] = useState<MwsGeoJsonFeature | null>(null)
  const [mouseScreenPos, setMouseScreenPos] = useState<{ x: number; y: number } | null>(null)
  const [cursorCoords, setCursorCoords] = useState<{ lng: number; lat: number } | null>(null)

  // Search State
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [searchOpen, setSearchOpen] = useState<boolean>(false)

  // Tile Error tracking for graceful fallback
  const [tileErrors, setTileErrors] = useState<Record<string, boolean>>({})

  // Drag state
  const isDraggingRef = useRef(false)
  const dragStartRef = useRef<{ mouseX: number; mouseY: number; startCenter: [number, number] } | null>(null)

  // Measure container dimensions
  useEffect(() => {
    if (!containerRef.current) return
    const updateSize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current
        if (clientWidth > 0 && clientHeight > 0) {
          setDimensions({ width: clientWidth, height: clientHeight })
        }
      }
    }
    updateSize()
    const observer = new ResizeObserver(updateSize)
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  // Fetch contextual GIS layers (Taluk Boundary & WRIS Rivers) once
  useEffect(() => {
    let isMounted = true
    fetch('/data/shiggaon_taluk_boundary.geojson')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (isMounted && data) setTalukGeoJson(data)
      })
      .catch(() => {})

    fetch('/data/shiggaon_rivers.geojson')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (isMounted && data) setRiversGeoJson(data)
      })
      .catch(() => {})

    return () => {
      isMounted = false
    }
  }, [])

  // Auto-fit to selected watershed when it changes
  useEffect(() => {
    if (!selectedId && !selectedMws) return
    if (!gisBoundaries?.features) return

    const target = gisBoundaries.features.find(
      (f) =>
        f.properties.id === selectedId ||
        f.properties.MWS === selectedMws ||
        f.properties.id === selectedMws
    )

    if (target) {
      const centroid = computeFeatureCentroid(target.geometry)
      setCenter(centroid)
      setZoom((prev) => Math.max(prev, 12.6))
    }
  }, [selectedId, selectedMws, gisBoundaries])

  // Center on observation marker coordinates when provided
  useEffect(() => {
    if (
      observationMarker &&
      typeof observationMarker.latitude === 'number' &&
      typeof observationMarker.longitude === 'number'
    ) {
      setCenter([observationMarker.longitude, observationMarker.latitude])
      setZoom((prev) => Math.max(prev, 13.5))
    }
  }, [observationMarker])

  // Center & reset to study area
  const handleResetView = useCallback(() => {
    setCenter([SHIGGAON_BBOX.centerLng, SHIGGAON_BBOX.centerLat])
    setZoom(11.2)
  }, [])

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    setZoom((prev) => Math.min(BASEMAPS[basemap].maxZoom, prev + 0.6))
  }, [basemap])

  const handleZoomOut = useCallback(() => {
    setZoom((prev) => Math.max(9.5, prev - 0.6))
  }, [])

  // Wheel zoom around mouse position
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault()
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return

      const mouseX = e.clientX - rect.left
      const mouseY = e.clientY - rect.top

      const [cwx, cwy] = lngLatToWorldPixels(center[0], center[1], zoom)
      const mouseWorldX = cwx + (mouseX - dimensions.width / 2)
      const mouseWorldY = cwy + (mouseY - dimensions.height / 2)
      const mouseLngLat = worldPixelsToLngLat(mouseWorldX, mouseWorldY, zoom)

      const zoomDelta = e.deltaY < 0 ? 0.25 : -0.25
      const newZoom = Math.min(BASEMAPS[basemap].maxZoom, Math.max(9.5, zoom + zoomDelta))
      if (newZoom === zoom) return

      // Adjust center to keep mouse point invariant
      const [newMouseWx, newMouseWy] = lngLatToWorldPixels(mouseLngLat[0], mouseLngLat[1], newZoom)
      const newCenterWx = newMouseWx - (mouseX - dimensions.width / 2)
      const newCenterWy = newMouseWy - (mouseY - dimensions.height / 2)
      const newCenterLngLat = worldPixelsToLngLat(newCenterWx, newCenterWy, newZoom)

      setZoom(newZoom)
      setCenter(newCenterLngLat)
    },
    [center, zoom, dimensions, basemap]
  )

  // Pan interaction
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return
      isDraggingRef.current = true
      dragStartRef.current = {
        mouseX: e.clientX,
        mouseY: e.clientY,
        startCenter: [...center],
      }
    },
    [center]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (rect) {
        const mouseX = e.clientX - rect.left
        const mouseY = e.clientY - rect.top
        setMouseScreenPos({ x: mouseX, y: mouseY })

        const [cwx, cwy] = lngLatToWorldPixels(center[0], center[1], zoom)
        const curWx = cwx + (mouseX - dimensions.width / 2)
        const curWy = cwy + (mouseY - dimensions.height / 2)
        const [curLng, curLat] = worldPixelsToLngLat(curWx, curWy, zoom)
        setCursorCoords({ lng: curLng, lat: curLat })
      }

      if (!isDraggingRef.current || !dragStartRef.current) return
      const dx = e.clientX - dragStartRef.current.mouseX
      const dy = e.clientY - dragStartRef.current.mouseY

      const [startWx, startWy] = lngLatToWorldPixels(
        dragStartRef.current.startCenter[0],
        dragStartRef.current.startCenter[1],
        zoom
      )
      const newCenter = worldPixelsToLngLat(startWx - dx, startWy - dy, zoom)
      setCenter(newCenter)
    },
    [center, zoom, dimensions]
  )

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false
    dragStartRef.current = null
  }, [])

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev)
  }, [])

  // Slippy Tiles computation
  const visibleTiles = useMemo(() => {
    const tz = Math.floor(zoom)
    const tileScale = Math.pow(2, zoom - tz)
    const scaledTileSize = TILE_SIZE * tileScale
    const [cwx, cwy] = lngLatToWorldPixels(center[0], center[1], tz)

    const halfW = dimensions.width / 2
    const halfH = dimensions.height / 2

    const minTileX = Math.floor((cwx - halfW / tileScale) / TILE_SIZE)
    const maxTileX = Math.floor((cwx + halfW / tileScale) / TILE_SIZE)
    const minTileY = Math.floor((cwy - halfH / tileScale) / TILE_SIZE)
    const maxTileY = Math.floor((cwy + halfH / tileScale) / TILE_SIZE)

    const tiles: {
      key: string
      url: string
      x: number
      y: number
      size: number
    }[] = []

    const maxCoord = Math.pow(2, tz) - 1

    for (let tx = minTileX; tx <= maxTileX; tx++) {
      if (tx < 0 || tx > maxCoord) continue
      for (let ty = minTileY; ty <= maxTileY; ty++) {
        if (ty < 0 || ty > maxCoord) continue
        const screenX = (tx * TILE_SIZE - cwx) * tileScale + halfW
        const screenY = (ty * TILE_SIZE - cwy) * tileScale + halfH
        const url = BASEMAPS[basemap].getTileUrl(tz, tx, ty)
        tiles.push({
          key: `${basemap}-${tz}-${tx}-${ty}`,
          url,
          x: Math.round(screenX * 10) / 10,
          y: Math.round(screenY * 10) / 10,
          size: Math.ceil(scaledTileSize),
        })
      }
    }
    return tiles
  }, [center, zoom, dimensions, basemap])

  // Convert geometry coordinates to SVG path string
  const geometryToPath = useCallback(
    (geom: MwsGeoJsonFeature['geometry'] | any): string => {
      if (!geom || !geom.coordinates) return ''
      const parts: string[] = []

      const renderRings = (rings: number[][][]) => {
        for (const ring of rings) {
          if (!ring || ring.length === 0) continue
          const [sx, sy] = projectToScreen(
            ring[0][0],
            ring[0][1],
            center,
            zoom,
            dimensions.width,
            dimensions.height
          )
          let ringPath = `M ${sx} ${sy}`
          for (let i = 1; i < ring.length; i++) {
            const [px, py] = projectToScreen(
              ring[i][0],
              ring[i][1],
              center,
              zoom,
              dimensions.width,
              dimensions.height
            )
            ringPath += ` L ${px} ${py}`
          }
          ringPath += ' Z'
          parts.push(ringPath)
        }
      }

      const renderLines = (lines: number[][][]) => {
        for (const line of lines) {
          if (!line || line.length === 0) continue
          const [sx, sy] = projectToScreen(
            line[0][0],
            line[0][1],
            center,
            zoom,
            dimensions.width,
            dimensions.height
          )
          let linePath = `M ${sx} ${sy}`
          for (let i = 1; i < line.length; i++) {
            const [px, py] = projectToScreen(
              line[i][0],
              line[i][1],
              center,
              zoom,
              dimensions.width,
              dimensions.height
            )
            linePath += ` L ${px} ${py}`
          }
          parts.push(linePath)
        }
      }

      if (geom.type === 'Polygon') {
        renderRings(geom.coordinates as number[][][])
      } else if (geom.type === 'MultiPolygon') {
        for (const poly of geom.coordinates as number[][][][]) {
          renderRings(poly)
        }
      } else if (geom.type === 'LineString') {
        renderLines([geom.coordinates as number[][]])
      } else if (geom.type === 'MultiLineString') {
        renderLines(geom.coordinates as number[][][])
      }

      return parts.join(' ')
    },
    [center, zoom, dimensions]
  )

  // Filter search results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim() || !gisBoundaries?.features) return []
    const q = searchQuery.toLowerCase().trim()
    return gisBoundaries.features
      .filter(
        (f) =>
          f.properties.MWS.toLowerCase().includes(q) ||
          f.properties.id.toLowerCase().includes(q)
      )
      .slice(0, 8)
  }, [searchQuery, gisBoundaries])

  // Scale bar calculation
  const scaleInfo = useMemo(() => {
    const lat = center[1]
    const metersPerPx = (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, zoom)
    const targetPx = 90
    const rawMeters = metersPerPx * targetPx

    let distanceMeters = 5000
    if (rawMeters < 300) distanceMeters = 100
    else if (rawMeters < 750) distanceMeters = 200
    else if (rawMeters < 1500) distanceMeters = 500
    else if (rawMeters < 3500) distanceMeters = 1000
    else if (rawMeters < 7000) distanceMeters = 2000
    else if (rawMeters < 14000) distanceMeters = 5000
    else distanceMeters = 10000

    const widthPx = Math.round(distanceMeters / metersPerPx)
    const label = distanceMeters >= 1000 ? `${distanceMeters / 1000} km` : `${distanceMeters} m`
    return { widthPx, label }
  }, [center, zoom])

  // Selected feature details
  const selectedFeature = useMemo(() => {
    if (!gisBoundaries?.features) return null
    return (
      gisBoundaries.features.find(
        (f) =>
          f.properties.id === selectedId ||
          f.properties.MWS === selectedMws ||
          f.properties.id === selectedMws
      ) || null
    )
  }, [selectedId, selectedMws, gisBoundaries])

  // Selected feature screen position for badge
  const selectedScreenCentroid = useMemo(() => {
    if (!selectedFeature) return null
    const [cLng, cLat] = computeFeatureCentroid(selectedFeature.geometry)
    return projectToScreen(cLng, cLat, center, zoom, dimensions.width, dimensions.height)
  }, [selectedFeature, center, zoom, dimensions])

  const isLoading = gisStatus === 'loading'
  const isOffline = gisStatus === 'unavailable'

  return (
    <div
      ref={containerRef}
      className={`gis-map-container ${isFullscreen ? 'gis-map-fullscreen' : ''} ${className}`}
      style={{
        position: isFullscreen ? 'fixed' : 'relative',
        top: isFullscreen ? 0 : undefined,
        left: isFullscreen ? 0 : undefined,
        width: isFullscreen ? '100vw' : '100%',
        height: isFullscreen ? '100vh' : height,
        minHeight: isFullscreen ? '100vh' : (height || 420),
        zIndex: isFullscreen ? 9999 : 1,
        backgroundColor: '#0c1219',
        overflow: 'hidden',
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: isFullscreen ? 0 : 8,
        border: isFullscreen ? 'none' : '1px solid rgba(255,255,255,0.14)',
        boxShadow: isFullscreen ? 'none' : '0 4px 20px rgba(0,0,0,0.3)',
      }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        handleMouseUp()
        setHoveredFeature(null)
        setMouseScreenPos(null)
      }}
    >
      {/* 1. RASTER SLIPPY BASEMAP TILES (NATURAL SATELLITE / TERRAIN REALISM) */}
      <div
        className="gis-tiles-layer"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          overflow: 'hidden',
        }}
      >
        {visibleTiles.map((tile) => {
          const hasError = tileErrors[tile.key]
          if (hasError) {
            return (
              <div
                key={tile.key}
                style={{
                  position: 'absolute',
                  left: tile.x,
                  top: tile.y,
                  width: tile.size,
                  height: tile.size,
                  background: 'linear-gradient(135deg, #0d1622 25%, #131f2f 100%)',
                  border: '1px solid rgba(255, 255, 255, 0.03)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'rgba(255,255,255,0.2)',
                  fontSize: 10,
                  fontFamily: 'monospace',
                }}
              >
                +
              </div>
            )
          }

          return (
            <img
              key={tile.key}
              src={tile.url}
              alt=""
              loading="lazy"
              crossOrigin="anonymous"
              onError={() => {
                setTileErrors((prev) => ({ ...prev, [tile.key]: true }))
              }}
              style={{
                position: 'absolute',
                left: tile.x,
                top: tile.y,
                width: tile.size,
                height: tile.size,
                // Natural satellite realism: NO aggressive filters that distort or darken the remote-sensing raster
                filter: 'none',
                transition: 'opacity 0.15s ease',
              }}
            />
          )
        })}
      </div>

      {/* 2. VECTOR SVG ANALYTICAL GIS OVERLAYS (SUBTLE, REFINED HIERARCHY) */}
      <svg
        width={dimensions.width}
        height={dimensions.height}
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 2,
        }}
      >
        <defs>
          {/* Subtle highlight glow for selected MWS */}
          <filter id="gis-selected-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#38bdf8" floodOpacity="0.75" />
          </filter>
          {/* Subtle grid pattern for fallback */}
          <pattern id="gis-grid-pattern" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="1" />
          </pattern>
        </defs>

        {/* Fallback subtle analytical grid */}
        <rect width="100%" height="100%" fill="url(#gis-grid-pattern)" />

        {/* A. SHIGGAON TALUK ADMINISTRATIVE BOUNDARY */}
        {layers.taluk && talukGeoJson?.features && (
          <g className="layer-taluk-boundary">
            {talukGeoJson.features.map((feat: any, idx: number) => {
              const pathD = geometryToPath(feat.geometry)
              return (
                <path
                  key={`taluk-${idx}`}
                  d={pathD}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth={1.8}
                  strokeDasharray="6 4"
                  strokeOpacity={0.80}
                  strokeLinecap="round"
                />
              )
            })}
          </g>
        )}

        {/* B. WRIS STREAMS & HYDROLOGY NETWORK (SUBTLE & REFINED) */}
        {layers.streams && riversGeoJson?.features && (
          <g className="layer-streams">
            {riversGeoJson.features.map((feat: any, idx: number) => {
              const pathD = geometryToPath(feat.geometry)
              const isMajor = feat.properties?.layer === 'major'
              return (
                <path
                  key={`stream-${idx}`}
                  d={pathD}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth={isMajor ? 1.3 : 0.85}
                  strokeOpacity={isMajor ? 0.65 : 0.50}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )
            })}
          </g>
        )}

        {/* C. 66 AUTHORITATIVE MICRO-WATERSHED POLYGONS (20-30% REFINED FILL OPACITY) */}
        {layers.mws && gisBoundaries?.features && (
          <g className="layer-micro-watersheds" style={{ pointerEvents: 'auto' }}>
            {gisBoundaries.features.map((feature) => {
              const props = feature.properties
              const isSelected =
                props.id === selectedId ||
                props.MWS === selectedMws ||
                props.id === selectedMws
              const isHovered =
                hoveredFeature?.properties.id === props.id ||
                Boolean(hoveredId && (props.id === hoveredId || props.MWS === hoveredId))
              const theme = RISK_THEME[props.risk_category] || {
                fill: '#64748b',
                stroke: '#334155',
                label: props.risk_category,
              }

              // Color determination
              let fillColor = theme.fill
              if (!layers.risk) {
                if (layers.lulc) {
                  fillColor = LULC_THEME['Agriculture']
                } else {
                  fillColor = '#0ea5e9'
                }
              }

              // Visual Polish: Refined 20-30% opacity hierarchy so satellite imagery remains visible underneath
              let fillOpacity = 0.24 // 24% default target
              if (isHovered) fillOpacity = 0.38
              if (isSelected) fillOpacity = 0.42

              // Subtle, crisp boundary lines
              let strokeColor = isSelected
                ? '#ffffff'
                : isHovered
                ? '#38bdf8'
                : 'rgba(255, 255, 255, 0.40)'
              let strokeWidth = isSelected ? 2.4 : isHovered ? 1.6 : 0.75

              const pathD = geometryToPath(feature.geometry)

              return (
                <path
                  key={props.id}
                  d={pathD}
                  fill={fillColor}
                  fillOpacity={fillOpacity}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeLinejoin="round"
                  filter={isSelected ? 'url(#gis-selected-glow)' : undefined}
                  style={{
                    cursor: onSelectMws ? 'pointer' : 'default',
                    transition: 'fill-opacity 0.12s ease, stroke-width 0.12s ease',
                  }}
                  onMouseEnter={() => setHoveredFeature(feature)}
                  onMouseLeave={() => {
                    if (hoveredFeature?.properties.id === props.id) {
                      setHoveredFeature(null)
                    }
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (onSelectMws) {
                      onSelectMws(props.id)
                    }
                  }}
                />
              )
            })}
          </g>
        )}

        {/* D. COMPACT SELECTED MWS LABEL (SINGLE-LINE REFINED PILL) */}
        {selectedScreenCentroid && selectedFeature && (
          <g
            className="selected-mws-centroid-badge"
            transform={`translate(${selectedScreenCentroid[0]}, ${selectedScreenCentroid[1]})`}
            style={{ pointerEvents: 'none' }}
          >
            {/* Small anchor dot on polygon centroid */}
            <circle r={3.5} fill="#ffffff" stroke="#38bdf8" strokeWidth={1.5} />

            {/* Small compact single-line translucent label: "4D4F2m3 · HIGH 55.3" */}
            <g transform="translate(0, -14)">
              <rect
                x={-64}
                y={-9}
                width={128}
                height={18}
                rx={3}
                fill="rgba(15, 23, 42, 0.90)"
                stroke="rgba(56, 189, 248, 0.65)"
                strokeWidth={1}
              />
              <text
                x={0}
                y={3.5}
                textAnchor="middle"
                fontSize={9.5}
                fontFamily="sans-serif"
                style={{ letterSpacing: '0.02em' }}
              >
                <tspan fill="#ffffff" fontWeight={700}>
                  {selectedFeature.properties.MWS}
                </tspan>
                <tspan fill="#94a3b8"> · </tspan>
                <tspan
                  fill={RISK_THEME[selectedFeature.properties.risk_category]?.fill || '#38bdf8'}
                  fontWeight={700}
                >
                  {selectedFeature.properties.risk_category}{' '}
                  {selectedFeature.properties.risk_score != null
                    ? Number(selectedFeature.properties.risk_score).toFixed(1)
                    : ''}
                </tspan>
              </text>
            </g>
          </g>
        )}

        {/* E. High-zoom non-cluttered MWS Labels (only when zoomed in) */}
        {zoom >= 13.0 &&
          gisBoundaries?.features &&
          gisBoundaries.features.map((feature) => {
            if (feature.properties.id === selectedId || feature.properties.MWS === selectedMws)
              return null
            const [cLng, cLat] = computeFeatureCentroid(feature.geometry)
            const [sx, sy] = projectToScreen(
              cLng,
              cLat,
              center,
              zoom,
              dimensions.width,
              dimensions.height
            )
            return (
              <text
                key={`lbl-${feature.properties.id}`}
                x={sx}
                y={sy}
                textAnchor="middle"
                fill="rgba(255, 255, 255, 0.85)"
                fontSize={9.5}
                fontWeight={600}
                fontFamily="sans-serif"
                style={{
                  pointerEvents: 'none',
                  textShadow: '0 1px 3px rgba(0,0,0,0.9), 0 0 2px #000',
                }}
              >
                {feature.properties.MWS}
              </text>
            )
          })}
        {/* F. FIELD OBSERVATION PHOTO MARKER (PIN & PULSING BEACON) */}
        {observationMarker &&
          typeof observationMarker.latitude === 'number' &&
          typeof observationMarker.longitude === 'number' && (() => {
            const [mX, mY] = projectToScreen(
              observationMarker.longitude,
              observationMarker.latitude,
              center,
              zoom,
              dimensions.width,
              dimensions.height
            )
            return (
              <g
                className="gis-field-observation-marker"
                transform={`translate(${mX}, ${mY})`}
                style={{ pointerEvents: 'none' }}
              >
                {/* Pulsing outer wave */}
                <circle r={18} fill="rgba(14, 165, 233, 0.25)">
                  <animate attributeName="r" values="12;24;12" dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.8;0.2;0.8" dur="2s" repeatCount="indefinite" />
                </circle>
                {/* Outer ring */}
                <circle r={10} fill="#0284c7" stroke="#ffffff" strokeWidth={2.5} />
                {/* Center dot */}
                <circle r={4} fill="#ffffff" />
                {/* Camera / Pin badge */}
                <g transform="translate(0, -20)">
                  <rect
                    x={-14}
                    y={-12}
                    width={28}
                    height={18}
                    rx={4}
                    fill="#0f172a"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                  />
                  <text
                    x={0}
                    y={1}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#ffffff"
                  >
                    📷
                  </text>
                </g>
              </g>
            )
          })()}
      </svg>

      {/* 3. GIS TOOLBAR CONTROLS (TOP-LEFT: COMPACT SEARCH & QUICK SELECTION) */}
      <div
        className="gis-top-left-controls"
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxWidth: 260,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            borderRadius: 5,
            backdropFilter: 'blur(8px)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.35)',
            padding: '1px 8px',
          }}
        >
          <span style={{ color: '#94a3b8', fontSize: 12, marginRight: 6 }}>🔍</span>
          <input
            type="text"
            placeholder="Search micro-watershed..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setSearchOpen(true)
            }}
            onFocus={() => setSearchOpen(true)}
            style={{
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#ffffff',
              fontSize: 11.5,
              fontFamily: 'sans-serif',
              width: 175,
              padding: '5px 0',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('')
                setSearchOpen(false)
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: 11,
                padding: '2px 4px',
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Search Results Dropdown */}
        {searchOpen && searchResults.length > 0 && (
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.96)',
              border: '1px solid rgba(255, 255, 255, 0.16)',
              borderRadius: 5,
              backdropFilter: 'blur(10px)',
              boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
              maxHeight: 200,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {searchResults.map((f) => {
              const isSel =
                f.properties.id === selectedId || f.properties.MWS === selectedMws
              return (
                <div
                  key={f.properties.id}
                  onClick={() => {
                    if (onSelectMws) onSelectMws(f.properties.id)
                    const centroid = computeFeatureCentroid(f.geometry)
                    setCenter(centroid)
                    setZoom(13.2)
                    setSearchOpen(false)
                  }}
                  style={{
                    padding: '7px 9px',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                    cursor: 'pointer',
                    background: isSel ? 'rgba(56, 189, 248, 0.18)' : 'transparent',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 11,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isSel
                      ? 'rgba(56, 189, 248, 0.18)'
                      : 'transparent'
                  }}
                >
                  <div>
                    <strong style={{ color: '#ffffff', fontSize: 11.5 }}>
                      {f.properties.MWS}
                    </strong>
                    <div style={{ color: '#94a3b8', fontSize: 9.5 }}>{f.properties.id}</div>
                  </div>
                  <span
                    style={{
                      padding: '2px 5px',
                      borderRadius: 3,
                      fontSize: 8.5,
                      fontWeight: 700,
                      background:
                        RISK_THEME[f.properties.risk_category]?.fill || '#475569',
                      color: '#ffffff',
                    }}
                  >
                    {f.properties.risk_category}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 4. GIS TOOLBAR CONTROLS (TOP-RIGHT: BASEMAP SELECTOR & LAYERS) */}
      <div
        className="gis-top-right-controls"
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 10,
          display: 'flex',
          gap: 6,
          alignItems: 'flex-start',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Basemap Switcher Buttons */}
        <div
          style={{
            display: 'flex',
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            borderRadius: 5,
            backdropFilter: 'blur(8px)',
            overflow: 'hidden',
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          }}
        >
          {(['satellite', 'terrain'] as BasemapType[]).map((bmKey, idx) => {
            const cfg = BASEMAPS[bmKey]
            const active = basemap === bmKey
            const label = bmKey === 'satellite' ? dict.gis.basemapSatellite : dict.gis.basemapTerrain
            const subtext = bmKey === 'satellite' ? dict.gis.basemapSatelliteSub : dict.gis.basemapTerrainSub
            return (
              <button
                key={bmKey}
                onClick={() => setBasemap(bmKey)}
                title={`${label} (${subtext})`}
                style={{
                  padding: '5px 10px',
                  background: active ? '#0284c7' : 'transparent',
                  color: active ? '#ffffff' : '#94a3b8',
                  border: 'none',
                  borderRight:
                    idx === 0 ? '1px solid rgba(255,255,255,0.1)' : 'none',
                  fontSize: 10.5,
                  fontWeight: active ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'background 0.12s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span>{bmKey === 'satellite' ? '🛰️' : '⛰️'}</span>
                {label}
              </button>
            )
          })}
        </div>

        {/* Layer Control Dropdown Toggle */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setLayerDrawerOpen((prev) => !prev)}
            style={{
              padding: '5px 10px',
              background: layerDrawerOpen ? '#0284c7' : 'rgba(15, 23, 42, 0.90)',
              border: '1px solid rgba(255, 255, 255, 0.16)',
              borderRadius: 5,
              color: '#ffffff',
              fontSize: 10.5,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              backdropFilter: 'blur(8px)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
            }}
          >
            <span>☰</span>
            {dict.gis.layerToggle} {layerDrawerOpen ? '▲' : '▼'}
          </button>

          {layerDrawerOpen && (
            <div
              style={{
                position: 'absolute',
                top: 32,
                right: 0,
                width: 200,
                background: 'rgba(15, 23, 42, 0.96)',
                border: '1px solid rgba(255, 255, 255, 0.16)',
                borderRadius: 5,
                padding: '9px 11px',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
                display: 'flex',
                flexDirection: 'column',
                gap: 7,
                fontSize: 10.5,
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: '#94a3b8',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  borderBottom: '1px solid rgba(255,255,255,0.08)',
                  paddingBottom: 3,
                }}
              >
                {dict.gis.overlaysHeading}
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', color: '#fff' }}>
                <input
                  type="checkbox"
                  checked={layers.mws}
                  onChange={(e) => setLayers((p) => ({ ...p, mws: e.target.checked }))}
                />
                <span>{dict.gis.layerMws}</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', color: '#fff' }}>
                <input
                  type="checkbox"
                  checked={layers.risk}
                  onChange={(e) => setLayers((p) => ({ ...p, risk: e.target.checked }))}
                />
                <span>{dict.gis.layerRisk}</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', color: '#fff' }}>
                <input
                  type="checkbox"
                  checked={layers.streams}
                  onChange={(e) => setLayers((p) => ({ ...p, streams: e.target.checked }))}
                />
                <span>{dict.gis.layerStreams}</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', color: '#fff' }}>
                <input
                  type="checkbox"
                  checked={layers.taluk}
                  onChange={(e) => setLayers((p) => ({ ...p, taluk: e.target.checked }))}
                />
                <span>{dict.gis.layerTaluk}</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', color: '#94a3b8' }}>
                <input
                  type="checkbox"
                  checked={layers.lulc}
                  onChange={(e) => setLayers((p) => ({ ...p, lulc: e.target.checked }))}
                />
                <span>{dict.gis.layerLulc}</span>
              </label>

              <div
                style={{
                  fontSize: 8.5,
                  color: '#64748b',
                  marginTop: 2,
                  borderTop: '1px solid rgba(255,255,255,0.08)',
                  paddingTop: 3,
                }}
              >
                {dict.gis.layerFieldObsEmpty}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 5. GIS NAVIGATION CONTROLS & NORTH ARROW (RIGHT-CENTER) */}
      <div
        className="gis-right-controls"
        style={{
          position: 'absolute',
          bottom: 38,
          right: 10,
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 5,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* North Arrow */}
        <div
          title={dict.gis.northIndicator}
          style={{
            width: 28,
            height: 28,
            background: 'rgba(15, 23, 42, 0.88)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(6px)',
            boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24">
            <polygon points="12,2 15,11 12,9 9,11" fill="#ef4444" />
            <polygon points="12,22 15,13 12,15 9,13" fill="#cbd5e1" />
            <text x="12" y="7.5" textAnchor="middle" fontSize="6" fill="#ffffff" fontWeight="bold">
              N
            </text>
          </svg>
        </div>

        {/* Zoom & Action Buttons */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            borderRadius: 5,
            overflow: 'hidden',
            backdropFilter: 'blur(8px)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.35)',
          }}
        >
          <button
            onClick={handleZoomIn}
            title={dict.gis.zoomIn}
            aria-label={dict.gis.zoomIn}
            style={{
              width: 28,
              height: 26,
              background: 'transparent',
              border: 'none',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              color: '#ffffff',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            +
          </button>
          <button
            onClick={handleZoomOut}
            title={dict.gis.zoomOut}
            aria-label={dict.gis.zoomOut}
            style={{
              width: 28,
              height: 26,
              background: 'transparent',
              border: 'none',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              color: '#ffffff',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            −
          </button>
          <button
            onClick={handleResetView}
            title={dict.gis.fitShiggaon}
            aria-label={dict.gis.fitShiggaon}
            style={{
              width: 28,
              height: 26,
              background: 'transparent',
              border: 'none',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              color: '#ffffff',
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ⌖
          </button>
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? dict.gis.fullscreenExit : dict.gis.fullscreenEnter}
            aria-label={isFullscreen ? dict.gis.fullscreenExit : dict.gis.fullscreenEnter}
            style={{
              width: 28,
              height: 26,
              background: 'transparent',
              border: 'none',
              color: '#ffffff',
              fontSize: 11,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {isFullscreen ? '✕' : '⛶'}
          </button>
        </div>
      </div>

      {/* 6. AUTHORITATIVE GIS HOVER TOOLTIP (EXACT FORMAT) */}
      {hoveredFeature && mouseScreenPos && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(mouseScreenPos.x + 12, dimensions.width - 210),
            top: Math.min(mouseScreenPos.y + 12, dimensions.height - 110),
            zIndex: 100,
            pointerEvents: 'none',
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(56, 189, 248, 0.5)',
            borderRadius: 5,
            padding: '7px 11px',
            boxShadow: '0 6px 20px rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
            minWidth: 170,
            lineHeight: 1.35,
          }}
        >
          <div
            style={{
              fontSize: 8.5,
              fontWeight: 700,
              color: '#94a3b8',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            {dict.gis.tooltipMws}
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 800,
              color: '#ffffff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}
          >
            <span>{hoveredFeature.properties.MWS}</span>
            <span style={{ fontSize: 9.5, color: '#94a3b8', fontWeight: 400 }}>
              {hoveredFeature.properties.id}
            </span>
          </div>

          <div style={{ marginTop: 3, fontSize: 10.5, color: '#e2e8f0' }}>
            {dict.gis.tooltipRisk}{' '}
            <strong
              style={{
                color:
                  RISK_THEME[hoveredFeature.properties.risk_category]?.fill || '#fff',
              }}
            >
              {hoveredFeature.properties.risk_category}
            </strong>{' '}
            ·{' '}
            {hoveredFeature.properties.risk_score != null
              ? Number(hoveredFeature.properties.risk_score).toFixed(2)
              : '—'}
          </div>
          <div style={{ fontSize: 9.5, color: '#94a3b8' }}>
            {dict.gis.tooltipDriver}{' '}
            <strong style={{ color: '#e2e8f0' }}>
              {hoveredFeature.properties.primary_driver || 'Water Stress'}
            </strong>
          </div>
        </div>
      )}

      {/* 7. UNIFIED PROFESSIONAL GIS STATUS BAR (CLEAN, INTEGRATED BOTTOM BAR) */}
      <div
        className="gis-status-bar"
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: 26,
          background: 'rgba(15, 23, 42, 0.92)',
          borderTop: '1px solid rgba(255, 255, 255, 0.12)',
          backdropFilter: 'blur(8px)',
          zIndex: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 8px',
          fontSize: 9,
          fontFamily: 'monospace',
          color: '#cbd5e1',
          overflowX: 'hidden',
          whiteSpace: 'nowrap',
        }}
      >
        {/* Left: Scale Bar & Coordinate Readout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {/* Alternating Scale Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <div
              style={{
                width: scaleInfo.widthPx,
                height: 3,
                border: '1px solid #ffffff',
                borderTop: 'none',
                background: '#000',
                display: 'flex',
              }}
            >
              <div style={{ width: '50%', height: '100%', background: '#ffffff' }} />
              <div style={{ width: '50%', height: '100%', background: '#000000' }} />
            </div>
            <span style={{ fontSize: 8.5, color: '#e2e8f0' }}>{scaleInfo.label}</span>
          </div>

          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>

          {/* Cursor Coordinates */}
          <span style={{ color: '#f8fafc' }}>
            {cursorCoords
              ? `${cursorCoords.lat.toFixed(4)}° N, ${cursorCoords.lng.toFixed(4)}° E`
              : `${center[1].toFixed(4)}° N, ${center[0].toFixed(4)}° E`}
          </span>

          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <span style={{ color: '#38bdf8' }}>EPSG:32643</span>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <span style={{ color: '#94a3b8' }}>Z {zoom.toFixed(1)}</span>
        </div>

        {/* Right: Compact Professional Cartographic Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'sans-serif', minWidth: 0, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <i style={{ width: 6, height: 6, borderRadius: 1, background: '#ba1a1a', display: 'inline-block' }} />
              {dict.gis.legendCritical} ({gisBoundaries?.risk_distribution?.CRITICAL ?? 5})
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <i style={{ width: 6, height: 6, borderRadius: 1, background: '#ed6c02', display: 'inline-block' }} />
              {dict.gis.legendHigh} ({gisBoundaries?.risk_distribution?.HIGH ?? 15})
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <i style={{ width: 6, height: 6, borderRadius: 1, background: '#c8961e', display: 'inline-block' }} />
              {dict.gis.legendMod} ({gisBoundaries?.risk_distribution?.MODERATE ?? 17})
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <i style={{ width: 6, height: 6, borderRadius: 1, background: '#1b5e20', display: 'inline-block' }} />
              {dict.gis.legendLow} ({gisBoundaries?.risk_distribution?.LOW ?? 29})
            </span>
          </div>

          <span style={{ color: 'rgba(255,255,255,0.2)', flexShrink: 0 }}>|</span>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ width: 8, height: 1.2, background: 'rgba(255,255,255,0.5)', display: 'inline-block' }} />
              {dict.gis.legendMws}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ width: 8, height: 1.5, background: '#fbbf24', display: 'inline-block' }} />
              {dict.gis.legendTaluk}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{ width: 8, height: 1.2, background: '#38bdf8', display: 'inline-block' }} />
              {dict.gis.legendStreams}
            </span>
          </div>

          <span style={{ color: 'rgba(255,255,255,0.2)', flexShrink: 0 }}>|</span>
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {BASEMAPS[basemap].attribution}
          </span>
        </div>
      </div>

      {/* 5. COMPACT FIELD OBSERVATION MAP CARD */}
      {observationMarker && (
        <div
          className="gis-observation-card"
          style={{
            position: 'absolute',
            bottom: 38,
            left: 14,
            zIndex: 14,
            background: 'rgba(15, 23, 42, 0.94)',
            border: '1px solid rgba(56, 189, 248, 0.45)',
            borderRadius: 8,
            padding: '10px 14px',
            color: '#ffffff',
            maxWidth: 270,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            backdropFilter: 'blur(10px)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.08em', color: '#38bdf8', textTransform: 'uppercase' }}>
              {dict.gis.obsFieldObs}
            </span>
            {onClearObservationMarker && (
              <button
                onClick={onClearObservationMarker}
                title={dict.gis.obsDismiss}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: 12,
                  cursor: 'pointer',
                  padding: '0 2px',
                }}
              >
                ✕
              </button>
            )}
          </div>

          <div style={{ fontSize: 11, marginBottom: 8, lineHeight: 1.4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span style={{ color: '#94a3b8' }}>{dict.gis.obsMws}</span>
              <strong style={{ color: '#f8fafc' }}>{observationMarker.MWS || selectedMws || '—'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span style={{ color: '#94a3b8' }}>{dict.gis.obsGisId}</span>
              <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#cbd5e1', fontSize: 10.5 }}>
                {observationMarker.id || selectedId || '—'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span style={{ color: '#94a3b8' }}>{dict.gis.obsGps}</span>
              <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#38bdf8', fontSize: 10 }}>
                {observationMarker.latitude.toFixed(4)}°N, {observationMarker.longitude.toFixed(4)}°E
              </strong>
            </div>
          </div>

          {/* Pipeline breadcrumb */}
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 6, fontSize: 9.5, color: '#94a3b8' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontFamily: 'sans-serif' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span>📷</span>
                <span style={{ color: '#e2e8f0' }}>{dict.gis.obsPhotoVerified.replace('{filename}', observationMarker.filename || 'Photo Verified')}</span>
              </div>
              <div style={{ textAlign: 'center', color: '#38bdf8', fontSize: 9, lineHeight: '10px' }}>↓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span>📍</span>
                <span style={{ color: '#e2e8f0' }}>{dict.gis.obsGpsLoc}</span>
              </div>
              <div style={{ textAlign: 'center', color: '#38bdf8', fontSize: 9, lineHeight: '10px' }}>↓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span>🗺️</span>
                <span style={{ color: '#e2e8f0' }}>{dict.gis.tooltipMws} ({observationMarker.MWS || selectedMws})</span>
              </div>
              <div style={{ textAlign: 'center', color: '#38bdf8', fontSize: 9, lineHeight: '10px' }}>↓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span>🌱</span>
                <span style={{ color: '#34d399' }}>{dict.gis.obsSpatialJoin}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading & Offline Overlays */}
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.75)',
            zIndex: 15,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 12 }}>{dict.gis.loadingBoundaries}</div>
          <span style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
            {dict.gis.loadingBoundariesSub}
          </span>
        </div>
      )}

      {isOffline && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.85)',
            zIndex: 15,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            textAlign: 'center',
          }}
        >
          <div style={{ fontWeight: 700, color: '#ef4444', fontSize: 13 }}>
            {dict.gis.boundariesUnavailable}
          </div>
          <span style={{ fontSize: 10.5, color: '#94a3b8', marginTop: 5, maxWidth: 360 }}>
            {gisError || dict.gis.boundariesUnavailableDesc}
          </span>
        </div>
      )}
    </div>
  )
}
