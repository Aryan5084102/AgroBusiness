// Machine-service feature API: repair jobs, spare parts, completion.
import { apiFetch } from '@/lib/api/client';

export type RepairStatus =
  | 'received'
  | 'under_inspection'
  | 'estimate_prepared'
  | 'awaiting_approval'
  | 'approved'
  | 'in_progress'
  | 'waiting_for_part'
  | 'quality_check'
  | 'ready'
  | 'delivered'
  | 'cancelled';

/** Statuses offered in the UI, in the order a job normally moves through them. */
export const REPAIR_STATUSES: RepairStatus[] = [
  'received',
  'under_inspection',
  'estimate_prepared',
  'awaiting_approval',
  'approved',
  'in_progress',
  'waiting_for_part',
  'quality_check',
  'ready',
  'delivered',
  'cancelled',
];

export interface RepairJob {
  id: string;
  job_number: string;
  status: RepairStatus;
  customer_id: string | null;
  customer_name: string | null;
  product_id: string | null;
  product_name: string | null;
  technician_id: string | null;
  technician_name: string | null;
  warehouse_id: string;
  complaint: string | null;
  is_warranty_covered: boolean;
  labour_charges: string;
  parts_total: string;
  customer_payable: string;
  received_date: string;
  completed_date: string | null;
  created_at: string;
}

export interface JobPart {
  id: string;
  product_id: string;
  product_name: string;
  base_quantity: string;
  unit_price: string;
  line_total: string;
  is_returned: boolean;
}

export interface RepairJobDetail extends RepairJob {
  parts: JobPart[];
}

export interface JobPage {
  items: RepairJob[];
  total: number;
  limit: number;
  offset: number;
  open_count: number;
}

export function fetchJobs(params: {
  status?: RepairStatus;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<JobPage> {
  const search = new URLSearchParams();
  if (params.status) search.set('status', params.status);
  if (params.search) search.set('search', params.search);
  search.set('limit', String(params.limit ?? 50));
  search.set('offset', String(params.offset ?? 0));
  return apiFetch<JobPage>(`/api/v1/service/jobs?${search.toString()}`);
}

export function fetchJob(jobId: string): Promise<RepairJobDetail> {
  return apiFetch<RepairJobDetail>(`/api/v1/service/jobs/${jobId}`);
}

export interface CreateJobInput {
  warehouseId: string;
  customerId?: string | null;
  productId?: string | null;
  complaint?: string;
}

export function createJob(input: CreateJobInput): Promise<RepairJob> {
  return apiFetch<RepairJob>('/api/v1/service/jobs', {
    method: 'POST',
    body: {
      warehouse_id: input.warehouseId,
      customer_id: input.customerId || null,
      product_id: input.productId || null,
      complaint: input.complaint || null,
    },
  });
}

export function updateJobStatus(jobId: string, status: RepairStatus): Promise<RepairJob> {
  return apiFetch<RepairJob>(`/api/v1/service/jobs/${jobId}/status`, {
    method: 'POST',
    body: { status },
  });
}

export function consumePart(
  jobId: string,
  productId: string,
  baseQuantity: string,
): Promise<{
  repair_job_part_id: string;
  parts_total: string;
  customer_payable: string;
}> {
  return apiFetch(`/api/v1/service/jobs/${jobId}/parts`, {
    method: 'POST',
    body: { product_id: productId, base_quantity: baseQuantity },
  });
}

export function returnPart(jobId: string, partId: string): Promise<{ status: string }> {
  return apiFetch(`/api/v1/service/jobs/${jobId}/parts/${partId}/return`, {
    method: 'POST',
  });
}

export function completeJob(jobId: string, labourCharges: string): Promise<RepairJob> {
  return apiFetch<RepairJob>(`/api/v1/service/jobs/${jobId}/complete`, {
    method: 'POST',
    body: { labour_charges: labourCharges },
  });
}
