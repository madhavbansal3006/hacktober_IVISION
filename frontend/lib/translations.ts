export type Language = 'en' | 'kn'

export interface TranslationDictionary {
  brandSubtitle: string
  dataMode: string
  simulation: string
  liveIoT: string
  allMws: string
  loadingMws: string
  offlineMws: string
  screens: Record<string, string>
  cropScreenTitle: string
  cropScreenSubtitle: string
  selectCatchment: string
  waterStress: string
  rainfallAnomaly: string
  salinityPh: string
  slopeRunoff: string
  topCrop: string
  cautionHeader: string
  cautionSub: string
  seasonAll: string
  seasonKharif: string
  seasonRabi: string
  seasonSummer: string
  catAll: string
  catMillets: string
  catCash: string
  catPulses: string
  catOilseeds: string
  catHorticulture: string
  advantages: string
  irrigation: string
  whyFits: string
  conservationTitle: string
}

export const translations: Record<Language, TranslationDictionary> = {
  en: {
    brandSubtitle: 'WATERSHED INTELLIGENCE',
    dataMode: 'DATA MODE',
    simulation: 'Simulation',
    liveIoT: 'Live IoT',
    allMws: 'All Micro-watersheds (66 Units)',
    loadingMws: 'Loading 66 MWS...',
    offlineMws: 'MWS Unavailable (Offline)',
    screens: {
      Dashboard: 'Dashboard',
      'Water Quality': 'Water Quality',
      'Crop Intelligence': 'Crop Intelligence',
      'IoT Network': 'IoT Network',
      'Micro-Watershed Profile': 'Micro-Watershed Profile',
      'GIS Explorer': 'GIS Explorer',
      'LULC Analysis': 'LULC Analysis',
      'Field Observations': 'Field Observations',
      'Reports & Exports': 'Reports & Exports',
    },
    cropScreenTitle: 'Crop Intelligence & Water-Optimized Suggestions',
    cropScreenSubtitle: 'Calibrated crop suitability rankings, drought mitigation strategies, and irrigation prescriptions tailored to each micro-watershed.',
    selectCatchment: 'SELECT CATCHMENT:',
    waterStress: '💧 Water Stress',
    rainfallAnomaly: '🌧️ Rainfall Anomaly',
    salinityPh: '🧪 Salinity & pH',
    slopeRunoff: '⛰️ Slope & Runoff',
    topCrop: 'TOP RECOMMENDED CROP',
    cautionHeader: 'Restricted / High-Risk Crops for this Catchment',
    cautionSub: 'Intensive water-depleting crops that pose acute groundwater depletion risks under current water stress.',
    seasonAll: 'All Seasons',
    seasonKharif: 'Kharif (Monsoon)',
    seasonRabi: 'Rabi (Post-Monsoon)',
    seasonSummer: 'Summer / Perennial',
    catAll: 'All Types',
    catMillets: 'Millets & Cereals',
    catCash: 'Spices & Cash',
    catPulses: 'Pulses',
    catOilseeds: 'Oilseeds',
    catHorticulture: 'Horticulture',
    advantages: 'Agronomic Advantages',
    irrigation: 'Recommended Irrigation',
    whyFits: 'Why this fits',
    conservationTitle: 'Targeted Soil & Moisture Conservation Protocols',
  },
  kn: {
    brandSubtitle: 'ಜಲಾನಯನ ಗುಪ್ತಚರ ವ್ಯವಸ್ಥೆ',
    dataMode: 'ಡೇಟಾ ವಿಧಾನ',
    simulation: 'ಅನುಕರಣೆ',
    liveIoT: 'ನೇರ ಐಒಟಿ',
    allMws: 'ಎಲ್ಲಾ 66 ಕಿರು ಜಲಾನಯನಗಳು',
    loadingMws: '66 ಜಲಾನಯನಗಳನ್ನು ಲೋಡ್ ಮಾಡಲಾಗುತ್ತಿದೆ...',
    offlineMws: 'ಜಲಾನಯನ ಲಭ್ಯವಿಲ್ಲ (ಆಫ್‌ಲೈನ್)',
    screens: {
      Dashboard: 'ನಿಯಂತ್ರಣ ಫಲಕ',
      'Water Quality': 'ನೀರಿನ ಗುಣಮಟ್ಟ',
      'Crop Intelligence': 'ಬೆಳೆ ಸಲಹೆ',
      'IoT Network': 'ಐಒಟಿ ಜಾಲ',
      'Micro-Watershed Profile': 'ಜಲಾನಯನ ವಿವರ',
      'GIS Explorer': 'ಜಿಐಎಸ್ ನಕ್ಷೆ',
      'LULC Analysis': 'ಭೂ ಬಳಕೆ ವಿಶ್ಲೇಷಣೆ',
      'Field Observations': 'ಕ್ಷೇತ್ರ ವೀಕ್ಷಣೆ',
      'Reports & Exports': 'ವರದಿಗಳು',
    },
    cropScreenTitle: 'ನೀರಿನ ಸ್ಥಿತಿಗೆ ಅನುಗುಣವಾದ ಬೆಳೆ ಬುದ್ಧಿಮತ್ತೆ ಮತ್ತು ಸಲಹೆಗಳು',
    cropScreenSubtitle: 'ಪ್ರತಿ ಕಿರು ಜಲಾನಯನ ಪ್ರದೇಶದ ನೀರಿನ ಕೊರತೆ, ಮಳೆ ಮತ್ತು ಮಣ್ಣಿನ ಸ್ಥಿತಿಗೆ ಅನುಗುಣವಾಗಿ ವೈಜ್ಞಾನಿಕ ಬೆಳೆ ಆಯ್ಕೆ ಮತ್ತು ನೀರಾವರಿ ಮಾರ್ಗದರ್ಶನ.',
    selectCatchment: 'ಜಲಾನಯನ ಆಯ್ಕೆಮಾಡಿ:',
    waterStress: '💧 ನೀರಿನ ಒತ್ತಡ / ಕೊರತೆ',
    rainfallAnomaly: '🌧️ ಮಳೆ ವ್ಯತ್ಯಾಸ',
    salinityPh: '🧪 ಲವಣಾಂಶ ಮತ್ತು pH',
    slopeRunoff: '⛰️ ಇಳಿಜಾರು ಮತ್ತು ಹರಿವು',
    topCrop: 'ಅತ್ಯುನ್ನತ ಶಿಫಾರಸು ಮಾಡಿದ ಬೆಳೆ',
    cautionHeader: 'ಈ ಜಲಾನಯನ ಪ್ರದೇಶಕ್ಕೆ ನಿರ್ಬಂಧಿತ / ಹೆಚ್ಚಿನ ಅಪಾಯದ ಬೆಳೆಗಳು',
    cautionSub: 'ಹೆಚ್ಚು ನೀರು ಬೇಡುವ ಬೆಳೆಗಳು ಅಂತರ್ಜಲ ಕುಸಿತ ಮತ್ತು ನೀರಿನ ಬಿಕ್ಕಟ್ಟಿಗೆ ಕಾರಣವಾಗುತ್ತವೆ.',
    seasonAll: 'ಎಲ್ಲಾ ಋತುಗಳು',
    seasonKharif: 'ಮುಂಗಾರು (ಖಾರೀಫ್)',
    seasonRabi: 'ಹಿಂಗಾರು (ರಬಿ)',
    seasonSummer: 'ಬೇಸಿಗೆ / ವಾರ್ಷಿಕ',
    catAll: 'ಎಲ್ಲಾ ವಿಧಗಳು',
    catMillets: 'ಸಿರಿಧಾನ್ಯ ಮತ್ತು ಆಹಾರ ಧಾನ್ಯ',
    catCash: 'ವಾಣಿಜ್ಯ ಮತ್ತು ಸಾಂಬಾರ ಪದಾರ್ಥ',
    catPulses: 'ಬೇಳೆಕಾಳುಗಳು',
    catOilseeds: 'ಎಣ್ಣೆಕಾಳುಗಳು',
    catHorticulture: 'ತೋಟಗಾರಿಕೆ',
    advantages: 'ಕೃಷಿ ಅನುಕೂಲಗಳು',
    irrigation: 'ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಾವರಿ ಪದ್ಧತಿ',
    whyFits: 'ಏಕೆ ಸೂಕ್ತವಾಗಿದೆ',
    conservationTitle: 'ಮಣ್ಣು ಮತ್ತು ತೇವಾಂಶ ಸಂರಕ್ಷಣಾ ಕ್ರಮಗಳು',
  },
}
