export type Hsl = { h: number; s: number; l: number }

export type ThemeDensity = 'compact' | 'comfortable' | 'spacious'
export type ThemeSurface = 'flat' | 'subtle' | 'elevated'
export type ThemeNeutral = 'default' | 'cool' | 'warm' | 'true'
export type ThemeBaseColor = 'default' | 'zinc' | 'slate' | 'stone' | 'gray' | 'mauve' | 'olive' | 'mist'
export type ThemeStyleName = 'vega' | 'nova' | 'maia' | 'lyra'

export type ThemeCustomization = {
  density: ThemeDensity
  surface: ThemeSurface
  neutral: ThemeNeutral
  baseColor: ThemeBaseColor
  style: ThemeStyleName
  primaryColor: string
  secondaryColor: string
  accentColor: string
  backgroundColor: string
  surfaceColor: string
  borderColor: string
  glowIntensity: number
  glassEffect: number
  borderIntensity: number
  shadowIntensity: number
  backgroundGrid: boolean
  ambientEffects: boolean
  animationIntensity: 'reduced' | 'standard' | 'enhanced'
  chartGlow: number
}

export const DEFAULT_THEME_CUSTOMIZATION: ThemeCustomization = {
  density: 'comfortable',
  surface: 'subtle',
  neutral: 'cool',
  baseColor: 'default',
  style: 'vega',
  primaryColor: '#6667FD',
  secondaryColor: '#66F0D1',
  accentColor: '#9B5CFF',
  backgroundColor: '#05060B',
  surfaceColor: '#111522',
  borderColor: '#FFFFFF',
  glowIntensity: 32,
  glassEffect: 55,
  borderIntensity: 10,
  shadowIntensity: 30,
  backgroundGrid: true,
  ambientEffects: true,
  animationIntensity: 'standard',
  chartGlow: 35,
}

const BACKGROUND_TOKENS = new Set([
  '--background',
  '--card',
  '--muted',
  '--secondary',
  '--accent',
  '--popover',
  '--input',
  '--sidebar-background',
  '--scrollbar-track',
  '--background-custom',
])

