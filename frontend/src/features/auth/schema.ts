import { z } from 'zod';

// Login form validation. Mirrors the constraints the backend will enforce in
// Phase 1 (real authentication is wired then).
export const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

export type LoginInput = z.infer<typeof loginSchema>;
