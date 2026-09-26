import { useTheme, type ColorTheme } from '@/app/providers/theme-provider'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { accentThemes, baseColorOrder, baseSwatches, colorThemeOrder, radiusPresets, themeStylePresets, type BaseColor, type ThemeStyle } from '@/constants/color-themes'
import { ColorDotPicker } from '@/features/theme/color-dot-picker'
import { SegmentedControl } from '@/features/theme/segmented-control'
import { ThemePreview } from '@/features/theme/theme-preview'
import useDirDetection from '@/hooks/use-dir-detection'
import { resolveTokenHex } from '@/lib/theme-color'
import { cn } from '@/lib/utils'
import { isPersianLocaleLanguage } from '@/utils/datePickerUtils'
import {
  getChartViewTypePreference,
  getCoresListUseConfigModal,
  getDatePickerPreference,
  setChartViewTypePreference,
  setCoresListUseConfigModal,
  setDatePickerPreference,
  type ChartViewType,
  type DatePickerPreference,
} from '@/utils/userPreferenceStorage'
import { BarChart3, CalendarClock, Check, FileJson2, Languages, Monitor, Moon, Palette, RotateCcw, Ruler, Sun, SunMoon, SwatchBook, TrendingUp } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

const chartViewOptions = ['bar', 'area'] as const

function Section({
  icon,
  title,
  description,
  action,
  children,
}: {
  icon: ReactNode
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            {icon}
            <p className="text-base font-semibold sm:text-lg">{title}</p>
          </div>
          {description && <p className="text-muted-foreground text-xs leading-relaxed sm:text-sm">{description}</p>}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  )
}

type AppearancePreset = {
  name: string
  description: string
  primaryColor: string
  secondaryColor: string
  accentColor: string
  backgroundColor: string
  surfaceColor: string
  glowIntensity: number
  glassEffect: number
}

const APPEARANCE_PRESETS: AppearancePreset[] = [
  { name: 'Cyber Pulse', description: 'Electric violet with mint telemetry energy.', primaryColor: '#6667FD', secondaryColor: '#66F0D1', accentColor: '#9B5CFF', backgroundColor: '#05060B', surfaceColor: '#111522', glowIntensity: 32, glassEffect: 55 },
  { name: 'Midnight Violet', description: 'Deep violet command center with restrained glow.', primaryColor: '#8B5CF6', secondaryColor: '#A78BFA', accentColor: '#C084FC', backgroundColor: '#07050D', surfaceColor: '#151020', glowIntensity: 28, glassEffect: 48 },
  { name: 'Neon Ocean', description: 'Cool cyan telemetry with a dark ocean foundation.', primaryColor: '#22D3EE', secondaryColor: '#67E8F9', accentColor: '#60A5FA', backgroundColor: '#03090D', surfaceColor: '#0B1720', glowIntensity: 30, glassEffect: 52 },
  { name: 'Aurora', description: 'Balanced violet and aqua for dense operational screens.', primaryColor: '#7C83FF', secondaryColor: '#5EEAD4', accentColor: '#A78BFA', backgroundColor: '#05080C', surfaceColor: '#101923', glowIntensity: 24, glassEffect: 60 },
  { name: 'Quantum', description: 'Sharper contrast for technical and developer workflows.', primaryColor: '#818CF8', secondaryColor: '#2DD4BF', accentColor: '#C4B5FD', backgroundColor: '#04050A', surfaceColor: '#0D111D', glowIntensity: 20, glassEffect: 42 },
  { name: 'Obsidian', description: 'Minimal black surfaces with precision accents.', primaryColor: '#A5B4FC', secondaryColor: '#5EEAD4', accentColor: '#C4B5FD', backgroundColor: '#020305', surfaceColor: '#0B0E14', glowIntensity: 14, glassEffect: 34 },
]

const APPEARANCE_COLORS = [
  ['primaryColor', 'Primary', '#6667FD'],
  ['secondaryColor', 'Secondary', '#66F0D1'],
  ['accentColor', 'Accent', '#9B5CFF'],
  ['backgroundColor', 'Background', '#05060B'],
  ['surfaceColor', 'Surface', '#111522'],
] as const

