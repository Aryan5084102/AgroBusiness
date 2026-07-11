// Validated, typed access to public environment variables. Only NEXT_PUBLIC_*
// values are exposed to the browser; secrets never live here.
import { z } from 'zod';

const schema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z.string().url().default('http://localhost:8000'),
});

const parsed = schema.safeParse({
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
});

if (!parsed.success) {
  // Fail fast with a readable message rather than obscure runtime errors.
  throw new Error(`Invalid public environment configuration: ${parsed.error.message}`);
}

export const env = parsed.data;
