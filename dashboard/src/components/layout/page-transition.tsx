import { ReactNode, useEffect, useState, useRef, memo } from 'react'
import { useLocation, useNavigationType } from 'react-router'
import { cn } from '@/lib/utils'

interface PageTransitionProps {
  children: ReactNode
  duration?: number
  delay?: number
  isContentTransition?: boolean
  className?: string
}

let mobileCache: boolean | null = null
let motionCache: boolean | null = null

const getMobile = () => {
  if (typeof window === 'undefined') return false
  if (mobileCache === null) {
    mobileCache = window.innerWidth < 768
    window.addEventListener(
      'resize',
      () => {
        mobileCache = window.innerWidth < 768
      },
      { passive: true },
    )
  }
  return mobileCache
}

const getMotion = () => {
  if (typeof window === 'undefined') return false
  if (motionCache === null) {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    motionCache = mq.matches
    mq.addEventListener('change', e => {
      motionCache = e.matches
    })
  }
  return motionCache
}

export default memo(function PageTransition({ children, isContentTransition = false, className }: PageTransitionProps) {
  const location = useLocation()
  const navType = useNavigationType()
  const [displayChildren, setDisplayChildren] = useState(children)
  const [opacity, setOpacity] = useState(1)
  const [offsetY, setOffsetY] = useState(0)
  const prev = useRef({
    pathname: location.pathname,
    hash: location.hash,
    search: location.search,
    key: location.key,
  })
  const first = useRef(true)
  const timeout = useRef<number | null>(null)

  useEffect(
    () => () => {
      if (timeout.current) clearTimeout(timeout.current)
    },
    [],
  )

  useEffect(() => {
    if (first.current) {
      first.current = false
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
      return
    }

    if (timeout.current) clearTimeout(timeout.current)

    if (navType === 'POP') {
      setDisplayChildren(children)
      setOpacity(1)
      setOffsetY(0)
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
      return
    }

    const pathnameHashSame = location.pathname === prev.current.pathname && location.hash === prev.current.hash
    /** Same route + only query changed (e.g. core editor `?kind=wg`); new location.key must not trigger shake. */
    if (pathnameHashSame && location.search !== prev.current.search) {
      setDisplayChildren(children)
      setOpacity(1)
      setOffsetY(0)
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
      return
    }

    const mobile = getMobile()
    const noMotion = getMotion()
    const current = `${location.pathname}${location.hash}`
    const prevKey = `${prev.current.pathname}${prev.current.hash}`
    const same = current === prevKey && location.key !== prev.current.key

    if (noMotion) {
      setDisplayChildren(children)
      setOpacity(1)
      setOffsetY(0)
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
      return
    }

    const ms = isContentTransition ? (mobile ? 230 : 260) : mobile ? 190 : 230

    if (same) {
      setDisplayChildren(children)
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
      return
    }

    if (current !== prevKey) {
      setOpacity(0)
      setOffsetY(7)
      requestAnimationFrame(() => {
        setDisplayChildren(children)
        requestAnimationFrame(() => {
          setOpacity(1)
          setOffsetY(0)
          timeout.current = window.setTimeout(() => {
            prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
          }, ms)
        })
      })
    } else {
      setDisplayChildren(children)
      prev.current = { pathname: location.pathname, hash: location.hash, search: location.search, key: location.key }
    }
  }, [location, navType, children, isContentTransition])

  useEffect(() => {
    if (opacity === 1) setDisplayChildren(children)
  }, [children, opacity])

  const noMotion = getMotion()
  const ms = isContentTransition ? (getMobile() ? 230 : 260) : getMobile() ? 190 : 230

  return (
    <div
      className={cn('w-full', className)}
      style={{
        opacity,
        transform: `translate3d(0, ${offsetY}px, 0)`,
        willChange: opacity === 1 ? 'auto' : 'opacity, transform',
        ...(!noMotion && { transition: `opacity ${ms}ms cubic-bezier(0.22, 1, 0.36, 1), transform ${ms}ms cubic-bezier(0.22, 1, 0.36, 1)` }),
      }}
    >
      {displayChildren}
    </div>
  )
})