function AppearanceControlCenter() {
  const { customization, setCustomization } = useTheme()
  const [showAdvanced, setShowAdvanced] = useState(false)

  const applyPreset = (preset: AppearancePreset) => {
    setCustomization({
      ...preset,
      borderColor: '#FFFFFF',
      borderIntensity: 10,
      shadowIntensity: 30,
      backgroundGrid: true,
      ambientEffects: true,
      animationIntensity: 'standard',
      chartGlow: 35,
      density: 'comfortable',
      surface: 'subtle',
      neutral: 'cool',
      style: 'vega',
    })
  }

  return (
    <section className="relative overflow-hidden rounded-2xl border border-primary/15 bg-card/60 p-4 shadow-[0_20px_60px_hsl(230_40%_2%_/_var(--shadow-opacity))] backdrop-blur-xl sm:p-6">
      <div className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-primary/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-20 size-64 rounded-full bg-secondary/8 blur-3xl" />

      <div className="relative space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/8 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
              <span className="size-1.5 rounded-full bg-primary shadow-[0_0_10px_hsl(var(--primary)/.8)]" />
              Appearance Engine
            </div>
            <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Command Center Theme</h2>
            <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">
              Shape the entire visual language from one place. Changes are previewed immediately and persisted locally.
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background/45 px-3 py-2 text-xs text-muted-foreground">
            <span className="text-foreground font-medium">Dark-native</span>
            <span className="mx-1.5">•</span>
            Live preview
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">Presets</p>
              <p className="text-muted-foreground text-xs">Complete visual identities, not single-color swaps.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {APPEARANCE_PRESETS.map(preset => (
              <button
                key={preset.name}
                type="button"
                onClick={() => applyPreset(preset)}
                className="group relative overflow-hidden rounded-xl border border-border/70 bg-background/45 p-3 text-start transition-all hover:-translate-y-0.5 hover:border-primary/35 hover:bg-background/70"
              >
                <div className="mb-3 flex items-center gap-1.5">
                  <span className="size-3 rounded-full" style={{ background: preset.primaryColor }} />
                  <span className="size-3 rounded-full" style={{ background: preset.secondaryColor }} />
                  <span className="size-3 rounded-full" style={{ background: preset.accentColor }} />
                </div>
                <p className="text-sm font-semibold">{preset.name}</p>
                <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">{preset.description}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
          <div className="rounded-xl border border-border/70 bg-background/35 p-4">
            <div className="mb-4">
              <p className="text-sm font-semibold">Identity colors</p>
              <p className="text-muted-foreground text-xs">All values feed the global design tokens.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {APPEARANCE_COLORS.map(([key, label]) => (
                <label key={key} className="group flex items-center gap-3 rounded-lg border border-border/60 bg-card/45 p-2.5">
                  <input
                    type="color"
                    value={customization[key]}
                    onChange={event => setCustomization({ [key]: event.target.value })}
                    className="size-9 shrink-0 cursor-pointer rounded-lg border-0 bg-transparent p-0"
                    aria-label={label}
                  />
                  <span className="min-w-0">
                    <span className="block text-xs font-medium">{label}</span>
                    <span className="text-muted-foreground font-mono text-[10px] uppercase">{customization[key]}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border/70 bg-background/35 p-4">
            <div className="mb-4">
              <p className="text-sm font-semibold">Live visual controls</p>
              <p className="text-muted-foreground text-xs">Keep effects purposeful and readable.</p>
            </div>
            <div className="space-y-4">
              {([
                ['glowIntensity', 'Glow', customization.glowIntensity],
                ['glassEffect', 'Glass', customization.glassEffect],
                ['borderIntensity', 'Borders', customization.borderIntensity],
                ['shadowIntensity', 'Shadows', customization.shadowIntensity],
                ['chartGlow', 'Chart glow', customization.chartGlow],
              ] as const).map(([key, label, value]) => (
                <label key={key} className="block">
                  <span className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="font-medium">{label}</span>
                    <span className="text-muted-foreground font-mono">{value}%</span>
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={value}
                    onChange={event => setCustomization({ [key]: Number(event.target.value) })}
                    className="h-1.5 w-full accent-[hsl(var(--primary))]"
                  />
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-xl border border-border/70 bg-background/35 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold">Interface behavior</p>
            <p className="text-muted-foreground text-xs">Density and motion are global, not page-specific.</p>
          </div>
          <div className="grid grid-cols-3 gap-1.5 rounded-lg border border-border/60 bg-card/40 p-1">
            {(['compact', 'comfortable', 'spacious'] as const).map(value => (
              <button key={value} type="button" onClick={() => setCustomization({ density: value })} className={cn('rounded-md px-3 py-1.5 text-xs capitalize transition-colors', customization.density === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground')}>
                {value}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant={customization.backgroundGrid ? 'default' : 'outline'} size="sm" onClick={() => setCustomization({ backgroundGrid: !customization.backgroundGrid })}>
              Grid {customization.backgroundGrid ? 'On' : 'Off'}
            </Button>
            <Button type="button" variant={customization.ambientEffects ? 'default' : 'outline'} size="sm" onClick={() => setCustomization({ ambientEffects: !customization.ambientEffects })}>
              Ambient {customization.ambientEffects ? 'On' : 'Off'}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => setShowAdvanced(value => !value)}>
              {showAdvanced ? 'Hide advanced' : 'Advanced controls'}
            </Button>
          </div>
          {showAdvanced && (
            <div className="flex flex-wrap gap-1.5 rounded-lg border border-border/60 bg-background/45 p-1">
              {(['reduced', 'standard', 'enhanced'] as const).map(value => (
                <button key={value} type="button" onClick={() => setCustomization({ animationIntensity: value })} className={cn('rounded-md px-2.5 py-1.5 text-xs capitalize', customization.animationIntensity === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground')}>
                  {value} motion
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export default function ThemeSettings() {
  const { t, i18n } = useTranslation()
  const {
    theme,
    colorTheme,
    radius,
    customization,
    resolvedTheme,
    setTheme,
    setColorTheme,
    setRadius,
    setCustomization,
    resetToDefaults,
    isSystemTheme,
  } = useTheme()
  const dir = useDirDetection()
  const [isResetting, setIsResetting] = useState(false)
  const [datePickerPreference, setDatePickerPreferenceState] = useState<DatePickerPreference>('locale')
  const [chartViewType, setChartViewTypeState] = useState<ChartViewType>('bar')
  const [coresListUseConfigModal, setCoresListUseConfigModalState] = useState(false)
  const isDatePickerFollowingLocale = datePickerPreference === 'locale'
  const defaultManualDatePreference: Exclude<DatePickerPreference, 'locale'> = isPersianLocaleLanguage(i18n.resolvedLanguage ?? i18n.language) ? 'persian' : 'gregorian'
  const datePickerModeCopy: Record<DatePickerPreference, string> = {
    locale: t('theme.datePickerModeLocale'),
    gregorian: t('theme.datePickerModeGregorian'),
    persian: t('theme.datePickerModePersian'),
  }
  const chartViewTypeCopy: Record<ChartViewType, string> = {
    bar: t('theme.chartViewBar'),
    area: t('theme.chartViewArea'),
  }

  useEffect(() => {
    setDatePickerPreferenceState(getDatePickerPreference())
    setChartViewTypeState(getChartViewTypePreference())
    setCoresListUseConfigModalState(getCoresListUseConfigModal())
  }, [])

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme)
    toast.success(t('success'), {
      description: t('theme.themeChanged'),
      duration: 2000,
    })
  }

  const handleColorChange = (colorName: ColorTheme) => {
    setColorTheme(colorName)
    toast.success(t('success'), {
      description: `${t('theme.themeSaved')} - ${t(`theme.${colorName}`)}`,
      duration: 2000,
    })
  }

  const handleBaseChange = (baseColor: BaseColor) => {
    setCustomization({ baseColor })
    toast.success(t('success'), {
      description: `${t('theme.themeSaved')} - ${t(`theme.${baseColor}`)}`,
      duration: 2000,
    })
  }

  const handleStyleChange = (style: ThemeStyle) => {
    const preset = themeStylePresets[style]
    setCustomization({ style, density: preset.density, surface: preset.surface })
    setRadius(preset.radius)
  }

  const persistDatePickerPreference = (preference: DatePickerPreference) => {
    setDatePickerPreferenceState(preference)
    setDatePickerPreference(preference)
    toast.success(t('success'), {
      description: `${t('theme.datePickerPreferenceSaved')} • ${datePickerModeCopy[preference]}`,
      duration: 2000,
    })
  }

  const handleDatePickerAutoToggle = (checked: boolean) => {
    if (checked) {
      persistDatePickerPreference('locale')
      return
    }
    const nextPreference = datePickerPreference === 'locale' ? defaultManualDatePreference : datePickerPreference
    persistDatePickerPreference(nextPreference)
  }

  const handleChartViewTypeChange = (viewType: ChartViewType) => {
    setChartViewTypeState(viewType)
    setChartViewTypePreference(viewType)
    toast.success(t('success'), {
      description: `${t('theme.chartViewSaved')} • ${chartViewTypeCopy[viewType]}`,
      duration: 2000,
    })
  }

  const handleCoresListUseConfigModalChange = (checked: boolean) => {
    setCoresListUseConfigModalState(checked)
    setCoresListUseConfigModal(checked)
    toast.success(t('success'), {
      description: `${t('theme.coresListEditorSaved')} • ${checked ? t('theme.coresListEditorModal') : t('theme.coresListEditorFullPage')}`,
      duration: 2000,
    })
  }

  const handleResetToDefaults = async () => {
    setIsResetting(true)
    try {
      resetToDefaults()
      setDatePickerPreferenceState('locale')
      setDatePickerPreference('locale')
      setChartViewTypeState('bar')
      setChartViewTypePreference('bar')
      setCoresListUseConfigModalState(false)
      setCoresListUseConfigModal(false)
      toast.success(t('success'), {
        description: t('theme.resetSuccess'),
        duration: 3000,
      })
    } catch {
      toast.error(t('error'), {
        description: t('theme.resetFailed'),
        duration: 3000,
      })
    } finally {
      setIsResetting(false)
    }
  }

  return (
    <div className="space-y-6 p-4 pb-10 sm:space-y-8 sm:py-6 lg:space-y-10 lg:py-8">
        <AppearanceControlCenter />

        <Section
          icon={<SunMoon className="text-primary h-4 w-4" />}
          title={t('theme.mode')}
          description={t('theme.modeDescription')}
          action={
            isSystemTheme ? (
              <span className="text-muted-foreground pt-1 text-xs sm:text-sm">
                {t('theme.system')}: {resolvedTheme === 'dark' ? t('theme.dark') : t('theme.light')}
              </span>
            ) : null
          }
        >
          <SegmentedControl
            value={theme}
            onChange={handleThemeChange}
            options={[
              { value: 'light', label: t('theme.light'), icon: <Sun className="h-4 w-4" /> },
              { value: 'dark', label: t('theme.dark'), icon: <Moon className="h-4 w-4" /> },
              { value: 'system', label: t('theme.system'), icon: <Monitor className="h-4 w-4" /> },
            ]}
          />
        </Section>

        <Section icon={<Ruler className="text-primary h-4 w-4" />} title={t('theme.style')} description={t('theme.styleDescription')}>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {(['vega', 'nova', 'maia', 'lyra'] as const).map(style => {
              const labels = {
                vega: t('theme.styleVega'),
                nova: t('theme.styleNova'),
                maia: t('theme.styleMaia'),
                lyra: t('theme.styleLyra'),
              }
              const descriptions = {
                vega: t('theme.styleVegaDescription'),
                nova: t('theme.styleNovaDescription'),
                maia: t('theme.styleMaiaDescription'),
                lyra: t('theme.styleLyraDescription'),
              }
              return (
              <button
                key={style}
                type="button"
                onClick={() => handleStyleChange(style)}
                className={cn(
                  'border-border/70 min-w-0 rounded-lg border p-2.5 text-start transition-colors sm:p-3',
                  customization.style === style ? 'border-primary bg-primary/5' : 'bg-background hover:border-primary/50 hover:bg-accent/30',
                )}
              >
                <div className="flex items-center justify-between gap-1.5">
                  <span className="truncate text-sm font-medium">{labels[style]}</span>
                  {customization.style === style && <Check className="text-primary h-3.5 w-3.5 shrink-0" />}
                </div>
                <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">{descriptions[style]}</p>
              </button>
              )
            })}
          </div>
        </Section>

        <Section icon={<SwatchBook className="text-primary h-4 w-4" />} title={t('theme.baseColor')} description={t('theme.baseColorDescription')}>
          <ColorDotPicker
            value={customization.baseColor}
            options={baseColorOrder}
            onChange={handleBaseChange}
            getLabel={name => t(`theme.${name}`)}
            getColor={name => baseSwatches[name]}
          />
        </Section>

        <Section icon={<Palette className="text-primary h-4 w-4" />} title={t('theme.themeColor')} description={t('theme.themeColorDescription')}>
          <ColorDotPicker
            value={colorTheme}
            options={colorThemeOrder}
            onChange={handleColorChange}
            getLabel={name => t(`theme.${name}`)}
            getColor={name => (name === 'default' ? baseSwatches[customization.baseColor] : resolveTokenHex(accentThemes[name][resolvedTheme], '--primary'))}
          />
        </Section>

        <Section icon={<Ruler className="text-primary h-4 w-4" />} title={t('theme.radius')} description={t('theme.radiusDescription')}>
          <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
            {radiusPresets.map(option => (
              <button
                key={option.value}
                type="button"
                onClick={() => setRadius(option.value)}
                className={cn(
                  'border-border/70 flex min-w-0 flex-col items-center gap-1.5 rounded-lg border px-1 py-2 transition-colors sm:gap-2 sm:px-2 sm:py-3',
                  radius === option.value ? 'border-primary bg-primary/5' : 'bg-background hover:border-primary/50 hover:bg-accent/30',
                )}
              >
                <div className="bg-muted flex size-8 items-center justify-center border sm:size-10" style={{ borderRadius: option.value }}>
                  <div className="bg-primary/40 size-3 sm:size-4" style={{ borderRadius: option.value }} />
                </div>
                <span className="text-center text-[10px] leading-tight font-medium sm:text-[11px]">{t(option.label)}</span>
              </button>
            ))}
          </div>
        </Section>

        <Section icon={<CalendarClock className="text-primary h-4 w-4" />} title={t('theme.datePicker')} description={t('theme.datePickerDescription')}>
          <div className="border-border/70 bg-muted/30 flex flex-col gap-3 rounded-lg border p-3 sm:p-4">
            <div className="flex items-start justify-between gap-3 sm:items-center">
              <div className="min-w-0 space-y-0.5">
                <p className="text-foreground text-sm font-medium">{t('theme.datePickerFollowLocale')}</p>
                <p className="text-muted-foreground text-xs leading-relaxed">{t('theme.datePickerManualHint')}</p>
              </div>
              <Switch className="shrink-0" checked={isDatePickerFollowingLocale} onCheckedChange={handleDatePickerAutoToggle} aria-label={t('theme.datePickerFollowLocale')} />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center" dir={dir}>
              <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                {(['gregorian', 'persian'] as const).map(option => (
                  <Button key={option} type="button" variant={datePickerPreference === option ? 'default' : 'outline'} size="sm" disabled={isDatePickerFollowingLocale} onClick={() => persistDatePickerPreference(option)} className="w-full sm:w-auto">
                    {datePickerModeCopy[option]}
                  </Button>
                ))}
              </div>
              <span className="text-muted-foreground flex min-w-0 items-center gap-1.5 text-xs">
                <Languages className="text-primary h-3.5 w-3.5 shrink-0" />
                <span className="text-foreground truncate font-medium">{datePickerModeCopy[datePickerPreference]}</span>
              </span>
            </div>
          </div>
        </Section>

        <Section icon={<BarChart3 className="text-primary h-4 w-4" />} title={t('theme.chartViewType')} description={t('theme.chartViewDescription')}>
          <SegmentedControl
            value={chartViewType}
            columns={2}
            onChange={value => handleChartViewTypeChange(value as ChartViewType)}
            options={chartViewOptions.map(option => ({
              value: option,
              label: option === 'bar' ? t('theme.chartViewBar') : t('theme.chartViewArea'),
              icon: option === 'bar' ? <BarChart3 className="h-4 w-4" /> : <TrendingUp className="h-4 w-4" />,
            }))}
          />
        </Section>

        <Section icon={<FileJson2 className="text-primary h-4 w-4" />} title={t('theme.coresListEditor')} description={t('theme.coresListEditorDescription')}>
          <div className="border-border/70 bg-muted/30 flex items-start justify-between gap-3 rounded-lg border p-3 sm:items-center sm:p-4">
            <div className="min-w-0 space-y-0.5">
              <p className="text-foreground text-sm font-medium">{t('theme.coresListEditorModal')}</p>
              <p className="text-muted-foreground text-xs leading-relaxed">{t('theme.coresListEditorModalHint')}</p>
            </div>
            <Switch className="shrink-0" checked={coresListUseConfigModal} onCheckedChange={handleCoresListUseConfigModalChange} aria-label={t('theme.coresListEditorModal')} />
          </div>
        </Section>

        <section className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <RotateCcw className="text-primary h-4 w-4 shrink-0" />
              <p className="text-base font-semibold sm:text-lg">{t('theme.resetToDefaults')}</p>
            </div>
            <p className="text-muted-foreground text-xs leading-relaxed sm:text-sm">{t('theme.resetDescription')}</p>
          </div>
          <Button variant="outline" onClick={handleResetToDefaults} disabled={isResetting} className="w-full shrink-0 sm:w-auto">
            {isResetting ? t('theme.resetting') : t('theme.reset')}
          </Button>
        </section>

        <ThemePreview />
    </div>
  )
}
