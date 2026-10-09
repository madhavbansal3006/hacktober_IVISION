import {
  WatershedSummary,
  WatershedDetail,
  BasinSummary,
  LiveRiskResult,
  EvidenceItem,
  IoTReading,
  ApiResponse,
  MwsGeoJsonCollection,
  LulcBasinSummary,
  WaterQualityRecord,
  WaterQualitySummary,
  MwsReport,
  BasinReport,
  BatchUploadResponse,
  WatershedCropAdvisory,
} from './types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function safeFetch<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const url = `${API_BASE_URL}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    })

    if (!response.ok) {
      return {
        data: null,
        status: response.status === 404 ? 'no_data' : 'unavailable',
        error: `Server responded with ${response.status}: ${response.statusText}`,
      }
    }

    const json = (await response.json()) as T
    return {
      data: json,
      status: 'available',
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Network error or backend offline'
    return {
      data: null,
      status: 'unavailable',
      error: message,
    }
  }
}

export async function fetchWatersheds(): Promise<ApiResponse<WatershedSummary[]>> {
  return safeFetch<WatershedSummary[]>('/api/v1/watersheds')
}

export async function fetchBasinSummary(): Promise<ApiResponse<BasinSummary>> {
  return safeFetch<BasinSummary>('/api/v1/watersheds/basin/summary')
}

export async function fetchWatershedProfile(mwsId: string): Promise<ApiResponse<WatershedDetail>> {
  return safeFetch<WatershedDetail>(`/api/v1/watersheds/${encodeURIComponent(mwsId)}`)
}

export async function fetchLatestTelemetry(watershedId?: string, deviceId?: string): Promise<ApiResponse<LiveRiskResult>> {
  const params = new URLSearchParams()
  if (watershedId && watershedId !== 'ALL') params.append('watershed_id', watershedId)
  if (deviceId) params.append('device_id', deviceId)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return safeFetch<LiveRiskResult>(`/api/v1/telemetry/latest${qs}`)
}

export async function postLiveTelemetry(reading: IoTReading): Promise<ApiResponse<LiveRiskResult>> {
  return safeFetch<LiveRiskResult>('/api/v1/telemetry', {
    method: 'POST',
    body: JSON.stringify(reading),
  })
}

export async function simulateTelemetryInference(reading: IoTReading): Promise<ApiResponse<LiveRiskResult>> {
  return safeFetch<LiveRiskResult>('/api/v1/telemetry/infer', {
    method: 'POST',
    body: JSON.stringify(reading),
  })
}

export async function fetchMwsBoundariesGeoJson(): Promise<ApiResponse<MwsGeoJsonCollection>> {
  return safeFetch<MwsGeoJsonCollection>('/api/v1/gis/mws-boundaries')
}

export async function fetchFieldEvidence(watershedId?: string): Promise<ApiResponse<EvidenceItem[]>> {
  const query = watershedId ? `?watershed_id=${encodeURIComponent(watershedId)}` : ''
  return safeFetch<EvidenceItem[]>(`/api/v1/field-observations${query}`)
}

export async function fetchFieldObservations(watershedId?: string): Promise<ApiResponse<EvidenceItem[]>> {
  return fetchFieldEvidence(watershedId)
}

export async function fetchFieldObservationById(imageId: string): Promise<ApiResponse<EvidenceItem>> {
  return safeFetch<EvidenceItem>(`/api/v1/field-observations/${encodeURIComponent(imageId)}`)
}

export async function fetchFieldObservationsByMws(mwsId: string): Promise<ApiResponse<EvidenceItem[]>> {
  return safeFetch<EvidenceItem[]>(`/api/v1/field-observations/mws/${encodeURIComponent(mwsId)}`)
}

export async function uploadFieldPhotos(files: File[]): Promise<ApiResponse<BatchUploadResponse>> {
  try {
    const formData = new FormData()
    files.forEach((file) => {
      formData.append('files', file)
    })

    const url = `${API_BASE_URL}/api/v1/field-observations/upload`
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const errText = await response.text().catch(() => response.statusText)
      return {
        data: null,
        status: response.status === 404 ? 'no_data' : 'unavailable',
        error: `Upload failed (${response.status}): ${errText}`,
      }
    }

    const json = (await response.json()) as BatchUploadResponse
    return {
      data: json,
      status: 'available',
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Network error or backend offline'
    return {
      data: null,
      status: 'unavailable',
      error: message,
    }
  }
}

export async function fetchLulcSummary(): Promise<ApiResponse<LulcBasinSummary>> {
  return safeFetch<LulcBasinSummary>('/api/v1/lulc/summary')
}

export async function fetchWaterQualitySummary(mode?: 'simulation' | 'live'): Promise<ApiResponse<WaterQualitySummary>> {
  const q = mode ? `?mode=${encodeURIComponent(mode)}` : ''
  return safeFetch<WaterQualitySummary>(`/api/v1/water-quality/summary${q}`)
}

export async function fetchWaterQualityMws(mwsId: string, mode?: 'simulation' | 'live'): Promise<ApiResponse<WaterQualityRecord>> {
  const q = mode ? `?mode=${encodeURIComponent(mode)}` : ''
  return safeFetch<WaterQualityRecord>(`/api/v1/water-quality/${encodeURIComponent(mwsId)}${q}`)
}

export async function fetchMwsReport(mwsId: string): Promise<ApiResponse<MwsReport>> {
  return safeFetch<MwsReport>(`/api/v1/reports/mws/${encodeURIComponent(mwsId)}`)
}

export async function fetchBasinReport(): Promise<ApiResponse<BasinReport>> {
  return safeFetch<BasinReport>('/api/v1/reports/basin')
}

export function getMwsReportCsvUrl(mwsId: string): string {
  return `${API_BASE_URL}/api/v1/reports/mws/${encodeURIComponent(mwsId)}/csv`
}

export function getBasinReportCsvUrl(): string {
  return `${API_BASE_URL}/api/v1/reports/basin/csv`
}

export async function fetchCropAdvisory(mwsIdentifier: string): Promise<ApiResponse<WatershedCropAdvisory>> {
  return safeFetch<WatershedCropAdvisory>(`/api/v1/crops/${encodeURIComponent(mwsIdentifier)}`)
}

