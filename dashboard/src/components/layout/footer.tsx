import { REPO_URL } from '@/constants/Project'
import { FC } from 'react'

const FooterContent = () => {
  return (
    <p className="inline-block text-center text-[11px] leading-relaxed text-muted-foreground/75">
      Developed by &nbsp;
<a className="font-medium text-primary/90 transition-colors hover:text-primary hover:underline" href={REPO_URL}>
        ManubisGuard

      </a>{' '}
      Team
    </p>
  )
}

export const Footer: FC = ({ ...props }) => {
  return (
    <div className="mg-app-footer relative mt-auto flex w-full shrink-0 items-center justify-center px-4 pt-5 pb-4" {...props}>
      <FooterContent />
    </div>
  )
}