const NEUTRAL_HUES: Record<Exclude<ThemeNeutral, 'default'>, number> = {
  cool: 220,
  warm: 32,
  true: 0,
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

export function round(value: number, digits = 1) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

export function parseHsl(value: string): Hsl | null {
  const match = value.trim().match(/^(-?[\d.]+)\s+([\d.]+)%\s+([\d.]+)%/)
  if (!match) return null
  return { h: Number(match[1]), s: Number(match[2]), l: Number(match[3]) }
}

export function formatHsl({ h, s, l }: Hsl): string {
  return `${round(h, 1)} ${round(s, 1)}% ${round(l, 1)}%`
}

function normalizeHex(input: string): string | null {
  let value = input.trim()
  if (!value.startsWith('#')) value = `#${value}`
  if (/^#[0-9a-fA-F]{3}$/.test(value)) {
    value = `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`
  }
  if (!/^#[0-9a-fA-F]{6}$/.test(value)) return null
  return value.toLowerCase()
}

export function hslToHex({ h, s, l }: Hsl): string {
  const sat = s / 100
  const light = l / 100
  const a = sat * Math.min(light, 1 - light)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = light - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color)
      .toString(16)
      .padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

export function hslCssToHex(value: string): string | null {
  if (value.startsWith('#')) return normalizeHex(value)
  const hsl = parseHsl(value)
  return hsl ? hslToHex(hsl) : null
}

function hexToHsl(input: string): string | null {
  const hex = normalizeHex(input)
  if (!hex) return null
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const delta = max - min
  let h = 0
  const l = (max + min) / 2
  let s = 0
  if (delta !== 0) {
    s = delta / (1 - Math.abs(2 * l - 1))
    if (max === r) h = 60 * (((g - b) / delta) % 6)
    else if (max === g) h = 60 * ((b - r) / delta + 2)
    else h = 60 * ((r - g) / delta + 4)
  }
  if (h < 0) h += 360
  return formatHsl({ h, s: s * 100, l: l * 100 })
}

function resolveVars(vars: Record<string, string>) {
  const resolved = { ...vars }
  for (let i = 0; i < 3; i++) {
    for (const [key, value] of Object.entries(resolved)) {
      const match = value.trim().match(/^var\((--[\w-]+)\)$/)
      if (match && resolved[match[1]]) {
        resolved[key] = resolved[match[1]]
      }
    }
  }
  return resolved
}

function applyNeutralTint(vars: Record<string, string>, neutral: ThemeNeutral) {
  if (neutral === 'default') return vars
  const hue = NEUTRAL_HUES[neutral]
  const next = { ...vars }
  for (const [key, value] of Object.entries(next)) {
    const hsl = parseHsl(value)
    if (!hsl) continue
    if (!BACKGROUND_TOKENS.has(key) && key !== '--border' && key !== '--sidebar-border' && key !== '--scrollbar-thumb') continue
    next[key] = formatHsl({
      h: hue,
      s: neutral === 'true' ? Math.min(hsl.s, 4) : clamp(Math.max(hsl.s, 4), 4, 12),
      l: hsl.l,
    })
  }
  return next
}

export function applyThemeCustomization(baseVars: Record<string, string>, customization: ThemeCustomization): Record<string, string> {
  const next = applyNeutralTint(resolveVars({ ...baseVars }), customization.neutral)
  const customTokens: Record<string, string> = {
    '--primary': hexToHsl(customization.primaryColor) ?? next['--primary'],
    '--secondary': hexToHsl(customization.secondaryColor) ?? next['--secondary'],
    '--accent': hexToHsl(customization.accentColor) ?? next['--accent'],
    '--background': hexToHsl(customization.backgroundColor) ?? next['--background'],
    '--card': hexToHsl(customization.surfaceColor) ?? next['--card'],
    '--input': hexToHsl(customization.surfaceColor) ?? next['--input'],
    '--border': hexToHsl(customization.borderColor) ?? next['--border'],
    '--ring': hexToHsl(customization.primaryColor) ?? next['--ring'],
    '--sidebar-background': hexToHsl(customization.backgroundColor) ?? next['--sidebar-background'],
    '--sidebar-primary': hexToHsl(customization.primaryColor) ?? next['--sidebar-primary'],
    '--sidebar-border': hexToHsl(customization.borderColor) ?? next['--sidebar-border'],
    '--glow-opacity': `${clamp(customization.glowIntensity, 0, 100) / 100}`,
    '--glass-opacity': `${0.35 + clamp(customization.glassEffect, 0, 100) / 100 * 0.5}`,
    '--border-opacity': `${clamp(customization.borderIntensity, 0, 100) / 100}`,
    '--shadow-opacity': `${clamp(customization.shadowIntensity, 0, 100) / 100}`,
    '--chart-glow-opacity': `${clamp(customization.chartGlow, 0, 100) / 100}`,
  }
  return { ...next, ...customTokens }
}

export function resolveTokenHex(vars: Record<string, string>, cssVar: string): string {
  const resolved = resolveVars(vars)
  return hslCssToHex(resolved[cssVar] ?? '') ?? '#888888'
}

export function parseThemeCustomization(raw: string | null): ThemeCustomization {
  if (!raw) return { ...DEFAULT_THEME_CUSTOMIZATION }
  try {
    const parsed = JSON.parse(raw) as Partial<ThemeCustomization>
    const baseColors: ThemeBaseColor[] = ['default', 'zinc', 'slate', 'stone', 'gray', 'mauve', 'olive', 'mist']
    const styles: ThemeStyleName[] = ['vega', 'nova', 'maia', 'lyra']
    return {
      density: parsed.density === 'compact' || parsed.density === 'spacious' ? parsed.density : 'comfortable',
      surface: parsed.surface === 'flat' || parsed.surface === 'elevated' ? parsed.surface : 'subtle',
      neutral: parsed.neutral === 'cool' || parsed.neutral === 'warm' || parsed.neutral === 'true' ? parsed.neutral : DEFAULT_THEME_CUSTOMIZATION.neutral,
      baseColor: baseColors.includes(parsed.baseColor as ThemeBaseColor) ? (parsed.baseColor as ThemeBaseColor) : 'default',
      style: styles.includes(parsed.style as ThemeStyleName) ? (parsed.style as ThemeStyleName) : 'vega',
      primaryColor: typeof parsed.primaryColor === 'string' ? parsed.primaryColor : DEFAULT_THEME_CUSTOMIZATION.primaryColor,
      secondaryColor: typeof parsed.secondaryColor === 'string' ? parsed.secondaryColor : DEFAULT_THEME_CUSTOMIZATION.secondaryColor,
      accentColor: typeof parsed.accentColor === 'string' ? parsed.accentColor : DEFAULT_THEME_CUSTOMIZATION.accentColor,
      backgroundColor: typeof parsed.backgroundColor === 'string' ? parsed.backgroundColor : DEFAULT_THEME_CUSTOMIZATION.backgroundColor,
      surfaceColor: typeof parsed.surfaceColor === 'string' ? parsed.surfaceColor : DEFAULT_THEME_CUSTOMIZATION.surfaceColor,
      borderColor: typeof parsed.borderColor === 'string' ? parsed.borderColor : DEFAULT_THEME_CUSTOMIZATION.borderColor,
      glowIntensity: clamp(Number(parsed.glowIntensity ?? DEFAULT_THEME_CUSTOMIZATION.glowIntensity), 0, 100),
      glassEffect: clamp(Number(parsed.glassEffect ?? DEFAULT_THEME_CUSTOMIZATION.glassEffect), 0, 100),
      borderIntensity: clamp(Number(parsed.borderIntensity ?? DEFAULT_THEME_CUSTOMIZATION.borderIntensity), 0, 100),
      shadowIntensity: clamp(Number(parsed.shadowIntensity ?? DEFAULT_THEME_CUSTOMIZATION.shadowIntensity), 0, 100),
      backgroundGrid: parsed.backgroundGrid !== false,
      ambientEffects: parsed.ambientEffects !== false,
      animationIntensity: parsed.animationIntensity === 'reduced' || parsed.animationIntensity === 'enhanced' ? parsed.animationIntensity : 'standard',
      chartGlow: clamp(Number(parsed.chartGlow ?? DEFAULT_THEME_CUSTOMIZATION.chartGlow), 0, 100),
    }
  } catch {
    return { ...DEFAULT_THEME_CUSTOMIZATION }
  }
}
