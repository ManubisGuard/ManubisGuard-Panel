import { useMutation } from '@tanstack/react-query'

import { orvalFetcher } from './http'
import type { ManagedDomain as ApiManagedDomain } from './api'

export type ManagedDomainLifecycle = Omit<ApiManagedDomain, 'status'> & {
  serve_tls?: boolean
  status: 'pending' | 'active' | 'expiring' | 'failed' | 'expired'
  certificate_issued_at?: string | null
  certificate_renewed_at?: string | null
  certificate_error?: string | null
  renewal_attempts?: number
  next_renewal_at?: string | null
  deployment_status?: 'not_deployed' | 'deployed' | 'failed'
  certificate_deployed_at?: string | null
  deployment_error?: string | null
}

export interface CertificateIssueRequest {
  domain_id: string
  force?: boolean
}

export interface ExistingCertificateInstallRequest {
  domain_id: string
  certificate_pem: string
  private_key_pem: string
}

export interface CertificateDeploymentRequest {
  domain_id: string
}

export interface CertificateLifecycleResponse {
  domain: ManagedDomainLifecycle
}

export interface CertificateDeploymentResponse {
  domain: ManagedDomainLifecycle
  deployed_domains: string[]
  skipped_domains: string[]
}

type MutationVariables<T> = { data: T }

export const issueManagedCertificate = async (request: CertificateIssueRequest, options?: RequestInit): Promise<CertificateLifecycleResponse> =>
  orvalFetcher<CertificateLifecycleResponse>('/api/settings/domains/certificate/issue', {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    body: JSON.stringify(request),
  })

export const useIssueManagedCertificate = () =>
  useMutation({
    mutationKey: ['issueManagedCertificate'],
    mutationFn: ({ data }: MutationVariables<CertificateIssueRequest>) => issueManagedCertificate(data),
  })

export const installExistingCertificate = async (request: ExistingCertificateInstallRequest, options?: RequestInit): Promise<CertificateLifecycleResponse> =>
  orvalFetcher<CertificateLifecycleResponse>('/api/settings/domains/certificate/install', {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    body: JSON.stringify(request),
  })

export const useInstallExistingCertificate = () =>
  useMutation({
    mutationKey: ['installExistingCertificate'],
    mutationFn: ({ data }: MutationVariables<ExistingCertificateInstallRequest>) => installExistingCertificate(data),
  })

export const deployManagedCertificates = async (request: CertificateDeploymentRequest, options?: RequestInit): Promise<CertificateDeploymentResponse> =>
  orvalFetcher<CertificateDeploymentResponse>('/api/settings/domains/certificate/deploy', {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    body: JSON.stringify(request),
  })

export const useDeployManagedCertificates = () =>
  useMutation({
    mutationKey: ['deployManagedCertificates'],
    mutationFn: ({ data }: MutationVariables<CertificateDeploymentRequest>) => deployManagedCertificates(data),
  })
