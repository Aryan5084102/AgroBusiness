'use client';

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  createCustomer,
  fetchCustomers,
  updateCustomer,
  type CreateCustomerInput,
  type UpdateCustomerInput,
} from './api';

export function useCustomers(options: { search?: string; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['customers', options.search ?? ''],
    queryFn: () => fetchCustomers(options.search),
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCustomerInput) => createCustomer(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['customers'] }),
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      customerId,
      input,
    }: {
      customerId: string;
      input: UpdateCustomerInput;
    }) => updateCustomer(customerId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['customers'] }),
  });
}
