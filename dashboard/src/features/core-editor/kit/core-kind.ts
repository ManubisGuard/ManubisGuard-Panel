import type { CoreKind } from '@pasarguard/core-kit'
import type { CoreResponseType } from '@/service/api'

export function apiCoreTypeToKind(type: CoreResponseType | undefined): CoreKind {
  if (type === 'wg' || type === 'amneziawg') return 'wg'
  return 'xray'
}

export function isSupportedCoreEditorKind(type: CoreResponseType | undefined): boolean {
  return type === 'wg' || type === 'amneziawg' || type === 'xray' || type == null || type === undefined
}
