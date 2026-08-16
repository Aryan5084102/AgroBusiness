'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  completeJob,
  consumePart,
  createJob,
  fetchJob,
  fetchJobs,
  returnPart,
  updateJobStatus,
  type CreateJobInput,
  type RepairStatus,
} from './api';

export function useJobs(
  params: { status?: RepairStatus; search?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ['service', 'jobs', params],
    queryFn: () => fetchJobs(params),
    enabled,
  });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ['service', 'job', jobId],
    queryFn: () => fetchJob(jobId as string),
    enabled: Boolean(jobId),
  });
}

// Parts consumption moves stock, so inventory views refresh alongside the job.
function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['service'] });
  queryClient.invalidateQueries({ queryKey: ['inventory'] });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateJobInput) => createJob(input),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useUpdateJobStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: RepairStatus }) =>
      updateJobStatus(jobId, status),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useConsumePart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      jobId,
      productId,
      baseQuantity,
    }: {
      jobId: string;
      productId: string;
      baseQuantity: string;
    }) => consumePart(jobId, productId, baseQuantity),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useReturnPart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, partId }: { jobId: string; partId: string }) =>
      returnPart(jobId, partId),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useCompleteJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, labourCharges }: { jobId: string; labourCharges: string }) =>
      completeJob(jobId, labourCharges),
    onSuccess: () => invalidate(queryClient),
  });
}
